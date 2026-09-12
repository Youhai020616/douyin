# 结构化输出约定

`dy-cli` 在 `--json-output` 模式下使用统一信封，便于 AI Agent 与脚本解析。

## 成功

```json
{
  "ok": true,
  "schema_version": "1",
  "data": ...
}
```

- `data` 为该命令的结果：`trending` / `live list` 等为数组，`search` / `detail` 等为对象（保留 API 原始字段）
- 失败时命令以非零退出码结束，错误信息输出到 stderr

## 错误信封（预留）

`dy_cli.utils.envelope.error_envelope()` 定义了如下格式，供后续版本统一错误输出使用，**当前命令尚未通过 stdout 输出此结构**：

```json
{
  "ok": false,
  "schema_version": "1",
  "error": { "code": "not_authenticated", "message": "need login" }
}
```

预留的 `error.code`：`not_authenticated`、`verify_check`、`api_error`、`empty_response`、`network_error`

## 支持 `--json-output` 的命令

`search`、`detail`、`comments`、`download`、`trending`、`live list`、`live info`、`profile`、`me`、`analytics`、`notifications`

## 已知限制

- `status`、`login`、`publish`、`like` 等命令暂无 `--json-output`
- 部分命令在 JSON 之前会向 stdout 打印一行进度提示（如 `ℹ 正在获取抖音热榜...`），解析时请从首个 `{` 开始
