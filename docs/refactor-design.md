# NekoBot Refactor Design Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine NekoBot's directory structure, improve code readability, enforce a 500-line file limit, unify logging, update `.gitignore`, and extract shared utilities.

**Architecture:** Extract cross-cutting concerns into a dedicated `nbot/utils/` package. Split monolithic files by responsibility. Introduce a single unified logging facade. Keep the bot runnable after each incremental phase.

**Tech Stack:** Python 3.13+, Flask, SocketIO, ncatbot, Rich, APScheduler, jmcomic.

## Global Constraints

- Every `.py` file must be at most 500 lines. No exceptions.
- All new code must use type hints and docstrings (Google style).
- Import ordering: stdlib > third-party > local (absolute) > local (relative).
- No `print()` in production code; use the unified logger.
- No duplicated config parsing or API key resolution.
- HTTP client consolidation: standardize on `httpx` for new async code; keep `requests` for sync, wrap in a single module.

---

## 1. Target Directory Layout

```
nekobot/
|-- bot.py                          # Entry point (keep small, <250 lines)
|-- .env.example                    # Template for environment variables
|-- .gitignore                      # Updated with all runtime artifacts
|-- downloads/                      # NEW: unified classified downloaded resources
|-- docs/
|   |-- refactor-design.md          # This document
|
|-- nbot/
|   |-- __init__.py
|   |-- config.py                   # Replaces nbot/config.py; central config loader
|   |
|   |-- utils/                      # NEW: shared cross-cutting utilities
|   |   |-- __init__.py
|   |   |-- logger.py               # Unified logging setup
|   |   |-- paths.py                # Project root, cache dir, workspace dir helpers
|   |   |-- http_client.py          # Consolidated HTTP (requests/httpx/aiohttp wrapper)
|   |   |-- base64_image.py         # Image file -> base64 data URL
|   |   |-- message_sender.py       # Dual group/private send helper
|   |   |-- sandbox_bridge.py       # QQ macOS sandbox hard-link bridge
|   |   |-- email_sender.py         # SMTP email sending
|   |   |-- switch_manager.py       # Group/user feature toggle persistence
|   |   |-- validators.py           # API result validation helpers
|   |
|   |-- core/                       # Core business logic
|   |   |-- __init__.py
|   |   |-- ai_pipeline.py          # Split into <=500 line pieces
|   |   |-- workspace.py            # Split into <=500 line pieces
|   |   |-- ... (other existing core modules)
|   |
|   |-- services/                   # AI services and tools
|   |   |-- __init__.py
|   |   |-- ai.py                   # AI client wrapper
|   |   |-- tools/                  # Split nbot/services/tools.py
|   |   |   |-- __init__.py
|   |   |   |-- registry.py         # Tool registry (from tool_registry.py)
|   |   |   |-- executor.py         # Tool execution dispatcher
|   |   |   |-- definitions.py      # TOOL_DEFINITIONS + WORKSPACE_TOOL_DEFINITIONS
|   |   |   |-- builtins.py         # ToolExecutor class methods
|   |   |   |-- workspace_tools.py  # _execute_workspace_tool and helpers
|   |   |   |-- memory_tools.py     # _execute_save_to_memory / _execute_read_memory
|   |   |   |-- pending_exec.py     # store_pending_execution / execute_pending_command
|   |   |   |-- todo_tools.py       # (existing)
|   |   |-- chat_service.py         # Chat orchestration
|   |   |-- ...
|   |
|   |-- commands/                   # NEW: split nbot/commands.py
|   |   |-- __init__.py             # Re-exports for backward compat
|   |   |-- registry.py             # @register_command + command_handlers dict
|   |   |-- dispatch.py             # dispatch_message, is_at_bot, message parsing
|   |   |-- admin.py                # Admin commands: /set_admin, /del_admin, etc.
|   |   |-- system.py               # /restart, /shutdown, /agree
|   |   |-- jmcomic/                # JM comic commands
|   |   |   |-- __init__.py
|   |   |   |-- rank.py             # /jmrank
|   |   |   |-- search.py           # /jm_search, /jm_tag
|   |   |   |-- download.py         # /jm, download_and_send_comic
|   |   |   |-- favorites.py        # /add_fav, /list_fav, /del_fav
|   |   |   |-- blacklist.py        # /add_black_list, /del_black_list, etc.
|   |   |   |-- settings.py         # /jm_send, /jm_pwd, /jm_email, /jm_send_user
|   |   |   |-- html_builder.py     # build_jm_grid_html, append_jm_card, close_jm_grid_html
|   |   |-- novel/                  # Light novel commands
|   |   |   |-- __init__.py
|   |   |   |-- search.py           # /findbook, /fa
|   |   |   |-- info.py             # /info
|   |   |   |-- hot.py              # /hotnovel, /random_novel
|   |   |   |-- download.py         # /novel_res, /select
|   |   |   |-- html_builder.py     # build_novel_grid_html, build_novel_detail_html
|   |   |   |-- wenku8_api.py       # get_novel_api_base_url, find_book_from_api, etc.
|   |   |-- media/                  # Media commands
|   |   |   |-- __init__.py
|   |   |   |-- image.py            # /random_image, /st, /loli, /r18, /di
|   |   |   |-- video.py            # /random_video, /dv, /df
|   |   |   |-- music.py            # /music, /random_music
|   |   |   |-- dice_rps.py         # /random_dice, /random_rps
|   |   |   |-- generate_photo.py   # /generate_photo
|   |   |-- chat/                   # Chat-related commands
|   |   |   |-- __init__.py
|   |   |   |-- tts.py              # /tts
|   |   |   |-- del_message.py      # /del_message
|   |   |   |-- translate.py        # /translate
|   |   |   |-- fortune.py          # /fortune
|   |   |   |-- remind.py           # /remind, /premind
|   |   |   |-- task.py             # /task, /list_tasks, /cancel_tasks
|   |   |-- mc/                     # Minecraft commands
|   |   |   |-- __init__.py
|   |   |   |-- status.py           # /mc, /mc_bind, /mc_unbind, /mc_show
|   |   |-- help.py                 # /help, get_all_help_text_for_prompt
|   |   |-- bot_api.py              # /bot (raw bot.api wrapper)
|   |   |-- at_all.py               # /at_all
|   |   |-- workspace_cmds.py       # /workspace, /ws_send
|   |   |-- smtp.py                 # /smtp
|   |   |-- wenku_cookie.py         # /set_wenku_cookie
|   |   |-- file_sender.py          # async_send_file, handle_generic_file
|   |   |-- email.py                # send_comic_email, _send_comic_email_sync
|   |   |-- scheduler.py            # schedule_task, schedule_task_by_date, schedule_job_task
|   |   |-- chatter.py              # chatter, chat_loop, update_user_active_chat_time
|   |   |-- data_persistence.py     # load_favorites, save_favorites, load_admin, write_admin, etc.
|   |   |-- message_patches.py      # BotAPI patch for message recording
|   |   |-- qq_sandbox.py           # QQ sandbox bridge wrappers
|   |
|   |-- web/                        # Web server and routes
|   |   |-- __init__.py
|   |   |-- server.py               # Split into <=500 line pieces
|   |   |-- ai_service.py           # Split into <=500 line pieces
|   |   |-- routes/
|   |   |   |-- personality.py      # Split into <=500 line pieces
|   |   |   |-- sessions.py         # Split into <=500 line pieces
|   |   |   |-- ...
|   |   |-- utils/
|   |   |   |-- config_loader.py    # Removed; use nbot.config instead
|   |   |   |-- ...
|   |
|   |-- cli/                        # CLI interface
|   |   |-- __init__.py
|   |   |-- app.py                  # Entry point
|   |   |-- screens.py              # Split cli_cc_style.py screens
|   |   |-- components.py           # Split cli_cc_style.py components
|   |   |-- styles.py               # Split cli_cc_style.py styles/appearance
|   |   |-- completer.py            # Command completer from prompt_toolkit
|   |
|   |-- plugins/                    # Message plugins
|   |   |-- __init__.py
|   |   |-- bilibili_parser.py
|   |   |-- douyin_parser.py
|   |   |-- dispatcher.py
|   |
|   |-- ai_commands.py              # Split into <=500 line pieces
|   |-- cli_cc_style.py             # Split into <=500 line pieces
|   |-- cli_simple.py               # Keep or split if >500 lines
|   |-- heartbeat.py                # Keep
|   |-- chat.py                     # Keep
```

