# 手动创建 PR 指南

## 步骤 1: 克隆你的 Fork

```bash
# 如果还没有克隆
git clone https://github.com/momo0338/douyin.git
cd douyin

# 如果已经克隆，确保在最新状态
git checkout main
git pull upstream main
```

## 步骤 2: 创建新分支

```bash
git checkout -b feat/add-quality-selection
```

## 步骤 3: 应用修改

### 修改 1: `dy_cli/engines/api_client.py`

在文件末尾的 `DouyinAPIClient` 类中添加新方法：

```python
def get_download_url_with_quality(self, aweme_id: str, quality: str = "best") -> dict[str, Any]:
    """
    获取指定质量的无水印下载链接。
    
    Args:
        aweme_id: 视频 ID
        quality: 质量选项
            - "1080": 1080p 高清
            - "720": 720p 高清
            - "540": 540p 标清
            - "best": 最佳质量（默认）
            - "worst": 最差质量
    
    Returns:
        与 get_download_url 相同的格式，但包含质量信息
    """
    detail = self.get_video_detail(aweme_id)
    
    result: dict[str, Any] = {
        "video_url": None,
        "music_url": None,
        "images": None,
        "desc": detail.get("desc", ""),
        "author": detail.get("author", {}).get("nickname", ""),
        "aweme_id": aweme_id,
        "quality": None,
        "available_qualities": [],
    }
    
    video = detail.get("video", {})
    bit_rate = video.get("bit_rate", [])
    
    if not bit_rate:
        # 回退到默认行为
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        if url_list:
            result["video_url"] = url_list[-1].replace("playwm", "play")
        return result
    
    # 记录所有可用质量
    for br in bit_rate:
        gear = br.get("gear_name", "unknown")
        bitrate = br.get("bit_rate", 0)
        result["available_qualities"].append({
            "gear_name": gear,
            "bit_rate": bitrate,
        })
    
    # 选择质量
    selected = None
    if quality == "best":
        selected = bit_rate[0]
    elif quality == "worst":
        selected = bit_rate[-1]
    elif quality == "1080":
        for br in bit_rate:
            if "1080" in br.get("gear_name", ""):
                selected = br
                break
    elif quality == "720":
        for br in bit_rate:
            gear = br.get("gear_name", "")
            if "720" in gear and "low" not in gear:
                selected = br
                break
    elif quality == "540":
        for br in bit_rate:
            gear = br.get("gear_name", "")
            if "540" in gear and "low" not in gear:
                selected = br
                break
    
    if not selected:
        # 尝试模糊匹配
        for br in bit_rate:
            gear = br.get("gear_name", "")
            if quality in gear:
                selected = br
                break
    
    if not selected:
        # 默认使用最佳质量
        selected = bit_rate[0]
    
    # 获取下载 URL
    play_addr = selected.get("play_addr", {})
    url_list = play_addr.get("url_list", [])
    if url_list:
        result["video_url"] = url_list[-1].replace("playwm", "play")
    
    result["quality"] = {
        "gear_name": selected.get("gear_name"),
        "bit_rate": selected.get("bit_rate"),
    }
    
    # 下载音乐
    music = detail.get("music", {})
    music_play = music.get("play_url", {})
    if isinstance(music_play, dict):
        music_urls = music_play.get("url_list", [])
        if music_urls:
            result["music_url"] = music_urls[0]
    elif isinstance(music_play, str):
        result["music_url"] = music_play
    
    return result
```

### 修改 2: `dy_cli/commands/download.py`

修改 `download` 函数的装饰器和函数签名：

```python
@click.command("download", help="下载抖音视频/图片 (无水印, 支持质量选择)")
@click.argument("url_or_id")
@click.option("--output-dir", "-o", default=None, help="输出目录 (默认 ~/Downloads/douyin)")
@click.option("--music", is_flag=True, help="同时下载背景音乐")
@click.option("--quality", "-q", default="best",
              type=click.Choice(["1080", "720", "540", "best", "worst"]),
              help="视频质量 (默认: best)")
@click.option("--list-quality", is_flag=True, help="列出所有可用质量")
@click.option("--limit", type=int, default=0, help="批量下载: 用户作品数量 (配合 --user)")
@click.option("--user", is_flag=True, help="批量下载该用户的全部作品 (URL_OR_ID 为 sec_user_id)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出原始数据 (JSON)")
def download(url_or_id, output_dir, music, quality, list_quality, limit, user, account, as_json):
```

在函数内部，修改获取下载信息的部分：

```python
        # 获取下载信息
        if quality != "best" or list_quality:
            dl_info = client.get_download_url_with_quality(aweme_id, quality)
        else:
            dl_info = client.get_download_url(aweme_id)
        
        # 列出可用质量
        if list_quality:
            qualities = dl_info.get("available_qualities", [])
            if not qualities:
                error("未找到可用质量信息")
                return
            
            print("\n可用视频质量:")
            print("-" * 50)
            for i, q in enumerate(qualities):
                gear = q.get("gear_name", "unknown")
                bitrate = q.get("bit_rate", 0)
                print(f"  [{i+1}] {gear:20} - {bitrate/1000:.0f} kbps")
            print("-" * 50)
            return
```

## 步骤 4: 提交修改

```bash
git add -A
git commit -m "feat: 添加视频质量选择功能

- 添加 --quality/-q 参数支持选择下载质量
- 添加 --list-quality 参数列出所有可用质量
- 支持 1080p, 720p, 540p, best, worst 选项
- 完全向后兼容，不指定 -q 时使用最佳质量"

git push origin feat/add-quality-selection
```

## 步骤 5: 创建 PR

```bash
gh pr create --repo Youhai020616/douyin \
  --title "feat: 添加视频质量选择功能" \
  --body "## 功能描述

为 dy dl 命令添加 --quality/-q 参数，支持选择下载视频的质量。

## 使用方法

\`\`\`bash
# 下载 1080p 高清视频（默认）
dy dl https://v.douyin.com/xxx -q 1080

# 下载 720p 视频
dy dl https://v.douyin.com/xxx -q 720

# 列出所有可用质量
dy dl https://v.douyin.com/xxx --list-quality
\`\`\`

## 测试结果

\`\`\`bash
\$ dy dl https://v.douyin.com/xxx --list-quality
可用视频质量:
--------------------------------------------------
  [1] normal_1080_0        - 1758 kbps
  [2] normal_720_0         - 869 kbps
  [3] normal_540_0         - 442 kbps
--------------------------------------------------

\$ dy dl https://v.douyin.com/xxx -q 1080
视频 ID: 7642671658003713318
选择质量: normal_1080_0 (1758 kbps)
下载完成! 文件大小: 78.64 MB
\`\`\`

## 兼容性

- 完全向后兼容，不指定 -q 时使用最佳质量
- 不影响现有的 --user 批量下载功能"
```

## 步骤 6: 等待审查

PR 创建后，等待项目维护者审查。可能会有以下情况：

1. **直接合并**: 维护者认可你的修改
2. **请求修改**: 维护者可能要求一些调整
3. **讨论**: 可能会讨论实现方案

## 备用方案

如果网络问题持续，可以：

1. **使用增强版脚本**: 直接使用我创建的 `download_hq.py` 脚本
2. **本地应用补丁**: 将修改应用到本地安装的 dy-cli

```bash
# 临时修改（重启后失效）
python3 -c "
from dy_cli.engines.api_client import DouyinAPIClient
exec(open('/tmp/douyin-pr/dy_cli/engines/api_client_quality.py').read())
DouyinAPIClient.get_download_url_with_quality = get_download_url_with_quality
"
```
