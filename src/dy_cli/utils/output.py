"""
统一输出格式化 — 表格、JSON、状态信息。
"""
from __future__ import annotations

import json
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
err_console = Console(stderr=True)


# ------------------------------------------------------------------
# 基础状态输出
# ------------------------------------------------------------------

def success(msg: str):
    console.print(f"[bold green]✓[/] {msg}")


def error(msg: str):
    err_console.print(f"[bold red]✗[/] {msg}")


def warning(msg: str):
    console.print(f"[bold yellow]⚠[/] {msg}")


def info(msg: str):
    console.print(f"[dim]ℹ[/] {msg}")


def status(label: str, value: str, style: str = ""):
    if style:
        console.print(f"  [bold]{label}:[/] [{style}]{value}[/]")
    else:
        console.print(f"  [bold]{label}:[/] {value}")


def print_json(data: Any, envelope: bool = True):
    """输出 JSON。envelope=True 时包裹在统一信封中。"""
    from dy_cli.utils.envelope import success_envelope
    output = success_envelope(data) if envelope else data
    console.print_json(json.dumps(output, ensure_ascii=False, indent=2))


def print_table(
    title: str,
    columns: list[str],
    rows: list[list[str]],
    max_width: int | None = None,
):
    table = Table(title=title, box=box.ROUNDED, show_lines=True, expand=False)
    for col in columns:
        table.add_column(col, overflow="fold", max_width=max_width or 40)
    for row in rows:
        table.add_row(*[str(v) for v in row])
    console.print(table)


# ------------------------------------------------------------------
# 抖音专属格式化
# ------------------------------------------------------------------

def _fmt_count(n: Any) -> str:
    """格式化数字，支持 '10.5万' 等。"""
    if n is None or n == "":
        return "-"
    if isinstance(n, str):
        return n
    if isinstance(n, (int, float)):
        if n >= 10000:
            return f"{n / 10000:.1f}万"
        return str(int(n))
    return str(n)


