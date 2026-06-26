"""Novel info and selection commands."""
import hashlib
import html
import os
import re
import time

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import load_address
from nbot.commands.novel.html_builder import build_novel_detail_html
from nbot.commands.novel.wenku8_api import get_api_book_info, download_api_book
from nbot.commands.novel.search import temp_selections, search_local_novel_cache
from nbot.utils.message_sender import send_text
from nbot.utils.logger import get_logger
from nbot.commands.state import api_book, books

_log = get_logger(__name__)


@register_command("/select", help_text="/select <编号> -> 选择要下载的轻小说(先使用/findbook或/fb搜索，再进行选择，重复使用/fb会覆盖之前的搜索结果)", category="6")
async def handle_select_book(msg, is_group=True):
    if (msg.user_id not in temp_selections) and (msg.user_id not in api_book):
        reply = "没有找到主人的搜索记录喵~请先使用/findbook搜索喵~"
        await send_text(msg, reply, is_group=is_group)
        return
    try:
        selection = int(msg.raw_message[len("/select"):].strip()) - 1
        matches = temp_selections.get(msg.user_id, [])
        api_books = api_book.get(msg.user_id, {})

        if 0 <= selection < len(matches) or (selection >= len(matches) and selection < len(matches) + len(api_books)):
            if selection < len(matches):
                author, title, url = matches[selection]
                reply = f"已选择《{title}》-- {author}喵~\n下载链接: {url}"
                await send_text(msg, reply, is_group=is_group)
            else:
                id, title = list(api_books.items())[selection - len(matches)]
                download_api_book(id, title)
                reply = f"已开始下载《{title}》喵~"
                await msg.reply(text=reply)
                api_book_file_path = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "novel", f"{title}.txt")
                if os.path.exists(api_book_file_path):
                    if is_group:
                        await bot.api.post_group_file(msg.group_id, file=api_book_file_path)
                    else:
                        await bot.api.upload_private_file(msg.user_id, file=api_book_file_path, name=title + ".txt")
                else:
                    await msg.reply(text="文件下载中，请稍后再试喵~")
        else:
            reply = "编号无效喵~请选择列表中的编号喵~"
            await send_text(msg, reply, is_group=is_group)
    except ValueError:
        reply = "请输入有效的编号喵~"
        await send_text(msg, reply, is_group=is_group)

    temp_selections.pop(str(msg.user_id), None)
    api_book.pop(str(msg.user_id), None)


@register_command("/info", help_text="/info <书名> -> 获取轻小说信息", category="6")
async def handle_info(msg, is_group=True):
    from nbot.commands.novel.wenku8_api import check_wenku8_cookie
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return

    if (msg.user_id not in temp_selections) and (msg.user_id not in api_book):
        reply = "没有找到您的搜索记录喵~请先使用/findbook搜索喵~"
        await send_text(msg, reply, is_group=is_group)
        return
    try:
        selection = int(msg.raw_message[len("/info"):].strip()) - 1
        matches = temp_selections[msg.user_id]
        api_books = api_book[msg.user_id]

        if 0 <= selection < len(matches) or (selection >= len(matches) and selection < len(matches) + len(api_books)):
            if selection < len(matches):
                author, title, url = matches[selection]
                book_id_match = re.search(r'id=(\d+)', url)
                if book_id_match:
                    book_id = book_id_match.group(1)
                    book_url = f"https://www.wenku8.net/book/{book_id}.htm"
                    info = get_book_detail_by_url(book_url)
                else:
                    info = None

                if info is None:
                    info = books.get(title)
                    if info is None:
                        info = {
                            'author': author,
                            'category': '未知',
                            'word_count': '未知',
                            'is_serialize': '未知',
                            'hot': '搜索结果',
                            'introduction': '暂无简介',
                            'last_date': '未知',
                            'page': book_url if 'book_url' in __import__('builtins').locals() else url,
                            'cover_url': f"https://img.wenku8.com/image/{int(book_id) // 1000 if 'book_id' in __import__('builtins').locals() else 0}/{book_id if 'book_id' in __import__('builtins').locals() else 0}/{book_id if 'book_id' in __import__('builtins').locals() else 0}s.jpg"
                        }
                    else:
                        _log.info(f"从JSON/内存字典获取到《{title}》的信息")

                try:
                    introduction = info['introduction']
                except Exception:
                    introduction = "暂无"
                cover = info['cover_url']

                cache_dir = os.path.join(load_address(), "novel_info")
                os.makedirs(cache_dir, exist_ok=True)
                file_token = hashlib.md5(f"info_{title}_{time.time()}".encode("utf-8")).hexdigest()[:8]
                filename = f"{file_token}_{title[:20]}.html"
                filepath = os.path.join(cache_dir, filename)

                build_novel_detail_html(title, info, filepath)

                text_reply = f"《{title}》的信息如下喵~\n作者: {author}\n分类: {info['category']}\n字数: {info['word_count']}\n状态: {info['is_serialize']}\n热度：{info['hot']}\n简介：{introduction}\n更新日期: {info['last_date']}\n下载链接: {url}\n详细页面：{info['page']}"

                if is_group:
                    await msg.reply(text=text_reply)
                    await bot.api.post_group_file(msg.group_id, file=filepath)
                else:
                    await bot.api.post_private_msg(msg.user_id, text=text_reply)
                    await bot.api.upload_private_file(msg.user_id, filepath, filename)
            else:
                id, title = list(api_books.items())[selection - len(matches)]

                info = get_api_book_info(id)
                if info is None:
                    reply = "没有找到该轻小说的信息喵~"
                    await msg.reply(text=reply)
                    return

                cache_dir = os.path.join(load_address(), "novel_info")
                os.makedirs(cache_dir, exist_ok=True)
                file_token = hashlib.md5(f"info_{title}_{time.time()}".encode("utf-8")).hexdigest()[:8]
                filename = f"{file_token}_{title[:20]}.html"
                filepath = os.path.join(cache_dir, filename)

                build_novel_detail_html(title, info, filepath)

                text_reply = f"《{title}》的信息如下喵~\n作者: {info['author']}\n分类: {info['category']}\n字数: {info['word_count']}\n状态: {info['is_serialize']}\n热度：{info['hot']}\n简介：{info['introduction']}\n更新日期: {info['last_date']}\n下载链接: {info['download_url']}\n详细页面：{info['page']}"

                if is_group:
                    await msg.reply(text=text_reply)
                    await bot.api.post_group_file(msg.group_id, file=filepath)
                else:
                    await bot.api.post_private_msg(msg.user_id, text=text_reply)
                    await bot.api.upload_private_file(msg.user_id, filepath, filename)

        else:
            reply = "编号无效喵~请选择列表中的编号喵~"
            await send_text(msg, reply, is_group=is_group)
    except ValueError:
        reply = "请输入有效的编号喵~"
        await send_text(msg, reply, is_group=is_group)


