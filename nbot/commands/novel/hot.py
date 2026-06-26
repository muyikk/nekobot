"""Novel hot list and random commands."""
import hashlib
import html
import os
import random
import re
import time

from nbot.commands import bot
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import load_address
from nbot.commands.novel.html_builder import (
    build_novel_grid_html,
    append_novel_card,
    close_novel_grid_html,
    build_novel_detail_html,
)
from nbot.commands.novel.wenku8_api import (
    check_wenku8_cookie,
    WENKU8_COOKIE,
)
from nbot.commands.novel.info import get_book_detail_by_url
from nbot.utils.message_sender import send_text
from nbot.utils.http_client import get_sync
from nbot.utils.logger import get_logger
from nbot.commands.state import books

_log = get_logger(__name__)


@register_command("/random_novel", "/rn", help_text="/random_novel 或者 /rn -> 发送随机小说", category="6")
async def handle_random_novel(msg, is_group=True):
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return

    novel, info = get_random_book_from_hotlist()

    if novel is None:
        _log.info("热门榜单获取失败，回退到JSON/内存字典")
        if books:
            novel = random.choice(list(books.keys()))
            info = books[novel]
            _log.info(f"从JSON/内存字典随机选择:《{novel}》")
        else:
            reply = "获取随机小说失败喵~请稍后再试~"
            await send_text(msg, reply, is_group=is_group)
            return

    url = info["download_url"]
    hot = info.get('hot', '未知')

    cache_dir = os.path.join(load_address(), "novel_random")
    os.makedirs(cache_dir, exist_ok=True)
    file_token = hashlib.md5(f"random_{novel}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{novel[:20]}.html"
    filepath = os.path.join(cache_dir, filename)

    build_novel_detail_html(novel, info, filepath)

    text_reply = f"抽选到了《{novel}》喵~\n"
    text_reply += f"简介如下喵~\n作者：{info['author']}\n字数：{info['word_count']}\n状态：{info['is_serialize']}\n热度：{hot}\n最新更新：{info['last_date']}\n简介：{info['introduction']}\n下载链接：{url}"

    if is_group:
        await msg.reply(text=text_reply)
        await bot.api.post_group_file(msg.group_id, file=filepath)
    else:
        await bot.api.post_private_msg(msg.user_id, text=text_reply)
        await bot.api.upload_private_file(msg.user_id, filepath, filename)


@register_command("/hotnovel", help_text="/hotnovel <day|month> [数量] -> 获取今日/本月热门轻小说(支持翻页)", category="6")
async def handle_hotnovel(msg, is_group=True):
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return

    parts = msg.raw_message.split()
    if len(parts) < 2:
        reply = "请输入查询类型喵~ 例如：/hotnovel day 或 /hotnovel month"
        await send_text(msg, reply, is_group=is_group)
        return

    rank_type = parts[1].lower()
    base_url = ""
    if rank_type == "day":
        base_url = "https://www.wenku8.net/modules/article/toplist.php?sort=dayvisit"
        type_name = "今日热门"
    elif rank_type in ["month", "mouth"]:
        base_url = "https://www.wenku8.net/modules/article/toplist.php?sort=monthvisit"
        type_name = "本月热门"
    else:
        reply = "目前只支持 day 或 month 喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    requested_count = 10
    if len(parts) >= 3:
        try:
            requested_count = int(parts[2])
            if requested_count <= 0:
                requested_count = 10
            if requested_count > 100:
                requested_count = 100
        except ValueError:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wenku8.net/",
        "Cookie": WENKU8_COOKIE
    }

    all_matches = []
    current_page = 1

    try:
        while len(all_matches) < requested_count:
            url = f"{base_url}&page={current_page}"
            response = get_sync(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            content = response.text

            if response.status_code == 403:
                _log.warning("热门榜单返回403错误，Cookie可能已失效或被反爬虫机制拦截")
                reply = "❌ 榜单获取失败，Cookie 可能已失效喵！\n请管理员使用 `/set_wenku_cookie <新Cookie>` 命令更新 Cookie 喵~"
                await send_text(msg, reply, is_group=is_group)
                return

            pattern = r'<div style="width:373px;height:136px;float:left;margin:5px 0px 5px 5px;">(.*?)</div>\s*</div>'
            page_matches = re.findall(pattern, content, re.DOTALL)

            if not page_matches:
                if current_page == 1:
                    if "出现错误" in content or (("登录" in content and "退出登录" not in content) or "login" in content.lower()):
                        reply = "❌ 榜单获取失败，Cookie 可能已失效喵！\n请管理员使用 `/set_wenku_cookie <新Cookie>` 命令更新 Cookie 喵~"
                    else:
                        reply = "没找到热门榜单喵，可能网页结构变了喵~"

                    await send_text(msg, reply, is_group=is_group)
                    return
                else:
                    break

            all_matches.extend(page_matches)
            if len(page_matches) < 20:
                break

            current_page += 1
            if current_page > 5:
                break

        results = []
        for match in all_matches[:requested_count]:
            title_url_match = re.search(r'<b><a style="font-size:13px;" href="([^"]+)" title="([^"]+)" target="_blank">', match)
            book_url = title_url_match.group(1) if title_url_match else ""
            title = title_url_match.group(2) if title_url_match else "未知"

            book_id = "0"
            id_match = re.search(r'/book/(\d+)\.htm', book_url)
            if id_match:
                book_id = id_match.group(1)

            node = int(book_id) // 1000

            author_cat_match = re.search(r'<p>作者:([^/]+)/分类:([^<]+)</p>', match)
            author = author_cat_match.group(1) if author_cat_match else "未知"
            category = author_cat_match.group(2) if author_cat_match else "未知"

            stats_match = re.search(r'<p>更新:([^/]+)/字数:([^/]+)/([^<]+)</p>', match)
            last_date = stats_match.group(1) if stats_match else "未知"
            word_count = stats_match.group(2) if stats_match else "未知"
            is_serialize = stats_match.group(3) if stats_match else "未知"

            tags_match = re.search(r'Tags:<span[^>]*>([^<]+)</span>', match)
            tags = tags_match.group(1) if tags_match else "无"

            intro_match = re.search(r'简介:([^<]+)', match)
            introduction = intro_match.group(1).strip() if intro_match else "暂无简介"

            img_match = re.search(r'<img src="([^"]+)"', match)
            cover_url = img_match.group(1) if img_match else f"https://img.wenku8.com/image/{node}/{book_id}/{book_id}s.jpg"

            download_url = f"https://dl.wenku8.com/down.php?type=txt&node={node}&id={book_id}"
            page_url = f"https://www.wenku8.net/book/{book_id}.htm"

            books[title] = {
                "author": author,
                "category": category,
                "last_date": last_date,
                "word_count": word_count,
                "is_serialize": is_serialize,
                "introduction": introduction,
                "tags": tags,
                "cover_url": cover_url,
                "download_url": download_url,
                "page": page_url,
                "hot": "热门榜单书籍"
            }

            results.append((author, title, download_url))

        from nbot.commands.novel.search import temp_selections
        temp_selections[msg.user_id] = results
        from nbot.commands.state import api_book
        api_book[msg.user_id] = {}

        cache_dir = os.path.join(load_address(), "novel_hot")
        os.makedirs(cache_dir, exist_ok=True)
        file_token = hashlib.md5(f"hotnovel_{rank_type}_{time.time()}".encode("utf-8")).hexdigest()[:8]
        filename = f"{file_token}_{type_name}.html"
        filepath = os.path.join(cache_dir, filename)

        build_novel_grid_html(f"{type_name} · 轻小说排行", filepath)

        for i, (author, title, download_url) in enumerate(results):
            book_id_match = re.search(r'id=(\d+)', download_url)
            book_id = book_id_match.group(1) if book_id_match else "0"
            append_novel_card(filepath, book_id, title, author, i + 1)

        close_novel_grid_html(filepath)

        if is_group:
            await msg.reply(text=f"✨ {type_name}前{len(results)}名喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
            await bot.api.post_group_file(msg.group_id, file=filepath)
        else:
            await bot.api.post_private_msg(msg.user_id, text=f"✨ {type_name}前{len(results)}名喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
            await bot.api.upload_private_file(msg.user_id, filepath, filename)

    except Exception as e:
        _log.error(f"Error in handle_hotnovel: {e}")
        reply = "获取热门榜单失败了喵，请稍后再试喵~"
        await send_text(msg, reply, is_group=is_group)


@register_command("/novel_res", help_text="/novel_res <res值> -> 根据res编号下载轻小说", category="6")
async def handle_novel_by_res(msg, is_group=True):
    res_value = msg.raw_message[len("/novel_res"):].strip()
    if not res_value:
        reply = "请输入要下载的res编号喵~例如：/novel_res 1121"
        await send_text(msg, reply, is_group=is_group)
        return

    target_title = None
    target_info = None
    for title, info in books.items():
        if str(info.get("res")) == res_value:
            target_title = title
            target_info = info
            break

    if not target_info:
        download_url = f"https://dl.wenku8.com/down.php?type=txt&node=1&id={res_value}"
        reply = f"已开始下载res为 {res_value} 的轻小说喵~"
        if is_group:
            await msg.reply(text=reply)
            await bot.api.post_group_file(msg.group_id, file=download_url)
        else:
            await bot.api.post_private_msg(msg.user_id, text=reply)
            await bot.api.upload_private_file(msg.user_id, file=download_url, name=f"{res_value}.txt")
        return

    download_url = target_info.get("download_url")
    if not download_url:
        reply = "该轻小说没有可用的下载链接喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    reply = f"已开始下载《{target_title}》喵~"
    if is_group:
        await msg.reply(text=reply)
        await bot.api.post_group_file(msg.group_id, file=download_url)
    else:
        await bot.api.post_private_msg(msg.user_id, text=reply)
        await bot.api.upload_private_file(msg.user_id, file=download_url, name=target_title + ".txt")


@register_command("/set_wenku_cookie", help_text="/set_wenku_cookie <Cookie> -> 更新文库8的Cookie(仅限管理员)", category="6", admin_show=True)
async def handle_set_wenku_cookie(msg, is_group=True):
    from nbot.commands.state import admin
    if str(msg.user_id) not in admin:
        reply = "主人，这个功能只有管理员才能使用喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    new_cookie = msg.raw_message[len("/set_wenku_cookie"):].strip()
    if not new_cookie:
        reply = "请输入新的 Cookie 喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    from nbot.commands.novel.wenku8_api import save_wenku8_cookie
    save_wenku8_cookie(new_cookie)
    reply = "✅ Cookie 更新成功喵！现在可以尝试使用 /hotnovel 喵~"
    await send_text(msg, reply, is_group=is_group)


def get_random_book_from_hotlist() -> tuple:
    """
    从今日热门榜单获取随机小说
    :return: (title, book_info_dict) 或 (None, None)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wenku8.net/",
        "Cookie": WENKU8_COOKIE
    }
    url = "https://www.wenku8.net/modules/article/toplist.php?sort=dayvisit&page=1"

    _log.info(f"获取热门榜单: {url}")
    try:
        response = get_sync(url, headers=headers, timeout=10)
        _log.info(f"热门榜单响应状态码: {response.status_code}")
        response.encoding = 'gbk'
        content = response.text

        pattern = r'<div style="width:373px;height:136px;float:left;margin:5px 0px 5px 5px;">(.*?)</div>\s*</div>'
        page_matches = re.findall(pattern, content, re.DOTALL)

        if not page_matches:
            return None, None

        match = random.choice(page_matches)

        title_url_match = re.search(r'<b><a style="font-size:13px;" href="([^"]+)" title="([^"]+)" target="_blank">', match)
        if not title_url_match:
            return None, None

        book_url = title_url_match.group(1)
        title = title_url_match.group(2)

        info = get_book_detail_by_url(book_url)
        if info is None:
            book_id_match = re.search(r'/book/(\d+)\.htm', book_url)
            book_id = book_id_match.group(1) if book_id_match else "0"
            node = int(book_id) // 1000 if book_id.isdigit() else 0

            author_cat_match = re.search(r'<p>作者:([^/]+)/分类:([^<]+)</p>', match)
            author = author_cat_match.group(1) if author_cat_match else "未知"

            info = {
                'author': author,
                'category': '未知',
                'word_count': '未知',
                'is_serialize': '未知',
                'last_date': '未知',
                'introduction': '暂无简介',
                'cover_url': f"https://img.wenku8.com/image/{node}/{book_id}/{book_id}s.jpg",
                'download_url': f"https://dl.wenku8.com/down.php?type=txt&node={node}&id={book_id}",
                'page': book_url,
                'hot': '今日热门'
            }

        return title, info
    except Exception as e:
        _log.error(f"获取随机小说失败: {e}")
        return None, None
