"""下载画质选择：bit_rate 解析、排序、选择与回退。"""
from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from dy_cli.engines.api_client import DouyinAPIClient
from dy_cli.main import cli

runner = CliRunner()


def _br(gear: str, bit_rate: int, w: int, h: int, h265: int = 0, url: str | None = None) -> dict:
    return {
        "gear_name": gear,
        "bit_rate": bit_rate,
        "is_h265": h265,
        "play_addr": {"width": w, "height": h, "url_list": [f"https://x/playwm/{url or gear}"]},
    }


# 故意乱序，且包含无 3-4 位数字的 gear（4K）与同分辨率多码率
VIDEO_DETAIL = {
    "desc": "demo",
    "author": {"nickname": "tester"},
    "video": {
        "play_addr": {"width": 1080, "height": 1920, "url_list": ["https://x/playwm/default"]},
        "bit_rate": [
            _br("720_3_1", 552_844, 720, 1280, h265=1),
            _br("normal_540_0", 1_992_914, 576, 1024),
            _br("adapt_lowest_4_1", 5_330_177, 2160, 3840, h265=1),
            _br("normal_720_0", 2_187_454, 720, 1280),
            _br("normal_1080_0", 3_107_362, 1080, 1920),
            _br("low_720_0", 2_005_151, 720, 1280),
        ],
    },
    "music": {"play_url": {"url_list": ["https://x/music.mp3"]}},
}

IMAGE_DETAIL = {
    "desc": "pics",
    "author": {"nickname": "tester"},
    "video": {},
    "images": [{"url_list": ["https://x/a.jpg"]}, {"url_list": ["https://x/b.jpg"]}],
    "music": {"play_url": "https://x/music.mp3"},
}

NO_BITRATE_DETAIL = {
    "desc": "old",
    "author": {"nickname": "tester"},
    "video": {"play_addr": {"url_list": ["https://x/playwm/only"]}},
}


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> DouyinAPIClient:
    c = DouyinAPIClient()
    c._detail = VIDEO_DETAIL  # type: ignore[attr-defined]
    monkeypatch.setattr(c, "get_video_detail", lambda _id: c._detail)  # type: ignore[attr-defined]
    return c


class TestParseAndSort:
    def test_sorted_by_resolution_then_bitrate(self, client: DouyinAPIClient):
        labels = [q["label"] for q in client.get_download_url("1")["available_qualities"]]
        assert labels == ["2160p", "1080p", "720p", "720p", "720p", "540p"]
        gears = [q["gear_name"] for q in client.get_download_url("1")["available_qualities"]]
        # 同为 720p 时按码率降序
        assert gears[2:5] == ["normal_720_0", "low_720_0", "720_3_1"]

    def test_resolution_from_gear_name_over_dimensions(self, client: DouyinAPIClient):
        q = client.get_download_url("1", quality="540")["quality"]
        assert q["label"] == "540p" and q["width"] == 576  # gear 说 540，实际宽 576

    def test_resolution_from_dimensions_when_gear_has_no_number(self, client: DouyinAPIClient):
        q = client.get_download_url("1", quality="2160")["quality"]
        assert q["gear_name"] == "adapt_lowest_4_1" and q["codec"] == "h265"

    def test_watermark_replaced(self, client: DouyinAPIClient):
        assert "playwm" not in client.get_download_url("1", quality="720")["video_url"]


class TestSelect:
    def test_auto_keeps_platform_default_url(self, client: DouyinAPIClient):
        r = client.get_download_url("1")
        assert r["video_url"] == "https://x/play/default"
        assert r["quality"] is None
        assert len(r["available_qualities"]) == 6  # 仍列出全部可选

    def test_best_and_worst(self, client: DouyinAPIClient):
        assert client.get_download_url("1", quality="best")["quality"]["label"] == "2160p"
        assert client.get_download_url("1", quality="worst")["quality"]["gear_name"] == "normal_540_0"

    def test_specific_resolution_picks_highest_bitrate(self, client: DouyinAPIClient):
        r = client.get_download_url("1", quality="720")
        assert r["quality"]["gear_name"] == "normal_720_0"
        assert r["video_url"].endswith("/normal_720_0")

    def test_missing_resolution_raises_with_available_list(self, client: DouyinAPIClient):
        with pytest.raises(ValueError, match=r"1440p 不可用.*2160p, 1080p, 720p, 540p"):
            client.get_download_url("1", quality="1440")

    def test_invalid_choice_rejected(self, client: DouyinAPIClient):
        with pytest.raises(ValueError, match="无效画质"):
            client.get_download_url("1", quality="4k")


class TestFallbacks:
    def test_image_post_unaffected_by_quality(self, client: DouyinAPIClient):
        client._detail = IMAGE_DETAIL  # type: ignore[attr-defined]
        r = client.get_download_url("1", quality="720")
        assert r["video_url"] is None
        assert r["images"] == ["https://x/a.jpg", "https://x/b.jpg"]
        assert r["music_url"] == "https://x/music.mp3"
        assert r["quality"] is None and r["available_qualities"] == []

    def test_no_bitrate_falls_back_to_default_and_keeps_music(self, client: DouyinAPIClient):
        client._detail = NO_BITRATE_DETAIL  # type: ignore[attr-defined]
        r = client.get_download_url("1", quality="1080")
        assert r["video_url"] == "https://x/play/only"
        assert r["quality"] is None


class TestCLI:
    def test_user_with_list_quality_rejected_before_network(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(DouyinAPIClient, "from_config", lambda *_: pytest.fail("不应创建客户端"))
        result = runner.invoke(cli, ["download", "X", "--user", "--list-quality", "--json-output"])
        assert result.exit_code == 1
        env = json.loads(result.stdout)
        assert env["error"]["code"] == "invalid_argument"

    def test_quality_choices_in_help(self):
        result = runner.invoke(cli, ["download", "--help"])
        assert result.exit_code == 0
        for c in DouyinAPIClient.QUALITY_CHOICES:
            assert c in result.output