### Directory Responsibility Mapping

| Directory | Responsibility |
|-----------|----------------|
| `nbot/utils/` | Cross-cutting utilities: logging, paths, config, HTTP, base64, message sending, sandbox bridge, email, switches, validation. No business logic. |
| `downloads/` | **NEW:** Unified root for all classified downloaded resources (videos, images, PDFs, audio, others). |
| `nbot/core/` | Core domain logic: AI pipeline, workspace, chat models, message middleware, knowledge, character engine. |
| `nbot/services/` | Service layer: AI client, tools, chat orchestration, TTS, STT. |
| `nbot/services/tools/` | Tool definitions, execution, registry, workspace tools, memory tools. |
| `nbot/commands/` | QQ command handlers split by domain (admin, system, jmcomic, novel, media, chat, mc). |
| `nbot/web/` | Flask/SocketIO server, routes, AI service for web. |
| `nbot/cli/` | Rich-based TUI. |
| `nbot/plugins/` | Message parsers (Bilibili, Douyin). |
| `nbot/channels/` | Channel adapters (QQ, Web, Feishu, Telegram). |
| `nbot/character/` | Character engine (planner, compiler, runtime, memory). |

---

## 2.5 Additional Nested Folders for Clearer Structure

To make the project structure clearer without adding too much depth, add one more level of nesting inside the following modules:

```text
nbot/
|-- core/
|   |-- pipeline/          # AI pipeline files
|   |   |-- pipeline.py
|   |   |-- callbacks.py
|   |   |-- tools.py
|   |-- workspace/         # Workspace files
|   |   |-- manager.py
|   |   |-- file_ops.py
|   |   |-- utils.py
|   |-- memory/            # Message history & memory
|   |   |-- message_history.py
|   |   |-- message_middleware.py
|   |   |-- auto_memory.py
|   |-- prompt/            # Prompt management
|   |   |-- prompt.py
|   |-- agent/             # Agent service & tool loop
|   |   |-- agent_service.py
|   |   |-- tool_loop.py
|   |-- parser/            # File parsing
|   |   |-- file_parser.py
|
|-- services/
|   |-- ai/                # AI client, chat orchestration, tools
|   |   |-- ai.py
|   |   |-- chat_service.py
|   |   |-- tools/
|   |-- channels/          # Channel-specific services
|   |   |-- telegram_service.py
|   |   |-- feishu_service.py
|   |   |-- feishu_ws_service.py
|   |   |-- feishu_chat_service.py
|   |-- audio/             # TTS & STT
|   |   |-- tts.py
|   |   |-- stt.py
|   |-- executor/          # Dynamic code execution
|   |   |-- dynamic_executor.py
|
|-- web/
|   |-- ai/                # Web AI service pieces
|   |   |-- service.py
|   |   |-- tools.py
|   |   |-- images.py
|   |   |-- trigger.py
|   |-- routes/
|   |   |-- chat/          # Session/chat routes
|   |   |   |-- sessions.py
|   |   |   |-- sessions_utils.py
|   |   |-- persona/       # Personality, character, Live2D routes
|   |   |   |-- personality.py
|   |   |   |-- compile.py
|   |   |   |-- platform.py
|   |   |   |-- characters.py
|   |   |   |-- live2d.py
|   |   |-- config/        # Configuration routes
|   |   |   |-- channels.py
|   |   |   |-- ai_models.py
|   |   |   |-- admin_misc.py
|   |   |-- system/        # Auth/admin routes
|   |   |   |-- auth.py
|   |   |   |-- admin.py
|
|-- commands/
|   |-- shared/            # Command-layer infrastructure
|   |   |-- data_persistence.py
|   |   |-- scheduler.py
|   |   |-- chatter.py
|   |   |-- message_patches.py
|   |   |-- qq_sandbox.py
|   |   |-- file_sender.py
|   |   |-- email.py
|   |-- ai/                # AI-enhanced slash commands (was ai_commands.py)
|   |   |-- registry.py
|   |   |-- handlers.py
|   |   |-- utils.py
```

### Nesting Principles

1. **Single responsibility per folder** — keep files that change together in the same package.
2. **No excessive depth** — only one extra level; keep import paths readable.
3. **Backward compatibility** — re-export public symbols from parent `__init__.py` where needed.
4. **500-line limit still applies** — nesting is for grouping, not for hiding large files.

### Additional Directory Responsibilities

