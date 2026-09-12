"""stdout/stderr 输出契约测试：stdout 只承载数据，错误在 --json-output 下走信封。"""
from __future__ import annotations

import json
import os

import pytest
from click.testing import CliRunner

from dy_cli.main import cli
from dy_cli.utils import config
from dy_cli.utils.envelope import ERROR_CODES

runner = CliRunner()


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """把 ~/.dy 指向临时目录，保证无 Cookie、无缓存。"""
    cfg_dir = str(tmp_path / ".dy")
    monkeypatch.setattr(config, "CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(config, "CONFIG_FILE", os.path.join(cfg_dir, "config.json"))
    monkeypatch.setattr(config, "COOKIES_DIR", os.path.join(cfg_dir, "cookies"))
    return cfg_dir


def _parse_stdout(result) -> dict:
    """stdout 必须是且仅是一个 JSON 文档。"""
    return json.loads(result.stdout)


class TestErrorEnvelope:
    def test_json_mode_emits_error_envelope_on_stdout(self):
        # publish 参数校验在任何网络/登录之前触发
        result = runner.invoke(cli, ["publish", "-t", "x", "--json-output"])
        assert result.exit_code == 1
        env = _parse_stdout(result)
        assert env["ok"] is False
        assert env["schema_version"] == "1"
        assert env["error"]["code"] == "invalid_argument"
        assert env["error"]["code"] in ERROR_CODES
        assert "--video" in env["error"]["message"]

    def test_tty_mode_prints_to_stderr_only(self):
        result = runner.invoke(cli, ["publish", "-t", "x"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "✗" in result.stderr
        assert "--video" in result.stderr

    def test_config_get_missing_key(self, isolated_home):
        result = runner.invoke(cli, ["config", "get", "no.such.key"])
        assert result.exit_code == 1
        assert result.stdout == ""
        assert "配置项不存在" in result.stderr


class TestSuccessEnvelope:
    def test_publish_dry_run_json(self, tmp_path):
        video = tmp_path / "v.mp4"
        video.write_bytes(b"\x00")
        result = runner.invoke(
            cli,
            ["publish", "-t", "标题", "-c", "描述", "-v", str(video), "--tags", "AI", "--dry-run", "--json-output"],
        )
        assert result.exit_code == 0, result.output
        env = _parse_stdout(result)
        assert env["ok"] is True
        assert env["data"]["dry_run"] is True
        assert env["data"]["title"] == "标题"
        assert env["data"]["tags"] == ["AI"]

    def test_status_json_without_cookie(self, isolated_home):
        result = runner.invoke(cli, ["status", "--json-output"])
        assert result.exit_code == 0, result.output
        env = _parse_stdout(result)
        assert env["ok"] is True
        assert env["data"]["authenticated"] is False
        assert env["data"]["reason"] == "no_cookie"
        assert env["data"]["account"] == "default"

    def test_logout_json_without_cookie(self, isolated_home):
        result = runner.invoke(cli, ["logout", "--json-output"])
        assert result.exit_code == 0, result.output
        env = _parse_stdout(result)
        assert env["data"]["logged_out"] is False

    def test_account_list_json_empty(self, isolated_home):
        result = runner.invoke(cli, ["account", "list", "--json-output"])
        assert result.exit_code == 0, result.output
        env = _parse_stdout(result)
        assert env["data"] == []


class TestStderrForProgress:
    def test_info_and_success_go_to_stderr(self, isolated_home):
        # logout 在 TTY 模式只打印状态提示，stdout 应为空
        result = runner.invoke(cli, ["logout"])
        assert result.exit_code == 0
        assert result.stdout == ""
        assert "未找到登录凭据" in result.stderr


class TestJsonOutputCoverage:
    """账号态 / 变更类命令也应提供 --json-output。"""

    @pytest.mark.parametrize(
        "args",
        [
            ["status"],
            ["login"],
            ["logout"],
            ["publish"],
            ["like"],
            ["favorite"],
            ["comment"],
            ["follow"],
            ["me"],
            ["account", "list"],
        ],
    )
    def test_has_json_output_flag(self, args):
        result = runner.invoke(cli, [*args, "--help"])
        assert result.exit_code == 0
        assert "--json-output" in result.output, f"{' '.join(args)} lacks --json-output"
