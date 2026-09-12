# Claude Code 集成指南

将 dy-cli 作为 Claude Code / Cursor 的技能使用。

## 方式一：作为 OpenClaw Skill

```bash
# 复制到技能目录
cp -r douyin ~/.openclaw/skills/douyin
```

Claude Code 会自动读取 `SKILL.md` 并使用对应工具。

## 方式二：直接在 Claude Code 中使用

在项目中激活环境后，Claude Code 可以直接调用 `dy` 命令：

```bash
source activate.sh

# Claude Code 可以执行这些命令
dy search "关键词"
dy trending
dy download URL
dy publish -t "标题" -c "描述" -v video.mp4
```

## 配置文件

`~/.dy/config.json` 配置示例：

```json
{
  "api": {
    "cookie_file": "~/.dy/cookies/default.json",
    "proxy": "",
    "timeout": 30
  },
  "playwright": {
    "headless": true,
    "chromium_path": "",
    "slow_mo": 0
  },
  "default": {
    "account": "default",
    "engine": "auto",
    "output": "table",
    "download_dir": "~/Downloads/douyin"
  }
}
```

## 提示

- 对于 AI 调用，建议使用 `--json-output`：stdout 只有一个 JSON 信封（成功 `{ok: true, data}` / 失败 `{ok: false, error: {code, message}}`），进度提示在 stderr，约定见 [SCHEMA.md](../SCHEMA.md)
- 先 `dy status --json-output` 检查 `data.authenticated`，再执行需要登录的操作；`dy login --json-output` 在已登录时不会交互询问
- 无人值守场景建议 `dy config set playwright.headless true`，避免弹出浏览器窗口
- 发布前使用 `--dry-run` 预览
- 批量操作时注意加延时，避免触发风控
