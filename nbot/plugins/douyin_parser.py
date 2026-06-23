"""
DouyinParser - 抖音视频解析插件

功能：
- 自动检测群聊/私聊中的抖音分享链接（v.douyin.com 短链、douyin.com/video）
- 获取视频信息（标题、作者、播放量等）并发送封面图
- 可选：下载并发送无水印视频到群
"""
import re
import os
import json
import html
import asyncio
import logging
import aiohttp
import requests

from nbot.commands import register_command, command_handlers, bot

_log = logging.getLogger(__name__)

_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_TMP_DIR = os.path.join(_PLUGIN_DIR, "..", "..", "tmp")

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/116.0.0.0 Mobile Safari/537.36"
)


def _create_session(cookies=None):
    connector = aiohttp.TCPConnector(ssl=False)
    return aiohttp.ClientSession(connector=connector, cookies=cookies)


# ---------------------------------------------------------------------------
# 抖音链接自动检测
# ---------------------------------------------------------------------------
async def on_douyin_message(msg, is_group: bool) -> bool:
    """检测消息中的抖音链接并自动解析。返回 True 表示已处理（应跳过后续 AI 流程）。"""
    raw_msg = msg.raw_message
    if not raw_msg:
        return False

    # 先跳过命令消息
    for commands, _ in command_handlers.items():
        for cmd in commands:
            if raw_msg.startswith(cmd):
                return False

    # 检查 CQ:json 卡片（QQ小程序分享）
    cq_json_match = re.match(r"\[CQ:json,data=(.+)\]", raw_msg, re.DOTALL)
    if cq_json_match:
        try:
            json_str = cq_json_match.group(1)
            json_str = (
                json_str.replace("&#44;", ",")
                        .replace("&quot;", '"')
                        .replace("&amp;", "&")
            )
            json_str = html.unescape(json_str)
            card_data = json.loads(json_str)
            meta = card_data.get("meta", {})
            _log.info(f"[Douyin] CQ:json 已解析, meta keys={list(meta.keys())}")

            url = None
            # 1) detail_1 卡片
            detail = meta.get("detail_1", {})
            url = detail.get("qqdocurl", "") or detail.get("url", "")
            if url:
                _log.info(f"[Douyin] 从 detail_1 提取到 URL: {url[:120]}")
            # 2) news 卡片
            if not url:
                news = meta.get("news", {})
                url = news.get("jumpUrl", "") or news.get("url", "")
                if url:
                    _log.info(f"[Douyin] 从 news 提取到 URL: {url[:120]}")
            # 3) 遍历 meta 下所有字段
            if not url:
                for key, val in meta.items():
                    if isinstance(val, dict):
                        for sub_key in ("jumpUrl", "qqdocurl", "url", "source_url", "preview"):
                            candidate = val.get(sub_key, "")
                            if candidate and ("douyin.com" in candidate or "v.douyin" in candidate):
                                url = candidate
                                _log.info(f"[Douyin] 从 meta.{key}.{sub_key} 提取到 URL: {url[:120]}")
                                break
                    if url:
                        break
            if not url:
                _log.info(f"[Douyin] 未提取到 URL, meta 结构: {json.dumps(meta, ensure_ascii=False)[:500]}")

            # 从 URL 匹配 douyin 短链
            if url:
                short_match = re.search(r"(v\.douyin\.com/[a-zA-Z0-9]+)", url)
                video_match = re.search(r"douyin\.com/video/(\d+)", url)
                share_match = re.search(r"douyin\.com/share/video/(\d+)", url)
                if short_match:
                    await _process_douyin(msg, is_group, short_match.group(1))
                    return True
                elif video_match:
                    await _process_douyin(msg, is_group, video_id=video_match.group(1))
                    return True
                elif share_match:
                    await _process_douyin(msg, is_group, video_id=share_match.group(1))
                    return True

            # 兜底：在整个 JSON 字符串中搜索
            full_text = json_str
            short_match = re.search(r"(v\.douyin\.com/[a-zA-Z0-9]+)", full_text)
            video_match = re.search(r"douyin\.com/video/(\d+)", full_text)
            if short_match:
                await _process_douyin(msg, is_group, short_match.group(1))
                return True
            elif video_match:
                await _process_douyin(msg, is_group, video_id=video_match.group(1))
                return True
        except Exception as e:
            _log.debug(f"解析抖音CQ:json卡片失败: {e}")

    # 检查文本中的抖音链接
    text_no_cq = re.sub(r"\[CQ:[^\]]+\]", "", raw_msg)
    short_match = re.search(r"(v\.douyin\.com/[a-zA-Z0-9]+)", text_no_cq)
    video_match = re.search(r"douyin\.com/video/(\d+)", text_no_cq)
    share_match = re.search(r"douyin\.com/share/video/(\d+)", text_no_cq)

    if short_match:
        await _process_douyin(msg, is_group, short_match.group(1))
        return True
    elif video_match:
        await _process_douyin(msg, is_group, video_id=video_match.group(1))
        return True
    elif share_match:
        await _process_douyin(msg, is_group, video_id=share_match.group(1))
        return True

    return False