| Directory | Responsibility |
|-----------|----------------|
| `nbot/core/pipeline/` | AI pipeline, callbacks, tool loop integration. |
| `nbot/core/workspace/` | Workspace manager and file operations. |
| `nbot/core/memory/` | Message history, middleware, automatic memory. |
| `nbot/core/prompt/` | Prompt construction and management. |
| `nbot/core/agent/` | Agent service and tool loop. |
| `nbot/core/parser/` | Multi-format file parser. |
| `nbot/services/ai/` | AI client, chat orchestration, tool set. |
| `nbot/services/channels/` | Telegram, Feishu channel services. |
| `nbot/services/audio/` | TTS, STT. |
| `nbot/services/executor/` | Sandboxed dynamic code execution. |
| `nbot/web/ai/` | Web AI service pieces. |
| `nbot/web/routes/chat/` | Session-related routes. |
| `nbot/web/routes/persona/` | Personality, character, Live2D routes. |
| `nbot/web/routes/config/` | Channel, model, misc config routes. |
| `nbot/web/routes/system/` | Authentication, admin routes. |
| `nbot/commands/shared/` | Command-layer shared infrastructure. |
| `nbot/commands/ai/` | AI-enhanced slash commands. |

---

## 2. Shared Utility Modules to Extract

### 2.1 `nbot/utils/logger.py` — Unified Logging

**Replaces:**
- `from ncatbot.utils.logger import get_log` in `bot.py`, `commands.py`
- `import logging; _log = logging.getLogger(__name__)` in ~45 files
- Manual logger suppression in `cli_cc_style.py`
- `CharacterEventLogger` custom logger

**Public API:**
```python
from nbot.utils.logger import get_logger, setup_logging, silence_loggers

def get_logger(name: str) -> logging.Logger:
    """Get a logger with the unified configuration."""

def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
    console: bool = True,
    json_format: bool = False,
) -> None:
    """Configure root logger with rotating file handler + optional console."""

def silence_loggers(*names: str, level: int = logging.CRITICAL + 1) -> None:
    """Suppress noisy third-party loggers (werkzeug, urllib3, etc.)."""
```

**Behavior:**
- One-time `dictConfig` or `logging.basicConfig` call at startup.
- All modules use `from nbot.utils.logger import get_logger; _log = get_logger(__name__)`.
- CLI mode calls `silence_loggers("nbot", "werkzeug", "urllib3", ...)` before importing other modules.
- Log format includes timestamp, level, logger name, and a `[server|cli|qq]` context tag.

### 2.2 `nbot/utils/paths.py` — Path Resolution

**Replaces:**
- `load_address()` in `commands.py` (used 20+ times)
- `os.path.join(os.path.dirname(__file__), ...)` scattered everywhere
- `_get_project_root()` in `commands.py`

**Public API:**
```python
from nbot.utils.paths import get_project_root, get_cache_dir, get_data_dir, get_workspace_dir, get_resources_dir

def get_project_root() -> str:
def get_cache_dir(subpath: str = "") -> str:
def get_data_dir(subpath: str = "") -> str:
def get_downloads_dir(subpath: str = "") -> str:
def get_workspace_dir() -> str:
def get_resources_dir(subpath: str = "") -> str:
def normalize_file_path(path: str) -> str:  # from commands.py
```

### 2.3 `nbot/config.py` — Single Environment Configuration

**Decision:** After the refactor, the project will use **only one environment file: `.env`**. `config.ini` and `config.example.ini` are deprecated and will be removed.

**Replaces:**
- `configparser.ConfigParser()` in `services/ai.py`, `commands.py`, `web/ai_service.py`, `web/utils/config_loader.py`
- `python-dotenv` loading scattered in `bot.py`
- `resolve_runtime_api_key()` duplicated in `services/ai.py` and `web/utils/config_loader.py`
- The existing `nbot/config.py` compatibility shim

**Public API:**
```python
from nbot.config import get_config, Config

class Config:
    """Singleton settings loaded from .env (with optional os.environ overrides)."""
    def get(self, key: str, fallback: str = "") -> str:
    def get_int(self, key: str, fallback: int = 0) -> int:
    def get_bool(self, key: str, fallback: bool = False) -> bool
    def get_list(self, key: str, sep: str = ",", fallback: list | None = None) -> list[str]
    def get_section(self, prefix: str) -> dict[str, str]
    def reload(self) -> None

def get_config() -> Config
```

**.env key naming convention:**
- Use `UPPER_SNAKE_CASE` keys.
- Group related settings with a section prefix and double underscore, e.g.:
  - `BOT_UIN`, `WS_URI`, `TOKEN`
  - `WEB_HOST`, `WEB_PORT`, `WEB_DEBUG`
  - `AI_PROVIDER`, `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`
  - `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`
  - `DOWNLOAD_MAX_AGE_DAYS`, `DOWNLOAD_MAX_TOTAL_SIZE_MB`
- `.env.example` is the single canonical template. It must contain every supported key with empty/default values and comments.

**Migration from `config.ini`:**
1. Provide a one-time migration script `tools/migrate_config_ini_to_env.py` that reads `config.ini` and appends equivalent keys to `.env` using the new naming convention.
2. Update every `config.get(section, key)` or `ConfigParser()` usage to `get_config().get("SECTION__KEY")` / `get_config().get_section("SECTION__")`.
3. Delete all `config.ini` references from production code. Keep `config.ini` in `.gitignore` so existing files do not accidentally get committed, but the application will no longer read it.
4. Remove `config.example.ini` from the repository; keep `.env.example` as the only environment template.

### 2.4 `nbot/utils/http_client.py` — Consolidated HTTP

**Replaces:**
- Mixed `requests`, `aiohttp`, `httpx` usage across the codebase.
- `urllib.request` in `services/tools.py`.

**Public API:**
```python
from nbot.utils.http_client import get_sync, post_sync, get_async, post_async, download_file

def get_sync(url: str, **kwargs) -> requests.Response:
def post_sync(url: str, **kwargs) -> requests.Response:
async def get_async(url: str, **kwargs) -> httpx.Response:
async def post_async(url: str, **kwargs) -> httpx.Response:
def download_file(url: str, dest: str, timeout: int = 60) -> str:
```

**Migration rule:** New code uses `httpx` for async. Existing `requests` calls are wrapped through this module. No new `aiohttp` or `urllib.request` usage.

### 2.5 `nbot/utils/base64_image.py` — Image Encoding

