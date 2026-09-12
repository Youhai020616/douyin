"""
dy publish — 发布命令 (Playwright 引擎)。
"""
from __future__ import annotations

import os

import click

from dy_cli.engines.playwright_client import PlaywrightClient, PlaywrightError
from dy_cli.utils import config
from dy_cli.utils.output import DyCliError, console, info, print_json, success


@click.command("publish", help="发布视频或图文到抖音")
@click.option("--title", "-t", required=True, help="标题")
@click.option("--content", "-c", default=None, help="描述正文")
@click.option("--content-file", type=click.Path(exists=True), default=None, help="从文件读取描述")
@click.option("--video", "-v", default=None, help="视频文件路径")
@click.option("--images", "-i", multiple=True, help="图片路径 (可多个)")
@click.option("--tags", multiple=True, help="标签 (可多个，如: --tags 旅行 --tags 美食)")
@click.option("--visibility", type=click.Choice(["公开", "好友可见", "仅自己可见"]),
              default="公开", help="可见范围")
@click.option("--schedule", default=None, help="定时发布 (ISO 8601, 如 2026-03-16T10:00:00+08:00)")
@click.option("--thumbnail", default=None, type=click.Path(exists=True), help="封面图片路径")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--headless", is_flag=True, help="无头模式 (不显示浏览器)")
@click.option("--dry-run", is_flag=True, help="预览模式，不实际发布")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def publish(title, content, content_file, video, images, tags, visibility, schedule, thumbnail,
            account, headless, dry_run, as_json):
    """发布视频或图文。"""

    # Handle content
    if content_file:
        with open(content_file, encoding="utf-8") as f:
            content = f.read().strip()
    if not content:
        content = ""

    # Validate media
    images = list(images)
    if not images and not video:
        raise DyCliError("invalid_argument", "必须提供视频 (--video) 或图片 (--images)")

    if video and images:
        raise DyCliError("invalid_argument", "不能同时提供视频和图片，请选择一种")

    # Validate files
    if video and not video.startswith("http") and not os.path.isfile(video):
        raise DyCliError("invalid_argument", f"视频文件不存在: {video}")

    for img in images:
        if not img.startswith("http") and not os.path.isfile(img):
            raise DyCliError("invalid_argument", f"图片文件不存在: {img}")

    tags = list(tags)

    # Dry run
    if dry_run:
        if as_json:
            print_json({
                "dry_run": True,
                "title": title,
                "content": content,
                "video": video,
                "images": images,
                "tags": tags,
                "visibility": visibility,
                "schedule": schedule,
                "thumbnail": thumbnail,
            })
            return
        console.print()
        info("📋 发布预览:")
        console.print(f"  [bold]标题:[/] {title}")
        console.print(f"  [bold]描述:[/] {content[:100]}{'...' if len(content) > 100 else ''}")
        if video:
            console.print(f"  [bold]视频:[/] {video}")
        else:
            console.print(f"  [bold]图片:[/] {', '.join(images)}")
        if tags:
            console.print(f"  [bold]标签:[/] {', '.join(tags)}")
        console.print(f"  [bold]可见:[/] {visibility}")
        if schedule:
            console.print(f"  [bold]定时:[/] {schedule}")
        if thumbnail:
            console.print(f"  [bold]封面:[/] {thumbnail}")
        console.print()
        return

    # Publish
    cfg = config.load_config()
    use_headless = headless or cfg["playwright"].get("headless", False)

    client = PlaywrightClient(
        account=account,
        headless=use_headless,
        slow_mo=cfg["playwright"].get("slow_mo", 0),
    )

    if not client.cookie_exists():
        raise DyCliError("not_authenticated", "未登录，请先运行: dy login")

    try:
        if video:
            info(f"正在发布视频: {os.path.basename(video)}")
            result = client.publish_video(
                title=title,
                content=content,
                video_path=os.path.abspath(video),
                tags=tags or None,
                visibility=visibility,
                schedule_at=schedule,
                thumbnail_path=thumbnail,
            )
        else:
            info(f"正在发布图文 ({len(images)} 张图片)")
            result = client.publish_image_text(
                title=title,
                content=content,
                images=[os.path.abspath(img) if not img.startswith("http") else img for img in images],
                tags=tags or None,
                visibility=visibility,
                schedule_at=schedule,
            )

    except PlaywrightError as e:
        raise DyCliError("playwright_error", f"发布失败: {e}")

    success("发布成功! 🎉")
    info("提示: 可用 [bold]dy search[/] 搜索验证发布状态")
    if as_json:
        print_json(result)