async def _resolve_short_url(short_path):
    """解析抖音短链 → video_id"""
    url = f"https://{short_path}"
    try:
        async with _create_session() as session:
            async with session.get(url, allow_redirects=True, timeout=15) as resp:
                final_url = str(resp.url)
                match = re.search(r"video/(\d+)", final_url)
                if match:
                    return match.group(1)
    except Exception as e:
        _log.warning(f"解析抖音短链失败: {e}")
    return None


async def _get_video_info(video_id: str) -> dict:
    """获取抖音视频信息（标题、封面、作者、无水印URL等）"""
    headers = {
        "User-Agent": MOBILE_UA,
        "Referer": "https://www.douyin.com/?is_from_mobile_home=1&recommend=1"
    }
    url = f"https://www.iesdouyin.com/share/video/{video_id}/"

    try:
        async with _create_session() as session:
            async with session.get(url, headers=headers, timeout=15) as resp:
                html_text = await resp.text()

        # 从页面中提取 _ROUTER_DATA（使用花括号深度追踪，避免正则被JSON内的分号截断）
        idx = html_text.find("_ROUTER_DATA")
        if idx == -1:
            _log.warning(f"无法从页面找到 _ROUTER_DATA, video_id={video_id}")
            return None

        chunk = html_text[idx:]
        start = chunk.find("{")
        if start == -1:
            _log.warning(f"_ROUTER_DATA 中未找到 JSON 起始, video_id={video_id}")
            return None

        # 使用花括号深度追踪提取完整 JSON
        depth = 0
        in_string = False
        escape = False
        end = -1
        for i in range(start, len(chunk)):
            c = chunk[i]
            if escape:
                escape = False
                continue
            if c == "\\":
                escape = True
                continue
            if c == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break

        if end == -1:
            _log.warning(f"无法提取完整 JSON, video_id={video_id}")
            return None

        json_data = json.loads(chunk[start:end + 1])
        item_list = json_data["loaderData"]["video_(id)/page"]["videoInfoRes"]["item_list"]
        if not item_list:
            _log.warning(f"item_list 为空, video_id={video_id}")
            return None
        item = item_list[0]

        video = item.get("video", {})
        author = item.get("author", {})
        stats = item.get("statistics", {})

        # 封面图
        cover_url = ""
        cover_list = video.get("cover", {}).get("url_list", [])
        if cover_list:
            cover_url = cover_list[0]

        # 无水印视频 URL
        play_uri = video.get("play_addr", {}).get("uri", "")
        video_url = ""
        if play_uri:
            video_url = f"https://www.douyin.com/aweme/v1/play/?video_id={play_uri}"

        # 尝试从 download_addr 获取（可能无水印）
        download_uri = video.get("download_addr", {}).get("uri", "")
        download_url = ""
        if download_uri:
            download_url = f"https://www.douyin.com/aweme/v1/play/?video_id={download_uri}"

        return {
            "video_id": video_id,
            "title": item.get("desc", ""),
            "cover_url": cover_url,
            "author": author.get("nickname", ""),
            "video_url": video_url,
            "download_url": download_url or video_url,
            "duration": video.get("duration", 0),
            "digg_count": stats.get("digg_count", 0),
            "comment_count": stats.get("comment_count", 0),
            "share_count": stats.get("share_count", 0),
        }
    except Exception as e:
        _log.error(f"获取抖音视频信息失败: {e}")
        return None