def print_videos(videos: list[dict], keyword: str = ""):
    """打印视频搜索结果列表。"""
    if not videos:
        warning("未找到相关视频")
        return

    title = f"搜索结果: {keyword} ({len(videos)} 条)" if keyword else f"视频列表 ({len(videos)} 条)"
    table = Table(title=title, box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("标题", max_width=30, overflow="fold")
    table.add_column("作者", max_width=12, overflow="fold")
    table.add_column("播放", justify="right", width=8)
    table.add_column("点赞", justify="right", width=8)
    table.add_column("评论", justify="right", width=8)
    table.add_column("类型", width=6)
    table.add_column("aweme_id", style="dim", max_width=22)

    for i, v in enumerate(videos, 1):
        desc = v.get("desc", "") or "-"
        author = v.get("author", {}).get("nickname", "-")
        stats = v.get("statistics", {})
        play = _fmt_count(stats.get("play_count", stats.get("digg_count", "-")))
        likes = _fmt_count(stats.get("digg_count", "-"))
        comments = _fmt_count(stats.get("comment_count", "-"))
        vtype = "图文" if v.get("media_type") == 2 else "视频"
        aweme_id = v.get("aweme_id", "-")

        # Truncate desc
        if len(desc) > 30:
            desc = desc[:28] + "…"

        table.add_row(str(i), desc, author, play, likes, comments, vtype, aweme_id)

    console.print(table)


def print_video_detail(detail: dict):
    """打印单个视频详情面板。"""
    desc = detail.get("desc", "无描述")
    author = detail.get("author", {})
    nickname = author.get("nickname", "-")
    uid = author.get("unique_id") or author.get("short_id") or "-"
    stats = detail.get("statistics", {})
    create_time = detail.get("create_time", "")

    panel_text = Text()
    panel_text.append(f"作者: {nickname}", style="bold")
    panel_text.append(f"  (@{uid})\n")
    if create_time:
        import datetime
        try:
            ts = int(create_time)
            dt = datetime.datetime.fromtimestamp(ts)
            panel_text.append(f"发布: {dt.strftime('%Y-%m-%d %H:%M')}\n")
        except (ValueError, TypeError, OSError):
            pass
    panel_text.append(
        f"▶ {_fmt_count(stats.get('play_count', '-'))}  "
        f"👍 {_fmt_count(stats.get('digg_count', '-'))}  "
        f"💬 {_fmt_count(stats.get('comment_count', '-'))}  "
        f"↗ {_fmt_count(stats.get('share_count', '-'))}  "
        f"⭐ {_fmt_count(stats.get('collect_count', '-'))}\n"
    )
    panel_text.append(f"\n{desc}\n")

    aweme_id = detail.get("aweme_id", "")
    console.print(Panel(panel_text, title=f"🎬 {aweme_id}", border_style="blue"))


def print_comments(comments: list[dict]):
    """打印评论列表。"""
    if not comments:
        info("暂无评论")
        return

    table = Table(title=f"💬 评论 ({len(comments)} 条)", box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("用户", max_width=14, overflow="fold")
    table.add_column("内容", max_width=45, overflow="fold")
    table.add_column("赞", justify="right", width=6)
    table.add_column("回复", justify="right", width=5)

    for i, c in enumerate(comments, 1):
        user = c.get("user", {})
        table.add_row(
            str(i),
            user.get("nickname", "-"),
            c.get("text", "-"),
            _fmt_count(c.get("digg_count", "-")),
            _fmt_count(c.get("reply_comment_total", 0)),
        )

    console.print(table)


def print_trending(items: list[dict]):
    """打印热榜。"""
    if not items:
        warning("暂无热榜数据")
        return

    table = Table(title="🔥 抖音热榜", box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="bold", width=4, justify="right")
    table.add_column("标题", max_width=40, overflow="fold")
    table.add_column("热度", justify="right", width=10)
    table.add_column("标签", width=10)

    LABEL_MAP = {0: "", 1: "新", 2: "热", 3: "爆", 4: "独家"}

    for i, item in enumerate(items, 1):
        title = item.get("word", item.get("title", "-"))
        hot = _fmt_count(item.get("hot_value", item.get("view_count", "-")))
        raw_label = item.get("label", item.get("tag", ""))
        if isinstance(raw_label, int):
            label = LABEL_MAP.get(raw_label, str(raw_label))
        else:
            label = str(raw_label)

        # Top 3 colored
        rank_style = "bold red" if i <= 3 else "dim"
        table.add_row(
            Text(str(i), style=rank_style),
            str(title),
            str(hot),
            label,
        )

    console.print(table)


def print_live_info(info_data: dict):
    """打印直播信息面板。"""
    title = info_data.get("title", "直播间")
    owner = info_data.get("owner", {})
    nickname = owner.get("nickname", "-")
    user_count = _fmt_count(info_data.get("user_count", "-"))
    status_val = "🟢 直播中" if info_data.get("status") == 2 else "⚫ 已结束"

    panel_text = Text()
    panel_text.append(f"主播: {nickname}\n", style="bold")
    panel_text.append(f"状态: {status_val}\n")
    panel_text.append(f"在线: {user_count}\n")

    stream_url = info_data.get("stream_url", "")
    if stream_url:
        panel_text.append(f"\n拉流: {stream_url[:80]}…\n" if len(stream_url) > 80 else f"\n拉流: {stream_url}\n")

    console.print(Panel(panel_text, title=f"📺 {title}", border_style="magenta"))


def print_live_rooms(rooms: list[dict]):
    """打印直播房间列表。"""
    if not rooms:
        warning("未找到直播房间")
        return

    table = Table(title=f"📺 直播房间 ({len(rooms)} 条)", box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("标题", max_width=34, overflow="fold")
    table.add_column("主播", max_width=16, overflow="fold")
    table.add_column("在线", justify="right", width=8)
    table.add_column("房间号", style="dim", max_width=18)

    for i, item in enumerate(rooms, 1):
        room_data = item.get("data", {})
        if not isinstance(room_data, dict):
            room_data = {}
        owner = room_data.get("owner", {})
        if not isinstance(owner, dict):
            owner = {}

        web_rid = (
            item.get("web_rid")
            or owner.get("web_rid")
            or room_data.get("web_rid")
            or room_data.get("id_str")
            or room_data.get("id")
            or "-"
        )
        title = room_data.get("title") or item.get("title") or "-"
        nickname = owner.get("nickname") or item.get("owner_nickname") or "-"
        user_count = room_data.get("user_count", item.get("user_count", "-"))

        table.add_row(
            str(i),
            str(title),
            str(nickname),
            _fmt_count(user_count),
            str(web_rid),
        )

    console.print(table)


def print_user_profile(profile: dict):
    """打印用户资料。"""
    nickname = profile.get("nickname", "-")
    unique_id = profile.get("unique_id") or profile.get("short_id") or "-"
    signature = profile.get("signature", "")
    follower = _fmt_count(profile.get("follower_count", "-"))
    following = _fmt_count(profile.get("following_count", "-"))
    total_favorited = _fmt_count(profile.get("total_favorited", "-"))
    aweme_count = profile.get("aweme_count", "-")

    panel_text = Text()
    panel_text.append(f"昵称: {nickname}", style="bold")
    panel_text.append(f"  @{unique_id}\n")
    panel_text.append(f"粉丝: {follower}  关注: {following}  获赞: {total_favorited}  作品: {aweme_count}\n")
    if signature:
        panel_text.append(f"\n{signature}")

    console.print(Panel(panel_text, title="👤 用户资料", border_style="green"))


def print_analytics(data: dict):
    """打印数据看板。"""
    rows = data.get("rows", [])
    if not rows:
        warning("暂无数据")
        return

    table = Table(title="📊 数据看板", box=box.ROUNDED, show_lines=True)
    table.add_column("标题", max_width=20, overflow="fold")
    table.add_column("发布时间", width=16)
    table.add_column("播放", justify="right", width=8)
    table.add_column("完播率", justify="right", width=8)
    table.add_column("点赞", justify="right", width=8)
    table.add_column("评论", justify="right", width=8)
    table.add_column("分享", justify="right", width=8)
    table.add_column("涨粉", justify="right", width=8)

    for row in rows:
        table.add_row(
            str(row.get("标题", "-")),
            str(row.get("发布时间", "-")),
            str(row.get("播放", "-")),
            str(row.get("完播率", "-")),
            str(row.get("点赞", "-")),
            str(row.get("评论", "-")),
            str(row.get("分享", "-")),
            str(row.get("涨粉", "-")),
        )

    console.print(table)