**Replaces:**
- Duplicated `base64.b64encode(...)` blocks in 6+ files (`commands.py`, `services/ai.py`, etc.)

**Public API:**
```python
from nbot.utils.base64_image import image_to_base64_url, file_to_base64_url

def image_to_base64_url(image_source: str) -> str:
    """Convert local image path or URL to base64 data URL."""

def file_to_base64_url(file_path: str, mime_type: str = "application/octet-stream") -> str:
    """Convert any file to base64 data URL."""
```

### 2.6 `nbot/utils/message_sender.py` — Dual Send Helper

**Replaces:**
- Repeated `if is_group: await msg.reply(...) else: await bot.api.post_private_msg(...)` pattern in `commands.py` (dozens of occurrences).

**Public API:**
```python
from nbot.utils.message_sender import send_text, send_file, reply_to

async def send_text(msg, text: str, is_group: bool = True) -> None:
async def send_file(msg, file_path: str, is_group: bool = True, filename: str = None) -> None:
async def reply_to(msg, text: str, is_group: bool = True) -> None:
```

### 2.7 `nbot/utils/sandbox_bridge.py` — QQ Sandbox Bridge

**Replaces:**
- `_should_bridge()`, `_bridge_to_qq_sandbox()`, `_wrap_botapi_upload()` in `commands.py`.

**Public API:**
```python
from nbot.utils.sandbox_bridge import apply_qq_sandbox_bridge

def apply_qq_sandbox_bridge() -> None:
    """Patch BotAPI upload methods to hard-link files into QQ sandbox."""
```

### 2.8 `nbot/utils/email_sender.py` — SMTP Email

**Replaces:**
- `_send_comic_email_sync()`, `send_comic_email()` in `commands.py`.

**Public API:**
```python
from nbot.utils.email_sender import send_email, load_smtp_config, save_smtp_config

async def send_email(to_addr: str, subject: str, body: str, attachment_path: str = None, smtp_config: dict = None) -> bool:
```

### 2.9 `nbot/utils/switch_manager.py` — Feature Toggles

**Replaces:**
- `SwitchManager` class in `commands.py`.

**Public API:**
```python
from nbot.utils.switch_manager import get_switch_manager

class SwitchManager:
    def get_switch_state(self, switch_name: str, group_id: str = None, user_id: str = None) -> bool:
    def set_switch_state(self, switch_name: str, state: bool, group_id: str = None, user_id: str = None) -> None:
    def toggle_switch(self, switch_name: str, group_id: str = None, user_id: str = None) -> bool:
    def save_switches(self) -> None:
    def load_switches(self) -> None:

def get_switch_manager() -> SwitchManager:
```

### 2.10 `nbot/utils/validators.py` — API Result Validation

**Replaces:**
- Ad-hoc `if response.status_code == 200` checks scattered across files.

**Public API:**
```python
from nbot.utils.validators import validate_api_response, is_success_response

def validate_api_response(response, expected_status: int = 200) -> dict:
```

---

## 3. File Splitting Strategy

### 3.1 `nbot/commands.py` (~4765 lines -> ~10-15 files, each <=500 lines)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/commands/registry.py` | ~80 | `register_command`, `command_handlers`, `get_all_help_text_for_prompt` |
| `nbot/commands/dispatch.py` | ~450 | `dispatch_message`, `is_at_bot`, `_bot_uin_candidates`, `_iter_mention_ids`, `_iter_message_segments`, `_is_at_all_enabled`, image/video URL extraction, file saving to workspace, Bilibili/Douyin plugin dispatch |
| `nbot/commands/shared/data_persistence.py` | ~200 | `load_favorites`, `save_favorites`, `load_admin`, `write_admin`, `load_blak_list`, `write_blak_list`, `load_running`, `write_running`, `load_smtp_config`, `save_smtp_config`, `load_email_config`, `save_email_config`, `read_at_all_group`, `write_at_all_group` |
| `nbot/commands/shared/scheduler.py` | ~150 | `schedule_task`, `schedule_task_by_date`, `schedule_job_task` |
| `nbot/commands/shared/chatter.py` | ~150 | `chatter`, `chat_loop`, `update_user_active_chat_time`, `update_running` |
| `nbot/commands/shared/message_patches.py` | ~120 | BotAPI message recording patches (post_private_msg, post_group_msg, reply wrappers) |
| `nbot/commands/shared/qq_sandbox.py` | ~120 | `_should_bridge`, `_bridge_to_qq_sandbox`, `_wrap_botapi_upload` |
| `nbot/commands/admin.py` | ~200 | `/set_admin`, `/del_admin`, `/get_admin`, `/set_ids`, `/set_online_status`, `/get_friends`, `/set_qq_avatar`, `/send_like`, `/set_group_admin`, `/del_group_admin`, `/agree` |
| `nbot/commands/system.py` | ~100 | `/restart`, `/shutdown` |
| `nbot/commands/jmcomic/` | ~800 total | All JM comic commands split into submodules |
| `nbot/commands/novel/` | ~700 total | All light novel commands split into submodules |
| `nbot/commands/media/` | ~500 total | Image, video, music, dice, photo generation |
| `nbot/commands/chat/` | ~400 total | TTS, del_message, translate, fortune, remind, task |
| `nbot/commands/mc/` | ~150 total | Minecraft status commands |
| `nbot/commands/help.py` | ~150 | `/help` command |
| `nbot/commands/bot_api.py` | ~100 | `/bot` raw API wrapper |
| `nbot/commands/at_all.py` | ~80 | `/at_all` |
| `nbot/commands/workspace_cmds.py` | ~150 | `/workspace`, `/ws_send` |
| `nbot/commands/smtp.py` | ~150 | `/smtp` config command |
| `nbot/commands/wenku_cookie.py` | ~80 | `/set_wenku_cookie` |
| `nbot/commands/shared/file_sender.py` | ~150 | `async_send_file`, `handle_generic_file` |
| `nbot/commands/shared/email.py` | ~100 | `send_comic_email`, `_send_comic_email_sync` |
| `nbot/commands/__init__.py` | ~100 | Re-exports, imports all submodules to register commands |

**`nbot/commands/__init__.py` backward compatibility:**
```python
# nbot/commands/__init__.py
from nbot.commands.registry import register_command, command_handlers, get_all_help_text_for_prompt
from nbot.commands.dispatch import dispatch_message, handle_group_message, handle_private_message
from nbot.commands.data_persistence import load_favorites, save_favorites, ...
# ... etc
# This preserves `from nbot.commands import register_command` usage in ai_commands.py
```

