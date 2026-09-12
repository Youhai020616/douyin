"""
统一输出信封 — Agent 友好的结构化输出。

所有 --json-output 输出使用此信封格式:
  成功: {ok: true, schema_version: "1", data: ...}
  失败: {ok: false, schema_version: "1", error: {code: ..., message: ...}}

本模块只定义数据结构，不做 I/O；输出逻辑见 dy_cli.utils.output。
"""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "1"

# 约定的 error.code 取值（与 SCHEMA.md 保持同步）
ERROR_CODES = (
    "not_authenticated",  # 未登录 / Cookie 失效
    "invalid_argument",   # 参数或短索引无效
    "api_error",          # 抖音 API 请求失败
    "playwright_error",   # 浏览器自动化失败
    "action_failed",      # 互动操作未生效（未找到按钮/输入框）
    "not_found",          # 资源不存在（账号、配置项）
    "not_live",           # 直播间未开播
    "missing_dependency", # 缺少外部依赖（如 ffmpeg）
)


def success_envelope(data: Any) -> dict:
    return {"ok": True, "schema_version": SCHEMA_VERSION, "data": data}


def error_envelope(code: str, message: str) -> dict:
    return {
        "ok": False,
        "schema_version": SCHEMA_VERSION,
        "error": {"code": code, "message": message},
    }
