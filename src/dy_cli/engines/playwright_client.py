"""
Playwright Client — 浏览器自动化引擎。

通过 Playwright 操控 creator.douyin.com 实现发布、登录、数据看板等功能。
参考: dreammis/social-auto-upload, withwz/douyin_upload
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime

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
                await page.wait_for_timeout(3000)
            except Exception:
                print("[dy] 登录超时")
                await browser.close()
                return False

            # Visit multiple pages to collect ALL cookies
            print("[dy] 正在收集完整 Cookie...")
            for url in [
                "https://www.douyin.com/",
                "https://creator.douyin.com/creator-micro/content/manage",
            ]:
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                    await page.wait_for_timeout(2000)
                except Exception:
                    pass

            # Save cookies
            os.makedirs(os.path.dirname(self.cookie_file), exist_ok=True)
            await context.storage_state(path=self.cookie_file)

            cookies = await context.cookies()
            douyin_count = len([c for c in cookies if "douyin" in c.get("domain", "")])
            print(f"[dy] Cookie 已保存: {douyin_count} 个 ({self.cookie_file})")
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

                # Handle cover (required by Douyin)
                await self._select_cover(page)

                # Handle visibility
                if visibility == "私密" or visibility == "仅自己可见":
                    try:
                        private_opt = page.locator('text=仅自己可见').first
                        if await private_opt.count() > 0:
                            await private_opt.click(force=True)
                    except Exception:
                        pass

                # Click the EXACT "发布" button (not "高清发布")
                await page.wait_for_timeout(2000)
                published = await page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.textContent.trim() === '发布' && !b.disabled) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")

                if published:
                    await page.wait_for_timeout(5000)
                    # Check for error toast
                    toast = await page.evaluate(
                        '()=>Array.from(document.querySelectorAll("[class*=toast]"))'
                        '.map(t=>t.textContent.trim()).filter(Boolean)'
                    )
                    if toast and "封面" in str(toast):
                        print("[dy] 封面设置失败，请手动设置封面后发布")
                    elif toast and "成功" in str(toast):
                        print("[dy] 发布成功!")
                    else:
                        # Wait for navigation to manage page
                        for _ in range(15):
                            await page.wait_for_timeout(2000)
                            if "manage" in page.url:
                                print("[dy] 发布成功!")
                                break
                        else:
                            print("[dy] 发布请求已提交")
                else:
                    print("[dy] 未找到发布按钮，内容已填写，请手动确认")
                    if not self.headless:
                        await page.wait_for_timeout(30000)

                return {"status": "published", "title": title}

            finally:
                await context.storage_state(path=self.cookie_file)
                await browser.close()

    async def _select_cover(self, page):
        """选择视频封面（必填项）。"""
        try:
            # Dismiss any overlay guides
            await page.evaluate(
                '()=>document.querySelectorAll("[class*=shepherd]").forEach(e=>e.remove())'
            )

            # Wait for AI cover generation
            for _ in range(15):
                await page.wait_for_timeout(1000)
                if await page.locator('text=生成中').count() == 0:
                    break

            # Click the cover area to open cover editor
            cover_divs = await page.evaluate("""() => {
                const els = document.querySelectorAll('[class*="cover"]');
                for (const el of els) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 100 && r.height > 80 && r.width < 300 &&
                        el.textContent.includes('选择封面') && el.onclick !== undefined) {
                        return {x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
                // Fallback: find by text
                const all = document.querySelectorAll('div');
                for (const el of all) {
                    const r = el.getBoundingClientRect();
                    if (el.textContent.trim() === '选择封面' && r.width > 50 && r.height > 50) {
                        return {x: r.x + r.width/2, y: r.y + r.height/2};
                    }
                }
                return null;
            }""")

            if cover_divs:
                await page.mouse.click(int(cover_divs["x"]), int(cover_divs["y"]))
                await page.wait_for_timeout(5000)

                # Click "完成" in cover editor to accept default frame
                done_btn = page.get_by_role("button", name="完成")
                if await done_btn.count() > 0:
                    await done_btn.last.click(force=True)
                    await page.wait_for_timeout(2000)
                    print("[dy] 封面已设置")
            else:
                print("[dy] 未找到封面选择区域")
        except Exception as e:
            print(f"[dy] 封面设置跳过: {e}")

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
                        private_opt = page.locator('text=仅自己可见').first
                        if await private_opt.count() > 0:
                            await private_opt.click(force=True)
                    except Exception:
                        pass

                # Handle schedule
                if schedule_at:
                    await self._set_schedule_time(page, schedule_at)

                # Click the EXACT "发布" button (not "高清发布")
                await page.wait_for_timeout(2000)
                published = await page.evaluate("""() => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.textContent.trim() === '发布' && !b.disabled) {
                            b.click();
                            return true;
                        }
                    }
                    return false;
                }""")

                if published:
                    await page.wait_for_timeout(5000)
                    print("[dy] 发布请求已提交")
                else:
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
            print("[dy] 定时发布设置失败，将立即发布")

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
                # Intercept XHR responses to capture analytics API data
                api_data = {}

                async def on_response(response):
                    url = response.url
                    if "content/data" in url or "item/list" in url or "data/stats" in url:
                        try:
                            body = await response.json()
                            api_data[url.split("?")[0].split("/")[-1]] = body
                        except Exception:
                            pass

                page.on("response", on_response)

                # Navigate to creator center
                await page.goto(self.CREATOR_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(3000)

                if await page.get_by_text("扫码登录").count() > 0:
                    raise PlaywrightError("Cookie 已失效")

                # Navigate to content analytics
                await page.goto(self.ANALYTICS_URL, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)

                # Try clicking "作品数据" tab
                for tab_name in ["作品数据", "作品管理"]:
                    try:
                        tab = page.locator(f"text={tab_name}").first
                        if await tab.count() > 0:
                            await tab.click()
                            await page.wait_for_timeout(3000)
                            break
                    except Exception:
                        pass

                # If we captured API data, use it directly
                if api_data:
                    return {"rows": [], "api_data": api_data, "url": page.url}

                # Fallback: scrape page content as structured text
                page_data = await page.evaluate("""() => {
                    const result = {rows: [], summary: {}, url: window.location.href};

                    // Get page text in structured blocks
                    const blocks = [];
                    document.querySelectorAll('main, [class*="content"]').forEach(el => {
                        if (el.offsetHeight > 100 && el.innerText.length > 20) {
                            blocks.push(el.innerText.substring(0, 2000));
                        }
                    });
                    result.page_content = blocks.slice(0, 3).join('\\n---\\n');

                    // Extract any visible metrics
                    document.querySelectorAll('[class*="metric"], [class*="stat"], [class*="overview"] > div').forEach(el => {
                        const text = el.innerText.trim();
                        if (text && text.length < 100) {
                            const parts = text.split('\\n');
                            if (parts.length >= 2) {
                                result.summary[parts[0]] = parts[1];
                            }
                        }
                    });

                    return result;
                }""")

                return page_data

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

    # ------------------------------------------------------------------
    # Comments (Playwright scraping — API needs a-bogus signature)
    # ------------------------------------------------------------------

    def get_comments(self, aweme_id: str, count: int = 20) -> list[dict]:
        """从视频页面抓取评论。"""
        if not self.cookie_exists():
            raise PlaywrightError("未登录")
        return _run_async(self._get_comments_async(aweme_id, count))

    def get_video_current_src(self, aweme_id: str) -> str:
        """从视频页面读取播放器当前真实媒体地址。"""
        if not self.cookie_exists():
            raise PlaywrightError("未登录")
        return _run_async(self._get_video_current_src_async(aweme_id))

    async def _get_video_current_src_async(self, aweme_id: str) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                storage_state=self.cookie_file,
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()

            try:
                await page.goto(
                    f"https://www.douyin.com/video/{aweme_id}",
                    wait_until="domcontentloaded",
                )
                await page.wait_for_selector("video", timeout=30000)
                await page.wait_for_function(
                    """() => {
                        const v = document.querySelector('video');
                        return !!(v && v.currentSrc && v.readyState >= 2);
                    }""",
                    timeout=30000,
                )
                current_src = await page.evaluate(
                    """() => {
                        const v = document.querySelector('video');
                        return v ? (v.currentSrc || '') : '';
                    }"""
                )
                if not current_src:
                    raise PlaywrightError("未能从播放器读取 currentSrc")
                return str(current_src)
            finally:
                await browser.close()

    async def _get_comments_async(self, aweme_id: str, count: int) -> list[dict]:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=self.cookie_file,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            try:
                await page.goto(
                    f"https://www.douyin.com/video/{aweme_id}",
                    wait_until="domcontentloaded",
                )
                await page.wait_for_timeout(6000)

                # Scroll to load more comments
                for _ in range(max(0, count // 10 - 1)):
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(1500)

                comments = await page.evaluate("""() => {
                    const items = document.querySelectorAll('[data-e2e="comment-item"]');
                    const results = [];
                    items.forEach(item => {
                        const lines = (item.innerText || '').split('\\n').filter(l => l.trim());
                        if (lines.length < 2) return;

                        const nickname = lines[0] || '';
                        const isAuthor = lines.includes('作者');

                        // Find the main comment text (skip '作者', '...' etc)
                        let text = '';
                        for (let i = 1; i < lines.length; i++) {
                            const l = lines[i];
                            if (l === '作者' || l === '...' || l === '展开' || l.length < 2) continue;
                            if (/^\\d+[天时分秒]前/.test(l) || /^\\d{4}/.test(l) || /·/.test(l)) break;
                            text = l;
                            break;
                        }

                        // Find likes (last numeric item)
                        let digg = 0;
                        const last = lines[lines.length - 1];
                        if (/^\\d+$/.test(last)) digg = parseInt(last);

                        if (nickname && text) {
                            results.push({
                                user: {nickname: nickname},
                                text: text,
                                digg_count: digg,
                                is_author: isAuthor,
                            });
                        }
                    });
                    return results;
                }""")

                return comments[:count]

            finally:
                await browser.close()

    # ------------------------------------------------------------------
    # Interactions (like / comment / favorite / follow)
    # ------------------------------------------------------------------

    def interact(self, aweme_id: str, action: str, **kwargs) -> dict:
        """
        在 douyin.com 视频页面执行互动操作。

        action: "like" | "unlike" | "favorite" | "unfavorite" | "comment" | "follow" | "unfollow"
        kwargs: content (for comment), sec_user_id (for follow)
        """
        if not self.cookie_exists():
            raise PlaywrightError("未登录，请先运行: dy login")
        return _run_async(self._interact_async(aweme_id, action, **kwargs))

    async def _interact_async(self, aweme_id: str, action: str, **kwargs) -> dict:
        from playwright.async_api import async_playwright
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(
                storage_state=self.cookie_file,
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            try:
                if action in ("follow", "unfollow"):
                    return await self._do_follow(page, kwargs.get("sec_user_id", aweme_id), action)

                # Navigate to video page
                url = f"https://www.douyin.com/video/{aweme_id}"
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)
                # Wait for action buttons to load
                for _ in range(10):
                    if await page.locator('[data-e2e="video-player-digg"]').count() > 0:
                        break
                    await page.wait_for_timeout(1000)

                if action == "like":
                    return await self._do_like(page, aweme_id)
                elif action == "unlike":
                    return await self._do_like(page, aweme_id, undo=True)
                elif action == "favorite":
                    return await self._do_favorite(page, aweme_id)
                elif action == "unfavorite":
                    return await self._do_favorite(page, aweme_id, undo=True)
                elif action == "comment":
                    return await self._do_comment(page, aweme_id, kwargs.get("content", ""))
                else:
                    raise PlaywrightError(f"未知操作: {action}")

            finally:
                await context.storage_state(path=self.cookie_file)
                await browser.close()

    async def _do_like(self, page, aweme_id: str, undo: bool = False) -> dict:
        """点赞/取消点赞 — JS 直接点击，绕过可见性检查。"""
        clicked = await page.evaluate("""() => {
            const el = document.querySelector('[data-e2e="video-player-digg"]');
            if (el) { el.click(); return true; }
            return false;
        }""")
        await page.wait_for_timeout(1500)
        return {"action": "unlike" if undo else "like", "aweme_id": aweme_id, "success": clicked}

    async def _do_favorite(self, page, aweme_id: str, undo: bool = False) -> dict:
        """收藏/取消收藏 — JS 直接点击。"""
        clicked = await page.evaluate("""() => {
            const el = document.querySelector('[data-e2e="video-player-collect"]');
            if (el) { el.click(); return true; }
            return false;
        }""")
        await page.wait_for_timeout(1500)
        return {"action": "unfavorite" if undo else "favorite", "aweme_id": aweme_id, "success": clicked}

    async def _do_comment(self, page, aweme_id: str, content: str) -> dict:
        """发表评论。"""
        if not content:
            raise PlaywrightError("评论内容不能为空")

        commented = False
        # Click comment icon to focus the input area
        comment_icon = page.locator('[data-e2e="feed-comment-icon"]')
        if await comment_icon.count() > 0:
            await comment_icon.first.click()
            await page.wait_for_timeout(1000)

        # Find comment input (contenteditable or textarea)
        input_sel = page.locator(
            '[data-e2e="comment-input"], '
            '[class*="comment"] [contenteditable="true"], '
            '[placeholder*="善语结善缘"], [placeholder*="说点什么"]'
        )
        if await input_sel.count() > 0:
            await input_sel.first.click()
            await page.wait_for_timeout(500)
            await page.keyboard.type(content, delay=30)
            await page.wait_for_timeout(500)

            # Submit
            send = page.locator(
                '[data-e2e="comment-post"], '
                'button:has-text("发布")'
            ).last
            if await send.count() > 0:
                await send.click()
                commented = True
            else:
                await page.keyboard.press("Enter")
                commented = True

        await page.wait_for_timeout(2000)
        return {"action": "comment", "aweme_id": aweme_id, "content": content, "success": commented}

    async def _do_follow(self, page, sec_user_id: str, action: str) -> dict:
        """关注/取消关注用户。"""
        await page.goto(f"https://www.douyin.com/user/{sec_user_id}", wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        if action == "follow":
            btn = page.locator('[data-e2e="user-info-follow"], button:has-text("关注")')
        else:
            btn = page.locator('button:has-text("已关注"), button:has-text("互相关注")')

        clicked = False
        if await btn.count() > 0:
            await btn.first.click()
            clicked = True
            await page.wait_for_timeout(1500)

        return {"action": action, "sec_user_id": sec_user_id, "success": clicked}
