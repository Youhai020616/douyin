"""
dy — 抖音命令行工具主入口。

Usage:
    dy search "关键词"                     搜索视频
    dy trending                            抖音热榜
    dy download URL                        无水印下载
    dy publish -t 标题 -c 描述 -v 视频     发布视频
    dy detail AWEME_ID                     视频详情
    dy comments AWEME_ID                   查看评论
    dy like AWEME_ID                       点赞
    dy comment AWEME_ID -c "内容"          评论
    dy favorite AWEME_ID                   收藏
    dy follow SEC_USER_ID                  关注
    dy live list                           列出推荐直播间
    dy live info ROOM_ID                   直播信息
    dy live record ROOM_ID                 录制直播
    dy analytics                           数据看板
    dy notifications                       通知消息
    dy me                                  我的信息
    dy profile SEC_USER_ID                 用户主页
    dy login                               登录
    dy logout                              退出登录
    dy status                              登录状态
    dy account list|add|remove|default     多账号管理
    dy config show|set|get|reset           配置管理
"""
from __future__ import annotations

import click

from dy_cli import __version__

BANNER = rf"""
  ╔═══════════════════════════════╗
  ║   🎬 dy-cli v{__version__}         ║
  ║   抖音命令行工具              ║
  ╚═══════════════════════════════╝
"""


class AliasGroup(click.Group):
    """支持命令别名的 Click Group。"""

    ALIASES = {
        "pub": "publish",
        "s": "search",
        "dl": "download",
        "t": "trending",
        "r": "detail",
        "read": "detail",
        "fav": "favorite",
        "noti": "notifications",
        "stat": "status",
        "acc": "account",
        "cfg": "config",
    }

    def get_command(self, ctx, cmd_name):
        resolved = self.ALIASES.get(cmd_name, cmd_name)
        return super().get_command(ctx, resolved)

    def format_help(self, ctx, formatter):
        formatter.write(BANNER)
        super().format_help(ctx, formatter)


@click.group(cls=AliasGroup, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="dy-cli")
@click.pass_context
def cli(ctx):
    """🎬 抖音命令行工具 — 搜索、下载、发布、互动、热榜、直播、数据分析"""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ------------------------------------------------------------------
# 注册所有命令
# ------------------------------------------------------------------

# 初始化
from dy_cli.commands.init import init

cli.add_command(init)

# 认证
from dy_cli.commands.auth import auth_status, login, logout

cli.add_command(login)
cli.add_command(logout)
cli.add_command(auth_status, "status")

# 搜索 & 详情
from dy_cli.commands.search import detail, search

cli.add_command(search)
cli.add_command(detail)

# 下载
from dy_cli.commands.download import download

cli.add_command(download)

# 发布
from dy_cli.commands.publish import publish

cli.add_command(publish)

# 互动
from dy_cli.commands.interact import comment, comments, favorite, follow, like

cli.add_command(like)
cli.add_command(favorite)
cli.add_command(comment)
cli.add_command(comments)
cli.add_command(follow)

# 热榜
from dy_cli.commands.trending import trending

cli.add_command(trending)

# 直播
from dy_cli.commands.live import live_group

cli.add_command(live_group, "live")

# 数据分析
from dy_cli.commands.analytics import analytics, notifications

cli.add_command(analytics)
cli.add_command(notifications)

# 用户
from dy_cli.commands.profile import me, profile

cli.add_command(me)
cli.add_command(profile)

# 账号管理
from dy_cli.commands.account import account_group

cli.add_command(account_group, "account")

# 配置管理
from dy_cli.commands.config_cmd import config_group

cli.add_command(config_group, "config")


def main():
    cli()


if __name__ == "__main__":
    main()
