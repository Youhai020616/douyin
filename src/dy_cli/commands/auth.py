"""
dy login / logout / status — 认证命令。

支持两种登录方式:
1. 浏览器 Cookie 自动提取 (默认, 零摩擦)
2. Playwright 扫码 (--qrcode)
"""
from __future__ import annotations

import json
import os

import click

from dy_cli.engines.playwright_client import PlaywrightClient, PlaywrightError
from dy_cli.utils import config
from dy_cli.utils.output import DyCliError, console, info, print_json, status, success, warning


def _extract_browser_cookies(account: str | None = None) -> bool:
    """从浏览器自动提取抖音 Cookie（需要用户在浏览器中已登录抖音）。"""
    try:
        import browser_cookie3 as bc3
    except ImportError:
        return False

    # 从多个域名收集 cookie
    all_cookies: dict[str, dict] = {}
    browsers = ["chrome", "firefox", "edge", "brave", "opera", "chromium", "safari"]
    domains = [".douyin.com", "www.douyin.com", "creator.douyin.com"]

    found_browser = None
    for browser_name in browsers:
        loader = getattr(bc3, browser_name, None)
        if not loader:
            continue
        for domain in domains:
            try:
                jar = loader(domain_name=domain)
                for c in jar:
                    if "douyin" in (c.domain or ""):
                        all_cookies[c.name] = {
                            "name": c.name,
                            "value": c.value,
                            "domain": c.domain,
                            "path": c.path or "/",
                        }
                        found_browser = browser_name
            except Exception:
                continue
        if all_cookies:
            break

    if not all_cookies:
        return False

    # 检查是否有关键 session cookie
    key_names = {"sessionid", "passport_csrf_token", "odin_tt", "sid_guard"}
    has_session = bool(key_names & set(all_cookies.keys()))

    if not has_session:
        info(f"从 {found_browser} 提取了 {len(all_cookies)} 个 cookie，但缺少登录态")
        info("请先在浏览器中登录 douyin.com，然后重试")
        return False

    # 保存为 Playwright storage_state 格式
    cookie_file = config.get_cookie_file(account)
    os.makedirs(os.path.dirname(cookie_file), exist_ok=True)
    storage = {
        "cookies": list(all_cookies.values()),
        "origins": [],
    }
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(storage, f, ensure_ascii=False, indent=2)
    info(f"从 {found_browser} 提取了 {len(all_cookies)} 个 cookie (含登录态)")
    return True


@click.command("login", help="登录抖音")
@click.option("--account", default=None, help="账号名")
@click.option("--browser", is_flag=True, help="从浏览器提取 Cookie (需在浏览器中已登录抖音)")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON (已登录时不交互询问)")
def login(account, browser, as_json):
    """登录抖音。默认扫码登录，--browser 从浏览器提取 Cookie。"""
    cfg = config.load_config()

    # 已登录检查
    client = PlaywrightClient(account=account, headless=True)
    if client.cookie_exists():
        try:
            if client.check_login():
                success("已登录抖音")
                if as_json:
                    print_json(_login_result(client, "existing"))
                    return
                if not click.confirm("是否重新登录?", default=False):
                    return
        except Exception:
            pass

    # 方式 1: 从浏览器提取 Cookie
    if browser:
        info("正在从浏览器提取 Cookie...")
        if _extract_browser_cookies(account):
            success("登录成功! 🎉 (从浏览器提取)")
            if as_json:
                print_json(_login_result(client, "browser"))
            return
        else:
            warning("浏览器 Cookie 提取失败，切换到扫码模式")

    # 方式 2: Playwright 扫码 (默认)
    info("正在打开浏览器，请使用抖音 App 扫码...")
    pw_client = PlaywrightClient(
        account=account,
        headless=False,
        slow_mo=cfg["playwright"].get("slow_mo", 0),
    )
    try:
        ok = pw_client.login()
    except PlaywrightError as e:
        raise DyCliError("playwright_error", f"登录失败: {e}")
    if not ok:
        raise DyCliError("not_authenticated", "登录超时或失败")
    success("登录成功! 🎉")
    if as_json:
        print_json(_login_result(pw_client, "qrcode"))


def _login_result(client: PlaywrightClient, method: str) -> dict:
    return {
        "authenticated": True,
        "method": method,  # existing | browser | qrcode
        "account": client.account,
        "cookie_file": client.cookie_file,
    }


@click.command("logout", help="退出登录")
@click.option("--account", default=None, help="账号名")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def logout(account, as_json):
    """退出登录（删除 Cookie）。"""
    client = PlaywrightClient(account=account)
    removed = client.logout()
    if removed:
        success("已退出登录，Cookie 已删除")
    else:
        info("未找到登录凭据")
    if as_json:
        print_json({"logged_out": removed, "account": client.account, "cookie_file": client.cookie_file})


@click.command("status", help="查看登录状态")
@click.option("--account", default=None, help="账号名")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def auth_status(account, as_json):
    """检查登录状态。"""
    client = PlaywrightClient(account=account)
    result = {
        "authenticated": False,
        "reason": None,  # None | no_cookie | expired | check_failed
        "account": client.account,
        "cookie_file": client.cookie_file,
    }

    if not client.cookie_exists():
        result["reason"] = "no_cookie"
    else:
        info("正在验证 Cookie...")
        try:
            result["authenticated"] = client.check_login()
            if not result["authenticated"]:
                result["reason"] = "expired"
        except Exception as e:
            result["reason"] = "check_failed"
            result["message"] = str(e)

    if as_json:
        print_json(result)
        return

    console.print()
    if result["authenticated"]:
        status("登录状态", "已登录", "green")
        status("Cookie", client.cookie_file, "dim")
    elif result["reason"] == "no_cookie":
        status("登录状态", "未登录 (无 Cookie 文件)", "red")
        info("使用 [bold]dy login[/] 登录")
    elif result["reason"] == "expired":
        status("登录状态", "Cookie 已失效", "yellow")
        info("使用 [bold]dy login[/] 重新登录")
    else:
        status("登录状态", f"检查失败: {result.get('message')}", "red")
    console.print()
