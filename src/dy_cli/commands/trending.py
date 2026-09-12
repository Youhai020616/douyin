"""
dy trending — 抖音热榜命令（抖音特色功能）。
"""
from __future__ import annotations

import time

import click

from dy_cli.engines.api_client import DouyinAPIClient, DouyinAPIError
from dy_cli.utils.export import export_data
from dy_cli.utils.output import DyCliError, console, info, print_json, print_trending, warning


@click.command("trending", help="🔥 抖音热榜")
@click.option("--count", type=int, default=50, help="显示条数 (默认 50)")
@click.option("--watch", is_flag=True, help="实时刷新模式 (每 5 分钟更新)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
@click.option("-o", "--output", default=None, help="导出到文件 (.json/.csv/.yaml)")
def trending(count, watch, account, as_json, output):
    """查看抖音热榜。"""
    client = DouyinAPIClient.from_config(account)

    try:
        if watch:
            _watch_trending(client, count, as_json)
        else:
            _show_trending(client, count, as_json, output)
    except KeyboardInterrupt:
        info("已退出热榜监控")
    except DouyinAPIError as e:
        raise DyCliError("api_error", f"获取热榜失败: {e}")
    finally:
        client.close()


def _show_trending(client: DouyinAPIClient, count: int, as_json: bool, output: str = None):
    """显示热榜。"""
    info("正在获取抖音热榜...")
    items = client.get_trending()

    if as_json:
        print_json(items[:count])
        return

    if output:
        export_data(items[:count], output)
        return

    print_trending(items[:count])

    if items:
        console.print()
        info(f"共 {len(items)} 条热搜，显示前 {min(count, len(items))} 条")


def _watch_trending(client: DouyinAPIClient, count: int, as_json: bool):
    """实时刷新热榜。"""
    interval = 300  # 5 minutes
    info(f"热榜监控模式 (每 {interval // 60} 分钟刷新，Ctrl+C 退出)")
    console.print()

    while True:
        try:
            items = client.get_trending()
            if as_json:
                print_json(items[:count])
            else:
                console.clear()
                import datetime
                now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                console.rule(f"[bold]🔥 抖音热榜 — {now}[/]")
                print_trending(items[:count])
                console.print()
                info(f"下次刷新: {interval // 60} 分钟后 (Ctrl+C 退出)")

            time.sleep(interval)
        except DouyinAPIError as e:
            warning(f"刷新失败: {e}, 等待重试...")
            time.sleep(60)
