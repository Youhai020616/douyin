"""
dy config — 配置管理命令。
"""
from __future__ import annotations

import click

from dy_cli.utils import config
from dy_cli.utils.output import DyCliError, console, info, print_json, success


@click.group("config", help="配置管理")
def config_group():
    pass


@config_group.command("show", help="显示当前配置")
def show():
    """显示所有配置。"""
    cfg = config.load_config()
    print_json(cfg)
    info(f"配置文件: {config.CONFIG_FILE}")


@config_group.command("set", help="设置配置项")
@click.argument("key")
@click.argument("value")
def set_config(key, value):
    """
    设置配置项。

    KEY 格式: api.proxy, playwright.headless, default.engine

    示例:
        dy config set api.proxy http://127.0.0.1:7897
        dy config set api.timeout 60
        dy config set playwright.headless true
        dy config set default.engine api
        dy config set default.download_dir ~/Videos/douyin
    """
    # Type inference
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)

    config.set_value(key, value)
    success(f"已设置 {key} = {value}")


@config_group.command("get", help="获取配置项")
@click.argument("key")
def get_config(key):
    """获取单个配置项。"""
    value = config.get(key)
    if value is None:
        raise DyCliError("not_found", f"配置项不存在: {key}")
    console.print(f"{key} = {value}")


@config_group.command("reset", help="重置为默认配置")
@click.confirmation_option(prompt="确认重置所有配置?")
def reset():
    """重置为默认配置。"""
    config.save_config(config.DEFAULT_CONFIG)
    success("配置已重置为默认值")