async def _process_douyin(msg, is_group, short_path: str = None, video_id: str = None):
    """处理抖音链接：解析短链 → 获取信息 → 发送封面+文字 → 下载视频"""
    try:
        # 先解析短链得到 video_id
        if short_path and not video_id:
            video_id = await _resolve_short_url(short_path)
            if not video_id:
                await msg.reply(text="无法解析抖音链接，可能链接已失效")
                return

        # 获取视频信息
        info = await _get_video_info(video_id)
        if not info:
            await msg.reply(text="获取抖音视频信息失败，请稍后再试")
            return

        title = info["title"] or "(无标题)"
        author = info["author"]
        cover_url = info["cover_url"]
        if cover_url.startswith("//"):
            cover_url = "https:" + cover_url

        dur = info["duration"]
        duration_str = f"{dur // 1000 // 60}:{dur // 1000 % 60:02d}" if dur else "未知"

        info_text = (
            f"\n【{title}】\n"
            f"作者: {author}\n"
            f"时长: {duration_str} | "
            f"点赞: {info['digg_count']} | "
            f"评论: {info['comment_count']} | "
            f"分享: {info['share_count']}"
        )

        # 下载封面图
        cover_path = None
        if cover_url:
            if not os.path.exists(_TMP_DIR):
                os.makedirs(_TMP_DIR, exist_ok=True)
            local_cover = os.path.abspath(
                os.path.join(_TMP_DIR, f"douyin_cover_{video_id}.jpg")
            )
            headers = {"User-Agent": MOBILE_UA, "Referer": "https://www.douyin.com/"}
            try:
                async with _create_session() as img_session:
                    async with img_session.get(cover_url, headers=headers, timeout=15) as img_resp:
                        if img_resp.status == 200:
                            with open(local_cover, "wb") as f:
                                f.write(await img_resp.read())
                            cover_path = local_cover
            except Exception as e:
                _log.warning(f"下载抖音封面图失败: {e}")

        # 构造富文本消息并发送
        message = []
        if cover_path:
            message.append({"type": "image", "data": {"file": cover_path}})
        message.append({"type": "text", "data": {"text": info_text}})

        if is_group:
            await bot.api._http.post("send_group_msg", {
                "group_id": msg.group_id,
                "message": message,
            })
        else:
            await bot.api._http.post("send_private_msg", {
                "user_id": msg.user_id,
                "message": message,
            })

        # 尝试下载并发送视频
        await _download_and_send_video(msg, is_group, info)

    except Exception as e:
        _log.error(f"处理抖音视频出错: {e}")
        await msg.reply(text="处理抖音视频时发生错误")


async def _download_and_send_video(msg, is_group, info: dict):
    """下载抖音视频并发送到群"""
    try:
        video_url = info.get("download_url") or info.get("video_url")
        if not video_url:
            return

        video_id = info["video_id"]
        if not os.path.exists(_TMP_DIR):
            os.makedirs(_TMP_DIR, exist_ok=True)
        video_path = os.path.abspath(
            os.path.join(_TMP_DIR, f"douyin_{video_id}.mp4")
        )

        headers = {"User-Agent": MOBILE_UA, "Referer": "https://www.douyin.com/"}

        # 下载视频（跟随重定向获取真实CDN地址）
        async with _create_session() as session:
            async with session.get(video_url, headers=headers, allow_redirects=True, timeout=300) as resp:
                if resp.status != 200:
                    _log.warning(f"下载抖音视频失败, status={resp.status}")
                    return
                with open(video_path, "wb") as f:
                    while True:
                        chunk = await resp.content.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)

        # 发送视频
        if is_group and hasattr(msg, "group_id"):
            await bot.api.post_group_file(
                group_id=msg.group_id, file=video_path
            )
        elif not is_group:
            await bot.api.upload_private_file(
                user_id=msg.user_id, file=video_path, name=os.path.basename(video_path)
            )
        else:
            await msg.reply(text="视频下载完成，但暂不支持发送~")

    except Exception as e:
        _log.warning(f"下载/发送抖音视频失败: {e}")


_log.info("DouyinParser 插件已加载")
