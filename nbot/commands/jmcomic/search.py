"""JM comic search and tag commands."""
import hashlib
import html
import os
import re
import time

from jmcomic import JmOption
from jmcomic.jmcomic import JmAlbumDetail, JmSearchPage, MissingAlbumPhotoException

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import load_address
from nbot.commands.jmcomic.html_builder import (
    build_jm_grid_html,
    append_jm_card,
    close_jm_grid_html,
)
from nbot.utils.message_sender import send_text, send_file
from nbot.commands.state import comic_cache


@register_command("/jm_search", help_text="/jm_search <内容> -> 搜索漫画", category="1")
async def handle_search(msg, is_group=True):
    await send_text(msg, "正在搜索喵~", is_group=is_group)

    cache_dir = os.path.join(load_address(), "search")
    os.makedirs(cache_dir, exist_ok=True)
    client = JmOption.default().new_jm_client()
    content = msg.raw_message[len("/jm_search"):].strip()

    if not content or content == " ":
        await send_text(msg, "搜索内容不能为空喵~", is_group=is_group)
        return

    file_token = hashlib.md5(f"{content}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{content}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    if re.match(r'^\d+$', content):
        id = content
        album: JmAlbumDetail = client.get_album_detail(id)
        cover_url = client.get_album_detail(id)[0].cover if album and len(album) > 0 else f"https://cdn-msp.jmcomic.me/media/albums/{id}.jpg"
        album_url = f"https://jmcm.la/album/{id}"
        html_head = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(album.title)} - JM 本子</title>
  <style>
    body {{ font-family: 'Segoe UI', 'PingFang SC', sans-serif; background:#111827; color:#f3f4f6; margin:0; padding:24px; }}
    .card {{ background:#1f2937; border:1px solid rgba(255,255,255,0.08); border-radius:16px; overflow:hidden; box-shadow:0 10px 24px rgba(0,0,0,0.22); max-width:400px; margin:0 auto; transition: transform 0.2s, box-shadow 0.2s; cursor:pointer; }}
    .card:hover {{ transform: translateY(-4px); box-shadow:0 14px 28px rgba(0,0,0,0.3); }}
    .cover {{ width:100%; aspect-ratio: 13 / 18; object-fit:cover; display:block; background:#0b1220; }}
    .meta {{ padding:16px 20px 20px; }}
    .title {{ font-size:18px; font-weight:700; line-height:1.4; word-break:break-word; margin-bottom:10px; }}
    .info {{ color:#9ca3af; font-size:13px; line-height:1.8; }}
    .tag {{ display:inline-block; background:#374151; border-radius:6px; padding:2px 8px; margin:2px; font-size:12px; }}
  </style>
</head>
<body>
  <a href="{html.escape(album_url, quote=True)}" target="_blank" style="text-decoration:none; color:inherit;">
  <div class="card">
    <img class="cover" src="{html.escape(cover_url, quote=True)}" alt="{html.escape(album.title, quote=True)}">
    <div class="meta">
      <div class="title">{html.escape(album.title)}</div>
      <div class="info">
        <div>ID: {html.escape(str(id))}</div>
        <div>页数: {album.page_count}</div>
        <div>浏览: {album.views}</div>
        <div>评论: {album.comment_count}</div>
        <div style="margin-top:8px;">{''.join(f'<span class="tag">{html.escape(str(tag))}</span>' for tag in album.tags)}</div>
      </div>
    </div>
  </div>
  </a>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_head)
        await send_file(msg, filepath, is_group=is_group, filename=filename)
        return

    build_jm_grid_html(f"{html.escape(content)} · JM 搜索", filepath)

    tot = 0
    for i in range(5):
        page: JmSearchPage = client.search_site(search_query=content, page=i+1)
        if len(page) == 0:
            break
        for album_id, title in page:
            tot += 1
            append_jm_card(filepath, album_id, title, tot, client=client)
            comic_cache.append(album_id)
        if tot >= 50:
            break

    close_jm_grid_html(filepath)

    if not os.path.exists(filepath):
        await send_text(msg, "搜索失败喵~，文件不存在", is_group=is_group)
        return

    await send_file(msg, filepath, is_group=is_group, filename=filename)


@register_command("/jm_tag", help_text="/jm_tag <标签> -> 搜索漫画标签", category="1")
async def handle_tag(msg, is_group=True):
    await send_text(msg, "正在搜索喵~", is_group=is_group)

    cache_dir = os.path.join(load_address(), "search")
    os.makedirs(cache_dir, exist_ok=True)
    content = msg.raw_message[len("/tag"):].strip()
    client = JmOption.default().new_jm_client()

    file_token = hashlib.md5(f"tag_{content}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{content}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    build_jm_grid_html(f"{html.escape(content)} · JM 标签搜索", filepath)

    tot = 0
    for i in range(5):
        page: JmSearchPage = client.search_tag(search_query=content, page=i+1)
        if len(page) == 0:
            break
        for album_id, title in page:
            tot += 1
            append_jm_card(filepath, album_id, title, tot, client=client)
            comic_cache.append(album_id)
        if tot >= 50:
            break

    close_jm_grid_html(filepath)

    await send_file(msg, filepath, is_group=is_group, filename=filename)
