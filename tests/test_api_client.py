"""Tests for Douyin API request construction."""

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import pytest

from dy_cli.engines.api_client import LIVE_FEED_URL, SEARCH_URL, VIDEO_SEARCH_URL, DouyinAPIClient
from dy_cli.utils.signature import build_request_url


@dataclass
class CapturedSearch:
    url: str = ""
    params: dict[str, str] = field(default_factory=dict)


SearchFixture = tuple[DouyinAPIClient, CapturedSearch]


@pytest.fixture
def captured_search(monkeypatch: pytest.MonkeyPatch) -> SearchFixture:
    client = DouyinAPIClient()
    captured = CapturedSearch()

    def fake_get(url: str, params: dict[str, str] | None = None, **_kwargs: object) -> dict[str, object]:
        assert params is not None
        captured.url = url
        captured.params = params
        return {"status_code": 0, "data": []}

    monkeypatch.setattr(client, "_get", fake_get)
    return client, captured


class TestSearchRequest:
    def test_unfiltered_general_search_uses_current_endpoint(self, captured_search: SearchFixture) -> None:
        client, captured = captured_search

        _ = client.search("AI")

        params = captured.params
        assert captured.url == SEARCH_URL
        assert params["search_channel"] == "aweme_general"
        assert params["is_filter_search"] == "0"
        assert params["need_filter_settings"] == "1"
        assert params["search_source"] == "normal_search"
        assert "filter_selected" not in params
        assert "sort_type" not in params
        assert "publish_time" not in params
        assert "filter_duration" not in params

    def test_pagination_omits_filter_settings(self, captured_search: SearchFixture) -> None:
        client, captured = captured_search

        _ = client.search("AI", offset=20)

        assert captured.params["need_filter_settings"] == "0"

    def test_general_filters_use_filter_selected(self, captured_search: SearchFixture) -> None:
        client, captured = captured_search

        _ = client.search("AI", sort_type=2, publish_time=7)

        params = captured.params
        expected_filter = '{"sort_type":"2","publish_time":"7"}'
        assert params["is_filter_search"] == "1"
        assert params["search_source"] == "tab_search"
        assert params["filter_selected"] == expected_filter

        request_url = build_request_url(captured.url, params)
        assert parse_qs(urlparse(request_url).query)["filter_selected"] == [expected_filter]
        assert "sort_type" not in params
        assert "publish_time" not in params

    @pytest.mark.parametrize(
        ("filter_duration", "expected_range"),
        [
            (1, "0-1"),
            (2, "1-5"),
            (3, "5-10000"),
        ],
    )
    def test_general_duration_uses_web_range(
        self,
        captured_search: SearchFixture,
        filter_duration: int,
        expected_range: str,
    ) -> None:
        client, captured = captured_search

        _ = client.search("AI", filter_duration=filter_duration)

        assert captured.params["filter_selected"] == (
            f'{{"sort_type":"0","publish_time":"0","filter_duration":"{expected_range}"}}'
        )
        assert "filter_duration" not in captured.params

    def test_atlas_uses_general_content_filter(self, captured_search: SearchFixture) -> None:
        client, captured = captured_search

        _ = client.search("AI", search_type="atlas")

        assert captured.url == SEARCH_URL
        assert captured.params["search_channel"] == "aweme_general"
        assert captured.params["search_source"] == "tab_search"
        assert captured.params["filter_selected"] == (
            '{"sort_type":"0","publish_time":"0","content_type":"2"}'
        )

    def test_unfiltered_video_search_uses_item_endpoint(self, captured_search: SearchFixture) -> None:
        client, captured = captured_search

        _ = client.search("AI", search_type="video")

        params = captured.params
        assert captured.url == VIDEO_SEARCH_URL
        assert params["search_channel"] == "aweme_video_web"
        assert params["is_filter_search"] == "0"
        assert "filter_selected" not in params
        assert "sort_type" not in params
        assert "publish_time" not in params
        assert "filter_duration" not in params

    def test_video_filters_remain_top_level(self, captured_search: SearchFixture) -> None:
        client, captured = captured_search

        _ = client.search("AI", search_type="video", sort_type=2, publish_time=7, filter_duration=3)

        params = captured.params
        assert captured.url == VIDEO_SEARCH_URL
        assert params["is_filter_search"] == "1"
        assert params["search_source"] == "tab_search"
        assert params["sort_type"] == "2"
        assert params["publish_time"] == "7"
        assert params["filter_duration"] == "5-10000"
        assert "filter_selected" not in params

    def test_invalid_duration_is_rejected(self, captured_search: SearchFixture) -> None:
        client, _captured = captured_search

        with pytest.raises(ValueError, match="filter_duration"):
            _ = client.search("AI", filter_duration=4)

    def test_user_search_still_uses_dedicated_method(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = DouyinAPIClient()
        captured: dict[str, str | int] = {}

        def fake_search_users(keyword: str, offset: int = 0, count: int = 10) -> dict[str, object]:
            captured.update(keyword=keyword, offset=offset, count=count)
            return {"status_code": 0, "user_list": []}

        monkeypatch.setattr(client, "search_users", fake_search_users)

        result = client.search("作者", search_type="user", offset=5, count=12)

        assert result == {"status_code": 0, "user_list": []}
        assert captured == {"keyword": "作者", "offset": 5, "count": 12}


class TestLiveRequest:
    def test_live_rooms_uses_home_feed_endpoint(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = DouyinAPIClient()
        captured: dict[str, object] = {}

        def fake_get(
            url: str,
            params: dict[str, str] | None = None,
            referer: str = "",
            **_kwargs: object,
        ) -> dict[str, object]:
            assert params is not None
            captured.update(url=url, params=params, referer=referer)
            return {"status_code": 0, "data": [{"web_rid": "123456", "data": {"title": "直播间"}}]}

        monkeypatch.setattr(client, "_get", fake_get)

        rooms = client.get_live_rooms(count=8)

        assert captured["url"] == LIVE_FEED_URL
        assert captured["referer"] == "https://live.douyin.com/"
        params = captured["params"]
        assert isinstance(params, dict)
        assert params["app_name"] == "douyin_web"
        assert params["device_platform"] == "web"
        assert params["custom_count"] == "8"
        assert params["action"] == "load_more"
        assert params["source_key"] == "web_homepage_hot_web_live_card"
        assert rooms == [{"web_rid": "123456", "data": {"title": "直播间"}}]


# ----------------------------------------------------------------------
# detail 端点：x-secsdk-web-signature + cookie jar 行为（PR #16）
# ----------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: dict[str, object] | None = None, headers: dict[str, str] | None = None) -> None:
        self._payload = payload or {}
        self.headers = headers or {}
        self.content = b"x"
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _offline_client(monkeypatch: pytest.MonkeyPatch, cookie: str = "", registered_ttwid: str = "") -> DouyinAPIClient:
    """构造不触网的 client：模拟 ttwid 注册接口把 cookie 下发在 .bytedance.com。"""
    import httpx

    def fake_post(self: httpx.Client, *_args: object, **_kwargs: object) -> _FakeResponse:
        if registered_ttwid:
            self.cookies.set("ttwid", registered_ttwid, domain=".bytedance.com")
        return _FakeResponse()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    return DouyinAPIClient(cookie=cookie)


class TestCookieJar:
    def test_parse_cookie_string_handles_equals_in_value_and_whitespace(self) -> None:
        from dy_cli.engines.api_client import _parse_cookie_string

        parsed = _parse_cookie_string(" a=1;  b=x==y ; ;broken; c= ")
        assert parsed == {"a": "1", "b": "x==y", "c": ""}

    def test_user_cookie_is_loaded_into_jar_and_sent_to_douyin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _offline_client(monkeypatch, cookie="sessionid=abc; UIFID=u123")

        req = client.client.build_request("GET", "https://www.douyin.com/aweme/v1/web/aweme/detail/")
        sent = req.headers.get("cookie") or ""

        assert "sessionid=abc" in sent
        assert "UIFID=u123" in sent

    def test_registered_ttwid_is_rehomed_to_douyin_domain(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _offline_client(monkeypatch, registered_ttwid="reg-ttwid")

        assert client._cookie("ttwid") == "reg-ttwid"
        req = client.client.build_request("GET", "https://www.douyin.com/aweme/v1/web/aweme/detail/")
        assert "ttwid=reg-ttwid" in (req.headers.get("cookie") or "")

    def test_user_ttwid_overrides_registered_ttwid(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _offline_client(monkeypatch, cookie="ttwid=user-ttwid", registered_ttwid="reg-ttwid")

        assert client._cookie("ttwid") == "user-ttwid"

    def test_get_and_post_do_not_set_explicit_cookie_header(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _offline_client(monkeypatch, cookie="sessionid=abc")
        seen: list[dict[str, str]] = []

        def fake_request(_method: str, _url: str, **kwargs: object) -> _FakeResponse:
            headers = kwargs.get("headers")
            assert isinstance(headers, dict)
            seen.append(headers)
            return _FakeResponse({"status_code": 0})

        monkeypatch.setattr(client, "_request_with_retry", fake_request)
        monkeypatch.setattr("dy_cli.engines.api_client.sign_url", lambda url: url)

        _ = client._get("https://www.douyin.com/x", params={"a": "1"})
        _ = client._post("https://www.douyin.com/y", data={"a": "1"})

        assert len(seen) == 2
        assert all("Cookie" not in h and "cookie" not in h for h in seen)


class TestSecsdkSignature:
    def test_ensure_secsdk_cookies_creates_csrf_once_and_respects_user_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client = _offline_client(monkeypatch)
        client._ensure_secsdk_cookies()
        first = client._cookie("passport_csrf_token")
        client._ensure_secsdk_cookies()
        assert first and client._cookie("passport_csrf_token") == first

        user_client = _offline_client(monkeypatch, cookie="passport_csrf_token=from-user")
        user_client._ensure_secsdk_cookies()
        assert user_client._cookie("passport_csrf_token") == "from-user"

    def test_get_uifid_prefers_cookie_without_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _offline_client(monkeypatch, cookie="UIFID_TEMP=from-cookie")

        def boom(*_a: object, **_k: object) -> _FakeResponse:
            raise AssertionError("should not hit network when uifid cookie exists")

        monkeypatch.setattr(client, "_request_with_retry", boom)
        assert client._get_uifid() == "from-cookie"

    def test_get_uifid_falls_back_to_trace_header_and_caches(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _offline_client(monkeypatch)
        calls: list[str] = []

        def fake_request(method: str, url: str, **_kwargs: object) -> _FakeResponse:
            calls.append(url)
            return _FakeResponse(headers={"x-tt-trace-host": "trace-uifid"})

        monkeypatch.setattr(client, "_request_with_retry", fake_request)

        assert client._get_uifid() == "trace-uifid"
        assert client._get_uifid() == "trace-uifid"
        assert calls == ["https://www.douyin.com/"]

    def test_secsdk_sign_is_deterministic_and_matches_algorithm(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import hashlib
        from urllib.parse import urlencode

        client = _offline_client(monkeypatch)
        monkeypatch.setattr(client, "_get_uifid", lambda: "UIFID-X")
        monkeypatch.setattr("dy_cli.engines.api_client.time.time", lambda: 1_700_000_000)

        signed = client._secsdk_sign({"aweme_id": "123", "aid": 6383})

        query = {"aweme_id": "123", "aid": 6383, "uifid": "UIFID-X", "timestamp": "1700000000"}
        expected = hashlib.md5(
            f"UIFID-X_1700000000_{DouyinAPIClient._SEC_SALT}_{urlencode(query)}".encode()
        ).hexdigest()
        assert signed == {**query, "x-secsdk-web-signature": expected}

    def test_get_skips_xbogus_when_sign_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        client = _offline_client(monkeypatch)
        sign_calls: list[str] = []
        urls: list[str] = []

        def fake_sign(url: str) -> str:
            sign_calls.append(url)
            return url + "&X-Bogus=zzz"

        monkeypatch.setattr("dy_cli.engines.api_client.sign_url", fake_sign)

        def fake_request(_method: str, url: str, **_kwargs: object) -> _FakeResponse:
            urls.append(url)
            return _FakeResponse({"status_code": 0})

        monkeypatch.setattr(client, "_request_with_retry", fake_request)

        _ = client._get("https://www.douyin.com/a", params={"k": "v"}, sign=False)
        _ = client._get("https://www.douyin.com/b", params={"k": "v"})

        assert sign_calls == ["https://www.douyin.com/b?k=v"]
        assert urls == ["https://www.douyin.com/a?k=v", "https://www.douyin.com/b?k=v&X-Bogus=zzz"]

    def test_video_detail_uses_minimal_signed_query_without_xbogus(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from dy_cli.engines.api_client import VIDEO_DETAIL_URL

        client = _offline_client(monkeypatch, cookie="UIFID=u1")
        captured: dict[str, object] = {}

        def fake_get(url: str, params: dict[str, object] | None = None, **kwargs: object) -> dict[str, object]:
            captured.update(url=url, params=params, kwargs=kwargs)
            return {"status_code": 0, "aweme_detail": {"aweme_id": "123"}}

        monkeypatch.setattr(client, "_get", fake_get)

        detail = client.get_video_detail("123")

        assert detail == {"aweme_id": "123"}
        assert captured["url"] == VIDEO_DETAIL_URL
        kwargs = captured["kwargs"]
        assert isinstance(kwargs, dict) and kwargs.get("sign") is False
        params = captured["params"]
        assert isinstance(params, dict)
        assert set(params) == {"aweme_id", "aid", "uifid", "timestamp", "x-secsdk-web-signature"}
        assert params["aweme_id"] == "123"
        assert params["aid"] == 6383
        assert params["uifid"] == "u1"
        assert "msToken" not in params and "device_platform" not in params
        assert client._cookie("passport_csrf_token")
