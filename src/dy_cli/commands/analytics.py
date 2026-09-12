"""
dy analytics / notifications — 数据分析命令 (Playwright)。
"""
from __future__ import annotations

import click

from dy_cli.engines.playwright_client import PlaywrightClient, PlaywrightError
from dy_cli.utils import config
from dy_cli.utils.output import (
    DyCliError,
    console,
    info,
    print_analytics,
    print_json,
    success,
    warning,
)


@click.command("analytics", help="📊 数据看板 (创作者数据分析)")
@click.option("--csv", "csv_file", default=None, help="导出 CSV 文件路径")
@click.option("--page-size", type=int, default=10, help="每页条数 (默认 10)")
@click.option("--account", default=None, help="账号名")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def analytics(csv_file, page_size, account, as_json):
    """获取创作者数据看板 (Playwright 引擎)。"""
    config.load_config()
    client = PlaywrightClient(
        account=account,
        headless=True,
    )

    if not client.cookie_exists():
        raise DyCliError("not_authenticated", "未登录，请先运行: dy login")

    info("正在获取数据看板 (Playwright)...")

    try:
        result = client.get_analytics(page_size=page_size)
    except PlaywrightError as e:
        raise DyCliError("playwright_error", f"获取数据失败: {e} (请确保已登录: dy status)")

    # Parse API data if captured
    api_items = result.get("api_data", {}).get("list", {}).get("items", [])
    if api_items:
        import datetime

        rows = []
        for item in api_items:
            metrics = item.get("metrics", {})
            create_time = item.get("create_time", 0)
            try:
                dt = datetime.datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError, OSError):
                dt = "-"
            rows.append({
                "标题": item.get("description", "-")[:20] or "-",
                "发布时间": dt,
                "播放": metrics.get("play_count", "-"),
                "完播率": metrics.get("finish_rate", "-"),
                "点赞": metrics.get("digg_count", "-"),
                "评论": metrics.get("comment_count", "-"),
                "分享": metrics.get("share_count", "-"),
                "涨粉": metrics.get("follow_count", "-"),
                "可见性": item.get("visibility", "-"),
            })
        result = {"rows": rows}

    if as_json:
        print_json(result)
    else:
        print_analytics(result)

    # Export CSV
    if csv_file:
        rows = result.get("rows", [])
        if rows:
            import csv
            keys = rows[0].keys()
            with open(csv_file, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(rows)
            success(f"CSV 已导出: {csv_file}")
        else:
            warning("无数据可导出")


@click.command("notifications", help="🔔 通知消息")
@click.option("--account", default=None, help="账号名")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def notifications(account, as_json):
    """获取通知消息 (Playwright 引擎)。"""
    config.load_config()
    client = PlaywrightClient(
        account=account,
        headless=True,
    )

    if not client.cookie_exists():
        raise DyCliError("not_authenticated", "未登录，请先运行: dy login")

    info("正在获取通知消息...")

    try:
        result = client.get_notifications()
    except PlaywrightError as e:
        raise DyCliError("playwright_error", f"获取通知失败: {e}")

    if as_json:
        print_json(result)
    else:
        _print_notifications(result)


def _print_notifications(data: dict):
    """格式化输出通知。"""
    from rich import box
    from rich.table import Table

    mentions = data.get("mentions", [])
    if not mentions:
        info("暂无新通知")
        return

    table = Table(title="🔔 通知消息", box=box.ROUNDED, show_lines=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("类型", width=8)
    table.add_column("用户", max_width=15)
    table.add_column("内容", max_width=40, overflow="fold")
    table.add_column("时间", width=16)

    for i, mention in enumerate(mentions, 1):
        table.add_row(
            str(i),
            mention.get("type", "-"),
            mention.get("user", "-"),
            mention.get("content", "-"),
            mention.get("time", "-"),
        )

    console.print(table)
