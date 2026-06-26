"""Novel subpackage."""
from nbot.commands.novel.search import handle_find_book, handle_find_author
from nbot.commands.novel.info import handle_select_book, handle_info
from nbot.commands.novel.hot import (
    handle_random_novel,
    handle_hotnovel,
    handle_novel_by_res,
    handle_set_wenku_cookie,
)
from nbot.commands.novel.html_builder import (
    build_novel_grid_html,
    append_novel_card,
    close_novel_grid_html,
    build_novel_detail_html,
)
from nbot.commands.novel.wenku8_api import (
    load_wenku8_cookie,
    save_wenku8_cookie,
    check_wenku8_cookie,
    get_novel_api_base_url,
    download_api_book,
    get_api_book_info,
)

__all__ = [
    "handle_find_book",
    "handle_find_author",
    "handle_select_book",
    "handle_info",
    "handle_random_novel",
    "handle_hotnovel",
    "handle_novel_by_res",
    "handle_set_wenku_cookie",
    "build_novel_grid_html",
    "append_novel_card",
    "close_novel_grid_html",
    "build_novel_detail_html",
    "load_wenku8_cookie",
    "save_wenku8_cookie",
    "check_wenku8_cookie",
    "get_novel_api_base_url",
    "download_api_book",
    "get_api_book_info",
]
