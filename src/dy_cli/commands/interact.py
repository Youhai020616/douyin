"""
dy like / comment / favorite / follow — 互动命令 (Playwright)。
"""
from __future__ import annotations

import click

from dy_cli.engines.playwright_client import PlaywrightClient, PlaywrightError
from dy_cli.utils.index_cache import resolve_id
from dy_cli.utils.output import DyCliError, info, print_comments, print_json, success


def _resolve(id_str: str) -> str:
    try:
        return resolve_id(id_str)
    except ValueError as e:
        raise DyCliError("invalid_argument", str(e))


def _pw(account=None) -> PlaywrightClient:
    return PlaywrightClient(account=account, headless=True)


_EMOJI = {"like": "👍", "unlike": "👍", "favorite": "⭐", "unfavorite": "⭐",
          "comment": "💬", "follow": "👥", "unfollow": "👥"}


def _run_action(account, aweme_id: str, action: str, label: str, failure_hint: str, as_json: bool, **kwargs):
    """执行一次互动并统一处理结果输出。"""
    try:
        result = _pw(account).interact(aweme_id, action, **kwargs)
    except PlaywrightError as e:
        raise DyCliError("playwright_error", f"{label}失败: {e}")
    if not result.get("success"):
        raise DyCliError("action_failed", f"{label}失败: {failure_hint}")
    success(f"{label}成功 {_EMOJI.get(action, '')}".rstrip())
    if as_json:
        print_json(result)


@click.command("like", help="点赞视频 (支持短索引: dy like 1)")
@click.argument("aweme_id")
@click.option("--unlike", is_flag=True, help="取消点赞")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def like(aweme_id, unlike, account, as_json):
    """点赞或取消点赞。"""
    aweme_id = _resolve(aweme_id)
    action = "unlike" if unlike else "like"
    label = "取消点赞" if unlike else "点赞"
    info(f"正在{label}: {aweme_id}")
    _run_action(account, aweme_id, action, label, "未找到按钮", as_json)


@click.command("favorite", help="收藏视频 (支持短索引: dy fav 1)")
@click.argument("aweme_id")
@click.option("--unfavorite", is_flag=True, help="取消收藏")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def favorite(aweme_id, unfavorite, account, as_json):
    """收藏或取消收藏。"""
    aweme_id = _resolve(aweme_id)
    action = "unfavorite" if unfavorite else "favorite"
    label = "取消收藏" if unfavorite else "收藏"
    info(f"正在{label}: {aweme_id}")
    _run_action(account, aweme_id, action, label, "未找到按钮", as_json)


@click.command("comment", help="评论视频 (支持短索引: dy comment 1 -c '好看')")
@click.argument("aweme_id")
@click.option("--content", "-c", required=True, help="评论内容")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def comment(aweme_id, content, account, as_json):
    """发表评论。"""
    aweme_id = _resolve(aweme_id)
    info(f"正在评论: {aweme_id}")
    _run_action(account, aweme_id, "comment", "评论", "未找到输入框", as_json, content=content)


@click.command("comments", help="查看视频评论 (支持短索引)")
@click.argument("aweme_id")
@click.option("--count", type=int, default=20, help="评论数量")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def comments(aweme_id, count, account, as_json):
    """查看视频评论列表 (Playwright 抓取)。"""
    aweme_id = _resolve(aweme_id)
    info(f"正在获取评论: {aweme_id}")

    try:
        comment_list = _pw(account).get_comments(aweme_id, count=count)
    except PlaywrightError as e:
        raise DyCliError("playwright_error", f"获取评论失败: {e}")

    if as_json:
        print_json(comment_list)
    else:
        print_comments(comment_list)


@click.command("follow", help="关注用户")
@click.argument("sec_user_id")
@click.option("--unfollow", is_flag=True, help="取消关注")
@click.option("--account", default=None, help="使用指定账号")
@click.option("--json-output", "as_json", is_flag=True, help="输出 JSON")
def follow(sec_user_id, unfollow, account, as_json):
    """关注或取消关注用户。"""
    action = "unfollow" if unfollow else "follow"
    label = "取消关注" if unfollow else "关注"
    info(f"正在{label}用户")
    _run_action(account, "", action, label, "未找到按钮", as_json, sec_user_id=sec_user_id)
