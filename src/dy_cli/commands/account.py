"""
dy account — 多账号管理命令。
"""
from __future__ import annotations

import os

import click
from rich import box
from rich.table import Table

from dy_cli.engines.playwright_client import PlaywrightClient
from dy_cli.utils import config
from dy_cli.utils.output import DyCliError, console, info, print_json, success


@click.group("account", help="多账号管理")
def account_group():
    pass


@account_group.command("list", help="列出所有账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def list_accounts(as_json):
    """列出已配置的账号。"""
    cookies_dir = config.COOKIES_DIR
    default_account = config.load_config()["default"]["account"]

    files = sorted(f for f in os.listdir(cookies_dir) if f.endswith(".json")) if os.path.isdir(cookies_dir) else []
    accounts = []
    for f in files:
        cookie_path = os.path.join(cookies_dir, f)
        name = f[: -len(".json")]
        accounts.append({
            "name": name,
            "cookie_file": cookie_path,
            "has_cookie": os.path.getsize(cookie_path) > 100,
            "is_default": name == default_account,
        })

    if as_json:
        print_json(accounts)
        return

    if not accounts:
        info("暂无配置账号")
        info("使用 [bold]dy account add <name>[/] 添加账号")
        return

    table = Table(title="📱 账号列表", box=box.ROUNDED)
    table.add_column("名称", style="bold")
    table.add_column("Cookie 文件")
    table.add_column("状态")
    table.add_column("默认", justify="center")
    for a in accounts:
        table.add_row(
            a["name"],
            a["cookie_file"],
            "✅ 有效" if a["has_cookie"] else "⚠️ 空",
            "⭐" if a["is_default"] else "",
        )
    console.print(table)


@account_group.command("add", help="添加新账号并登录")
@click.argument("name")
def add_account(name):
    """添加新账号并打开浏览器登录。"""
    cookie_file = config.get_cookie_file(name)
    if os.path.isfile(cookie_file):
        if not click.confirm(f"账号 '{name}' 已存在，是否重新登录?", default=False):
            return

    info(f"正在为账号 '{name}' 打开登录页面...")
    client = PlaywrightClient(account=name, headless=False)
    try:
        ok = client.login()
    except Exception as e:
        raise DyCliError("playwright_error", f"登录失败: {e}")
    if not ok:
        raise DyCliError("not_authenticated", "登录失败")
    success(f"账号 '{name}' 已添加并登录")


@account_group.command("remove", help="删除账号")
@click.argument("name")
@click.confirmation_option(prompt="确认删除此账号?")
def remove_account(name):
    """删除账号 (Cookie 文件)。"""
    cookie_file = config.get_cookie_file(name)
    if not os.path.isfile(cookie_file):
        raise DyCliError("not_found", f"账号 '{name}' 不存在")
    os.remove(cookie_file)
    success(f"账号 '{name}' 已删除")


@account_group.command("default", help="设置默认账号")
@click.argument("name")
def set_default(name):
    """设置默认账号。"""
    cookie_file = config.get_cookie_file(name)
    if not os.path.isfile(cookie_file):
        warning_text = f"账号 '{name}' 尚未登录"
        info(warning_text)
        if not click.confirm("仍要设为默认?", default=False):
            return

    config.set_value("default.account", name)
    success(f"默认账号已设为: {name}")