### 3.2 `nbot/web/server.py` (~3031 lines -> ~8 files, each <=500 lines)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/web/server.py` | ~450 | `create_web_app`, `WebChatServer.__init__`, `_register_routes`, `_register_auth_middleware`, `_register_socket_events`, `_extract_request_token`, `_enforce_api_auth` |
| `nbot/web/server_auth.py` | ~250 | `_hash_token`, `_generate_login_token`, `_validate_login_token`, `_cleanup_expired_tokens`, `_save_login_tokens`, `_check_login_rate_limit`, `_record_login_failure`, `_reset_login_failures`, `_verify_password` |
| `nbot/web/server_ai.py` | ~450 | `_initialize_ai_client`, `_load_ai_config`, `_apply_ai_model`, `_load_ai_models` |
| `nbot/web/server_heartbeat.py` | ~350 | `_init_heartbeat_scheduler`, `_start_heartbeat_job`, `_stop_heartbeat_job`, `_execute_heartbeat`, `_load_heartbeat_content`, `_send_heartbeat_to_target`, `_build_heartbeat_user_message`, `_build_heartbeat_assistant_message` |
| `nbot/web/server_workflow.py` | ~450 | `_init_workflow_scheduler`, `_schedule_workflow`, `_unschedule_workflow`, `_validate_workflow`, `_mark_workflow_status`, `_execute_workflow`, `_create_workflow_session`, `_send_workflow_result`, `trigger_workflow_by_message` |
| `nbot/web/server_task.py` | ~350 | `_init_custom_task_scheduler`, `_build_custom_task_trigger`, `_validate_custom_task`, `_mark_task_status`, `_schedule_custom_task`, `_unschedule_custom_task`, `_get_custom_task`, `_execute_custom_task`, `get_task_center_items` |
| `nbot/web/server_knowledge.py` | ~200 | `_retrieve_knowledge`, `_keyword_search`, `_check_knowledge_index` |
| `nbot/web/server_qq_sync.py` | ~150 | `sync_qq_messages`, `_auto_start_feishu_ws_channels` |
| `nbot/web/server_personality.py` | ~250 | `_load_personality`, `_load_custom_personality_presets` |
| `nbot/web/server_message.py` | ~200 | `_generate_session_name`, `_build_workflow_user_message`, `_build_workflow_assistant_message`, `_build_web_manager_payload` |
| `nbot/web/server_utils.py` | ~150 | `_format_uptime`, `_start_background_initialization`, `parse_document_with_mineru` |

**`WebChatServer` becomes a thin coordinator:**
```python
# nbot/web/server.py
class WebChatServer:
    def __init__(self, app, socketio):
        # ... basic setup ...
        from nbot.web.server_auth import AuthMixin
        from nbot.web.server_ai import AIMixin
        from nbot.web.server_heartbeat import HeartbeatMixin
        # ... etc
        # Or use composition: self.auth = AuthManager(self)
```

### 3.3 `nbot/cli_cc_style.py` (~2880 lines -> ~5 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/cli/app.py` | ~150 | Entry point, `CCStyleCLI.run()` |
| `nbot/cli/screens.py` | ~450 | Screen classes (main, chat, settings, etc.) |
| `nbot/cli/components.py` | ~450 | Reusable UI components (panels, tables, etc.) |
| `nbot/cli/styles.py` | ~200 | Color schemes, theme definitions, ASCII art |
| `nbot/cli/completer.py` | ~200 | `CommandCompleter` for prompt_toolkit |
| `nbot/cli/utils.py` | ~150 | `escape_rich_tags`, `PYFIGLET_AVAILABLE` check, etc. |

### 3.4 `nbot/services/tools.py` (~2310 lines -> ~7 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/services/ai/tools/definitions.py` | ~400 | `TOOL_DEFINITIONS`, `WORKSPACE_TOOL_DEFINITIONS` |
| `nbot/services/ai/tools/builtins.py` | ~500 | `ToolExecutor` class with static methods |
| `nbot/services/ai/tools/executor.py` | ~200 | `execute_tool()`, tool dispatch logic |
| `nbot/services/ai/tools/workspace_tools.py` | ~450 | `_execute_workspace_tool()` and all workspace operations |
| `nbot/services/ai/tools/memory_tools.py` | ~150 | `_execute_save_to_memory()`, `_execute_read_memory()` |
| `nbot/services/ai/tools/pending_exec.py` | ~150 | `store_pending_execution()`, `execute_pending_command()`, `reject_pending_command()` |
| `nbot/services/ai/tools/__init__.py` | ~100 | Re-exports: `get_all_tool_definitions`, `execute_tool`, `ToolExecutor` |

### 3.5 `nbot/web/ai_service.py` (~1851 lines -> ~4 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/web/ai/service.py` | ~450 | `get_ai_response`, `stream_ai_response` |
| `nbot/web/ai/tools.py` | ~450 | `get_ai_response_with_tools`, `parse_tool_call_from_text` |
| `nbot/web/ai/images.py` | ~350 | `get_ai_response_with_images`, image URL processing |
| `nbot/web/ai/trigger.py` | ~250 | `trigger_ai_response_for_request`, `stream_send_response` |

### 3.6 `nbot/web/routes/personality.py` (~1405 lines -> ~3 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/web/routes/persona/personality.py` | ~450 | Route handlers for personality CRUD |
| `nbot/web/routes/persona/compile.py` | ~350 | `compile_personality_prompt()` and prompt building |
| `nbot/web/routes/persona/platform.py` | ~350 | Role card platform upload/download/preview |

### 3.7 `nbot/web/routes/sessions.py` (~1121 lines -> ~2 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/web/routes/chat/sessions.py` | ~450 | Main session route handlers |
| `nbot/web/routes/chat/sessions_utils.py` | ~350 | `_normalize_tags`, `_runtime_snapshot_signature`, `_copy_character_runtime_state`, etc. |

### 3.8 `nbot/core/ai_pipeline.py` (~1271 lines -> ~3 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/core/pipeline/pipeline.py` | ~450 | `AIPipeline` class, `PipelineContext`, `PipelineResult` |
| `nbot/core/pipeline/callbacks.py` | ~400 | `PipelineCallbacks` implementations |
| `nbot/core/pipeline/tools.py` | ~300 | Tool loop integration within pipeline |

