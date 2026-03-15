"""
dy search / detail — 搜索和详情命令。
"""
from __future__ import annotations

import click

from dy_cli.engines.api_client import DouyinAPIClient, DouyinAPIError
from dy_cli.utils.export import export_data
from dy_cli.utils.index_cache import resolve_id, save_index
from dy_cli.utils.output import (
    error,
    info,
    print_comments,
    print_json,
    print_video_detail,
    print_videos,
    warning,
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
@click.option("-o", "--output", default=None, help="导出到文件 (.json/.csv/.yaml)")
def search(keyword, sort, pub_time, search_type, count, account, as_json, output):
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

    # Extract results based on search type
    data_list = result.get("data", [])

    if search_type == "user":
        # 用户搜索: 专用 endpoint 返回顶层 user_list[].user_info
        users = []
        for u in result.get("user_list", []):
            ui = u.get("user_info", {})
            if ui:
                users.append(ui)
        # Fallback: 综合搜索结果中的用户
        if not users:
            for item in data_list:
                for u in item.get("user_list", []):
                    ui = u.get("user_info", {})
                    if ui:
                        users.append(ui)

        if output:
            export_data(users, output)
            return

        _print_user_list(users, keyword=keyword)
    else:
        # 视频搜索: data[].aweme_info
        videos = []
        for item in data_list:
            aweme_info = item.get("aweme_info")
            if aweme_info:
                videos.append(aweme_info)

        # 缓存索引 — 支持 dy read 1 / dy download 3
        save_index(videos)

        if output:
            export_data(videos, output)
            return

        print_videos(videos, keyword=keyword)


def _print_user_list(users: list[dict], keyword: str = ""):
    """打印用户搜索结果。"""
    from rich import box
    from rich.table import Table

    from dy_cli.utils.output import _fmt_count, console

    if not users:
        warning("未找到相关用户")
        return

    title = f"用户搜索: {keyword} ({len(users)} 条)" if keyword else f"用户列表 ({len(users)} 条)"
    table = Table(title=title, box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("昵称", max_width=16, overflow="fold")
    table.add_column("抖音号", max_width=14, overflow="fold")
    table.add_column("粉丝", justify="right", width=10)
    table.add_column("获赞", justify="right", width=10)
    table.add_column("简介", max_width=30, overflow="fold")
    table.add_column("sec_uid", style="dim", max_width=20, overflow="ellipsis")

    for i, u in enumerate(users, 1):
        table.add_row(
            str(i),
            u.get("nickname", "-"),
            u.get("unique_id") or u.get("short_id") or "-",
            _fmt_count(u.get("follower_count", "-")),
            _fmt_count(u.get("total_favorited", "-")),
            (u.get("signature") or "-")[:30],
            (u.get("sec_uid") or "")[:18] + "…" if len(u.get("sec_uid", "")) > 18 else u.get("sec_uid", ""),
        )

    console.print(table)


@click.command("detail", help="查看视频详情 (支持短索引: dy detail 1)")
@click.argument("aweme_id")
@click.option("--comments", is_flag=True, help="同时加载评论")
@click.option("--comment-count", type=int, default=20, help="评论数量 (默认 20)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def detail(aweme_id, comments, comment_count, account, as_json):
    """查看视频详情和评论。支持短索引 (dy search → dy detail 1)。"""
    try:
        aweme_id = resolve_id(aweme_id)
    except ValueError as e:
        error(str(e))
        raise SystemExit(1)
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
