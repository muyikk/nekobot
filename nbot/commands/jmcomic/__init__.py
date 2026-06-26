"""JM comic subpackage."""
from nbot.commands.jmcomic.rank import handle_jmrank
from nbot.commands.jmcomic.search import handle_search, handle_tag
from nbot.commands.jmcomic.download import handle_jmcomic, download_and_send_comic
from nbot.commands.jmcomic.favorites import (
    handle_add_favorite,
    handle_list_favorites,
    handle_del_favorite,
)
from nbot.commands.jmcomic.blacklist import (
    handle_add_black_list,
    handle_add_global_black_list,
    handle_del_global_black_list,
    handle_del_black_list,
    handle_list_black_list,
)
from nbot.commands.jmcomic.settings import (
    handle_jm_clear,
    handle_jm_send_user,
    handle_jm_send,
    handle_jm_pwd,
    handle_jm_email,
    handle_get_fav,
)
from nbot.commands.jmcomic.html_builder import (
    build_jm_grid_html,
    append_jm_card,
    close_jm_grid_html,
    fetch_cover_url,
)

__all__ = [
    "handle_jmrank",
    "handle_search",
    "handle_tag",
    "handle_jmcomic",
    "download_and_send_comic",
    "handle_add_favorite",
    "handle_list_favorites",
    "handle_del_favorite",
    "handle_add_black_list",
    "handle_add_global_black_list",
    "handle_del_global_black_list",
    "handle_del_black_list",
    "handle_list_black_list",
    "handle_jm_clear",
    "handle_jm_send_user",
    "handle_jm_send",
    "handle_jm_pwd",
    "handle_jm_email",
    "handle_get_fav",
    "build_jm_grid_html",
    "append_jm_card",
    "close_jm_grid_html",
    "fetch_cover_url",
]