### 3.9 `nbot/ai_commands.py` (~1258 lines -> ~3 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/commands/ai/registry.py` | ~450 | `register_ai_commands()` and main registration |
| `nbot/commands/ai/handlers.py` | ~450 | Individual AI command handlers |
| `nbot/commands/ai/utils.py` | ~200 | `get_group_history_items`, `history_items_to_text`, etc. |

### 3.10 `nbot/core/workspace.py` (~1235 lines -> ~3 files)

| New File | Lines | Responsibility |
|----------|-------|----------------|
| `nbot/core/workspace/manager.py` | ~450 | `WorkspaceManager` class, singleton |
| `nbot/core/workspace/file_ops.py` | ~400 | File operations: create, read, edit, delete, list |
| `nbot/core/workspace/utils.py` | ~200 | `_resolve_within`, `_normalize_edit_block`, `_replace_content_block` |

---

## 4. Logging System Redesign

### Current Problems
1. `ncatbot.utils.logger.get_log()` used in `bot.py` and `commands.py`.
2. `logging.getLogger(__name__)` used in ~45 files with no central config.
3. No `dictConfig`; CLI manually suppresses loggers.
4. `print()` in `bot.py` (`run_cli()`).
5. `CharacterEventLogger` adds another custom logger.
6. Log dir `logs/` already ignored, rotated by ncatbot.

### New Design

**Config location:** `nbot/utils/logger.py` (code) + `config/logging.ini` (optional override).

**Setup:**
```python
# nbot/utils/logger.py
import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    os.makedirs(log_dir, exist_ok=True)
    handlers = {
        "console": {
            "class": "logging.StreamHandler",
            "level": level,
            "formatter": "standard",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": level,
            "formatter": "standard",
            "filename": os.path.join(log_dir, "nekobot.log"),
            "maxBytes": 10_000_000,
            "backupCount": 5,
            "encoding": "utf-8",
        },
    }
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"standard": {"format": DEFAULT_FORMAT}},
        "handlers": handlers,
        "loggers": {
            "nbot": {"level": level, "handlers": ["console", "file"], "propagate": False},
            "ncatbot": {"level": "WARNING", "handlers": ["file"], "propagate": False},
            "werkzeug": {"level": "ERROR", "handlers": ["file"], "propagate": False},
            "urllib3": {"level": "WARNING", "handlers": ["file"], "propagate": False},
            "apscheduler": {"level": "WARNING", "handlers": ["file"], "propagate": False},
        },
        "root": {"level": "WARNING", "handlers": ["file"]},
    })

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

def silence_loggers(*names: str, level: int = logging.CRITICAL + 1) -> None:
    for name in names:
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False
        for h in logger.handlers:
            h.setLevel(level)
```

**Migration from `get_log()`:**
```python
# Before:
from ncatbot.utils.logger import get_log
_log = get_log()

# After:
from nbot.utils.logger import get_logger
_log = get_logger(__name__)
```

**Migration from `logging.getLogger(__name__)`:**
```python
# Before:
import logging
_log = logging.getLogger(__name__)

# After:
from nbot.utils.logger import get_logger
_log = get_logger(__name__)
```

**CLI quiet mode:**
```python
# In cli/app.py or bot.py before CLI starts:
from nbot.utils.logger import silence_loggers
silence_loggers("nbot", "werkzeug", "urllib3", "requests", "socketio", "engineio", "apscheduler")
```

**Request/server status context:**
Add a logging filter that injects request ID or server mode into log records.
```python
class ContextFilter(logging.Filter):
    def filter(self, record):
        record.context = getattr(threading.local(), "log_context", "")
        return True
```

**Avoid `print()`:**
Replace all `print()` in `bot.py` with `_log.info()` or `_log.error()`. The CLI should use Rich's `Console` for user-facing output, not `print()`.

---

## 5. .gitignore Updates

### Current `.gitignore`:
```
**/__pycache__/
cache
logs
saved_message
.env
admin.txt
switches.json
.DS_Store
data
resources
**/tmp/
nbot/plugins/bilibili
!resources/prompts/
config.ini
```

### Missing entries to add:
```gitignore
# OS files
Thumbs.db
*.swp
*.swo
*~

# Python artifacts
*.pyc
*.pyo
*.egg-info/
dist/
build/
.pytest_cache/
.mypy_cache/

# Virtual environments
venv/
.venv/
env/

# IDE
.vscode/
.idea/
*.iml

# Runtime data (already partially covered)
data/
logs/
cache/
tmp/
saved_message/

# Config files (user-specific)
.env
config.ini
admin.txt
switches.json
smtp_config.json
email_config.json
wenku8_cookie.txt
mc.txt

# Web data
nbot/web/static/uploads/
!nbot/web/static/uploads/.gitkeep

# Test artifacts
.coverage
htmlcov/

# Misc
*.log
*.pid
```

### Proposed complete `.gitignore`:
```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
.venv/
env/
ENV/

# IDE
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db

# Testing
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/

# Runtime / User-specific
.env
config.ini
admin.txt
switches.json
smtp_config.json
email_config.json
wenku8_cookie.txt
mc.txt
*.pid
*.log

# Data directories
cache/
logs/
tmp/
saved_message/
data/
downloads/
resources/
!resources/prompts/

# Web uploads
nbot/web/static/uploads/
!nbot/web/static/uploads/.gitkeep

# Plugin downloads
nbot/plugins/bilibili
```

---

## 6. Migration Order

The goal is to keep the bot runnable after each phase. Each phase is a PR-sized chunk.

### Phase 1: Foundation — Utilities and Logging
1. Create `nbot/utils/` directory.
2. Implement `nbot/utils/logger.py` with unified setup.
3. Implement `nbot/utils/paths.py`, including `get_downloads_dir()` and `make_download_path()` for the unified download resource folder.
4. Implement `nbot/config.py` (merge from `web/utils/config_loader.py` and `services/ai.py`).
5. Update `bot.py` to call `setup_logging()` at startup.
6. Replace `get_log()` and `logging.getLogger(__name__)` in a few key files (`bot.py`, `commands.py` top) to validate.
7. **Commit. Smoke test:** `python bot.py --help` or basic startup.

### Phase 2: HTTP and Base64 Consolidation
1. Implement `nbot/utils/http_client.py`.
2. Implement `nbot/utils/base64_image.py`.
3. Replace direct `requests`/`urllib` calls in `commands.py` and `services/tools.py` with the new wrappers.
4. **Commit. Smoke test:** Run a command that fetches a URL (e.g., `/random_image`).

