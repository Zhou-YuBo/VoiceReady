# Kernel JSONL 协议 v1

## 快速理解

Rust 启动一个常驻 Python Kernel。
双方通过标准输入和标准输出通信。
每行只放一个 JSON 对象。

## 请求

```json
{
  "protocol_version": 1,
  "request_id": "req-001",
  "method": "health",
  "params": {
    "project_root": "E:/VoiceReadyDemo"
  }
}
```

`request_id` 必须由调用方生成。
响应必须原样返回同一个 ID。

## 响应

成功响应包含 `ok: true` 和 `result`。
失败响应包含 `ok: false` 和 `error`。

## 方法

| 方法 | 作用 |
|---|---|
| `health` | 返回数据库健康状态 |
| `create_project` | 创建项目并初始化数据库 |
| `open_project` | 校验并打开已有项目 |
| `shutdown` | 请求 Kernel 优雅退出 |

## 进程约束

- `stdout` 只输出协议响应。
- 日志输出到 `stderr`。
- 单个请求失败不会终止进程。
- 非法 JSON 返回 `INVALID_JSON`。
- 未知方法返回 `METHOD_NOT_FOUND`。