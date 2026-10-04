<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'

type KernelStatus = { online: boolean; python: string }
type HealthResult = {
  project_root: string
  database_path: string
  schema_version: number
  integrity_ok: boolean
  project_count: number
}
type KernelResponse = { result?: HealthResult }

const kernel = ref<KernelStatus>({ online: false, python: '' })
const project = ref<HealthResult | null>(null)
const busy = ref(false)
const error = ref('')

async function refreshKernel() {
  try {
    kernel.value = await invoke<KernelStatus>('kernel_status')
  } catch (reason) {
    kernel.value = { online: false, python: '' }
    error.value = String(reason)
  }
}

async function chooseProject(action: 'create_project' | 'open_project') {
  error.value = ''
  const selected = await open({ directory: true, multiple: false, recursive: true })
  if (!selected || Array.isArray(selected)) return
  busy.value = true
  try {
    const response = await invoke<KernelResponse>(action, { projectRoot: selected })
    project.value = response.result ?? null
    await refreshKernel()
  } catch (reason) {
    error.value = String(reason)
  } finally {
    busy.value = false
  }
}

onMounted(refreshKernel)
</script>

<template>
  <main class="shell">
    <header class="topbar">
      <div>
        <p class="eyebrow">VOICE READY / CORE</p>
        <h1>项目工作台</h1>
        <p class="subtitle">先建立可靠的项目边界，再接入素材和审核流程。</p>
      </div>
      <div class="status-pill" :class="kernel.online ? 'online' : 'offline'">
        <span class="status-dot" />
        {{ kernel.online ? 'Kernel 在线' : 'Kernel 离线' }}
      </div>
    </header>

    <section class="grid">
      <article class="card entry-card">
        <p class="card-label">PROJECT ENTRY</p>
        <h2>开始一个 VoiceReady 项目</h2>
        <p class="muted">选择项目根目录。数据库会放在该目录的 voiceready/db 下。</p>
        <div class="actions">
          <button class="primary" :disabled="busy || !kernel.online" @click="chooseProject('create_project')">
            创建项目
          </button>
          <button class="secondary" :disabled="busy || !kernel.online" @click="chooseProject('open_project')">
            打开项目
          </button>
        </div>
        <p v-if="busy" class="notice">正在处理项目请求…</p>
        <p v-if="error" class="error">{{ error }}</p>
      </article>

      <article class="card">
        <p class="card-label">KERNEL STATUS</p>
        <h2>运行环境</h2>
        <dl class="facts">
          <div><dt>状态</dt><dd>{{ kernel.online ? '可用' : '不可用' }}</dd></div>
          <div><dt>Python</dt><dd class="mono">{{ kernel.python || '未检测' }}</dd></div>
        </dl>
      </article>

      <article class="card health-card">
        <p class="card-label">PROJECT HEALTH</p>
        <h2>项目健康</h2>
        <div v-if="project" class="facts">
          <div><span>项目根目录</span><code>{{ project.project_root }}</code></div>
          <div><span>数据库</span><code>{{ project.database_path }}</code></div>
          <div><span>Schema</span><strong>v{{ project.schema_version }}</strong></div>
          <div><span>完整性</span><strong :class="project.integrity_ok ? 'good' : 'bad'">{{ project.integrity_ok ? '通过' : '失败' }}</strong></div>
          <div><span>项目数量</span><strong>{{ project.project_count }}</strong></div>
        </div>
        <p v-else class="empty">创建或打开项目后，这里会显示数据库状态。</p>
      </article>
    </section>
  </main>
</template>