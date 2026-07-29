"""
增强版 API 客户端 - 添加视频质量选择功能
"""

from typing import Any


def get_download_url_with_quality(self, aweme_id: str, quality: str = "best") -> dict[str, Any]:
    """
    获取指定质量的无水印下载链接。
    
    Args:
        aweme_id: 视频 ID
        quality: 质量选项
            - "1080": 1080p 高清
            - "720": 720p 高清
            - "540": 540p 标清
            - "best": 最佳质量（默认）
            - "worst": 最差质量
    
    Returns:
        与 get_download_url 相同的格式，但包含质量信息
    """
    detail = self.get_video_detail(aweme_id)
    
    result: dict[str, Any] = {
        "video_url": None,
        "music_url": None,
        "images": None,
        "desc": detail.get("desc", ""),
        "author": detail.get("author", {}).get("nickname", ""),
        "aweme_id": aweme_id,
        "quality": None,
        "available_qualities": [],
    }
    
    video = detail.get("video", {})
    bit_rate = video.get("bit_rate", [])
    
    if not bit_rate:
        # 回退到默认行为
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        if url_list:
            result["video_url"] = url_list[-1].replace("playwm", "play")
        return result
    
    # 记录所有可用质量
    for br in bit_rate:
        gear = br.get("gear_name", "unknown")
        bitrate = br.get("bit_rate", 0)
        result["available_qualities"].append({
            "gear_name": gear,
            "bit_rate": bitrate,
        })
    
    # 选择质量
    selected = None
    if quality == "best":
        selected = bit_rate[0]
    elif quality == "worst":
        selected = bit_rate[-1]
    elif quality == "1080":
        for br in bit_rate:
            if "1080" in br.get("gear_name", ""):
                selected = br
                break
    elif quality == "720":
        for br in bit_rate:
            gear = br.get("gear_name", "")
            if "720" in gear and "low" not in gear:
                selected = br
                break
    elif quality == "540":
        for br in bit_rate:
            gear = br.get("gear_name", "")
            if "540" in gear and "low" not in gear:
                selected = br
                break
    
    if not selected:
        # 尝试模糊匹配
        for br in bit_rate:
            gear = br.get("gear_name", "")
            if quality in gear:
                selected = br
                break
    
    if not selected:
        # 默认使用最佳质量
        selected = bit_rate[0]
    
    # 获取下载 URL
    play_addr = selected.get("play_addr", {})
    url_list = play_addr.get("url_list", [])
    if url_list:
        result["video_url"] = url_list[-1].replace("playwm", "play")
    
    result["quality"] = {
        "gear_name": selected.get("gear_name"),
        "bit_rate": selected.get("bit_rate"),
    }
    
    # 下载音乐
    music = detail.get("music", {})
    music_play = music.get("play_url", {})
    if isinstance(music_play, dict):
        music_urls = music_play.get("url_list", [])
        if music_urls:
            result["music_url"] = music_urls[0]
    elif isinstance(music_play, str):
        result["music_url"] = music_play
    
    return result


# 使用方法：将此方法添加到 DouyinAPIClient 类
# from dy_cli.engines.api_client import DouyinAPIClient
# DouyinAPIClient.get_download_url_with_quality = get_download_url_with_quality
