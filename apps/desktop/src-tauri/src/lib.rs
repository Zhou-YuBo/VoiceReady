use serde_json::{Value, json};
use std::env;
use std::fs::{self, OpenOptions};
use std::io::{BufRead, BufReader, Write};
use std::path::PathBuf;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;
use std::thread;
use tauri::State;

const PROTOCOL_VERSION: u64 = 1;

struct KernelManager {
    child: Option<Child>,
    stdin: Option<ChildStdin>,
    stdout: Option<BufReader<ChildStdout>>,
    python: PathBuf,
    working_dir: PathBuf,
    next_request_id: u64,
}

struct KernelState(Mutex<KernelManager>);

impl KernelManager {
    fn new() -> Self {
        let working_dir = workspace_root();
        let python = env::var_os("VOICEREADY_KERNEL_PYTHON")
            .map(PathBuf::from)
            .or_else(|| {
                let candidate = working_dir.join(".venv/Scripts/python.exe");
                candidate.exists().then_some(candidate)
            })
            .unwrap_or_else(|| PathBuf::from("python"));
        Self {
            child: None,
            stdin: None,
            stdout: None,
            python,
            working_dir,
            next_request_id: 1,
        }
    }

    fn start(&mut self) -> Result<(), String> {
        if self.child.is_some() {
            return Ok(());
        }
        let mut command = Command::new(&self.python);
        command
            .current_dir(&self.working_dir)
            .args(["-m", "voiceready_kernel", "--stdio"])
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped());
        let mut child = command.spawn().map_err(|error| {
            format!(
                "Unable to start Python Kernel ({}): {error}",
                self.python.display()
            )
        })?;
        if let Some(stderr) = child.stderr.take() {
            let log_path = self.working_dir.join(".codex-tmp/kernel-stderr.log");
            if let Some(parent) = log_path.parent() {
                let _ = fs::create_dir_all(parent);
            }
            thread::spawn(move || {
                if let Ok(mut log) = OpenOptions::new().create(true).append(true).open(log_path) {
                    let mut reader = BufReader::new(stderr);
                    let _ = std::io::copy(&mut reader, &mut log);
                }
            });
        }
        self.stdin = child.stdin.take();
        self.stdout = child.stdout.take().map(BufReader::new);
        self.child = Some(child);
        Ok(())
    }

    fn stop(&mut self) {
        self.stdin = None;
        self.stdout = None;
        if let Some(mut child) = self.child.take() {
            let _ = child.kill();
            let _ = child.wait();
        }
    }

    fn restart(&mut self) -> Result<(), String> {
        self.stop();
        self.start()
    }

    fn call(&mut self, method: &str, params: Value) -> Result<Value, String> {
        self.start()?;
        let request_id = format!("rust-{}", self.next_request_id);
        self.next_request_id += 1;
        let request = json!({"protocol_version": PROTOCOL_VERSION, "request_id": request_id, "method": method, "params": params});
        let write_result = (|| {
            let stdin = self
                .stdin
                .as_mut()
                .ok_or_else(|| "Kernel stdin unavailable".to_string())?;
            writeln!(
                stdin,
                "{}",
                serde_json::to_string(&request).map_err(|e| e.to_string())?
            )
            .map_err(|error| format!("Failed to write Kernel request: {error}"))?;
            stdin
                .flush()
                .map_err(|error| format!("Failed to flush Kernel request: {error}"))
        })();
        if let Err(error) = write_result {
            return match self.restart() {
                Ok(()) => Err(format!("{error}; Kernel restarted")),
                Err(restart_error) => {
                    Err(format!("{error}; Kernel restart failed: {restart_error}"))
                }
            };
        }
        let mut line = String::new();
        let read_result = self
            .stdout
            .as_mut()
            .ok_or_else(|| "Kernel stdout unavailable".to_string())?
            .read_line(&mut line);
        if let Err(error) = read_result {
            return match self.restart() {
                Ok(()) => Err(format!(
                    "Failed to read Kernel response: {error}; Kernel restarted"
                )),
                Err(restart_error) => Err(format!(
                    "Failed to read Kernel response: {error}; Kernel restart failed: {restart_error}"
                )),
            };
        }
        if line.trim().is_empty() {
            return match self.restart() {
                Ok(()) => Err("Kernel exited; Kernel restarted".to_string()),
                Err(restart_error) => Err(format!(
                    "Kernel exited; Kernel restart failed: {restart_error}"
                )),
            };
        }
        let response: Value = serde_json::from_str(&line)
            .map_err(|error| format!("Kernel returned invalid JSON: {error}"))?;
        if response.get("protocol_version").and_then(Value::as_u64) != Some(PROTOCOL_VERSION) {
            return Err("Kernel returned an unsupported protocol version".to_string());
        }
        if response.get("request_id").and_then(Value::as_str) != Some(request_id.as_str()) {
            return Err("Kernel response request_id does not match".to_string());
        }
        if response.get("ok") == Some(&Value::Bool(false)) {
            let error_object = response.get("error").and_then(Value::as_object);
            let code = error_object
                .and_then(|item| item.get("code"))
                .and_then(Value::as_str)
                .unwrap_or("KERNEL_REQUEST_FAILED");
            let message = error_object
                .and_then(|item| item.get("message"))
                .and_then(Value::as_str)
                .unwrap_or("Kernel request failed");
            return Err(format!("{code}: {message}"));
        }
        Ok(response)
    }

    fn status(&mut self) -> Value {
        let running = self
            .child
            .as_mut()
            .map(|child| {
                child
                    .try_wait()
                    .map(|status| status.is_none())
                    .unwrap_or(false)
            })
            .unwrap_or(false);
        if !running && self.child.is_some() {
            self.stop();
        }
        json!({"online": running, "python": self.python.display().to_string()})
    }
}

