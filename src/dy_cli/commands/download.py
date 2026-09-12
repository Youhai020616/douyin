"""
dy download — 无水印下载命令（抖音特色功能）。
"""
from __future__ import annotations

import os
import re

import click
from rich.progress import BarColumn, DownloadColumn, Progress, SpinnerColumn, TextColumn, TransferSpeedColumn

from dy_cli.engines.api_client import DouyinAPIClient, DouyinAPIError
from dy_cli.utils import config
from dy_cli.utils.index_cache import resolve_id
from dy_cli.utils.output import DyCliError, console, info, print_json, print_table, success, warning


@click.command("download", help="下载抖音视频/图片 (无水印, 支持短索引/批量/画质选择)")
@click.argument("url_or_id")
@click.option("--output-dir", "-o", default=None, help="保存目录 (默认 ~/Downloads/douyin)")
@click.option("--music", is_flag=True, help="同时下载背景音乐")
@click.option(
    "--quality", "-q",
    type=click.Choice(DouyinAPIClient.QUALITY_CHOICES),
    default="auto",
    show_default=True,
    help="视频画质: auto=平台默认, best/worst=最高/最低, 或指定分辨率 (不存在时报错)",
)
@click.option("--list-quality", is_flag=True, help="只列出可用画质，不下载")
@click.option("--limit", type=int, default=0, help="批量下载: 用户作品数量 (需配合 --user)")
@click.option("--user", is_flag=True, help="批量下载该用户的全部作品 (URL_OR_ID 为 sec_user_id)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="仅输出下载链接与画质信息 (JSON)")
def download(url_or_id, output_dir, music, quality, list_quality, limit, user, account, as_json):
    """
    下载抖音视频/图片（无水印）。支持短索引、批量下载和画质选择。

    单个下载:
      dy dl 1                          (搜索后用短索引)
      dy dl https://v.douyin.com/xxx   (分享链接)
      dy dl 1234567890                 (视频 ID)

    画质:
      dy dl 1 --list-quality           (列出可用画质)
      dy dl 1 -q 720                   (下载 720p)

    批量下载用户作品:
      dy dl SEC_USER_ID --user --limit 20
    """
    if user and list_quality:
        raise DyCliError("invalid_argument", "--list-quality 不能与 --user 同时使用，请对单个视频查看画质")

    cfg = config.load_config()
    output_dir = output_dir or cfg["default"].get("download_dir", os.path.expanduser("~/Downloads/douyin"))
    os.makedirs(output_dir, exist_ok=True)

    client = DouyinAPIClient.from_config(account)

    try:
        # 批量下载用户作品
        if user:
            _batch_download_user(client, url_or_id, output_dir, music, limit or 20, quality)
            return

        # Resolve aweme_id (支持短索引)
        try:
            url_or_id = resolve_id(url_or_id)
        except ValueError as e:
            raise DyCliError("invalid_argument", str(e))
        if url_or_id.isdigit():
            aweme_id = url_or_id
        else:
            info("正在解析分享链接...")
            aweme_id = client.resolve_share_url(url_or_id)

        info(f"视频 ID: {aweme_id}")

        # Get download info
        info("正在获取下载链接...")
        try:
            dl_info = client.get_download_url(aweme_id, quality=quality)
        except ValueError as e:
            raise DyCliError("invalid_argument", str(e))

        if as_json:
            print_json(dl_info)
            return

        if list_quality:
            _print_qualities(dl_info)
            return

        desc = dl_info.get("desc", "untitled")
        author = dl_info.get("author", "unknown")
        selected = dl_info.get("quality")
        if selected:
            info(f"画质: {selected['label']} {selected['gear_name']} ({selected['bit_rate'] // 1000} kbps, {selected['codec']})")
        elif quality != "auto" and dl_info.get("video_url"):
            warning("该视频无画质信息，已使用平台默认地址")

        # Sanitize filename
        safe_name = re.sub(r'[\\/:*?"<>|\n\r]', '_', desc)[:50].strip('_') or aweme_id
        prefix = f"{author}_{safe_name}"
        if selected:
            prefix = f"{prefix}_{selected['label']}"

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
            for idx, img_url in enumerate(image_urls, 1):
                img_path = os.path.join(output_dir, f"{prefix}_{idx}.jpg")
                info(f"正在下载图片 {idx}/{len(image_urls)}...")
                _download_with_progress(client, img_url, img_path)
                downloaded_files.append(img_path)

        # Download music
        if music:
            music_url = dl_info.get("music_url")
            if music_url:
                music_path = os.path.join(output_dir, f"{prefix}_music.mp3")
                info("正在下载音乐...")
                _download_with_progress(client, music_url, music_path)
                downloaded_files.append(music_path)
            else:
                warning("未找到背景音乐")

        # Summary
        if downloaded_files:
            console.print()
            success(f"下载完成! ({len(downloaded_files)} 个文件)")
            for f in downloaded_files:
                size = os.path.getsize(f)
                size_str = f"{size / 1024 / 1024:.1f}MB" if size > 1024 * 1024 else f"{size / 1024:.0f}KB"
                console.print(f"  📁 {f} ({size_str})")
        else:
            warning("未找到可下载的内容")

    except DouyinAPIError as e:
        raise DyCliError("api_error", f"下载失败: {e}")
    finally:
        client.close()


def _print_qualities(dl_info: dict) -> None:
    """以表格列出可用画质。"""
    qualities = dl_info.get("available_qualities") or []
    if not qualities:
        warning("该作品无画质信息" + ("（图文作品）" if dl_info.get("images") else ""))
        return
    rows = [
        [q["label"], q["gear_name"] or "-", f"{q['bit_rate'] // 1000}", f"{q['width']}x{q['height']}", q["codec"]]
        for q in qualities
    ]
    print_table(f"可用画质: {dl_info.get('aweme_id', '')}", ["画质", "gear", "码率 kbps", "分辨率", "编码"], rows)
    info("使用 -q <画质> 下载，如: dy dl <ID> -q 720")


def _batch_download_user(
    client: DouyinAPIClient,
    sec_user_id: str,
    output_dir: str,
    music: bool,
    limit: int,
    quality: str = "auto",
):
    """批量下载用户作品。指定画质不可用的作品会跳过并警告。"""
    info(f"正在获取用户作品列表 (limit={limit})...")
    try:
        profile = client.get_user_profile(sec_user_id)
        nickname = profile.get("nickname", sec_user_id)
        info(f"用户: {nickname}")
    except Exception:
        nickname = sec_user_id

    user_dir = os.path.join(output_dir, re.sub(r'[\\/:*?"<>|\n\r]', '_', nickname))
    os.makedirs(user_dir, exist_ok=True)

    posts = client.get_user_posts(sec_user_id, count=min(limit, 20))
    aweme_list = posts.get("aweme_list", [])

    if not aweme_list:
        warning("未找到作品")
        return

    info(f"找到 {len(aweme_list)} 个作品，开始下载...")
    downloaded = 0
    import time

    for i, aweme in enumerate(aweme_list[:limit], 1):
        aweme_id = aweme.get("aweme_id", "")
        desc = aweme.get("desc", "untitled")
        safe = re.sub(r'[\\/:*?"<>|\n\r]', '_', desc)[:40].strip('_') or aweme_id

        try:
            dl_info = client.get_download_url(aweme_id, quality=quality)
            video_url = dl_info.get("video_url")
            if video_url:
                suffix = f"_{dl_info['quality']['label']}" if dl_info.get("quality") else ""
                path = os.path.join(user_dir, f"{i:03d}_{safe}{suffix}.mp4")
                if os.path.exists(path):
                    info(f"[{i}/{len(aweme_list)}] 已存在，跳过: {safe[:30]}")
                    continue
                info(f"[{i}/{len(aweme_list)}] {safe[:30]}...")
                _download_with_progress(client, video_url, path)
                downloaded += 1

            # Images
            images = dl_info.get("images")
            if images:
                for idx, img_url in enumerate(images, 1):
                    path = os.path.join(user_dir, f"{i:03d}_{safe}_{idx}.jpg")
                    client.download_file(img_url, path)
                downloaded += 1

            time.sleep(1)  # Rate limit
        except Exception as e:
            warning(f"[{i}] 下载失败: {e}")
            continue

    console.print()
    success(f"批量下载完成! {downloaded}/{len(aweme_list)} 个作品")
    console.print(f"  📁 {user_dir}")


def _download_with_progress(client: DouyinAPIClient, url: str, output_path: str):
    """带进度条的下载。"""
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(os.path.basename(output_path), total=None)

        def on_progress(downloaded: int, total: int):
            if total > 0:
                progress.update(task, total=total, completed=downloaded)
            else:
                progress.update(task, completed=downloaded)

        client.download_file(url, output_path, progress_callback=on_progress)
