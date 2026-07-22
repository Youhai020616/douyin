"""
抖音签名工具 — 通过 Playwright 在浏览器内执行签名 JS。

抖音 API 请求需要 a-bogus / x-bogus 签名参数。
本模块使用 Playwright 启动浏览器执行签名计算，避免 Node.js 额外依赖。
"""
from __future__ import annotations

import asyncio
import random
import string
from urllib.parse import urlencode

# ------------------------------------------------------------------
# 基础参数生成（不需要 JS 签名的请求）
# ------------------------------------------------------------------

def generate_device_id() -> str:
    """生成随机设备 ID。"""
    return "".join(random.choices(string.digits, k=19))


def generate_iid() -> str:
    """生成随机 install_id。"""
    return "".join(random.choices(string.digits, k=19))


def get_ms_token(length: int = 128) -> str:
    """生成随机 msToken。"""
    chars = string.ascii_letters + string.digits
    return "".join(random.choices(chars, k=length))


def get_base_params() -> dict[str, str]:
    """获取抖音 Web 端基础请求参数。"""
    return {
        "device_platform": "webapp",
        "aid": "6383",
        "channel": "channel_pc_web",
        "pc_client_type": "1",
        "version_code": "170400",
        "version_name": "17.4.0",
        "update_version_code": "170400",
        "cookie_enabled": "true",
        "screen_width": "1920",
        "screen_height": "1080",
        "browser_language": "zh-CN",
        "browser_platform": "MacIntel",
        "browser_name": "Chrome",
        "browser_version": "120.0.0.0",
        "browser_online": "true",
        "engine_name": "Blink",
        "engine_version": "120.0.0.0",
        "os_name": "Mac OS",
        "os_version": "10.15.7",
        "cpu_core_num": "8",
        "device_memory": "8",
        "platform": "PC",
        "downlink": "10",
        "effective_type": "4g",
        "round_trip_time": "50",
        "msToken": get_ms_token(),
    }


def build_request_url(base_url: str, params: dict[str, str]) -> str:
    """构建完整请求 URL。"""
    return f"{base_url}?{urlencode(params)}"


# ------------------------------------------------------------------
# Web 端请求头
# ------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def get_headers(cookie: str = "", referer: str = "https://www.douyin.com/") -> dict[str, str]:
    """获取抖音 Web 端请求头。"""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": referer,
        "User-Agent": random.choice(USER_AGENTS),
    }
    if cookie:
        headers["Cookie"] = cookie
    return headers


# ------------------------------------------------------------------
# Playwright 签名（异步）
# ------------------------------------------------------------------

_SIGN_PAGE = None  # cache browser page


async def get_sign_page():
    """获取或创建用于签名的 Playwright 页面（单例缓存）。"""
    global _SIGN_PAGE
    if _SIGN_PAGE and not _SIGN_PAGE.is_closed():
        return _SIGN_PAGE

    from playwright.async_api import async_playwright
    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto("https://www.douyin.com/", wait_until="domcontentloaded")
    # Wait a bit for JS to load
    await page.wait_for_timeout(2000)
    _SIGN_PAGE = page
    return page


async def sign_url_async(url: str) -> str:
    """
    使用 Playwright 浏览器内签名 URL。

    在已加载的抖音页面中执行签名 JS，获取 x-bogus / a-bogus 参数。
    """
    try:
        page = await get_sign_page()
        # 尝试调用抖音内置签名函数
        signed = await page.evaluate(
            """(url) => {
                try {
                    // 抖音 Web 端内置的签名函数
                    if (window._webmsxyw) {
                        return window._webmsxyw(url);
                    }
                    if (window.byted_acrawler && window.byted_acrawler.sign) {
                        return window.byted_acrawler.sign({url: url});
                    }
                } catch(e) {}
                return null;
            }""",
            url,
        )
        if signed and isinstance(signed, dict):
            x_bogus = signed.get("X-Bogus", "")
            if x_bogus:
                separator = "&" if "?" in url else "?"
                return f"{url}{separator}X-Bogus={x_bogus}"
        return url
    except Exception:
        return url


def sign_url(url: str) -> str:
    """同步版本的 URL 签名。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return url  # fallback in async context
        return loop.run_until_complete(sign_url_async(url))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(sign_url_async(url))
        finally:
            loop.close()


async def close_sign_page():
    """关闭签名页面，释放资源。"""
    global _SIGN_PAGE
    if _SIGN_PAGE and not _SIGN_PAGE.is_closed():
        browser = _SIGN_PAGE.context.browser
        await _SIGN_PAGE.close()
        if browser:
            await browser.close()
    _SIGN_PAGE = None
