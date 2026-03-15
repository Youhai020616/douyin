"""
dy search / detail — 搜索和详情命令。
"""
from __future__ import annotations

import json

import click

from dy_cli.engines.api_client import DouyinAPIClient, DouyinAPIError
from dy_cli.utils.output import (
    success, error, info, warning, console,
    print_videos, print_json, print_video_detail, print_comments,
)


SORT_MAP = {
    "综合": 0,
    "最多点赞": 1,
    "最新发布": 2,
}

TIME_MAP = {
    "不限": 0,
    "一天内": 1,
    "一周内": 7,
    "半年内": 182,
}


@click.command("search", help="搜索抖音视频")
@click.argument("keyword")
@click.option("--sort", type=click.Choice(["综合", "最多点赞", "最新发布"]),
              default="综合", help="排序方式")
@click.option("--time", "pub_time", type=click.Choice(["不限", "一天内", "一周内", "半年内"]),
              default="不限", help="发布时间")
@click.option("--type", "search_type", type=click.Choice(["general", "video", "user"]),
              default="general", help="搜索类型")
@click.option("--count", type=int, default=20, help="结果数量 (默认 20)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON 格式")
def search(keyword, sort, pub_time, search_type, count, account, as_json):
    """搜索抖音视频/用户。"""
    client = DouyinAPIClient.from_config(account)
    info(f"正在搜索: {keyword}")

    try:
        result = client.search(
            keyword=keyword,
            sort_type=SORT_MAP.get(sort, 0),
            publish_time=TIME_MAP.get(pub_time, 0),
            search_type=search_type,
            count=count,
        )
    except DouyinAPIError as e:
        error(f"搜索失败: {e}")
        raise SystemExit(1)
    finally:
        client.close()

    if as_json:
        print_json(result)
        return

    # Extract video list
    data_list = result.get("data", [])
    videos = []
    for item in data_list:
        aweme_info = item.get("aweme_info")
        if aweme_info:
            videos.append(aweme_info)

    print_videos(videos, keyword=keyword)


@click.command("detail", help="查看视频详情")
@click.argument("aweme_id")
@click.option("--comments", is_flag=True, help="同时加载评论")
@click.option("--comment-count", type=int, default=20, help="评论数量 (默认 20)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def detail(aweme_id, comments, comment_count, account, as_json):
    """查看视频详情和评论。"""
    client = DouyinAPIClient.from_config(account)

    try:
        info(f"正在获取详情: {aweme_id}")
        video_detail = client.get_video_detail(aweme_id)

        if as_json and not comments:
            print_json(video_detail)
            return

        print_video_detail(video_detail)

        # Load comments if requested
        if comments:
            info("正在加载评论...")
            try:
                comment_data = client.get_comments(aweme_id, count=comment_count)
                comment_list = comment_data.get("comments", [])

                if as_json:
                    print_json({"detail": video_detail, "comments": comment_list})
                else:
                    print_comments(comment_list)
            except DouyinAPIError as e:
                warning(f"评论加载失败: {e}")
                info("评论 API 需要签名，可单独用 [bold]dy comments[/] 尝试")

    except DouyinAPIError as e:
        error(f"获取详情失败: {e}")
        raise SystemExit(1)
    finally:
        client.close()