### Phase 3: Extract Message Sender and Sandbox Bridge
1. Implement `nbot/utils/message_sender.py`.
2. Implement `nbot/utils/sandbox_bridge.py`.
3. Replace dual-send patterns in `commands.py` with `send_text()` / `send_file()`.
4. Move sandbox bridge code out of `commands.py`.
5. **Commit. Smoke test:** Send a test message in QQ group and private.

### Phase 4: Split `nbot/commands.py` — Part 1 (Infrastructure)
1. Create `nbot/commands/` directory.
2. Move `register_command`, `command_handlers` to `nbot/commands/registry.py`.
3. Move dispatch logic to `nbot/commands/dispatch.py`.
4. Move data persistence to `nbot/commands/data_persistence.py`.
5. Move scheduler to `nbot/commands/scheduler.py`.
6. Move chatter to `nbot/commands/chatter.py`.
7. Move message patches to `nbot/commands/message_patches.py`.
8. Move QQ sandbox to `nbot/commands/qq_sandbox.py`.
9. Create `nbot/commands/__init__.py` with re-exports.
10. Update `bot.py` and `ai_commands.py` imports.
11. **Commit. Smoke test:** Full QQ bot startup and basic commands.

### Phase 5: Split `nbot/commands.py` — Part 2 (Domain Commands)
1. Move admin commands to `nbot/commands/admin.py`.
2. Move system commands to `nbot/commands/system.py`.
3. Move JM comic commands to `nbot/commands/jmcomic/`.
4. Move novel commands to `nbot/commands/novel/`.
5. Move media commands to `nbot/commands/media/`.
6. Move chat commands to `nbot/commands/chat/`.
7. Move MC commands to `nbot/commands/mc/`.
8. Move help to `nbot/commands/help.py`.
9. Move remaining commands to appropriate files.
10. **Commit. Smoke test:** Test each command category.

### Phase 6: Split `nbot/web/server.py`
1. Create `nbot/web/server_*.py` files.
2. Move auth methods to `server_auth.py`.
3. Move AI client methods to `server_ai.py`.
4. Move heartbeat to `server_heartbeat.py`.
5. Move workflow to `server_workflow.py`.
6. Move custom task to `server_task.py`.
7. Move knowledge to `server_knowledge.py`.
8. Move QQ sync to `server_qq_sync.py`.
9. Move personality loading to `server_personality.py`.
10. Move message building to `server_message.py`.
11. Move utils to `server_utils.py`.
12. Keep `server.py` as thin coordinator.
13. **Commit. Smoke test:** Web dashboard startup, login, basic chat.

### Phase 7: Split `nbot/services/tools.py`
1. Create `nbot/services/ai/tools/` directory.
2. Move definitions to `ai/tools/definitions.py`.
3. Move `ToolExecutor` to `ai/tools/builtins.py`.
4. Move execution dispatch to `ai/tools/executor.py`.
5. Move workspace tools to `ai/tools/workspace_tools.py`.
6. Move memory tools to `ai/tools/memory_tools.py`.
7. Move pending execution to `ai/tools/pending_exec.py`.
8. **Commit. Smoke test:** Tool execution in web chat.

### Phase 8: Split `nbot/web/ai_service.py` and Routes
1. Split `ai_service.py` into `web/ai/service.py`, `web/ai/tools.py`, `web/ai/images.py`, `web/ai/trigger.py`.
2. Split `routes/personality.py` into `routes/persona/personality.py`, `routes/persona/compile.py`, `routes/persona/platform.py`.
3. Split `routes/sessions.py` into `routes/chat/sessions.py`, `routes/chat/sessions_utils.py`.
4. **Commit. Smoke test:** Web AI chat with images, personality switch.

### Phase 9: Split `nbot/core/ai_pipeline.py`, `nbot/ai_commands.py`, `nbot/core/workspace.py`
1. Split `core/ai_pipeline.py` into `core/pipeline/pipeline.py`, `core/pipeline/callbacks.py`, `core/pipeline/tools.py`.
2. Split `ai_commands.py` into `commands/ai/registry.py`, `commands/ai/handlers.py`, `commands/ai/utils.py`.
3. Split `core/workspace.py` into `core/workspace/manager.py`, `core/workspace/file_ops.py`, `core/workspace/utils.py`.
4. **Commit. Smoke test:** Full AI pipeline, workspace operations.

### Phase 10: Split `nbot/cli_cc_style.py`
1. Create `nbot/cli/` directory.
2. Split into `app.py`, `screens.py`, `components.py`, `styles.py`, `completer.py`, `utils.py`.
3. **Commit. Smoke test:** CLI mode startup.

### Phase 11: Final Cleanup
1. Update `.gitignore`.
2. Run file length check: `find nbot -name "*.py" | xargs wc -l | awk '$1 > 500 {print}'`.
3. Add docstrings and type hints to any remaining gaps.
4. Remove dead code.
5. **Commit. Final smoke test.**

---

## 7. Engineering Standards

### Naming Conventions
- Modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private helpers: `_leading_underscore`

### Docstrings
- Google style: `Args:`, `Returns:`, `Raises:`.
- Every public function and class must have a docstring.
- One-line docstrings for trivial internal helpers are acceptable.

### Type Hints
- All new function signatures must have type hints.
- Use `from __future__ import annotations` to avoid forward-reference issues.
- Use `Optional[X]` or `X | None` (Python 3.10+ style preferred).

### Import Ordering
```python
from __future__ import annotations

# stdlib
import os
import sys
from typing import Dict, List, Optional

# third-party
import requests
from flask import Flask

# local (absolute)
from nbot.utils.logger import get_logger
from nbot.utils.paths import get_project_root

# local (relative) — only when necessary
from . import something
```

### Max File Length Enforcement
- Hard limit: 500 lines per `.py` file.
- Use `find nbot -name "*.py" | xargs wc -l | awk '$1 > 500 {print}'` to check.
- CI/lint step should fail if any file exceeds 500 lines.

### Comment Style
- Use `#` for inline comments.
- Use `"""` for docstrings.
- Avoid Chinese comments in new code; use English for consistency.
- Keep existing Chinese comments during refactor; translate only if modifying that section.

---

## 8. Verification Plan

### 8.1 File Length Check
```bash
find nbot -name "*.py" | xargs wc -l | awk '$1 > 500 {print}'
```
Expected: empty output after refactor.

