"""
增强版下载命令 - 添加视频质量选择功能
"""

import click


# 添加到 download 命令的选项
QUALITY_OPTIONS = [
    click.option("--quality", "-q", default="best",
                 type=click.Choice(["1080", "720", "540", "best", "worst"]),
                 help="视频质量 (默认: best)"),
    click.option("--list-quality", is_flag=True, help="列出所有可用质量"),
]


def download_with_quality(url_or_id, output_dir, music, quality, list_quality, limit, user, account, as_json):
    """
    增强版下载函数，支持质量选择
    """
    import os
    import re
    from dy_cli.engines.api_client import DouyinAPIClient, DouyinAPIError
    from dy_cli.utils import config
    from dy_cli.utils.index_cache import resolve_id
    from dy_cli.utils.output import console, error, info, success, warning
    
    # 将质量选择方法添加到客户端
    from dy_cli.engines.api_client_quality import get_download_url_with_quality
    DouyinAPIClient.get_download_url_with_quality = get_download_url_with_quality
    
    cfg = config.load_config()
    output_dir = output_dir or cfg["default"].get("download_dir", os.path.expanduser("~/Downloads/douyin"))
    os.makedirs(output_dir, exist_ok=True)

    client = DouyinAPIClient.from_config(account)

    try:
        # 批量下载用户作品
        if user:
            _batch_download_user(client, url_or_id, output_dir, music, limit or 20, as_json, quality)
            return

        # Resolve aweme_id (支持短链接)
        try:
            url_or_id = resolve_id(url_or_id)
        except ValueError as e:
            error(str(e))
            raise SystemExit(1)
        if url_or_id.isdigit():
            aweme_id = url_or_id
        else:
            info("正在解析短链接...")
            aweme_id = client.resolve_share_url(url_or_id)

        info(f"视频 ID: {aweme_id}")

        # 获取下载信息
        info("正在获取下载链接...")
        
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

        if as_json:
            from dy_cli.utils.output import print_json
            print_json(dl_info)
            return

        desc = dl_info.get("desc", "untitled")
        author = dl_info.get("author", "unknown")
        quality_info = dl_info.get("quality", {})

        # 显示选择的质量
        if quality_info:
            gear = quality_info.get("gear_name", "unknown")
            bitrate = quality_info.get("bit_rate", 0)
            info(f"选择质量: {gear} ({bitrate/1000:.0f} kbps)")

        # Sanitize filename
        safe_name = re.sub(r'[\\/:*?"<>|\n\r]', '_', desc)[:50].strip('_') or aweme_id
        prefix = f"{author}_{safe_name}"
        
        # 添加质量后缀
        if quality_info:
            gear = quality_info.get("gear_name", "")
            if gear:
                prefix = f"{prefix}_{gear}"

        downloaded_files = []

        # Download video
        video_url = dl_info.get("video_url")
        if video_url:
            video_path = os.path.join(output_dir, f"{prefix}.mp4")
            info("正在下载视频...")
            _download_with_progress(client, video_url, video_path)
            downloaded_files.append(video_path)

        # Download images (for image posts)
        image_urls = dl_info.get("images")
        if image_urls:
            for i, img_url in enumerate(image_urls):
                img_path = os.path.join(output_dir, f"{prefix}_image_{i+1}.jpg")
                info(f"正在下载图片 {i+1}/{len(image_urls)}...")
                _download_with_progress(client, img_url, img_path)
                downloaded_files.append(img_path)

        # Download music (optional)
        if music:
            music_url = dl_info.get("music_url")
            if music_url:
                music_path = os.path.join(output_dir, f"{prefix}_music.mp3")
                info("正在下载音乐...")
                _download_with_progress(client, music_url, music_path)
                downloaded_files.append(music_path)

        success(f"下载完成! 共 {len(downloaded_files)} 个文件")

    except DouyinAPIError as e:
        error(f"API 错误: {e}")
        raise SystemExit(1)
    except Exception as e:
        error(f"下载失败: {e}")
        raise SystemExit(1)
    finally:
        client.close()
