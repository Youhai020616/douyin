"""Tests for dy_cli.utils.signature"""
from dy_cli.utils.signature import (
    build_request_url,
    generate_device_id,
    get_base_params,
    get_headers,
    get_ms_token,
)


class TestDeviceId:
    def test_length(self):
        did = generate_device_id()
        assert len(did) == 19
        assert did.isdigit()

    def test_unique(self):
        a = generate_device_id()
        b = generate_device_id()
        assert a != b


class TestMsToken:
    def test_default_length(self):
        token = get_ms_token()
        assert len(token) == 128

    def test_custom_length(self):
        token = get_ms_token(64)
        assert len(token) == 64

    def test_alphanumeric(self):
        token = get_ms_token()
        assert token.isalnum()


class TestBaseParams:
    def test_required_keys(self):
        params = get_base_params()
        assert "device_platform" in params
        assert "aid" in params
        assert "msToken" in params
        assert params["device_platform"] == "webapp"

    def test_web_client_version_matches_search_request(self):
        params = get_base_params()
        assert params["version_code"] == "170400"
        assert params["version_name"] == "17.4.0"
        assert params["update_version_code"] == "170400"

    def test_mstoken_unique(self):
        p1 = get_base_params()
        p2 = get_base_params()
        assert p1["msToken"] != p2["msToken"]


class TestHeaders:
    def test_default_headers(self):
        h = get_headers()
        assert "User-Agent" in h
        assert "Referer" in h
        assert "Cookie" not in h

    def test_with_cookie(self):
        h = get_headers(cookie="session=abc")
        assert h["Cookie"] == "session=abc"

    def test_custom_referer(self):
        h = get_headers(referer="https://test.com/")
        assert h["Referer"] == "https://test.com/"


class TestBuildUrl:
    def test_basic(self):
        url = build_request_url("https://api.example.com/v1/search", {"q": "test"})
        assert "q=test" in url
        assert url.startswith("https://api.example.com/v1/search?")

    def test_multiple_params(self):
        url = build_request_url("https://a.com/b", {"a": "1", "b": "2"})
        assert "a=1" in url
        assert "b=2" in url
