"""
dy me / profile — 用户信息命令。
"""
from __future__ import annotations

import click

from dy_cli.engines.api_client import DouyinAPIClient, DouyinAPIError
from dy_cli.engines.playwright_client import PlaywrightClient, PlaywrightError
from dy_cli.utils.output import (
    DyCliError,
    console,
    info,
    print_json,
    print_user_profile,
    print_videos,
    success,
)


@click.command("me", help="查看自己的账号信息")
@click.option("--account", default=None, help="账号名")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def me(account, as_json):
    """查看当前登录账号信息。"""
    client = PlaywrightClient(account=account, headless=True)

    if not client.cookie_exists():
        raise DyCliError("not_authenticated", "未登录，请先运行: dy login")

    info("正在检查登录状态...")
    try:
        logged_in = client.check_login()
    except PlaywrightError as e:
        raise DyCliError("playwright_error", f"检查失败: {e}")
    if not logged_in:
        raise DyCliError("not_authenticated", "Cookie 已失效，请重新登录: dy login")

    if as_json:
        print_json({"authenticated": True, "account": client.account, "cookie_file": client.cookie_file})
        return
    success("已登录抖音 ✅")
    console.print(f"  [bold]Cookie:[/] {client.cookie_file}")


@click.command("profile", help="查看用户主页")
@click.argument("sec_user_id")
@click.option("--posts", is_flag=True, help="同时加载作品列表")
@click.option("--post-count", type=int, default=20, help="作品数量 (默认 20)")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def profile(sec_user_id, posts, post_count, account, as_json):
    """查看用户主页信息和作品。"""
    client = DouyinAPIClient.from_config(account)

    try:
        info("正在获取用户资料...")
        user = client.get_user_profile(sec_user_id)
        aweme_list = None
        if posts:
            info("正在获取作品列表...")
            aweme_list = client.get_user_posts(sec_user_id, count=post_count).get("aweme_list", [])
    except DouyinAPIError as e:
        raise DyCliError("api_error", f"获取用户资料失败: {e}")
    finally:
        client.close()

    if as_json:
        print_json(user if aweme_list is None else {"user": user, "posts": aweme_list})
        return

    print_user_profile(user)
    if aweme_list is not None:
        print_videos(aweme_list, keyword=f"{user.get('nickname', '')} 的作品")
