"""Tests for Douyin API request construction."""

from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse

import pytest

from dy_cli.engines.api_client import SEARCH_URL, VIDEO_SEARCH_URL, DouyinAPIClient
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
