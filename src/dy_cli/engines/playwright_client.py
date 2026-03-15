"""
Playwright Client — 浏览器自动化引擎。

通过 Playwright 操控 creator.douyin.com 实现发布、登录、数据看板等功能。
参考: dreammis/social-auto-upload, withwz/douyin_upload
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Optional

from dy_cli.utils import config


class PlaywrightError(Exception):
    """Playwright 操作错误。"""


def _run_async(coro):
    """在同步上下文中运行异步函数。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


class PlaywrightClient:
    """
    抖音 Playwright 自动化客户端。

    功能:
    - 扫码登录 / Cookie 管理
    - 视频发布 / 图文发布
    - 数据看板抓取
    - 通知获取
    """

    CREATOR_URL = "https://creator.douyin.com"
    UPLOAD_URL = "https://creator.douyin.com/creator-micro/content/upload"
    PUBLISH_IMAGE_URL = "https://creator.douyin.com/creator-micro/content/publish/image"
    ANALYTICS_URL = "https://creator.douyin.com/creator-micro/data/stats/self-content"
    DOUYIN_URL = "https://www.douyin.com"

    def __init__(
        self,
        account: str | None = None,
        headless: bool = False,
        slow_mo: int = 0,
    ):
        self.account = account or "default"
        self.headless = headless
        self.slow_mo = slow_mo
        self.cookie_file = config.get_cookie_file(self.account)

    # ------------------------------------------------------------------
    # Cookie management
    # ------------------------------------------------------------------

    def cookie_exists(self) -> bool:
        """检查 Cookie 文件是否存在。"""
        return os.path.isfile(self.cookie_file)

    def check_login(self) -> bool:
        """验证 Cookie 是否有效。"""
        if not self.cookie_exists():
            return False
        return _run_async(self._check_login_async())

    async def _check_login_async(self) -> bool:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(storage_state=self.cookie_file)
                page = await context.new_page()
                await page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
                try:
                    await page.wait_for_url(
                        "**/creator-micro/content/upload**",
                        timeout=8000,
                    )
                except Exception:
                    return False

                # Check if redirected to login page
                if await page.get_by_text("手机号登录").count() > 0:
                    return False
                if await page.get_by_text("扫码登录").count() > 0:
                    return False

                return True
            finally:
                await browser.close()

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    def login(self) -> bool:
        """打开浏览器扫码登录，保存 Cookie。"""
        return _run_async(self._login_async())

    async def _login_async(self) -> bool:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=False, slow_mo=self.slow_mo)
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(self.CREATOR_URL, wait_until="domcontentloaded")

            print("[dy] 请使用抖音 App 扫码登录...")
            print("[dy] 登录成功后，浏览器会自动关闭")

            # Wait for user to login — detect navigation to creator dashboard
            try:
                await page.wait_for_url(
                    "**/creator-micro/**",
                    timeout=120000,  # 2 minutes
                )
                # Wait a bit for cookies to settle
                await page.wait_for_timeout(3000)
            except Exception:
                print("[dy] 登录超时")
                await browser.close()
                return False

            # Save cookies
            os.makedirs(os.path.dirname(self.cookie_file), exist_ok=True)
            await context.storage_state(path=self.cookie_file)
            print(f"[dy] Cookie 已保存: {self.cookie_file}")
            await browser.close()
            return True

    def logout(self) -> bool:
        """删除 Cookie 文件。"""
        if os.path.isfile(self.cookie_file):
            os.remove(self.cookie_file)
            return True
        return False

    # ------------------------------------------------------------------
    # Publish video
    # ------------------------------------------------------------------

    def publish_video(
        self,
        title: str,
        content: str,
        video_path: str,
        tags: list[str] | None = None,
        visibility: str = "公开",
        schedule_at: str | None = None,
        thumbnail_path: str | None = None,
    ) -> dict:
        """发布视频到抖音。"""
        if not os.path.isfile(video_path):
            raise PlaywrightError(f"视频文件不存在: {video_path}")
        if not self.cookie_exists():
            raise PlaywrightError("未登录，请先运行: dy login")

        return _run_async(
            self._publish_video_async(
                title, content, video_path, tags, visibility, schedule_at, thumbnail_path
            )
        )

    async def _publish_video_async(
        self,
        title: str,
        content: str,
        video_path: str,
        tags: list[str] | None,
        visibility: str,
        schedule_at: str | None,
        thumbnail_path: str | None,
    ) -> dict:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
            )
            context = await browser.new_context(storage_state=self.cookie_file)
            page = await context.new_page()

            try:
                # Navigate to upload page
                await page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # Check login
                if await page.get_by_text("扫码登录").count() > 0:
                    raise PlaywrightError("Cookie 已失效，请重新登录: dy login")

                # Upload video file
                upload_input = page.locator('input[type="file"]').first
                await upload_input.set_input_files(video_path)
                print(f"[dy] 正在上传视频: {os.path.basename(video_path)}")

                # Wait for upload to complete (look for editor/title input)
                await page.wait_for_timeout(5000)

                # Wait for upload progress to finish
                for _ in range(120):  # max 10 minutes
                    # Check if upload is complete
                    ready = await page.locator('[class*="title"] input, [class*="title"] textarea, [contenteditable="true"]').count()
                    if ready > 0:
                        break
                    await page.wait_for_timeout(5000)

                # Fill title — find the title input
                title_input = page.locator('[class*="title"] input, [class*="title"] textarea').first
                try:
                    await title_input.wait_for(timeout=5000)
                    await title_input.clear()
                    await title_input.fill(title)
                except Exception:
                    # Try contenteditable
                    pass

                # Fill description/content
                content_editor = page.locator('[contenteditable="true"]').first
                try:
                    await content_editor.wait_for(timeout=5000)
                    await content_editor.click()

                    # Type content
                    full_text = content
                    if tags:
                        tag_text = " ".join(f"#{t}" for t in tags)
                        full_text = f"{content} {tag_text}"

                    await page.keyboard.type(full_text, delay=50)
                except Exception:
                    pass

                # Handle visibility
                if visibility == "私密" or visibility == "仅自己可见":
                    try:
                        perm_btn = page.locator('text=谁可以看').first
                        if await perm_btn.count() > 0:
                            await perm_btn.click()
                            await page.wait_for_timeout(500)
                            private_opt = page.locator('text=仅自己可见').first
                            if await private_opt.count() > 0:
                                await private_opt.click()
                    except Exception:
                        pass

                # Handle schedule
                if schedule_at:
                    await self._set_schedule_time(page, schedule_at)

                # Set thumbnail if provided
                if thumbnail_path and os.path.isfile(thumbnail_path):
                    try:
                        cover_btn = page.locator('text=选择封面').first
                        if await cover_btn.count() > 0:
                            await cover_btn.click()
                            await page.wait_for_timeout(1000)
                            cover_upload = page.locator('input[type="file"]').last
                            await cover_upload.set_input_files(thumbnail_path)
                            await page.wait_for_timeout(2000)
                    except Exception:
                        pass

                # Click publish button
                await page.wait_for_timeout(2000)
                publish_btn = page.locator('button:has-text("发布")').first
                try:
                    await publish_btn.wait_for(timeout=10000)
                    await publish_btn.click()
                    await page.wait_for_timeout(5000)
                    print("[dy] 发布请求已提交")
                except Exception:
                    print("[dy] 未找到发布按钮，内容已填写，请手动确认")
                    if not self.headless:
                        await page.wait_for_timeout(30000)

                return {"status": "published", "title": title}

            finally:
                await context.storage_state(path=self.cookie_file)
                await browser.close()

    # ------------------------------------------------------------------
    # Publish image/text
    # ------------------------------------------------------------------

    def publish_image_text(
        self,
        title: str,
        content: str,
        images: list[str],
        tags: list[str] | None = None,
        visibility: str = "公开",
        schedule_at: str | None = None,
    ) -> dict:
        """发布图文到抖音。"""
        for img in images:
            if not img.startswith("http") and not os.path.isfile(img):
                raise PlaywrightError(f"图片文件不存在: {img}")
        if not self.cookie_exists():
            raise PlaywrightError("未登录，请先运行: dy login")

        return _run_async(
            self._publish_image_text_async(title, content, images, tags, visibility, schedule_at)
        )

    async def _publish_image_text_async(
        self,
        title: str,
        content: str,
        images: list[str],
        tags: list[str] | None,
        visibility: str,
        schedule_at: str | None,
    ) -> dict:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
            )
            context = await browser.new_context(storage_state=self.cookie_file)
            page = await context.new_page()

            try:
                # Navigate to image publish page
                await page.goto(self.UPLOAD_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # Check login
                if await page.get_by_text("扫码登录").count() > 0:
                    raise PlaywrightError("Cookie 已失效，请重新登录: dy login")

                # Switch to image tab if present
                try:
                    img_tab = page.locator('text=图文').first
                    if await img_tab.count() > 0:
                        await img_tab.click()
                        await page.wait_for_timeout(1000)
                except Exception:
                    pass

                # Upload images — only local files
                local_images = [img for img in images if not img.startswith("http")]
                if local_images:
                    upload_input = page.locator('input[type="file"][accept*="image"]').first
                    try:
                        await upload_input.wait_for(timeout=5000)
                        await upload_input.set_input_files(local_images)
                        print(f"[dy] 正在上传 {len(local_images)} 张图片")
                        await page.wait_for_timeout(3000)
                    except Exception:
                        # Try generic file input
                        upload_input = page.locator('input[type="file"]').first
                        await upload_input.set_input_files(local_images)
                        await page.wait_for_timeout(3000)

                # Fill title
                title_input = page.locator('[class*="title"] input, [class*="title"] textarea').first
                try:
                    await title_input.wait_for(timeout=5000)
                    await title_input.clear()
                    await title_input.fill(title)
                except Exception:
                    pass

                # Fill content
                content_editor = page.locator('[contenteditable="true"]').first
                try:
                    await content_editor.wait_for(timeout=5000)
                    await content_editor.click()

                    full_text = content
                    if tags:
                        tag_text = " ".join(f"#{t}" for t in tags)
                        full_text = f"{content} {tag_text}"

                    await page.keyboard.type(full_text, delay=50)
                except Exception:
                    pass

                # Handle visibility
                if visibility == "私密" or visibility == "仅自己可见":
                    try:
                        perm_btn = page.locator('text=谁可以看').first
                        if await perm_btn.count() > 0:
                            await perm_btn.click()
                            await page.wait_for_timeout(500)
                            private_opt = page.locator('text=仅自己可见').first
                            if await private_opt.count() > 0:
                                await private_opt.click()
                    except Exception:
                        pass

                # Handle schedule
                if schedule_at:
                    await self._set_schedule_time(page, schedule_at)

                # Click publish
                await page.wait_for_timeout(2000)
                publish_btn = page.locator('button:has-text("发布")').first
                try:
                    await publish_btn.wait_for(timeout=10000)
                    await publish_btn.click()
                    await page.wait_for_timeout(5000)
                    print("[dy] 发布请求已提交")
                except Exception:
                    print("[dy] 未找到发布按钮，内容已填写，请手动确认")
                    if not self.headless:
                        await page.wait_for_timeout(30000)

                return {"status": "published", "title": title}

            finally:
                await context.storage_state(path=self.cookie_file)
                await browser.close()

    # ------------------------------------------------------------------
    # Schedule helper
    # ------------------------------------------------------------------

    async def _set_schedule_time(self, page, schedule_at: str):
        """设置定时发布时间。"""
        try:
            # Parse datetime
            dt = datetime.fromisoformat(schedule_at)
            date_str = dt.strftime("%Y年%m月%d日 %H:%M")

            # Find schedule checkbox/toggle
            schedule_toggle = page.locator('text=定时发布').first
            if await schedule_toggle.count() > 0:
                await schedule_toggle.click()
                await page.wait_for_timeout(1000)

                # Find and fill the datetime picker
                time_input = page.locator('[class*="schedule"] input, [class*="time"] input').first
                if await time_input.count() > 0:
                    await time_input.clear()
                    await time_input.fill(date_str)
                    await page.keyboard.press("Enter")
        except Exception:
            print(f"[dy] 定时发布设置失败，将立即发布")

    # ------------------------------------------------------------------
    # Analytics
    # ------------------------------------------------------------------

    def get_analytics(self, page_size: int = 10) -> dict:
        """获取创作者数据看板。"""
        if not self.cookie_exists():
            raise PlaywrightError("未登录")
        return _run_async(self._get_analytics_async(page_size))

    async def _get_analytics_async(self, page_size: int) -> dict:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=self.cookie_file)
            page = await context.new_page()

            try:
                # First go to creator center to establish session
                await page.goto(self.CREATOR_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                # Check if logged in
                if await page.get_by_text("扫码登录").count() > 0:
                    raise PlaywrightError("Cookie 已失效")

                # Navigate to analytics page
                await page.goto(self.ANALYTICS_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)

                # Try clicking "作品数据" tab if present
                try:
                    content_tab = page.locator('text=作品数据').first
                    if await content_tab.count() > 0:
                        await content_tab.click()
                        await page.wait_for_timeout(3000)
                except Exception:
                    pass

                # Extract data from the page — try multiple selectors
                data = await page.evaluate("""() => {
                    const rows = [];

                    // Strategy 1: table rows
                    document.querySelectorAll('table tr, [class*="table"] tr').forEach(tr => {
                        const cells = tr.querySelectorAll('td');
                        if (cells.length >= 3) {
                            const texts = Array.from(cells).map(c => c.textContent.trim());
                            rows.push({
                                '标题': texts[0] || '-',
                                '发布时间': texts[1] || '-',
                                '播放': texts[2] || '-',
                                '完播率': texts[3] || '-',
                                '点赞': texts[4] || '-',
                                '评论': texts[5] || '-',
                                '分享': texts[6] || '-',
                                '涨粉': texts[7] || '-',
                            });
                        }
                    });

                    // Strategy 2: card-style content items
                    if (rows.length === 0) {
                        document.querySelectorAll('[class*="content-card"], [class*="item-wrap"], [class*="data-row"]').forEach(item => {
                            const title = item.querySelector('[class*="title"]')?.textContent?.trim() || '-';
                            const numbers = [];
                            item.querySelectorAll('[class*="num"], [class*="count"], [class*="data"]').forEach(n => {
                                numbers.push(n.textContent.trim());
                            });
                            if (title !== '-' || numbers.length > 0) {
                                rows.push({
                                    '标题': title,
                                    '发布时间': numbers[0] || '-',
                                    '播放': numbers[1] || '-',
                                    '完播率': numbers[2] || '-',
                                    '点赞': numbers[3] || '-',
                                    '评论': numbers[4] || '-',
                                    '分享': numbers[5] || '-',
                                    '涨粉': numbers[6] || '-',
                                });
                            }
                        });
                    }

                    // Get summary stats
                    const summary = {};
                    document.querySelectorAll('[class*="overview"] [class*="item"], [class*="summary"] [class*="item"]').forEach(item => {
                        const label = item.querySelector('[class*="label"], [class*="name"]')?.textContent?.trim();
                        const value = item.querySelector('[class*="value"], [class*="num"]')?.textContent?.trim();
                        if (label && value) summary[label] = value;
                    });

                    return { rows, summary, url: window.location.href };
                }""")

                return data

            finally:
                await browser.close()

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def get_notifications(self) -> dict:
        """获取消息通知。"""
        if not self.cookie_exists():
            raise PlaywrightError("未登录")
        return _run_async(self._get_notifications_async())

    async def _get_notifications_async(self) -> dict:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(storage_state=self.cookie_file)
            page = await context.new_page()

            try:
                await page.goto(
                    "https://creator.douyin.com/creator-micro/message",
                    wait_until="domcontentloaded",
                )
                await page.wait_for_timeout(5000)

                data = await page.evaluate("""() => {
                    const notifications = [];
                    const items = document.querySelectorAll('[class*="message-item"], [class*="notification-item"]');
                    items.forEach(item => {
                        notifications.push({
                            type: item.querySelector('[class*="type"]')?.textContent?.trim() || '-',
                            user: item.querySelector('[class*="name"]')?.textContent?.trim() || '-',
                            content: item.querySelector('[class*="content"]')?.textContent?.trim() || '-',
                            time: item.querySelector('[class*="time"]')?.textContent?.trim() || '-',
                        });
                    });
                    return { mentions: notifications };
                }""")

                return data

            finally:
                await browser.close()
