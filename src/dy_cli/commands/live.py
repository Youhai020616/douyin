"""
dy live — 直播相关命令（抖音特色功能）。
"""
from __future__ import annotations

import os
import shutil
import subprocess

import click

from dy_cli.engines.api_client import DouyinAPIClient, DouyinAPIError
from dy_cli.utils import config
from dy_cli.utils.output import console, error, info, print_json, print_live_info, print_live_rooms, success, warning


@click.group("live", help="📺 直播功能 (列出/查看/录制)")
def live_group():
    pass


@live_group.command("list", help="列出推荐直播间")
@click.option("--count", type=click.IntRange(1, 50), default=20, show_default=True, help="房间数量")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def live_list(count, account, as_json):
    """列出直播首页推荐房间。"""
    client = DouyinAPIClient.from_config(account)

    try:
        info(f"正在获取推荐直播间: {count} 条")
        rooms = client.get_live_rooms(count=count)

        if as_json:
            print_json(rooms)
        else:
            print_live_rooms(rooms)

    except DouyinAPIError as e:
        error(f"获取直播房间失败: {e}")
        raise SystemExit(1)
    finally:
        client.close()


@live_group.command("info", help="查看直播间信息")
@click.argument("room_id")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def live_info(room_id, account, as_json):
    """查看直播间信息（观众数、主播、拉流地址）。"""
    client = DouyinAPIClient.from_config(account)

    try:
        info(f"正在获取直播间信息: {room_id}")
        data = client.get_live_info(room_id)

        if as_json:
            print_json(data)
        else:
            print_live_info(data)

            # Show stream URLs if available
            stream_data = data.get("stream_url", {})
            if isinstance(stream_data, dict):
                flv_url = stream_data.get("flv_pull_url", {})
                hls_url = stream_data.get("hls_pull_url_map", {})
                if flv_url or hls_url:
                    console.print()
                    info("拉流地址:")
                    for quality, url in (flv_url or hls_url).items():
                        console.print(f"  [{quality}] {url[:80]}…" if len(url) > 80 else f"  [{quality}] {url}")

    except DouyinAPIError as e:
        error(f"获取直播信息失败: {e}")
        raise SystemExit(1)
    finally:
        client.close()


@live_group.command("record", help="录制直播")
@click.argument("room_id")
@click.option("--output", "-o", default=None, help="输出文件路径")
@click.option("--quality", type=click.Choice(["FULL_HD1", "HD1", "SD1", "SD2"]),
              default="FULL_HD1", help="画质 (默认最高)")
@click.option("--account", default=None, help="使用指定账号")
def live_record(room_id, output, quality, account):
    """
    录制直播视频 (需要 ffmpeg)。

    使用 ffmpeg 拉流保存，Ctrl+C 停止录制。
    """
    # Check ffmpeg
    if not shutil.which("ffmpeg"):
        error("需要安装 ffmpeg: brew install ffmpeg (macOS)")
        raise SystemExit(1)

    client = DouyinAPIClient.from_config(account)

    try:
        info(f"正在获取直播拉流地址: {room_id}")
        data = client.get_live_info(room_id)

        # Check if live
        status_val = data.get("status")
        if status_val != 2:
            error("直播间未开播或已结束")
            raise SystemExit(1)

        # Get stream URL
        stream_data = data.get("stream_url", {})
        flv_urls = stream_data.get("flv_pull_url", {})
        hls_urls = stream_data.get("hls_pull_url_map", {})

        stream_url = None
        urls = flv_urls or hls_urls
        if isinstance(urls, dict):
            # Try preferred quality, fallback to any available
            stream_url = urls.get(quality) or next(iter(urls.values()), None)

        if not stream_url:
            error("未获取到拉流地址")
            raise SystemExit(1)

        # Output file
        if not output:
            cfg = config.load_config()
            dl_dir = cfg["default"].get("download_dir", os.path.expanduser("~/Downloads/douyin"))
            os.makedirs(dl_dir, exist_ok=True)
            owner = data.get("owner", {}).get("nickname", room_id)
            import datetime
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output = os.path.join(dl_dir, f"live_{owner}_{ts}.mp4")

        info(f"开始录制: {output}")
        info("按 Ctrl+C 停止录制")
        console.print()

        # Use ffmpeg to record
        cmd = [
            "ffmpeg",
            "-i", stream_url,
            "-c", "copy",
            "-movflags", "+faststart",
            output,
        ]

        try:
            subprocess.run(cmd, check=True)
        except KeyboardInterrupt:
            console.print()
            if os.path.isfile(output):
                size = os.path.getsize(output)
                size_str = f"{size / 1024 / 1024:.1f}MB"
                success(f"录制完成: {output} ({size_str})")
            else:
                warning("录制已取消")
        except subprocess.CalledProcessError as e:
            error(f"ffmpeg 录制失败: {e}")

    except DouyinAPIError as e:
        error(f"获取直播信息失败: {e}")
        raise SystemExit(1)
    finally:
        client.close()
