---
name: douyin
description: |
  抖音全能 Skill：搜索、下载、发布、互动、热榜、直播、数据看板。
  API Client 负责搜索/下载/采集（即时），Playwright 负责发布/登录/数据分析（按需浏览器）。
metadata:
  trigger: 抖音相关操作（搜索、下载、发布、热榜、直播、数据、评论）
---

# 抖音统一 Skill

本 Skill 整合两套引擎：
- **API Client**（httpx 逆向 API）：搜索、下载、评论、热榜、直播、用户 — 即时响应
- **Playwright**（浏览器自动化）：发布、登录、数据看板、通知 — 按需启动

## 目录结构

```
douyin/
├── SKILL.md
├── src/dy_cli/
│   ├── main.py
│   ├── engines/
│   │   ├── api_client.py
│   │   └── playwright_client.py
│   ├── commands/
│   │   ├── search.py, download.py, publish.py
│   │   ├── trending.py, live.py, analytics.py
│   │   └── auth.py, profile.py, interact.py, ...
│   └── utils/
│       ├── config.py, output.py, signature.py
├── scripts/
│   ├── douyin_login.py
│   ├── douyin_publisher.py
│   ├── douyin_analytics.py
│   └── chrome_launcher.py
└── config/
    └── accounts.json.example
```

## 工具选择指南

| 操作 | 用哪个 | 命令 |
|------|--------|------|
| 搜索视频 | API | `dy search "关键词"` |
| 无水印下载 | API | `dy download URL` |
| 热榜 | API | `dy trending` |
| 视频详情 | API | `dy detail AWEME_ID` |
| 评论列表 | API | `dy comments AWEME_ID` |
| 用户资料 | API | `dy profile SEC_USER_ID` |
| 直播信息 | API | `dy live info ROOM_ID` |
| 直播录制 | API + ffmpeg | `dy live record ROOM_ID` |
| **发布视频/图文** | Playwright | `dy publish -t 标题 -c 描述 -v 视频` |
| **扫码登录** | Playwright | `dy login` |
| **数据看板** | Playwright | `dy analytics` |
| **通知消息** | Playwright | `dy notifications` |

---

## Part 1: API 工具（搜索/下载/采集）

### 搜索

```bash
dy search "AI创业"
dy search "咖啡" --sort 最多点赞 --time 一天内
dy search "科技" --type video --count 50 --json-output
dy search "风景" --type atlas                          # 图文搜索
```

参数:
- `--sort`: 综合 | 最多点赞 | 最新发布
- `--time`: 不限 | 一天内 | 一周内 | 半年内
- `--type`: general | video | user

### 下载

```bash
dy download https://v.douyin.com/xxxxx/
dy download 1234567890
dy download URL --music --output-dir ~/Videos
dy download URL --json-output    # 仅输出链接
```

### 热榜

```bash
dy trending
dy trending --count 20
dy trending --watch              # 每 5 分钟刷新
dy trending --json-output
```

### 视频详情

```bash
dy detail AWEME_ID
dy detail AWEME_ID --comments
dy detail AWEME_ID --json-output
```

### 评论

```bash
dy comments AWEME_ID
dy comments AWEME_ID --count 50 --json-output
```

### 用户

```bash
dy profile SEC_USER_ID
dy profile SEC_USER_ID --posts --post-count 30
dy me
```

### 直播

```bash
dy live info ROOM_ID
dy live info ROOM_ID --json-output
dy live record ROOM_ID                   # 需要 ffmpeg
dy live record ROOM_ID --quality HD1
```

---

## Part 2: Playwright 工具（发布/登录/数据）

### 前置条件

```bash
pip install playwright
playwright install chromium
```

### 登录

```bash
dy login                        # 打开浏览器扫码
dy status                       # 检查登录状态
dy logout                       # 退出登录
```

Cookie 存储位置: `~/.dy/cookies/{account}.json`

### 发布

```bash
# 视频
dy publish -t "标题" -c "描述" -v video.mp4
dy publish -t "标题" -c "描述" -v video.mp4 --tags 旅行 --tags 美食

# 图文
dy publish -t "标题" -c "描述" -i img1.jpg -i img2.jpg

# 选项
dy publish ... --visibility 仅自己可见     # 私密
dy publish ... --schedule "2026-03-16T08:00:00+08:00"  # 定时
dy publish ... --thumbnail cover.jpg       # 封面
dy publish ... --headless                  # 无头模式
dy publish ... --dry-run                   # 预览不发布
```

### 数据看板

```bash
dy analytics
dy analytics --csv data.csv
dy analytics --json-output
```

### 通知

```bash
dy notifications
dy notifications --json-output
```

---

## Part 3: 配置与运维

### 配置文件

`~/.dy/config.json`:

```bash
dy config show
dy config set api.proxy http://127.0.0.1:7897
dy config set api.timeout 60
dy config set playwright.headless true
dy config set default.download_dir ~/Videos
```

### 多账号

```bash
dy account list
dy account add work
dy account default work
dy login --account work
dy search "关键词" --account work
```

### 登录态维护
- Cookie 存储在 `~/.dy/cookies/`
- 过期后需重新 `dy login` 扫码
- 不同账号 Cookie 文件独立

### 注意事项
- 抖音签名算法 (a-bogus) 频繁更新，搜索/下载功能可能需要定期适配
- 创作者中心 UI 也会更新，发布功能可能需要调整选择器
- 批量操作建议加 2-5 秒延时，避免触发风控
- 所有命令支持 `--json-output` 输出机器可读格式
- 所有命令支持 `--account` 指定账号
