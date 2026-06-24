"""
BilibiliParser - B站视频解析插件

功能：
- /bparser_login  生成B站登录二维码（用于查看大会员限定内容）
- 自动检测群聊/私聊中的 B站链接（BV号、AV号、b23.tv短链）
- 获取视频信息（标题、简介、播放量等）并发送封面图
- 可选：下载并发送视频文件到群
"""
import re
import os
import base64
import json
import html
import ssl
import time
import sqlite3
import asyncio
import logging
import aiohttp
import requests
import qrcode
from io import BytesIO
from cryptography.fernet import Fernet

from nbot.commands import register_command, command_handlers, bot
from ncatbot.core import MessageChain
from ncatbot.core.element import Image, Text

_log = logging.getLogger(__name__)

# 存储路径
_PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_DIR = os.path.join(_PLUGIN_DIR, "bilibili")
_DB_PATH = os.path.join(_DB_DIR, "cookies.db")
_KEY_PATH = os.path.join(_DB_DIR, "cookie.key")
_TMP_DIR = os.path.join(_PLUGIN_DIR, "..", "..", "tmp")

_cookies = None
_fernet = None


def _ensure_db():
    if not os.path.exists(_DB_DIR):
        os.makedirs(_DB_DIR, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS cookies (id INTEGER PRIMARY KEY, data TEXT)")
    conn.commit()
    conn.close()
    global _fernet
    if not os.path.exists(_KEY_PATH):
        key = Fernet.generate_key()
        with open(_KEY_PATH, "wb") as f:
            f.write(key)
    with open(_KEY_PATH, "rb") as f:
        _fernet = Fernet(f.read())


def load_cookies():
    global _cookies
    _ensure_db()
    conn = sqlite3.connect(_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT data FROM cookies WHERE id=1")
    row = c.fetchone()
    conn.close()
    if row:
        try:
            decrypted = _fernet.decrypt(row[0].encode()).decode()
            _cookies = json.loads(decrypted)
            return _cookies
        except Exception:
            _cookies = None
    return None


def save_cookies(cookies):
    global _cookies
    _ensure_db()
    encrypted = _fernet.encrypt(json.dumps(cookies).encode()).decode()
    conn = sqlite3.connect(_DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM cookies WHERE id=1")
    c.execute("INSERT INTO cookies (id, data) VALUES (?, ?)", (1, encrypted))
    conn.commit()
    conn.close()
    _cookies = cookies


def _create_session(cookies=None):
    """创建带 SSL 配置的 aiohttp session（关闭证书验证，兼容部分 Python 环境）"""
    connector = aiohttp.TCPConnector(ssl=False)
    return aiohttp.ClientSession(connector=connector, cookies=cookies)


# ---------------------------------------------------------------------------
# /bparser_login - B站扫码登录
# ---------------------------------------------------------------------------
@register_command("/bparser_login", help_text="/bparser_login -> B站扫码登录(查看大会员限定内容)", category="3")
async def handle_bparser_login(msg, is_group=True):
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Referer": "https://passport.bilibili.com/login"
        }
        qr_res = requests.get(
            "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
            headers=headers, timeout=15
        )
        qr_json = qr_res.json()
        qr_data = qr_json.get("data")
        if not qr_data or "url" not in qr_data or "qrcode_key" not in qr_data:
            await msg.reply(text=f"获取登录二维码失败: {qr_json}")
            return

        qr_url = qr_data["url"]
        qrcode_key = qr_data["qrcode_key"]

        qr_img = qrcode.make(qr_url)
        buf = BytesIO()
        qr_img.save(buf, format="PNG")
        buf.seek(0)

        if not os.path.exists(_TMP_DIR):
            os.makedirs(_TMP_DIR, exist_ok=True)
        img_path = os.path.join(_TMP_DIR, f"bili_qr_{int(time.time())}.png")
        with open(img_path, "wb") as f:
            f.write(buf.getvalue())

        # 发送二维码
        if is_group:
            await bot.api.post_group_file(group_id=msg.group_id, file=img_path)
        else:
            await bot.api.upload_private_file(user_id=msg.user_id, file=img_path, name="bilibili_login.png")
        await msg.reply(text="请使用B站APP扫描上方二维码登录（3分钟内有效）")

        # 后台轮询登录状态
        asyncio.create_task(_poll_login_status(msg, qrcode_key))

    except Exception as e:
        _log.error(f"B站登录失败: {e}")
        await msg.reply(text=f"登录失败: {e}")


async def _poll_login_status(msg, qrcode_key):
    """轮询B站扫码登录状态"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://passport.bilibili.com/login"
    }
    for _ in range(30):
        await asyncio.sleep(7)
        try:
            check_res = requests.get(
                f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}",
                headers=headers, timeout=10
            )
            status_data = check_res.json().get("data")
            if not status_data:
                continue

            code = status_data.get("code", -1)
            if code == 0:  # 登录成功
                cookies = {
                    "SESSDATA": requests.utils.dict_from_cookiejar(
                        check_res.cookies
                    ).get("SESSDATA", "")
                }
                save_cookies(cookies)
                await msg.reply(text="B站登录成功！")
                return
            elif code == 86038:
                await msg.reply(text="二维码已过期，请重新登录")
                return
            elif code == 86061:
                # 已扫描待确认
                _log.info("B站二维码已扫描，等待确认...")
        except Exception:
            continue

    await msg.reply(text="登录超时，请重试")


# ---------------------------------------------------------------------------
# B站链接自动检测
# ---------------------------------------------------------------------------
async def on_bilibili_message(msg, is_group: bool) -> bool:
    """检测消息中的 B站链接并自动解析。返回 True 表示已处理（应跳过后续 AI 流程）。"""
    raw_msg = msg.raw_message
    if not raw_msg:
        return False

    # 先跳过命令消息
    for commands, _ in command_handlers.items():
        for cmd in commands:
            if raw_msg.startswith(cmd):
                return False

    # 检查 CQ:json 卡片（QQ内分享的B站链接以json卡片形式存在）
    cq_json_match = re.match(r"\[CQ:json,data=(.+)\]", raw_msg, re.DOTALL)
    if cq_json_match:
        try:
            json_str = cq_json_match.group(1)
            json_str = (
                json_str.replace("&#44;", ",")
                        .replace("&quot;", '"')
                        .replace("&amp;", "&")
            )
            # 额外处理剩余的 HTML 实体（如 &#123; 等）
            json_str = html.unescape(json_str)
            card_data = json.loads(json_str)
            meta = card_data.get("meta", {})
            _log.info(f"[Bili] CQ:json 已解析, meta keys={list(meta.keys())}, app={card_data.get('app', '')}, prompt={card_data.get('prompt', '')[:100]}")

            # 尝试多种来源提取 URL：
            # 1) detail_1 卡片（旧版/文档分享）
            detail = meta.get("detail_1", {})
            url = detail.get("qqdocurl", "") or detail.get("url", "")
            if url:
                _log.info(f"[Bili] 从 detail_1 提取到 URL: {url[:120]}")
            # 2) news 卡片（小程序分享）
            if not url:
                news = meta.get("news", {})
                url = news.get("jumpUrl", "") or news.get("url", "")
                if url:
                    _log.info(f"[Bili] 从 news 提取到 URL: {url[:120]}")
            if not url:
                # 3) 遍历 meta 下所有字段寻找 URL
                for key, val in meta.items():
                    if isinstance(val, dict):
                        for sub_key in ("jumpUrl", "qqdocurl", "url", "source_url", "preview"):
                            candidate = val.get(sub_key, "")
                            if candidate and ("bilibili" in candidate or "b23.tv" in candidate or "BV" in candidate):
                                url = candidate
                                _log.info(f"[Bili] 从 meta.{key}.{sub_key} 提取到 URL: {url[:120]}")
                                break
                    if url:
                        break
            if not url:
                _log.info(f"[Bili] 未提取到 URL, meta 结构: {json.dumps(meta, ensure_ascii=False)[:500]}")

            # 从提取到的 URL 匹配 b23.tv 短链
            if url:
                b23_match = re.search(r"(b23\.tv/[a-zA-Z0-9_-]+)", url)
                bv_match = re.search(r"BV([a-zA-Z0-9]{10})", url)
                av_match = re.search(r"av(\d+)", url, re.IGNORECASE)
                if b23_match:
                    video_id = await _resolve_short_url_async("https://" + b23_match.group(1))
                    if video_id:
                        await _process_video(msg, is_group, video_id)
                    return True
                elif bv_match:
                    await _process_video(msg, is_group, f"bvid={bv_match.group(0)}")
                    return True
                elif av_match:
                    await _process_video(msg, is_group, f"aid={av_match.group(1)}")
                    return True

            # 3) 兜底：在整个 JSON 字符串中搜索 b23.tv / BV / AV
            full_text = json_str
            b23_match = re.search(r"(b23\.tv/[a-zA-Z0-9_-]+)", full_text)
            bv_match = re.search(r"BV([a-zA-Z0-9]{10})", full_text)
            av_match = re.search(r"av(\d+)", full_text, re.IGNORECASE)
            if b23_match:
                video_id = await _resolve_short_url_async("https://" + b23_match.group(1))
                if video_id:
                    await _process_video(msg, is_group, video_id)
                return True
            elif bv_match:
                await _process_video(msg, is_group, f"bvid={bv_match.group(0)}")
                return True
            elif av_match:
                await _process_video(msg, is_group, f"aid={av_match.group(1)}")
                return True
        except Exception as e:
            _log.debug(f"解析CQ:json卡片失败: {e}")

    # 检查文本中的 BV号、AV号、b23.tv短链
    text_no_cq = re.sub(r"\[CQ:[^\]]+\]", "", raw_msg)
    bvid_match = re.search(r"BV([a-zA-Z0-9]{10})", text_no_cq)
    aid_match = re.search(r"av(\d+)", text_no_cq, re.IGNORECASE)
    short_match = re.search(r"(b23\.tv/[a-zA-Z0-9_-]+)", text_no_cq)

    video_id = None
    if bvid_match:
        video_id = f"bvid=BV{bvid_match.group(1)}"
    elif aid_match:
        video_id = f"aid={aid_match.group(1)}"
    elif short_match:
        video_id = await _resolve_short_url_async("https://" + short_match.group(1))

    if video_id:
        await _process_video(msg, is_group, video_id)
        return True

    return False


async def _resolve_short_url_async(url):
    """解析B站短链 → video_id"""
    try:
        async with _create_session() as session:
            async with session.get(url, allow_redirects=False, timeout=10) as resp:
                if resp.status in (301, 302):
                    location = resp.headers.get("Location", "")
                    match = re.search(r"video/(?:av(\d+)|BV([a-zA-Z0-9]{10}))", location)
                    if match:
                        if match.group(1):
                            return f"aid={match.group(1)}"
                        elif match.group(2):
                            return f"bvid={match.group(2)}"
    except Exception as e:
        _log.warning(f"解析短链失败: {e}")
    return None


async def _process_video(msg, is_group, video_id: str):
    """获取并发送B站视频信息（封面+详情）"""
    api_url = f"https://api.bilibili.com/x/web-interface/view?{video_id}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/91.0.4472.124 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com/"
    }

    try:
        global _cookies
        if _cookies is None:
            load_cookies()

        async with _create_session(cookies=_cookies) as session:
            async with session.get(api_url, headers=headers, timeout=15) as resp:
                if resp.status != 200:
                    await msg.reply(text="获取视频信息失败，请稍后再试")
                    return
                data = await resp.json()
                video_info = data.get("data")
                if not video_info:
                    await msg.reply(text="未获取到视频信息，可能视频不存在")
                    return

                title = video_info.get("title", "")
                desc = video_info.get("desc", "")
                if len(desc) > 100:
                    desc = desc[:100] + "..."
                cover_url = video_info.get("pic", "")
                stats = video_info.get("stat", {})
                owner = video_info.get("owner", {})
                author = owner.get("name", "")

                info_text = (
                    f"\n【{title}】\n"
                    f"UP主: {author}\n"
                )
                if desc:
                    info_text += f"简介: {desc}\n"
                info_text += (
                    f"播放: {stats.get('view', 0)} | 点赞: {stats.get('like', 0)}\n"
                    f"收藏: {stats.get('favorite', 0)} | 投币: {stats.get('coin', 0)}"
                )

                # 封面图：B 站 CDN 要求 Referer 头，QQ bot 后端不带 → 403 Forbidden。
                # 我们下载到内存后 base64 编码，塞进消息里——不需本地文件也不靠 bot 后端拉。
                elements = []
                if cover_url:
                    if cover_url.startswith("//"):
                        cover_url = "https:" + cover_url
                    try:
                        async with _create_session() as img_session:
                            async with img_session.get(
                                cover_url, headers=headers, timeout=10
                            ) as img_resp:
                                if img_resp.status == 200:
                                    img_data = await img_resp.read()
                                    b64 = base64.b64encode(img_data).decode("ascii")
                                    elements.append(Image(f"data:image/jpeg;base64,{b64}"))
                    except Exception as e:
                        _log.warning(f"下载B站封面图失败: {e}")
                elements.append(Text(info_text))

                messagechain = MessageChain(*elements)

                if is_group:
                    await bot.api.post_group_msg(
                        group_id=msg.group_id, rtf=messagechain
                    )
                else:
                    await bot.api.post_private_msg(
                        user_id=msg.user_id, rtf=messagechain
                    )

                # 尝试发送视频
                await _try_send_video(msg, is_group, video_info)

    except Exception as e:
        _log.error(f"处理B站视频出错: {e}")
        await msg.reply(text="处理视频信息时发生错误")


async def _try_send_video(msg, is_group, video_info: dict):
    """下载B站视频并以视频消息发送到群/私聊"""
    try:
        cid = video_info.get("cid")
        bvid = video_info.get("bvid")
        aid = video_info.get("aid")
        if not cid:
            return

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com/"
        }

        playurl_api = f"https://api.bilibili.com/x/player/playurl?cid={cid}"
        if bvid:
            playurl_api += f"&bvid={bvid}"
        else:
            playurl_api += f"&aid={aid}"
        playurl_api += "&qn=80"  # 1080P

        async with _create_session(cookies=_cookies) as session:
            async with session.get(playurl_api, headers=headers, timeout=15) as resp:
                play_data = await resp.json()
                data = play_data.get("data", {})
                durl = data.get("durl", [])
                dash = data.get("dash")

        video_url = None
        if durl:
            video_url = durl[0].get("url")
        elif dash:
            # 部分新版视频只有 DASH（无 durl）——取最高画质 video 流
            videos = dash.get("video", [])
            if videos:
                video_url = videos[0].get("baseUrl") or videos[0].get("base_url")
                _log.info(
                    f"[Bili] 视频 {bvid} 无 durl，降级使用 DASH video 流 "
                    f"(id={videos[0].get('id')}, codecs={videos[0].get('codecs')})"
                )
        if not video_url:
            _log.warning(f"[Bili] 视频 {bvid} 无可用播放 URL（无 durl 也无 dash.video）")
            return

        if not os.path.exists(_TMP_DIR):
            os.makedirs(_TMP_DIR, exist_ok=True)
        video_path = os.path.abspath(
            os.path.join(_TMP_DIR, f"bili_{bvid or aid}_{cid}.mp4")
        )

        # 下载视频（带 Referer 防 B 站 CDN 403）
        async with _create_session() as session:
            async with session.get(video_url, headers=headers, timeout=300) as resp:
                with open(video_path, "wb") as f:
                    while True:
                        chunk = await resp.content.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)

        # 以视频消息发送（sandbox bridge 自动 hard link 进 QQ 沙盒）
        if is_group and hasattr(msg, "group_id"):
            await bot.api.post_group_file(
                group_id=msg.group_id, video=video_path
            )
        elif not is_group:
            await bot.api.post_private_file(
                user_id=msg.user_id, video=video_path
            )
        else:
            await msg.reply(text="视频下载完成，但暂不支持发送~")

    except Exception as e:
        _log.warning(f"下载/发送B站视频失败: {e}", exc_info=True)
        try:
            err_text = f"视频下载/发送失败喵~: {e}"
            if is_group and hasattr(msg, "group_id"):
                await msg.reply(text=err_text)
            else:
                await bot.api.post_private_msg(msg.user_id, text=err_text)
        except Exception:
            pass  # 反馈失败别再炸一次


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------
load_cookies()
_log.info("BilibiliParser 插件已加载，当前cookies: " + str(bool(_cookies)))
