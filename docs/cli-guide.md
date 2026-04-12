# 🎬 dy-cli 使用指南

抖音命令行工具 — 一条命令搞定搜索、下载、发布、互动、热榜、直播、数据分析。

## 安装

### 前提条件

- Python 3.10+
- Playwright Chromium (setup.sh 会自动安装)
- ffmpeg (可选，直播录制需要: `brew install ffmpeg`)

### 一键安装

```bash
git clone https://github.com/your-username/douyin.git
cd douyin
bash setup.sh
```

`setup.sh` 会自动完成:
- ✅ 检测 Python 版本
- ✅ 创建虚拟环境 `.venv`
- ✅ 安装所有依赖 (`httpx`, `playwright`, `click`, `rich`)
- ✅ 安装 Playwright Chromium
- ✅ 注册 `dy` 命令
- ✅ 生成 `activate.sh` 快捷激活脚本

### 手动安装

```bash
git clone https://github.com/your-username/douyin.git
cd douyin
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
playwright install chromium
dy --version
```

## 快速开始

### 首次使用

```bash
source activate.sh
dy init
```

`dy init` 引导你完成:
1. ✅ 环境检查 (Python, Playwright, httpx)
2. ✅ 安装 Playwright Chromium
3. ✅ 配置代理 (国内直接回车跳过)
4. ✅ 扫码登录抖音

### 以后每次使用

```bash
source activate.sh
dy search "关键词"
```

---

## 命令详解

### 搜索

```bash
dy search "AI创业"                        # 综合搜索
dy search "咖啡" --sort 最多点赞          # 按点赞排序
dy search "春招" --time 一天内            # 限制时间
dy search "科技" --type video             # 仅视频
dy search "风景" --type atlas             # 仅图文
dy search "科技" --count 50              # 返回 50 条
dy search "科技" --json-output           # JSON 输出
```

### 下载

```bash
dy download https://v.douyin.com/xxxxx/   # 分享链接
dy download 1234567890                     # 视频 ID
dy download URL --music                    # 同时下载 BGM
dy download URL -o ~/Videos/douyin         # 指定目录
dy download URL --json-output              # 仅输出链接
```

### 发布

```bash
# 视频发布
dy publish -t "标题" -c "描述" -v video.mp4

# 图文发布
dy publish -t "标题" -c "描述" -i img1.jpg -i img2.jpg

# 完整选项
dy publish -t "旅行日记" -c "巴厘岛真美" \
  -v trip.mp4 \
  --tags 旅行 --tags 巴厘岛 \
  --visibility 公开 \
  --schedule "2026-03-16T08:00:00+08:00" \
  --thumbnail cover.jpg

# 预览
dy publish -t "测试" -c "测试" -v test.mp4 --dry-run

# 从文件读取描述
dy publish -t "深度文章" --content-file desc.txt -v video.mp4
```

### 热榜

```bash
dy trending                              # 显示 Top 50
dy trending --count 20                   # 显示 Top 20
dy trending --watch                      # 每 5 分钟刷新
dy trending --json-output                # JSON 输出
```

### 直播

```bash
dy live info ROOM_ID                     # 直播间信息
dy live record ROOM_ID                   # 录制直播 (需要 ffmpeg)
dy live record ROOM_ID --quality HD1     # 指定画质
dy live record ROOM_ID -o live.mp4       # 指定输出文件
```

### 互动

```bash
dy like AWEME_ID                         # 点赞
dy favorite AWEME_ID                     # 收藏
dy comment AWEME_ID -c "写得好!"         # 评论
dy follow SEC_USER_ID                    # 关注
dy comments AWEME_ID                     # 查看评论
dy comments AWEME_ID --count 50          # 更多评论
```

### 用户

```bash
dy me                                    # 我的信息
dy profile SEC_USER_ID                   # 用户主页
dy profile SEC_USER_ID --posts           # 含作品列表
```

### 数据看板

```bash
dy analytics                             # 数据看板
dy analytics --csv data.csv              # 导出 CSV
dy notifications                         # 通知消息
```

### 多账号

```bash
dy account list                          # 列出账号
dy account add work                      # 添加并登录
dy account default work                  # 设为默认
dy account remove work                   # 删除
dy login --account work                  # 指定账号登录
```

### 配置

```bash
dy config show                           # 查看全部
dy config set api.proxy http://...       # 设置代理
dy config set api.timeout 60             # 请求超时
dy config set playwright.headless true   # 无头模式
dy config set default.download_dir ~/Vid # 下载目录
dy config get api.proxy                  # 获取单项
dy config reset                          # 重置默认
```

---

## 命令别名

| 别名 | 完整命令 |
|------|---------|
| `dy pub` | `dy publish` |
| `dy s` | `dy search` |
| `dy dl` | `dy download` |
| `dy t` | `dy trending` |
| `dy fav` | `dy favorite` |
| `dy noti` | `dy notifications` |
| `dy stat` | `dy status` |
| `dy acc` | `dy account` |
| `dy cfg` | `dy config` |

---

## 引擎说明

| 引擎 | 功能 | 速度 |
|------|------|------|
| **API** | 搜索、下载、评论、热榜、直播、用户 | ⚡ 快 |
| **Playwright** | 发布、登录、数据看板、通知 | 🐢 较慢 (需浏览器) |

命令自动选择最优引擎，无需手动指定。

---

## 常见问题

### Q: 搜索返回空结果?
可能是签名算法问题。尝试先登录：
```bash
dy login
dy search "关键词"
```

### Q: 发布失败?
1. 确保已登录: `dy status`
2. Cookie 过期需重新登录: `dy login`
3. 抖音创作者中心 UI 可能更新，需要更新脚本

### Q: 如何设置代理?
```bash
dy config set api.proxy http://127.0.0.1:7897
```

### Q: 直播录制需要什么?
安装 ffmpeg:
```bash
brew install ffmpeg       # macOS
apt install ffmpeg         # Ubuntu
```
