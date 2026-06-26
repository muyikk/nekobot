"""Novel search commands."""
import hashlib
import html
import os
import re
import time

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import load_address
from nbot.commands.novel.html_builder import (
    build_novel_grid_html,
    append_novel_card,
    close_novel_grid_html,
)
from nbot.commands.novel.wenku8_api import (
    check_wenku8_cookie,
    search_wenku8_books,
    find_book_from_api,
)
from nbot.utils.message_sender import send_text
from nbot.utils.logger import get_logger
from nbot.commands.state import api_book, books

_log = get_logger(__name__)


@register_command("/findbook", "/fb", help_text="/findbook 或者 /fb <书名> -> 搜索并选择下载轻小说", category="6")
async def handle_find_book(msg, is_group=True):
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return

    search_term = ""
    if msg.raw_message.startswith("/findbook"):
        search_term = msg.raw_message[len("/findbook"):].strip()
    elif msg.raw_message.startswith("/fb"):
        search_term = msg.raw_message[len("/fb"):].strip()
    if not search_term:
        reply = "请输入要搜索的书名喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    await send_text(msg, "正在搜索轻小说喵~", is_group=is_group)

    cache_dir = os.path.join(load_address(), "novel_search")
    os.makedirs(cache_dir, exist_ok=True)
    file_token = hashlib.md5(f"novel_{search_term}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{search_term}.html"
    filepath = os.path.join(cache_dir, filename)

    build_novel_grid_html(f"{html.escape(search_term)} · 轻小说搜索", filepath)

    local_matches = search_local_novel_cache(search_term)
    web_matches = []
    if len(local_matches) < 5:
        web_matches = search_wenku8_books(search_term, "articlename")

    seen_titles = set()
    matches = []

    for author, title, download_url in local_matches:
        if title not in seen_titles:
            seen_titles.add(title)
            matches.append((author, title, download_url))

    for author, title, download_url in web_matches:
        if title not in seen_titles:
            seen_titles.add(title)
            matches.append((author, title, download_url))

    api_book[msg.user_id] = find_book_from_api(search_term)

    if not matches and not api_book[msg.user_id]:
        close_novel_grid_html(filepath)
        reply = f"没有找到包含'{search_term}'的轻小说喵~"
        if is_group:
            await msg.reply(text=reply)
            await bot.api.post_group_file(msg.group_id, file=filepath)
        else:
            await bot.api.post_private_msg(msg.user_id, text=reply)
            await bot.api.upload_private_file(msg.user_id, filepath, filename)
        return

    for i, (author, title, download_url) in enumerate(matches):
        book_id_match = re.search(r'id=(\d+)', download_url)
        book_id = book_id_match.group(1) if book_id_match else "0"
        append_novel_card(filepath, book_id, title, author, i + 1)
        if title not in books:
            books[title] = {
                "download_url": download_url,
                "page": f"https://www.wenku8.net/book/{book_id}.htm",
                "author": author
            }

    if api_book[msg.user_id]:
        start_seq = len(matches) + 1
        for i, (_, title) in enumerate(api_book[msg.user_id].items()):
            if title not in seen_titles:
                book_id = api_book[msg.user_id][_].get("book_id", "0")
                author = api_book[msg.user_id][_].get("author", "未知")
                append_novel_card(filepath, book_id, title, author, start_seq + i)
                if title not in books:
                    books[title] = api_book[msg.user_id][_]

    close_novel_grid_html(filepath)

    temp_selections[msg.user_id] = matches

    if is_group:
        await msg.reply(text=f"找到 {len(matches) + len(api_book[msg.user_id]) if api_book[msg.user_id] else len(matches)} 本轻小说喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
        await bot.api.post_group_file(msg.group_id, file=filepath)
    else:
        await bot.api.post_private_msg(msg.user_id, text=f"找到 {len(matches) + len(api_book[msg.user_id]) if api_book[msg.user_id] else len(matches)} 本轻小说喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
        await bot.api.upload_private_file(msg.user_id, filepath, filename)


@register_command("/fa", help_text="/fa <作者> -> 搜索作者", category="6")
async def handle_find_author(msg, is_group=True):
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return

    search_term = msg.raw_message[len("/fa"):].strip()
    if not search_term:
        reply = "请输入要搜索的作者喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    matches = search_wenku8_books(search_term, "author")

    if not matches:
        reply = f"没有找到包含'{search_term}'的作者喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    choices = "\n".join([f"{i+1}. {title} -- {author}" for i, (author, title, _) in enumerate(matches)])
    reply = f"找到以下匹配的作者的轻小说喵~:\n{choices}\n\n请回复'/select 编号'选择要下载的轻小说喵~\n回复'/info 编号'获取轻小说信息喵~"
    temp_selections[msg.user_id] = matches

    await send_text(msg, reply, is_group=is_group)


def search_local_novel_cache(search_term: str) -> list:
    """
    在本地 novel_details2.json 缓存中搜索小说

    :param search_term: 搜索关键词
    :return: 搜索结果列表 [(author, title, download_url), ...]
    """
    results = []
    search_term_lower = search_term.lower()

    try:
        cache_file = os.path.join(os.path.dirname(__file__), '..', '..', 'resources', 'config', 'novel_details2.json')
        if not os.path.exists(cache_file):
            _log.warning(f"本地缓存文件不存在: {cache_file}")
            return results

        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = __import__('json').load(f)

        for title, info in cache_data.items():
            author = info.get('author', '')
            if search_term_lower in title.lower() or search_term_lower in author.lower():
                download_url = info.get('download_url', '')
                results.append((author, title, download_url))

        _log.info(f"本地缓存搜索结果: 找到 {len(results)} 本包含 '{search_term}' 的小说")
    except Exception as e:
        _log.error(f"搜索本地缓存失败: {e}")

    return results


temp_selections = {}
