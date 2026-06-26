"""Wenku8 API helpers for novel commands."""
import os

from nbot.utils.http_client import get_sync
from nbot.utils.logger import get_logger

_log = get_logger(__name__)

WENKU8_COOKIE = ""


def load_wenku8_cookie():
    global WENKU8_COOKIE
    if os.path.exists("wenku8_cookie.txt"):
        with open("wenku8_cookie.txt", "r", encoding="utf-8") as f:
            WENKU8_COOKIE = f.read().strip()


def save_wenku8_cookie(cookie):
    global WENKU8_COOKIE
    WENKU8_COOKIE = cookie
    with open("wenku8_cookie.txt", "w", encoding="utf-8") as f:
        f.write(cookie)


def check_wenku8_cookie() -> str:
    """
    检查 WENKU8_COOKIE 是否已设置
    :return: 如果未设置返回提示消息，否则返回 None
    """
    if not WENKU8_COOKIE:
        return "❌ Cookie 未设置喵！\n请管理员使用 `/set_wenku_cookie <Cookie>` 命令设置 Cookie 喵~\n或者去 www.wenku8.net 登录后获取 Cookie"
    return None


NOVEL_API_BASE_URLS = [
    "http://43.248.77.205:22222",
    "https://fq.shusan.cn",
]
_novel_api_base_url = None


def get_novel_api_base_url():
    global _novel_api_base_url
    if _novel_api_base_url:
        return _novel_api_base_url

    for base_url in NOVEL_API_BASE_URLS:
        try:
            url = f"{base_url.rstrip('/')}/api/search"
            res = get_sync(url, params={"key": "test", "tab_type": 3}, timeout=5)
            if not res.ok:
                continue
            data = res.json()
            if isinstance(data, dict) and isinstance(data.get("data"), dict):
                _novel_api_base_url = base_url.rstrip("/")
                return _novel_api_base_url
        except Exception:
            continue

    return None


def download_api_book(id, name):
    base_url = get_novel_api_base_url()
    if not base_url:
        _log.error("下载失败：没有可用的API地址")
        return
    url = f"{base_url}/api/content"
    params = {
        "tab": "下载",
        "book_id": id
    }
    try:
        response = get_sync(url, params=params, timeout=30)
    except Exception as e:
        _log.error(f"下载失败：{e}")
        return
    if response.status_code == 200:
        content = response.text
        path = os.path.join(os.path.dirname(__file__), "..", "..", "cache", "novel", f"{name}.txt")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            file.write(content)
    else:
        _log.error(f"下载失败，状态码：{response.status_code}")


def get_api_book_info(id):
    base_url = get_novel_api_base_url()
    if not base_url:
        _log.error("获取失败：没有可用的API地址")
        return None
    url = f"{base_url}/api/detail"
    params = {"book_id": id}
    try:
        response = get_sync(url, params=params, timeout=10)
    except Exception as e:
        _log.error(f"获取失败：{e}")
        return None
    if response.status_code == 200:
        raw = response.json()
        book = raw['data']['data']
        info = {
            'author': book['author'],
            'category': book['category'],
            'word_count': f"{int(book['word_number']):,}",
            'is_serialize': '连载中' if int(book['creation_status']) == 1 else '已完结',
            'hot': book['read_cnt_text'],
            'last_date': __import__('datetime').datetime.fromtimestamp(int(book['last_publish_time'])).strftime('%Y-%m-%d'),
            'download_url': f"https://tomato-novel-downloader.vercel.app/?book_id={book['book_id']}",
            'page': f"https://fanqienovel.com/page/{book['book_id']}",
            'cover': book['thumb_url'],
            'introduction': book['abstract'].replace('\n', ''),
            'title': book['book_name'],
        }
        return info
    else:
        _log.error(f"获取失败，状态码：{response.status_code}")
        return None


load_wenku8_cookie()