### 8.2 Unit Tests
- Add `tests/` directory if not present.
- Test each utility module in isolation:
  - `tests/utils/test_logger.py`
  - `tests/utils/test_paths.py`
  - `tests/test_config.py`
  - `tests/utils/test_http_client.py`
  - `tests/utils/test_base64_image.py`
  - `tests/utils/test_message_sender.py`

### 8.3 Existing Test
- Run `python tools/test_jm_upload.py` to verify JM comic upload still works.
- Run `python tools/test_commands.py` if available.

### 8.4 Startup Smoke Test
```bash
# Test QQ bot mode
python bot.py --no-web

# Test web-only mode
python bot.py --only-web

# Test CLI mode
python bot.py --cli

# Test CLI + Web mode
python bot.py --cli-and-web
```

### 8.5 Command Smoke Test
- Send `/help` in QQ group and private.
- Send `/jmrank 周排行`.
- Send `/findbook test`.
- Send `/random_image`.
- Send `/tts`.
- Send `/workspace`.

### 8.6 Web Route Smoke Test
- Login to web dashboard.
- Create a new session.
- Send a message and get AI response.
- Upload a file to workspace.
- Switch personality.
- Test heartbeat configuration.

### 8.7 Lint Check
```bash
# If using ruff
ruff check nbot/
ruff format --check nbot/

# If using flake8
flake8 nbot/ --max-line-length=100
```

---

## 9. Design Document Location

**Recommended path:** `docs/refactor-design.md`

This keeps documentation separate from code but within the repo. The `docs/` directory can also host other architecture docs.

---

## 10. Unified Download Resource Directory

**Goal:** All downloaded resources (videos, images, PDFs, audio, etc.) should be saved under one root folder and classified by type, instead of being scattered across `tmp/`, `cache/pdf/`, `cache/jm_cover_cache/`, etc.

### 10.1 Directory Layout

```
downloads/
|-- videos/          # Bilibili, Douyin and other downloaded videos
|-- images/          # Cover images, generated photos, random images
|-- pdfs/            # JM comic PDFs and other PDF downloads
|-- audio/           # TTS output, music, voice messages
|-- others/          # Files that do not fit the above categories
```

- Root path: `downloads/` under the project root (parallel to `cache/`, `logs/`, `data/`).
- The whole `downloads/` directory is ignored by `.gitignore`.
- Subdirectories are created on demand by the path helper with `os.makedirs(..., exist_ok=True)`.

### 10.2 Classification Rules

| Resource Type | Destination | Examples |
|---------------|-------------|----------|
| Video         | `downloads/videos/` | `bili_xxx.mp4`, `douyin_xxx.mp4` |
| Image         | `downloads/images/` | `jm_cover_123.jpg`, `random_456.png` |
| PDF           | `downloads/pdfs/`   | `jm_123456.pdf`, `novel_xxx.pdf` |
| Audio         | `downloads/audio/`  | `tts_xxx.mp3`, `music_xxx.mp3` |
| Other         | `downloads/others/` | Unknown or mixed attachments |

### 10.3 Naming Convention

Use a deterministic, collision-resistant name:

```
{source}_{resource_id}_{timestamp}.{ext}
```

Examples:
- `bili_BV1xxxx_20260625_143052.mp4`
- `douyin_1234567890_20260625_143052.mp4`
- `jm_123456_20260625_143052.pdf`
- `jm_cover_123456_20260625_143052.jpg`

### 10.4 Path Helper API

Extend `nbot/utils/paths.py`:

```python
from enum import Enum
from pathlib import Path

class DownloadType(str, Enum):
    VIDEO = "videos"
    IMAGE = "images"
    PDF = "pdfs"
    AUDIO = "audio"
    OTHER = "others"

def get_downloads_dir(subpath: str = "") -> str:
    """Return the absolute path to the downloads root or a subpath."""

def make_download_path(
    source: str,
    resource_id: str,
    ext: str,
    dtype: DownloadType = DownloadType.OTHER,
    timestamp: str | None = None,
) -> str:
    """Build and return an absolute, classified download file path."""
```

### 10.5 Migration of Existing Download Locations

Current scattered locations to migrate:

| Current Path | New Path | Notes |
|--------------|----------|-------|
| `tmp/bili_*.mp4` | `downloads/videos/` | Update `bilibili_parser.py` |
| `tmp/douyin_*.mp4` | `downloads/videos/` | Update `douyin_parser.py` |
| `cache/pdf/{id}.pdf` | `downloads/pdfs/` | Update JM comic PDF output |
| `cache/jm_cover_cache/{id}.jpg` | `downloads/images/` | Update JM cover cache logic |
| `cache/search/*.html`, `cache/rank/*.html` | Keep in `cache/` | These are not user-downloaded resources |
| Random image/video temp files | `downloads/images/` or `downloads/videos/` | Update media commands |

**Migration strategy:**
1. Implement `get_downloads_dir()` and `make_download_path()` in Phase 1.
2. In each refactor phase, update the relevant downloader to use the new helper.
3. Keep a one-time backward-compat shim for the first release: if an old path exists and the new path does not, prefer the old path (or optionally move it lazily).
4. After all commands are migrated, remove the shim.

### 10.6 Cleanup / Retention Policy

- Add optional download settings keys in `.env` (e.g. `DOWNLOAD_MAX_AGE_DAYS`, `DOWNLOAD_MAX_TOTAL_SIZE_MB`):
  - `max_age_days = 7` — automatically delete files older than N days.
  - `max_total_size_mb = 2048` — trigger cleanup when total size exceeds limit.
- Implement a lightweight cleanup helper in `nbot/utils/paths.py` or a new `nbot/utils/download_cleanup.py`.
- Run cleanup periodically via APScheduler or on startup.

### 10.7 .gitignore Update

`downloads/` is already added to the proposed `.gitignore` in Section 5.

---

## Summary of Critical Files for Implementation

- `/Users/feewee009/myCode/nekobot/nbot/utils/logger.py` — Unified logging setup
- `/Users/feewee009/myCode/nekobot/nbot/config.py` — Central .env configuration
- `/Users/feewee009/myCode/nekobot/nbot/utils/paths.py` — Path resolution helpers
- `/Users/feewee009/myCode/nekobot/nbot/utils/message_sender.py` — Dual send helper
- `/Users/feewee009/myCode/nekobot/nbot/commands/__init__.py` — Backward-compat re-exports
- `/Users/feewee009/myCode/nekobot/nbot/web/server.py` — Thin coordinator after split