def get_book_detail_by_url(book_url: str) -> dict:
    """
    通过URL获取小说详情（类似/hotnovel的实现）
    :param book_url: 小说详情页面URL，如 https://www.wenku8.net/book/1234.htm 或 /book/1234.htm
    :return: 包含小说详细信息的字典
    """
    from nbot.commands.novel.wenku8_api import WENKU8_COOKIE
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wenku8.net/",
        "Cookie": WENKU8_COOKIE
    }

    if not book_url.startswith(('http://', 'https://')):
        book_url = 'https://www.wenku8.net' + book_url

    _log.info(f"获取小说详情: {book_url}")
    try:
        from nbot.utils.http_client import get_sync
        response = get_sync(book_url, headers=headers, timeout=10)
        _log.info(f"详情页响应状态码: {response.status_code}")

        if response.status_code == 404 or '网站已关闭' in response.text or '有缘再相聚' in response.text:
            _log.warning("wenku8.net 网站已关闭或页面不存在")
            return None

        response.encoding = "gbk"
        content = response.text

        book_id_match = re.search(r'/book/(\d+)\.htm', book_url)
        book_id = book_id_match.group(1) if book_id_match else "0"
        node = int(book_id) // 1000 if book_id.isdigit() else 0

        title_match = re.search(r'<span property="v:itemreviewed">([^<]+)</span>', content)
        title = title_match.group(1).strip() if title_match else "未知"

        author_match = re.search(r'作者：\s*<a[^>]*>([^<]+)</a>', content)
        author = author_match.group(1).strip() if author_match else "未知"

        category_match = re.search(r'类别：\s*<a[^>]*>([^<]+)</a>', content)
        category = category_match.group(1).strip() if category_match else "未知"

        status_match = re.search(r'状态：\s*<font[^>]*>([^<]+)</font>', content)
        is_serialize = status_match.group(1).strip() if status_match else "未知"

        word_count_match = re.search(r'字数：\s*([\d,]+)', content)
        word_count = word_count_match.group(1).replace(',', '') if word_count_match else "未知"

        update_match = re.search(r'更新时间：\s*([\d-]+)', content)
        last_date = update_match.group(1) if update_match else "未知"

        intro_match = re.search(r'<span class="hottext">内容简介：</span>\s*<br\s*/?>\s*([^<]+)', content, re.DOTALL)
        introduction = intro_match.group(1).strip() if intro_match else "暂无简介"

        cover_match = re.search(r'<img src="([^"]+)"[^>]*alt="[^"]*封面"', content)
        cover_url = cover_match.group(1) if cover_match else f"https://img.wenku8.com/image/{node}/{book_id}/{book_id}s.jpg"

        download_url = f"https://dl.wenku8.com/down.php?type=txt&node={node}&id={book_id}"

        return {
            "title": title,
            "author": author,
            "category": category,
            "word_count": word_count,
            "is_serialize": is_serialize,
            "last_date": last_date,
            "introduction": introduction,
            "cover_url": cover_url,
            "download_url": download_url,
            "page": book_url,
            "hot": "URL获取"
        }
    except Exception as e:
        _log.error(f"获取小说详情失败: {book_url}, 错误: {e}")
        return None
