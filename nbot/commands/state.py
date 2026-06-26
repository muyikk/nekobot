"""Shared mutable state for the commands package.

Centralizes all global variables to avoid circular imports between
nbot.commands submodules and nbot.commands.py.
"""

from typing import Any, Dict, List

#: Mapping of command tuples to handler functions.
command_handlers: Dict[tuple, Any] = {}

#: List of admin QQ IDs (strings).
admin: List[str] = []

#: Comic blacklist structured by scope.
black_list_comic: Dict[str, Any] = {"global": [], "groups": {}, "users": {}}

#: Running chat state per user {user_id: dict}.
running: Dict[str, Any] = {}

#: Active asyncio tasks per user {user_id: Task}.
tasks: Dict[str, Any] = {}

#: User favorites {user_id: [comic_ids]}.
user_favorites: Dict[str, List[str]] = {}

#: Group favorites {group_id: {user_id: [comic_ids]}}.
group_favorites: Dict[str, Dict[str, List[str]]] = {}

#: In-memory cache of recently listed comic IDs.
comic_cache: List[str] = []

#: API book search results {user_id: {book_id: book_name}}.
api_book: Dict[str, Any] = {}

#: Scheduled task storage {name: Task}.
schedule_tasks: Dict[str, Any] = {}

#: SMTP configuration {user_id or "global": dict}.
smtp_config: Dict[str, Any] = {}

#: User email addresses {user_id: email}.
user_email: Dict[str, str] = {}

#: Groups where @all is enabled.
at_all_group: List[str] = []

#: Novel/books data {title: info_dict}.
books: Dict[str, Any] = {}

#: Whether TTS is enabled globally.
if_tts: bool = False
