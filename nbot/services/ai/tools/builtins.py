"""内置工具执行器 - ToolExecutor 类及其内置工具方法."""
from typing import Dict, Any

from .news_tools import search_news
from .web_tools import search_web
from .exec_tools import exec_command
from .misc_tools import (
    get_weather,
    get_date_time,
    http_get,
    download_file,
    send_message,
    get_session_thinking_history,
)


class ToolExecutor:
    """工具执行器."""

    search_news = staticmethod(search_news)
    get_weather = staticmethod(get_weather)
    search_web = staticmethod(search_web)
    get_date_time = staticmethod(get_date_time)
    http_get = staticmethod(http_get)
    exec_command = staticmethod(exec_command)
    download_file = staticmethod(download_file)
    send_message = staticmethod(send_message)
    get_session_thinking_history = get_session_thinking_history
