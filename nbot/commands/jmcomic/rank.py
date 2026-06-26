"""JM comic rank command."""
import hashlib
import html
import os
import time

from jmcomic import JmMagicConstants, JmOption
from jmcomic.jmcomic import JmCategoryPage

from nbot.commands import bot, switch
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import load_address
from nbot.commands.jmcomic.html_builder import (
    build_jm_grid_html,
    append_jm_card,
    close_jm_grid_html,
)
from nbot.utils.message_sender import send_text, send_file
from nbot.commands.state import comic_cache

JM_RANK_DECODE_LIMIT = 50


@register_command("/jmrank", help_text="/jmrank <月排行/周排行> -> 获取排行榜", category="1")
async def handle_jmrank(msg, is_group=True):
    await send_text(msg, "正在获取排行喵~", is_group=is_group)
    select = msg.raw_message[len("/jmrank"):].strip()
    op = JmOption.default()
    cl = op.new_jm_client()
    page: JmCategoryPage = cl.categories_filter(
        page=1,
        time=JmMagicConstants.TIME_ALL,
        category=JmMagicConstants.CATEGORY_ALL,
        order_by=JmMagicConstants.ORDER_BY_LATEST,
    )
    if select == "月排行":
        page: JmCategoryPage = cl.month_ranking(1)
    elif select == "周排行":
        page: JmCategoryPage = cl.week_ranking(1)
    else:
        page: JmCategoryPage = cl.week_ranking(1)
    cache_dir = os.path.join(load_address(), "rank")
    os.makedirs(cache_dir, exist_ok=True)
    file_token = hashlib.md5(f"{select}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{select}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    build_jm_grid_html(f"{html.escape(select)} · JM 排行", filepath)

    tot = 0
    for aid, atitle in page:
        tot += 1
        append_jm_card(filepath, aid, atitle, tot, client=cl)
        comic_cache.append(aid)
        if tot >= JM_RANK_DECODE_LIMIT:
            break

    close_jm_grid_html(filepath)

    if not os.path.exists(filepath):
        await send_text(msg, "获取排行失败喵~，文件不存在", is_group=is_group)
        return
    await send_file(msg, filepath, is_group=is_group, filename=filename)