impl Drop for KernelManager {
    fn drop(&mut self) {
        self.stop();
    }
}

fn workspace_root() -> PathBuf {
    let current = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    for ancestor in current.ancestors() {
        let has_workspace_manifest = ancestor.join("pyproject.toml").is_file();
        let has_kernel_manifest = ancestor.join("apps/kernel/pyproject.toml").is_file();
        if has_workspace_manifest && has_kernel_manifest {
            return ancestor.to_path_buf();
        }
    }
    current
}

fn project_params(project_root: String) -> Value {
    json!({"project_root": project_root})
}

#[tauri::command]
fn kernel_status(state: State<'_, KernelState>) -> Result<Value, String> {
    let mut manager = state
        .0
        .lock()
        .map_err(|_| "Kernel state lock is poisoned".to_string())?;
    manager.start()?;
    Ok(manager.status())
}

#[tauri::command]
fn kernel_health(state: State<'_, KernelState>, project_root: String) -> Result<Value, String> {
    let mut manager = state
        .0
        .lock()
        .map_err(|_| "Kernel state lock is poisoned".to_string())?;
    manager.call("health", project_params(project_root))
}

#[tauri::command]
fn create_project(state: State<'_, KernelState>, project_root: String) -> Result<Value, String> {
    let mut manager = state
        .0
        .lock()
        .map_err(|_| "Kernel state lock is poisoned".to_string())?;
    manager.call("create_project", project_params(project_root))
}

#[tauri::command]
fn open_project(state: State<'_, KernelState>, project_root: String) -> Result<Value, String> {
    let mut manager = state
        .0
        .lock()
        .map_err(|_| "Kernel state lock is poisoned".to_string())?;
    manager.call("open_project", project_params(project_root))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(KernelState(Mutex::new(KernelManager::new())))
        .invoke_handler(tauri::generate_handler![
            kernel_status,
            kernel_health,
            create_project,
            open_project
        ])
        .run(tauri::generate_context!())
        .expect("error while building VoiceReady desktop application");
}
