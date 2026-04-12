"""
Douyin API Client — 逆向 API 采集客户端。

通过 httpx 调用抖音 Web 端接口，实现搜索、下载、评论、热榜等功能。
参考: JoeanAmier/TikTokDownloader, Evil0ctal/Douyin_TikTok_Download_API
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from collections.abc import Callable
from typing import Any

import httpx

logger = logging.getLogger(__name__)

from dy_cli.utils import config
from dy_cli.utils.signature import (
    build_request_url,
    get_base_params,
    get_headers,
    sign_url,
)

# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

DOUYIN_DOMAIN = "https://www.douyin.com"
API_DOMAIN = "https://www.douyin.com"

# API endpoints
SEARCH_URL = f"{API_DOMAIN}/aweme/v1/web/general/search/single/"
VIDEO_DETAIL_URL = f"{API_DOMAIN}/aweme/v1/web/aweme/detail/"
VIDEO_COMMENTS_URL = f"{API_DOMAIN}/aweme/v1/web/comment/list/"
USER_PROFILE_URL = f"{API_DOMAIN}/aweme/v1/web/user/profile/other/"
USER_POSTS_URL = f"{API_DOMAIN}/aweme/v1/web/aweme/post/"
TRENDING_URL = f"{API_DOMAIN}/aweme/v1/web/hot/search/list/"
USER_SEARCH_URL = f"{API_DOMAIN}/aweme/v1/web/discover/search/"
LIVE_INFO_URL = "https://live.douyin.com/webcast/room/web/enter/"
FEED_URL = f"{API_DOMAIN}/aweme/v1/web/tab/feed/"
SUGGEST_URL = f"{API_DOMAIN}/aweme/v1/web/api/suggest_words/"

# iesdouyin API (share API, more stable, less anti-crawl)
IESDOUYIN_DETAIL_URL = "https://www.iesdouyin.com/web/api/v2/aweme/iteminfo/"

# ttwid registration
TTWID_URL = "https://ttwid.bytedance.com/ttwid/union/register/"

# Share URL pattern
SHARE_URL_PATTERN = re.compile(r"https?://(?:www\.)?(?:douyin\.com|iesdouyin\.com)/(?:video|note|share/video)/(\d+)")
SHORT_URL_PATTERN = re.compile(r"https?://v\.douyin\.com/\w+/?")

REQUEST_TIMEOUT = 30

# 搜索通道映射: CLI search_type → 抖音 API search_channel
SEARCH_CHANNEL_MAP = {
    "general": "aweme_general",
    "video": "aweme_video_web",
    "atlas": "aweme_atlas",
}


class DouyinAPIError(Exception):
    """抖音 API 调用错误。"""


class DouyinAPIClient:
    """
    抖音 Web 端 API 客户端。

    通过逆向 Web 端接口实现数据采集。
    """

    def __init__(
        self,
        cookie: str = "",
        proxy: str = "",
        timeout: int = REQUEST_TIMEOUT,
    ):
        self.cookie: str = cookie
        self.proxy: str = proxy
        self.timeout: int = timeout
        self._client: httpx.Client | None = None
        self._last_request_time: float = 0.0
        self._request_delay: float = 1.0
        self._base_delay: float = 1.0
        self._verify_count: int = 0
        self._max_retries: int = 3

    # ------------------------------------------------------------------
    # HTTP client
    # ------------------------------------------------------------------

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            transport_kwargs: dict[str, Any] = {}
            if self.proxy:
                transport_kwargs["proxy"] = self.proxy
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                **transport_kwargs,
            )
            self._init_cookies()
        return self._client

    def _init_cookies(self) -> None:
        """获取 ttwid 等必要 cookie。"""
        if self._client is None:
            return
        try:
            _ = self._client.post(
                TTWID_URL,
                json={
                    "region": "cn",
                    "aid": 1768,
                    "needFid": False,
                    "service": "www.douyin.com",
                    "migrate_info": {"ticket": "", "source": "node"},
                    "cbUrlProtocol": "https",
                    "union": True,
                },
                headers={"Content-Type": "application/json"},
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Rate limiting & anti-detection
    # ------------------------------------------------------------------

    def _rate_limit_delay(self) -> None:
        """高斯抖动延迟，模拟人类浏览节奏。"""
        if self._request_delay <= 0:
            return
        elapsed = time.time() - self._last_request_time
        if elapsed < self._request_delay:
            jitter = max(0, random.gauss(0.3, 0.15))
            # 5% 概率增加长停顿（模拟阅读行为）
            if random.random() < 0.05:
                jitter += random.uniform(2.0, 5.0)
            sleep_time = self._request_delay - elapsed + jitter
            logger.debug("Rate-limit delay: %.2fs", sleep_time)
            time.sleep(sleep_time)

    def _handle_verify(self, _resp: httpx.Response) -> None:
        """验证码冷却：渐进式退避。"""
        self._verify_count += 1
        cooldown: float = min(30.0, 5.0 * (2 ** (self._verify_count - 1)))
        logger.warning("Verify triggered (count=%d), cooldown %.0fs", self._verify_count, cooldown)
        self._request_delay = max(self._request_delay, self._base_delay * 2)
        time.sleep(cooldown)

    def _request_with_retry(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """带重试和退避的请求。"""
        self._rate_limit_delay()
        last_exc: Exception | None = None
        last_resp: httpx.Response | None = None

        for attempt in range(self._max_retries):
            try:
                resp = self.client.request(method, url, **kwargs)
                self._last_request_time = time.time()

                # 重试: 429 / 5xx
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_resp = resp
                    wait: float = float(2**attempt) + random.uniform(0, 1)
                    logger.warning(
                        "HTTP %d, retry in %.1fs (%d/%d)", resp.status_code, wait, attempt + 1, self._max_retries
                    )
                    time.sleep(wait)
                    continue

                self._verify_count = 0
                return resp

            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_exc = exc
                wait: float = float(2**attempt) + random.uniform(0, 1)
                logger.warning("Network error: %s, retry in %.1fs (%d/%d)", exc, wait, attempt + 1, self._max_retries)
                time.sleep(wait)

        if last_exc:
            raise DouyinAPIError(f"请求失败 ({self._max_retries} 次重试后): {last_exc}") from last_exc
        raise DouyinAPIError(f"请求失败: HTTP {last_resp.status_code if last_resp else 'unknown'}")

    # ------------------------------------------------------------------
    # HTTP methods
    # ------------------------------------------------------------------

    def _get(self, url: str, params: dict[str, str] | None = None, **kwargs: Any) -> dict[str, Any]:
        """GET 请求，带签名、重试和反爬。"""
        headers = get_headers(cookie=self.cookie)

        # 构建完整 URL 并签名（添加 X-Bogus / a-bogus 参数）
        if params:
            full_url = build_request_url(url, params)
            signed_url = sign_url(full_url)
            # 签名后参数已包含在 URL 中，不再单独传 params
            resp = self._request_with_retry("GET", signed_url, headers=headers, **kwargs)
        else:
            resp = self._request_with_retry("GET", url, headers=headers, **kwargs)

        try:
            _ = resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise DouyinAPIError(f"HTTP {e.response.status_code}: {url}") from e

        if not resp.content:
            raise DouyinAPIError(f"空响应 (可能需要登录或签名): {url.split('/')[-2]}")

        try:
            data: dict[str, Any] = resp.json()  # type: ignore[assignment]
        except json.JSONDecodeError as e:
            raise DouyinAPIError(f"JSON 解析失败: {e}") from e

        # 检测 verify_check — 只记录，不重试（避免死循环）
        nil_info: dict[str, Any] = data.get("search_nil_info", {})  # type: ignore[assignment]
        if nil_info.get("search_nil_type") == "verify_check":
            self._verify_count += 1
            logger.warning("verify_check detected (count=%d)", self._verify_count)

        return data

    def _post(self, url: str, data: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        """POST 请求，带重试和反爬。"""
        headers = get_headers(cookie=self.cookie)
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        resp = self._request_with_retry("POST", url, data=data, headers=headers, **kwargs)

        try:
            _ = resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise DouyinAPIError(f"HTTP {e.response.status_code}: {url}") from e

        try:
            result: dict[str, Any] = resp.json()  # type: ignore[assignment]
            return result
        except json.JSONDecodeError as e:
            raise DouyinAPIError(f"JSON 解析失败: {e}") from e

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Cookie management
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, account: str | None = None) -> DouyinAPIClient:
        """从配置文件创建客户端。"""
        cfg = config.load_config()
        cookie_file = config.get_cookie_file(account)
        cookie = ""
        if os.path.exists(cookie_file):
            try:
                with open(cookie_file, encoding="utf-8") as f:
                    cookie_data = json.load(f)
                # Support playwright storage_state format
                if isinstance(cookie_data, dict) and "cookies" in cookie_data:
                    cookies: list[dict[str, str]] = cookie_data["cookies"]
                    cookie = "; ".join(f"{c['name']}={c['value']}" for c in cookies if "douyin" in c.get("domain", ""))
                elif isinstance(cookie_data, str):
                    cookie = cookie_data
            except Exception:
                pass

        proxy: str = cfg["api"].get("proxy", "")
        timeout: int = cfg["api"].get("timeout", REQUEST_TIMEOUT)
        return cls(cookie=cookie, proxy=proxy, timeout=int(timeout))

    # ------------------------------------------------------------------
    # URL parsing
    # ------------------------------------------------------------------

    def resolve_share_url(self, url: str) -> str:
        """从分享链接提取 aweme_id。"""
        # Direct URL
        match = SHARE_URL_PATTERN.search(url)
        if match:
            return match.group(1)

        # Short URL — follow redirect (don't auto-follow, check 302 location)
        if SHORT_URL_PATTERN.match(url):
            try:
                # Step 1: Don't follow redirects, get 302 Location header
                no_follow = httpx.Client(follow_redirects=False, timeout=self.timeout)
                resp = no_follow.get(url, headers=get_headers())
                no_follow.close()

                location = str(resp.headers.get("location", ""))
                match = SHARE_URL_PATTERN.search(location)
                if match:
                    return match.group(1)

                # Step 2: If redirected to homepage, try following with full client
                resp2 = self.client.get(url, headers=get_headers())
                final_url = str(resp2.url)
                match = SHARE_URL_PATTERN.search(final_url)
                if match:
                    return match.group(1)

                # Step 3: Search in response body for video ID pattern
                body = resp2.text[:50000]
                match = re.search(r"(?:video|aweme)[/_]?(?:id)?[=:/](\d{15,})", body)
                if match:
                    return match.group(1)

            except Exception:
                pass

        # Try extracting numbers that look like aweme_id from the URL itself
        match = re.search(r"/(\d{15,})", url)
        if match:
            return match.group(1)

        raise DouyinAPIError(f"无法从链接提取视频 ID: {url}")

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        keyword: str,
        sort_type: int = 0,
        publish_time: int = 0,
        filter_duration: int = 0,
        search_type: str = "general",
        offset: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """
        搜索抖音内容。

        Args:
            keyword: 搜索关键词
            sort_type: 0=综合, 1=最多点赞, 2=最新发布
            publish_time: 0=不限, 1=一天内, 7=一周内, 182=半年内
            filter_duration: 0=不限, 1=1分钟内, 2=1-5分钟, 3=5分钟以上
            search_type: general(综合), video(视频), atlas(图文), user(用户)
            offset: 偏移量
            count: 每页数量
        """
        # 用户搜索使用专用 endpoint
        if search_type == "user":
            return self.search_users(keyword, offset=offset, count=count)

        # 映射 search_channel
        search_channel = SEARCH_CHANNEL_MAP.get(search_type, "aweme_general")

        # 当使用了筛选条件时，is_filter_search 须为 "1"，否则服务端忽略筛选参数
        has_filter = sort_type != 0 or publish_time != 0 or filter_duration != 0
        is_filter_search = "1" if has_filter else "0"

        params = {
            **get_base_params(),
            "keyword": keyword,
            "search_channel": search_channel,
            "sort_type": str(sort_type),
            "publish_time": str(publish_time),
            "filter_duration": str(filter_duration),
            "offset": str(offset),
            "count": str(count),
            "search_source": "normal_search",
            "query_correct_type": "1",
            "is_filter_search": is_filter_search,
        }
        data = self._get(SEARCH_URL, params=params)

        if data.get("status_code") != 0:
            raise DouyinAPIError(f"搜索失败: {data.get('status_msg', 'unknown error')}")

        return data

    def search_users(
        self,
        keyword: str,
        offset: int = 0,
        count: int = 10,
    ) -> dict[str, Any]:
        """搜索用户（使用专用 endpoint）。"""
        params = {
            **get_base_params(),
            "keyword": keyword,
            "search_channel": "aweme_user_search",
            "offset": str(offset),
            "count": str(count),
            "search_source": "normal_search",
            "is_filter_search": "0",
        }
        data = self._get(USER_SEARCH_URL, params=params)

        if data.get("status_code") != 0:
            raise DouyinAPIError(f"用户搜索失败: {data.get('status_msg', 'unknown error')}")

        return data

    # ------------------------------------------------------------------
    # Video detail
    # ------------------------------------------------------------------

    def get_video_detail(self, aweme_id: str) -> dict[str, Any]:
        """获取视频详情（自动 fallback 到 share API）。"""
        # Primary: Web API
        try:
            params = {
                **get_base_params(),
                "aweme_id": aweme_id,
            }
            data = self._get(VIDEO_DETAIL_URL, params=params)
            if data.get("status_code") == 0:
                aweme_detail = data.get("aweme_detail", {})
                if aweme_detail:
                    return aweme_detail
        except DouyinAPIError:
            pass

        # Fallback: iesdouyin share API (更稳定，无签名要求)
        return self._get_detail_via_share(aweme_id)

    def _get_detail_via_share(self, aweme_id: str) -> dict[str, Any]:
        """通过 iesdouyin share 页面 SSR 数据获取详情。"""
        headers = get_headers()
        headers["User-Agent"] = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )
        try:
            resp = self.client.get(
                f"https://www.iesdouyin.com/share/video/{aweme_id}/",
                headers=headers,
            )
            _ = resp.raise_for_status()
            text = resp.text

            # Extract _ROUTER_DATA from SSR page
            idx = text.find("_ROUTER_DATA")
            if idx < 0:
                raise DouyinAPIError(f"无法从分享页提取数据: {aweme_id}")

            start = text.find("{", idx)
            if start < 0:
                raise DouyinAPIError(f"无法解析分享页数据: {aweme_id}")

            depth = 0
            end = start
            for i, c in enumerate(text[start : start + 50000]):
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = start + i + 1
                        break

            raw = text[start:end].replace("\\u002F", "/")
            data: dict[str, Any] = json.loads(raw)  # type: ignore[assignment]
            loader: dict[str, Any] = data.get("loaderData", {})  # type: ignore[assignment]

            # Find the video page data
            for _key, val in loader.items():
                if isinstance(val, dict):
                    video_res: dict[str, Any] = val.get("videoInfoRes", {})
                    if isinstance(video_res, dict):
                        items: list[Any] = video_res.get("item_list", [])
                        if items:
                            return items[0]  # type: ignore[no-any-return]

            # item_list empty = overseas IP blocked
            raise DouyinAPIError(
                f"视频数据为空 (可能需要国内 IP/代理): {aweme_id}\n"
                "  提示: dy config set api.proxy http://your-proxy:port"
            )

        except httpx.RequestError as e:
            raise DouyinAPIError(f"请求失败: {e}") from e
        except json.JSONDecodeError as e:
            raise DouyinAPIError(f"JSON 解析失败: {e}") from e

    # ------------------------------------------------------------------
    # Comments
    # ------------------------------------------------------------------

    def get_comments(
        self,
        aweme_id: str,
        cursor: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """获取视频评论列表。"""
        params = {
            **get_base_params(),
            "aweme_id": aweme_id,
            "cursor": str(cursor),
            "count": str(count),
            "item_type": "0",
        }
        data = self._get(VIDEO_COMMENTS_URL, params=params)

        if data.get("status_code") != 0:
            raise DouyinAPIError(f"获取评论失败: {data.get('status_msg', 'unknown error')}")

        return data

    # ------------------------------------------------------------------
    # User
    # ------------------------------------------------------------------

    def get_user_profile(self, sec_user_id: str) -> dict[str, Any]:
        """获取用户资料。"""
        params = {
            **get_base_params(),
            "sec_user_id": sec_user_id,
        }
        data = self._get(USER_PROFILE_URL, params=params)

        if data.get("status_code") != 0:
            raise DouyinAPIError(f"获取用户资料失败: {data.get('status_msg', 'unknown error')}")

        return data.get("user", data)

    def get_user_posts(
        self,
        sec_user_id: str,
        max_cursor: int = 0,
        count: int = 20,
    ) -> dict[str, Any]:
        """获取用户作品列表。"""
        params = {
            **get_base_params(),
            "sec_user_id": sec_user_id,
            "max_cursor": str(max_cursor),
            "count": str(count),
        }
        data = self._get(USER_POSTS_URL, params=params)

        if data.get("status_code") != 0:
            raise DouyinAPIError(f"获取用户作品失败: {data.get('status_msg', 'unknown error')}")

        return data

    # ------------------------------------------------------------------
    # Trending
    # ------------------------------------------------------------------

    def get_trending(self) -> list[dict[str, Any]]:
        """获取抖音热榜。"""
        params = get_base_params()
        data = self._get(TRENDING_URL, params=params)

        if data.get("status_code") != 0:
            raise DouyinAPIError(f"获取热榜失败: {data.get('status_msg', 'unknown error')}")

        word_list = data.get("data", {}).get("word_list", [])
        return word_list

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def get_download_url(self, aweme_id: str) -> dict[str, Any]:
        """
        获取无水印下载链接。

        Returns:
            {
                "video_url": str | None,
                "music_url": str | None,
                "images": list[str] | None,
                "desc": str,
                "author": str,
            }
        """
        detail = self.get_video_detail(aweme_id)

        result: dict[str, Any] = {
            "video_url": None,
            "music_url": None,
            "images": None,
            "desc": detail.get("desc", ""),
            "author": detail.get("author", {}).get("nickname", ""),
            "aweme_id": aweme_id,
        }

        # Video
        video = detail.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        if url_list:
            # 取最后一个（通常是最高质量）
            result["video_url"] = url_list[-1].replace("playwm", "play")

        # Images (for image posts)
        images = detail.get("images", [])
        if images:
            image_urls = []
            for img in images:
                url_list = img.get("url_list", [])
                if url_list:
                    image_urls.append(url_list[-1])
            result["images"] = image_urls

        # Music
        music = detail.get("music", {})
        music_play = music.get("play_url", {})
        if isinstance(music_play, dict):
            music_urls = music_play.get("url_list", [])
            if music_urls:
                result["music_url"] = music_urls[0]
        elif isinstance(music_play, str):
            result["music_url"] = music_play

        return result

    def download_file(
        self,
        url: str,
        output_path: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> str:
        """
        下载文件到本地。

        Args:
            url: 下载链接
            output_path: 保存路径
            progress_callback: 进度回调 (downloaded, total)

        Returns:
            保存的文件路径
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        headers = get_headers()

        with self.client.stream("GET", url, headers=headers) as stream_resp:
            stream_resp.raise_for_status()
            total = int(stream_resp.headers.get("Content-Length", 0))
            downloaded = 0

            with open(output_path, "wb") as f:
                for chunk in stream_resp.iter_bytes(chunk_size=8192):
                    _ = f.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

        return output_path

    # ------------------------------------------------------------------
    # Live
    # ------------------------------------------------------------------

    def get_live_info(self, web_rid: str) -> dict[str, Any]:
        """
        获取直播间信息。

        Args:
            web_rid: 直播间 ID (URL 中的数字, 如 live.douyin.com/123456789)
        """
        params = {
            **get_base_params(),
            "aid": "6383",
            "app_name": "douyin_web",
            "live_id": "1",
            "device_platform": "web",
            "enter_from": "web_live",
            "web_rid": web_rid,
            "room_id_str": "",
            "enter_source": "",
        }
        data = self._get(LIVE_INFO_URL, params=params)

        if data.get("status_code") != 0:
            raise DouyinAPIError(f"获取直播信息失败: {data.get('status_msg', 'unknown error')}")

        room_data = data.get("data", {})
        rooms = room_data.get("data", []) if isinstance(room_data.get("data"), list) else []
        if rooms:
            return rooms[0]
        return room_data

    # ------------------------------------------------------------------
    # Feed
    # ------------------------------------------------------------------

    def get_feed(self, count: int = 10) -> list[dict[str, Any]]:
        """获取推荐 Feed。"""
        params = {
            **get_base_params(),
            "count": str(count),
        }
        data = self._get(FEED_URL, params=params)
        return data.get("aweme_list", [])
