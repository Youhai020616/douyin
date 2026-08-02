"""Tests for CLI commands (no network, help/version only)."""

import pytest
from click.testing import CliRunner

from dy_cli.commands import search
from dy_cli.main import cli

runner = CliRunner()


class TestCLI:
    def test_version(self):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "dy-cli" in result.output

    def test_help(self):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "抖音命令行工具" in result.output

    def test_all_commands_registered(self):
        result = runner.invoke(cli, ["--help"])
        commands = [
            "search", "trending", "download", "publish",
            "detail", "like", "favorite", "comment",
            "follow", "live", "analytics", "notifications",
            "me", "profile", "login", "logout", "status",
            "account", "config", "init", "comments",
        ]
        for cmd in commands:
            assert cmd in result.output, f"Command '{cmd}' not in help output"


class TestSubcommandHelp:
    """Every subcommand should respond to --help without error."""

    SUBCOMMANDS = [
        ["search", "--help"],
        ["trending", "--help"],
        ["download", "--help"],
        ["publish", "--help"],
        ["detail", "--help"],
        ["like", "--help"],
        ["favorite", "--help"],
        ["comment", "--help"],
        ["comments", "--help"],
        ["follow", "--help"],
        ["live", "--help"],
        ["live", "list", "--help"],
        ["live", "info", "--help"],
        ["live", "record", "--help"],
        ["analytics", "--help"],
        ["notifications", "--help"],
        ["me", "--help"],
        ["profile", "--help"],
        ["login", "--help"],
        ["logout", "--help"],
        ["status", "--help"],
        ["account", "--help"],
        ["account", "list", "--help"],
        ["config", "--help"],
        ["config", "show", "--help"],
        ["init", "--help"],
    ]

    def test_all_help(self):
        for args in self.SUBCOMMANDS:
            result = runner.invoke(cli, args)
            assert result.exit_code == 0, f"'{' '.join(args)}' failed: {result.output}"


class TestAliases:
    def test_s_alias(self):
        result = runner.invoke(cli, ["s", "--help"])
        assert "搜索" in result.output

    def test_dl_alias(self):
        result = runner.invoke(cli, ["dl", "--help"])
        assert "下载" in result.output

    def test_t_alias(self):
        result = runner.invoke(cli, ["t", "--help"])
        assert "热榜" in result.output

    def test_pub_alias(self):
        result = runner.invoke(cli, ["pub", "--help"])
        assert "发布" in result.output

    def test_read_alias(self):
        result = runner.invoke(cli, ["read", "--help"])
        assert "详情" in result.output

    def test_r_alias(self):
        result = runner.invoke(cli, ["r", "--help"])
        assert "详情" in result.output

    def test_fav_alias(self):
        result = runner.invoke(cli, ["fav", "--help"])
        assert "收藏" in result.output

    def test_cfg_alias(self):
        result = runner.invoke(cli, ["cfg", "--help"])
        assert "配置" in result.output

    def test_acc_alias(self):
        result = runner.invoke(cli, ["acc", "--help"])
        assert "账号" in result.output


class TestDetailComments:
    def test_comments_fall_back_to_logged_in_playwright_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        aweme_id = "1234567890123456789"

        class FakeAPIClient:
            def get_video_detail(self, requested_aweme_id: str) -> dict[str, str]:
                assert requested_aweme_id == aweme_id
                return {"aweme_id": requested_aweme_id}

            def close(self) -> None:
                return None

        class FakePlaywrightClient:
            def __init__(self, account: str | None, headless: bool) -> None:
                assert account == "test-account"
                assert headless is True

            def get_comments(self, requested_aweme_id: str, count: int) -> list[dict[str, str]]:
                assert requested_aweme_id == aweme_id
                assert count == 3
                return [{"text": "fallback comment"}]

        monkeypatch.setattr(search.DouyinAPIClient, "from_config", lambda _account: FakeAPIClient())
        monkeypatch.setattr(search, "PlaywrightClient", FakePlaywrightClient)
        monkeypatch.setattr(search, "print_video_detail", lambda _detail: None)
        monkeypatch.setattr(search, "warning", lambda _message: None)

        printed: list[list[dict[str, str]]] = []
        monkeypatch.setattr(search, "print_comments", lambda comments: printed.append(comments))

        search.detail.callback(aweme_id, True, 3, "test-account", False)

        assert printed == [[{"text": "fallback comment"}]]
