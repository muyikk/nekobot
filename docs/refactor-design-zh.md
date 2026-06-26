# NekoBot 重构设计方案

## 1. 目标与总体约束

**目标：** 细化 NekoBot 的功能与目录结构，提升代码可读性，强制每个 `.py` 文件不超过 500 行，统一日志系统，完善 `.gitignore`，并提取公共工具方法。

**总体架构：** 将横向关注点集中到 `nbot/utils/`；按职责拆分单体大文件；引入统一的日志门面；每个阶段结束后机器人仍应可运行。

**技术栈：** Python 3.13+、Flask、SocketIO、ncatbot、Rich、APScheduler、jmcomic。

### 全局约束

- 任意 `.py` 文件不得超过 500 行，无例外。
- 新代码必须带类型注解与 Google 风格 docstring。
- 导入顺序：stdlib → 第三方 → 本地绝对路径 → 本地相对路径。
- 生产代码禁止 `print()`，统一使用日志器。
- 禁止重复的配置解析与 API key 解析逻辑。
- HTTP 客户端统一：新异步代码使用 `httpx`；同步代码使用 `requests`，统一封装在一个模块中。

---

## 2. 目标目录结构

```
nekobot/
|-- bot.py                          # 入口文件，保持小巧（<250 行）
|-- .env.example                    # 唯一的环境变量模板
|-- .gitignore                      # 包含所有运行时产物
|-- downloads/                      # 新增：统一的下载资源分类目录
|-- docs/
|   |-- refactor-design.md          # 英文设计文档
|   |-- refactor-design-zh.md       # 中文设计文档（本文档）
|
|-- nbot/
|   |-- __init__.py
|   |-- config.py                   # 唯一的 .env 配置入口
|   |
|   |-- utils/                      # 新增：横向公共工具
|   |   |-- __init__.py
|   |   |-- logger.py               # 统一日志设置
|   |   |-- paths.py                # 项目根目录、缓存目录、下载目录等路径助手
|   |   |-- http_client.py          # 统一 HTTP 客户端封装
|   |   |-- base64_image.py         # 图片/文件转 base64 data URL
|   |   |-- message_sender.py       # 群聊/私聊统一发送助手
|   |   |-- sandbox_bridge.py       # QQ macOS 沙盒桥接
|   |   |-- email_sender.py         # SMTP 邮件发送
|   |   |-- switch_manager.py       # 群/用户功能开关持久化
|   |   |-- validators.py           # API 返回结果校验助手
|   |
|   |-- core/                       # 核心领域逻辑
|   |   |-- ai_pipeline.py          # 拆分为 ≤500 行的多个文件
|   |   |-- workspace.py            # 拆分为 ≤500 行的多个文件
|   |   |-- ...
|   |
|   |-- services/                   # 服务层
|   |   |-- ai.py                   # AI 客户端封装
|   |   |-- tools/                  # 拆分 nbot/services/tools.py
|   |   |-- chat_service.py         # 聊天编排
|   |   |-- ...
|   |
|   |-- commands/                   # 新增：拆分 nbot/commands.py
|   |   |-- registry.py             # 命令注册与命令表
|   |   |-- dispatch.py             # 消息分发
|   |   |-- admin.py                # 管理员命令
|   |   |-- system.py               # 系统命令
|   |   |-- jmcomic/                # JM 漫画命令
|   |   |-- novel/                  # 轻小说命令
|   |   |-- media/                  # 媒体命令
|   |   |-- chat/                   # 聊天相关命令
|   |   |-- mc/                     # Minecraft 命令
|   |   |-- ...
|   |
|   |-- web/                        # Web 面板与路由
|   |   |-- server.py               # 拆分为协调器
|   |   |-- server_*.py             # 各职责模块
|   |   |-- ai_service.py           # 拆分为多个文件
|   |   |-- routes/                 # 路由模块
|   |
|   |-- cli/                        # CLI 交互终端
|   |   |-- app.py
|   |   |-- screens.py
|   |   |-- components.py
|   |   |-- styles.py
|   |   |-- completer.py
|   |
|   |-- plugins/                    # 消息解析插件
|   |   |-- bilibili_parser.py
|   |   |-- douyin_parser.py
|   |
|   |-- ai_commands.py              # 拆分后保留入口
|   |-- cli_cc_style.py             # 拆分后保留入口或删除
|   |-- heartbeat.py
|   |-- chat.py
```

### 目录职责对照表

| 目录 | 职责 |
|------|------|
| `nbot/utils/` | 横向工具：日志、路径、配置、HTTP、base64、消息发送、沙盒桥接、邮件、开关、校验。不含业务逻辑。 |
| `downloads/` | **新增**：统一的下载资源根目录，按类型（视频/图片/PDF/音频/其他）分类存放。 |
| `nbot/core/` | 核心领域逻辑：AI pipeline、workspace、聊天模型、消息中间件、知识库、角色引擎。 |
| `nbot/services/` | 服务层：AI 客户端、工具、聊天编排、TTS、STT。 |
| `nbot/services/tools/` | 工具定义、执行、注册表、workspace 工具、记忆工具。 |
| `nbot/commands/` | QQ 命令处理器，按领域拆分为多个子模块。 |
| `nbot/web/` | Flask/SocketIO Web 面板、路由、AI 服务。 |
| `nbot/cli/` | 基于 Rich 的 TUI。 |
| `nbot/plugins/` | 消息解析器（Bilibili、Douyin）。 |
| `nbot/channels/` | 多频道适配器（QQ、Web、Feishu、Telegram）。 |
| `nbot/character/` | 角色扮演引擎。 |

---

## 2.5 进一步嵌套的文件夹结构

为了让项目结构更清晰，同时不过度增加目录深度，建议在以下模块内再增加一层子目录：

```text
nbot/
|-- core/
|   |-- pipeline/          # AI pipeline 相关
|   |   |-- pipeline.py
|   |   |-- callbacks.py
|   |   |-- tools.py
|   |-- workspace/         # Workspace 相关
|   |   |-- manager.py
|   |   |-- file_ops.py
|   |   |-- utils.py
|   |-- memory/            # 消息历史与记忆
|   |   |-- message_history.py
|   |   |-- message_middleware.py
|   |   |-- auto_memory.py
|   |-- prompt/            # Prompt 管理
|   |   |-- prompt.py
|   |-- agent/             # Agent 与工具循环
|   |   |-- agent_service.py
|   |   |-- tool_loop.py
|   |-- parser/            # 文件解析
|   |   |-- file_parser.py
|
|-- services/
|   |-- ai/                # AI 客户端、聊天编排、工具
|   |   |-- ai.py
|   |   |-- chat_service.py
|   |   |-- tools/
|   |-- channels/          # 各频道服务
|   |   |-- telegram_service.py
|   |   |-- feishu_service.py
|   |   |-- feishu_ws_service.py
|   |   |-- feishu_chat_service.py
|   |-- audio/             # 语音相关
|   |   |-- tts.py
|   |   |-- stt.py
|   |-- executor/          # 动态执行
|   |   |-- dynamic_executor.py
|
|-- web/
|   |-- ai/                # Web AI 服务拆分
|   |   |-- service.py
|   |   |-- tools.py
|   |   |-- images.py
|   |   |-- trigger.py
|   |-- routes/
|   |   |-- chat/          # 会话相关路由
|   |   |   |-- sessions.py
|   |   |   |-- sessions_utils.py
|   |   |-- persona/       # 人格、角色、Live2D
|   |   |   |-- personality.py
|   |   |   |-- compile.py
|   |   |   |-- platform.py
|   |   |   |-- characters.py
|   |   |   |-- live2d.py
|   |   |-- config/        # 配置类路由
|   |   |   |-- channels.py
|   |   |   |-- ai_models.py
|   |   |   |-- admin_misc.py
|   |   |-- system/        # 系统/管理类路由
|   |   |   |-- auth.py
|   |   |   |-- admin.py
|
|-- commands/
|   |-- shared/            # 命令层公共基础设施
|   |   |-- data_persistence.py
|   |   |-- scheduler.py
|   |   |-- chatter.py
|   |   |-- message_patches.py
|   |   |-- qq_sandbox.py
|   |   |-- file_sender.py
|   |   |-- email.py
|   |-- ai/                # AI 增强命令（原 ai_commands.py）
|   |   |-- registry.py
|   |   |-- handlers.py
|   |   |-- utils.py
```

### 嵌套原则

1. **职责内聚**：同一子系统的文件放在同一子目录，例如所有 workspace 文件放在 `core/workspace/`。
2. **避免过深**：最多再增加一层子目录，保持导入路径简洁。
3. **向后兼容**：通过顶层 `__init__.py` 重新导出关键符号，旧导入路径可继续工作。
4. **500 行限制不变**：嵌套仅用于分组，文件本身仍需 ≤500 行。

### 目录职责补充

| 新增目录 | 职责 |
|----------|------|
| `nbot/core/pipeline/` | AI pipeline、回调、工具调用循环。 |
| `nbot/core/workspace/` | Workspace 管理器与文件操作。 |
| `nbot/core/memory/` | 消息历史、消息中间件、自动记忆。 |
| `nbot/core/prompt/` | Prompt 构建与管理。 |
| `nbot/core/agent/` | Agent 服务与工具循环。 |
| `nbot/core/parser/` | 多格式文件解析。 |
| `nbot/services/ai/` | AI 客户端、聊天编排、工具集。 |
| `nbot/services/channels/` | Telegram、Feishu 等频道服务。 |
| `nbot/services/audio/` | TTS、STT。 |
| `nbot/services/executor/` | 动态代码执行。 |
| `nbot/web/ai/` | Web 端 AI 服务。 |
| `nbot/web/routes/chat/` | 会话相关路由。 |
| `nbot/web/routes/persona/` | 人格、角色、Live2D 路由。 |
| `nbot/web/routes/config/` | 频道、模型、杂项配置路由。 |
| `nbot/web/routes/system/` | 认证、管理员路由。 |
| `nbot/commands/shared/` | 命令层公共基础设施。 |
| `nbot/commands/ai/` | AI 增强 slash 命令（原 `ai_commands.py`）。 |

---

## 3. 公共工具模块提取

### 3.1 `nbot/utils/logger.py` — 统一日志

**替代：**
- `bot.py`、`commands.py` 中的 `from ncatbot.utils.logger import get_log`
- 约 45 个文件中的 `import logging; _log = logging.getLogger(__name__)`
- `cli_cc_style.py` 中的手动日志抑制
- `CharacterEventLogger`

**公共 API：**
```python
from nbot.utils.logger import get_logger, setup_logging, silence_loggers

def get_logger(name: str) -> logging.Logger:
    """获取统一配置的日志器。"""

def setup_logging(
    level: str = "INFO",
    log_dir: str = "logs",
    max_bytes: int = 10_000_000,
    backup_count: int = 5,
    console: bool = True,
) -> None:
    """配置根日志器：控制台 + 滚动文件。"""

def silence_loggers(*names: str, level: int = logging.CRITICAL + 1) -> None:
    """静默指定的第三方日志器。"""
```

**行为：**
- 启动时一次性调用 `setup_logging()`。
- 所有模块统一使用 `from nbot.utils.logger import get_logger; _log = get_logger(__name__)`。
- CLI 模式启动前调用 `silence_loggers()` 抑制嘈杂日志。
- 日志格式包含时间、级别、logger 名，以及 `[server|cli|qq]` 上下文标签。

### 3.2 `nbot/utils/paths.py` — 路径解析

**替代：**
- `commands.py` 中的 `load_address()`（使用 20+ 次）
- 各处散落的 `os.path.join(os.path.dirname(__file__), ...)`

**公共 API：**
```python
from nbot.utils.paths import (
    get_project_root,
    get_cache_dir,
    get_data_dir,
    get_downloads_dir,
    get_workspace_dir,
    get_resources_dir,
    normalize_file_path,
)

def get_project_root() -> str:
def get_cache_dir(subpath: str = "") -> str:
def get_data_dir(subpath: str = "") -> str:
def get_downloads_dir(subpath: str = "") -> str:
def get_workspace_dir() -> str:
def get_resources_dir(subpath: str = "") -> str:
def normalize_file_path(path: str) -> str:
```

### 3.3 `nbot/config.py` — 单一环境配置

**决策：** 重构后只使用一个环境文件 **`.env`**。`config.ini` 与 `config.example.ini` 废弃并删除。

**替代：**
- `services/ai.py`、`commands.py`、`web/ai_service.py`、`web/utils/config_loader.py` 中的 `configparser.ConfigParser()`
- `bot.py` 中散落的 `python-dotenv` 加载
- `services/ai.py` 与 `web/utils/config_loader.py` 中重复的 `resolve_runtime_api_key()`
- 现有的 `nbot/config.py` 兼容 shim

**公共 API：**
```python
from nbot.config import get_config, Config

class Config:
    """从 .env 加载的单例配置（可被 os.environ 覆盖）。"""
    def get(self, key: str, fallback: str = "") -> str: ...
    def get_int(self, key: str, fallback: int = 0) -> int: ...
    def get_bool(self, key: str, fallback: bool = False) -> bool: ...
    def get_list(self, key: str, sep: str = ",", fallback: list | None = None) -> list[str]: ...
    def get_section(self, prefix: str) -> dict[str, str]: ...
    def reload(self) -> None: ...

def get_config() -> Config
```

**.env 键名规范：**
- 全部使用 `UPPER_SNAKE_CASE`。
- 用双下划线模拟原 section，例如：
  - `BOT_UIN`、`WS_URI`、`TOKEN`
  - `WEB_HOST`、`WEB_PORT`、`WEB_DEBUG`
  - `AI_PROVIDER`、`AI_API_KEY`、`AI_BASE_URL`、`AI_MODEL`
  - `SMTP_HOST`、`SMTP_PORT`、`SMTP_USER`、`SMTP_PASS`
  - `DOWNLOAD_MAX_AGE_DAYS`、`DOWNLOAD_MAX_TOTAL_SIZE_MB`
- `.env.example` 是唯一的环境变量模板，需包含所有支持项的默认值与注释。

**从 `config.ini` 迁移：**
1. 提供一次性脚本 `tools/migrate_config_ini_to_env.py`，将 `config.ini` 转换为 `.env`。
2. 所有 `config.get(section, key)` 改为 `get_config().get("SECTION__KEY")`。
3. 生产代码中彻底移除 `config.ini` 读取逻辑；`.gitignore` 中保留 `config.ini`，避免旧文件被误提交。
4. 删除仓库中的 `config.example.ini`，仅保留 `.env.example`。

### 3.4 `nbot/utils/http_client.py` — 统一 HTTP

**替代：** 代码中混用的 `requests`、`aiohttp`、`httpx`、`urllib.request`。

**公共 API：**
```python
from nbot.utils.http_client import get_sync, post_sync, get_async, post_async, download_file

def get_sync(url: str, **kwargs) -> requests.Response: ...
def post_sync(url: str, **kwargs) -> requests.Response: ...
async def get_async(url: str, **kwargs) -> httpx.Response: ...
async def post_async(url: str, **kwargs) -> httpx.Response: ...
def download_file(url: str, dest: str, timeout: int = 60) -> str: ...
```

**迁移规则：** 新异步代码使用 `httpx`；现有 `requests` 调用统一通过此模块包装；不再新增 `aiohttp` 或 `urllib.request` 调用。

### 3.5 `nbot/utils/base64_image.py` — Base64 编码

**替代：** 6 个以上文件中重复的 `base64.b64encode(...)` 代码块。

```python
from nbot.utils.base64_image import image_to_base64_url, file_to_base64_url

def image_to_base64_url(image_source: str) -> str: ...
def file_to_base64_url(file_path: str, mime_type: str = "application/octet-stream") -> str: ...
```

### 3.6 `nbot/utils/message_sender.py` — 统一消息发送

**替代：** `commands.py` 中重复几十次的 `if is_group: msg.reply(...) else: bot.api.post_private_msg(...)`。

```python
from nbot.utils.message_sender import send_text, send_file, reply_to

async def send_text(msg, text: str, is_group: bool = True) -> None: ...
async def send_file(msg, file_path: str, is_group: bool = True, filename: str | None = None) -> None: ...
async def reply_to(msg, text: str, is_group: bool = True) -> None: ...
```

### 3.7 `nbot/utils/sandbox_bridge.py` — QQ 沙盒桥接

**替代：** `commands.py` 中的 `_should_bridge()`、`_bridge_to_qq_sandbox()`、`_wrap_botapi_upload()`。

```python
from nbot.utils.sandbox_bridge import apply_qq_sandbox_bridge

def apply_qq_sandbox_bridge() -> None:
    """在启动时自动为 BotAPI 上传方法打补丁，将文件 hard-link 到 QQ 沙盒。"""
```

### 3.8 `nbot/utils/email_sender.py` — SMTP 邮件

**替代：** `commands.py` 中的 `_send_comic_email_sync()`、`send_comic_email()`。

```python
from nbot.utils.email_sender import send_email, load_smtp_config, save_smtp_config

async def send_email(
    to_addr: str,
    subject: str,
    body: str,
    attachment_path: str | None = None,
    smtp_config: dict | None = None,
) -> bool: ...
```

### 3.9 `nbot/utils/switch_manager.py` — 功能开关

**替代：** `commands.py` 中的 `SwitchManager`。

```python
from nbot.utils.switch_manager import get_switch_manager, SwitchManager

class SwitchManager:
    def get_switch_state(self, switch_name: str, group_id: str | None = None, user_id: str | None = None) -> bool: ...
    def set_switch_state(self, switch_name: str, state: bool, group_id: str | None = None, user_id: str | None = None) -> None: ...
    def toggle_switch(self, switch_name: str, group_id: str | None = None, user_id: str | None = None) -> bool: ...
```

### 3.10 `nbot/utils/validators.py` — API 返回校验

**替代：** 各处零散的 `if response.status_code == 200` 与 `result.get("status") == "ok"`。

```python
from nbot.utils.validators import validate_api_response, is_success_response

def validate_api_response(response, expected_status: int = 200) -> dict: ...
def is_success_response(result: dict) -> bool: ...
```

---

## 4. 文件拆分策略

### 4.1 `nbot/commands.py`（4765 行 → 约 15 个文件）

| 新文件 | 行数 | 职责 |
|--------|------|------|
| `nbot/commands/registry.py` | ~80 | 命令注册、`command_handlers`、帮助文本 |
| `nbot/commands/dispatch.py` | ~450 | 消息分发、@ 判断、插件分发 |
| `nbot/commands/shared/data_persistence.py` | ~200 | 收藏、管理员、黑名单、运行状态等持久化 |
| `nbot/commands/shared/scheduler.py` | ~150 | 定时任务 |
| `nbot/commands/shared/chatter.py` | ~150 | 闲聊循环 |
| `nbot/commands/shared/message_patches.py` | ~120 | BotAPI 消息记录补丁 |
| `nbot/commands/shared/qq_sandbox.py` | ~120 | QQ 沙盒桥接包装 |
| `nbot/commands/admin.py` | ~200 | 管理员命令 |
| `nbot/commands/system.py` | ~100 | `/restart`、`/shutdown` |
| `nbot/commands/jmcomic/*.py` | ~800 | JM 漫画相关命令 |
| `nbot/commands/novel/*.py` | ~700 | 轻小说相关命令 |
| `nbot/commands/media/*.py` | ~500 | 图片、视频、音乐、骰子等 |
| `nbot/commands/chat/*.py` | ~400 | TTS、翻译、运势、提醒等 |
| `nbot/commands/mc/*.py` | ~150 | Minecraft 命令 |
| `nbot/commands/__init__.py` | ~100 | 向后兼容的重新导出 |

### 4.2 `nbot/web/server.py`（3031 行 → 约 8 个文件）

| 新文件 | 行数 | 职责 |
|--------|------|------|
| `nbot/web/server.py` | ~450 | 协调器：初始化、注册路由与事件 |
| `nbot/web/server_auth.py` | ~250 | 登录、Token、密码、限流 |
| `nbot/web/server_ai.py` | ~450 | AI 客户端初始化与模型配置 |
| `nbot/web/server_heartbeat.py` | ~350 | 心跳调度 |
| `nbot/web/server_workflow.py` | ~450 | 工作流调度 |
| `nbot/web/server_task.py` | ~350 | 自定义任务调度 |
| `nbot/web/server_knowledge.py` | ~200 | 知识库检索 |
| `nbot/web/server_qq_sync.py` | ~150 | QQ 消息同步 |
| `nbot/web/server_personality.py` | ~250 | 角色预设加载 |
| `nbot/web/server_message.py` | ~200 | 消息构建 |
| `nbot/web/server_utils.py` | ~150 | 格式化运行时间、MinerU 解析等 |

### 4.3 其他大文件拆分

| 原文件 | 拆分结果 |
|--------|----------|
| `nbot/cli_cc_style.py`（2880 行） | `nbot/cli/app.py`、`screens.py`、`components.py`、`styles.py`、`completer.py`、`utils.py` |
| `nbot/services/tools.py`（2310 行） | `nbot/services/ai/tools/definitions.py`、`nbot/services/ai/tools/builtins.py`、`nbot/services/ai/tools/executor.py`、`nbot/services/ai/tools/workspace_tools.py`、`nbot/services/ai/tools/memory_tools.py`、`nbot/services/ai/tools/pending_exec.py` |
| `nbot/web/ai_service.py`（1851 行） | `nbot/web/ai/service.py`、`nbot/web/ai/tools.py`、`nbot/web/ai/images.py`、`nbot/web/ai/trigger.py` |
| `nbot/web/routes/personality.py`（1405 行） | `nbot/web/routes/persona/personality.py`、`nbot/web/routes/persona/compile.py`、`nbot/web/routes/persona/platform.py` |
| `nbot/web/routes/sessions.py`（1121 行） | `nbot/web/routes/chat/sessions.py`、`nbot/web/routes/chat/sessions_utils.py` |
| `nbot/core/ai_pipeline.py`（1271 行） | `nbot/core/pipeline/pipeline.py`、`nbot/core/pipeline/callbacks.py`、`nbot/core/pipeline/tools.py` |
| `nbot/ai_commands.py`（1258 行） | `nbot/commands/ai/registry.py`、`nbot/commands/ai/handlers.py`、`nbot/commands/ai/utils.py` |
| `nbot/core/workspace.py`（1235 行） | `nbot/core/workspace/manager.py`、`nbot/core/workspace/file_ops.py`、`nbot/core/workspace/utils.py` |

---

## 5. 日志系统重构

### 当前问题
1. `ncatbot.utils.logger.get_log()` 与 `logging.getLogger(__name__)` 混用。
2. 没有统一的 `dictConfig`，CLI 手动抑制日志器。
3. `bot.py` 中存在 `print()`。
4. `CharacterEventLogger` 是另一套自定义日志。

### 新设计

**配置位置：** `nbot/utils/logger.py`。

```python
import logging
import logging.config
import os
from logging.handlers import RotatingFileHandler

DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def setup_logging(level: str = "INFO", log_dir: str = "logs") -> None:
    os.makedirs(log_dir, exist_ok=True)
    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"standard": {"format": DEFAULT_FORMAT}},
        "handlers": {
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
        },
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
```

**迁移示例：**
```python
# 迁移前
from ncatbot.utils.logger import get_log
_log = get_log()

# 迁移后
from nbot.utils.logger import get_logger
_log = get_logger(__name__)
```

**CLI 静默：**
```python
from nbot.utils.logger import silence_loggers
silence_loggers("nbot", "werkzeug", "urllib3", "requests", "socketio", "engineio", "apscheduler")
```

**上下文标签：** 通过 `logging.Filter` 注入 `[server|cli|qq]` 上下文，便于追踪服务状态。

---

## 6. `.gitignore` 更新

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

# 虚拟环境
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

# 测试
.pytest_cache/
.mypy_cache/
.coverage
htmlcov/

# 运行时 / 用户特定配置
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

# 数据目录
cache/
logs/
tmp/
saved_message/
data/
downloads/
resources/
!resources/prompts/

# Web 上传
nbot/web/static/uploads/
!nbot/web/static/uploads/.gitkeep

# 插件下载
nbot/plugins/bilibili
```

---

## 7. 迁移顺序

目标是每阶段结束后机器人仍可运行。

### Phase 1：基础工具与日志
1. 创建 `nbot/utils/`。
2. 实现 `nbot/utils/logger.py`。
3. 实现 `nbot/utils/paths.py`（含 `get_downloads_dir()`、`make_download_path()`）。
4. 实现 `nbot/config.py`（统一的 `.env` 配置）。
5. 在 `bot.py` 中调用 `setup_logging()`。
6. 在关键文件中替换 `get_log()` 与 `logging.getLogger(__name__)`。
7. **提交并冒烟测试：** `python bot.py --help`

### Phase 2：HTTP 与 Base64 统一
1. 实现 `nbot/utils/http_client.py`。
2. 实现 `nbot/utils/base64_image.py`。
3. 在 `commands.py`、`services/tools.py` 中替换直接 HTTP 调用。
4. **冒烟测试：** `/random_image`

### Phase 3：消息发送与沙盒桥接
1. 实现 `nbot/utils/message_sender.py`。
2. 实现 `nbot/utils/sandbox_bridge.py`。
3. 替换 `commands.py` 中的群/私发分支。
4. **冒烟测试：** 在 QQ 群和私聊各发送一条消息。

### Phase 4：拆分 `nbot/commands.py` 基础设施部分
1. 创建 `nbot/commands/`。
2. 迁移注册、分发、持久化、调度、闲聊、消息补丁、沙盒包装。
3. 创建 `__init__.py` 做兼容导出。
4. 更新 `bot.py` 与 `ai_commands.py` 的导入。
5. **冒烟测试：** QQ 机器人启动与基础命令。

### Phase 5：拆分 `nbot/commands.py` 业务命令
1. 按领域迁移 admin、system、jmcomic、novel、media、chat、mc 等命令。
2. **冒烟测试：** 每个命令类别抽测。

### Phase 6：拆分 `nbot/web/server.py`
1. 创建 `nbot/web/server_*.py`。
2. 按职责迁移认证、AI、心跳、工作流、任务、知识库、QQ 同步、角色、消息、工具函数。
3. 保留 `server.py` 为薄协调器。
4. **冒烟测试：** Web 面板启动、登录、基础聊天。

### Phase 7：拆分 `nbot/services/tools.py`
1. 创建 `nbot/services/ai/tools/`。
2. 迁移定义、执行器、内置工具、workspace 工具、记忆工具、待执行命令到 `services/ai/tools/`。
3. **冒烟测试：** Web 聊天中调用工具。

### Phase 8：拆分 Web AI 服务与路由
1. 拆分 `web/ai/service.py`、`web/ai/tools.py`、`web/ai/images.py`、`web/ai/trigger.py`；拆分 `routes/personality.py` 到 `routes/persona/`；拆分 `routes/sessions.py` 到 `routes/chat/`。
2. **冒烟测试：** Web AI 图片聊天、切换人格。

### Phase 9：拆分核心 pipeline、AI 命令、workspace
1. 拆分 `core/ai_pipeline.py` 到 `core/pipeline/`；拆分 `ai_commands.py` 到 `commands/ai/`；拆分 `core/workspace.py` 到 `core/workspace/`。
2. **冒烟测试：** 完整 AI pipeline 与 workspace 操作。

### Phase 10：拆分 CLI
1. 创建 `nbot/cli/`。
2. 拆分 `cli_cc_style.py`。
3. **冒烟测试：** CLI 模式启动。

### Phase 11：最终清理
1. 更新 `.gitignore`。
2. 运行文件长度检查：`find nbot -name "*.py" | xargs wc -l | awk '$1 > 500 {print}'`，期望无输出。
3. 补齐 docstring 与类型注解。
4. 删除死代码。
5. **最终冒烟测试。**

---

## 8. 工程规范

### 命名
- 模块：`snake_case.py`
- 类：`PascalCase`
- 函数/变量：`snake_case`
- 常量：`UPPER_SNAKE_CASE`
- 私有辅助：`_leading_underscore`

### Docstring
- Google 风格，公共函数/类必须包含 `Args:` / `Returns:` / `Raises:`。

### 类型注解
- 所有新函数签名必须带类型注解。
- 文件顶部使用 `from __future__ import annotations`。
- 使用 `X | None` 风格（Python 3.10+）。

### 导入顺序
```python
from __future__ import annotations

# stdlib
import os
from typing import Optional

# third-party
import requests
from flask import Flask

# local absolute
from nbot.utils.logger import get_logger
from nbot.utils.paths import get_project_root

# local relative（仅在必要时）
from . import something
```

### 文件长度
- 硬限制：每 `.py` 文件 ≤500 行。
- 检查命令：`find nbot -name "*.py" | xargs wc -l | awk '$1 > 500 {print}'`
- CI/lint 中应失败阻断。

### 注释
- 行内注释使用 `#`。
- docstring 使用 `"""`。
- 新代码注释使用英文；重构时仅对修改的段落决定是否翻译旧中文注释。

---

## 9. 验证计划

### 9.1 文件长度检查
```bash
find nbot -name "*.py" | xargs wc -l | awk '$1 > 500 {print}'
```

### 9.2 单元测试
新增 `tests/` 目录：
- `tests/utils/test_logger.py`
- `tests/utils/test_paths.py`
- `tests/test_config.py`
- `tests/utils/test_http_client.py`
- `tests/utils/test_base64_image.py`
- `tests/utils/test_message_sender.py`

### 9.3 现有测试
- `python tools/test_jm_upload.py`
- 如有 `tools/test_commands.py` 也运行。

### 9.4 启动冒烟测试
```bash
python bot.py --no-web
python bot.py --only-web
python bot.py --cli
python bot.py --cli-and-web
```

### 9.5 命令冒烟测试
- `/help`
- `/jmrank 周排行`
- `/findbook test`
- `/random_image`
- `/tts`
- `/workspace`

### 9.6 Web 路由冒烟测试
- 登录面板
- 创建会话并发送消息获取 AI 回复
- 上传文件到 workspace
- 切换人格
- 配置心跳

### 9.7 代码检查
```bash
ruff check nbot/
ruff format --check nbot/
# 或
flake8 nbot/ --max-line-length=100
```

---

## 10. 统一下载资源目录

**目标：** 将散落在 `tmp/`、`cache/pdf/`、`cache/jm_cover_cache/` 等位置的下载资源统一放到 `downloads/`，并按类型分类。

### 10.1 目录结构
```
downloads/
|-- videos/          # Bilibili、Douyin 等视频
|-- images/          # 封面图、随机图、生成图
|-- pdfs/            # JM 漫画 PDF 等
|-- audio/           # TTS、音乐、语音
|-- others/          # 其他附件
```

### 10.2 分类规则

| 资源类型 | 目录 | 示例 |
|----------|------|------|
| 视频 | `downloads/videos/` | `bili_BV1xxxx_20260625_143052.mp4` |
| 图片 | `downloads/images/` | `jm_cover_123_20260625_143052.jpg` |
| PDF | `downloads/pdfs/` | `jm_123456_20260625_143052.pdf` |
| 音频 | `downloads/audio/` | `tts_xxx_20260625_143052.mp3` |
| 其他 | `downloads/others/` | 未知或混合附件 |

### 10.3 命名规范
```
{source}_{resource_id}_{timestamp}.{ext}
```

### 10.4 路径助手 API
```python
from enum import Enum

class DownloadType(str, Enum):
    VIDEO = "videos"
    IMAGE = "images"
    PDF = "pdfs"
    AUDIO = "audio"
    OTHER = "others"

def get_downloads_dir(subpath: str = "") -> str: ...
def make_download_path(
    source: str,
    resource_id: str,
    ext: str,
    dtype: DownloadType = DownloadType.OTHER,
    timestamp: str | None = None,
) -> str: ...
```

### 10.5 现有路径迁移

| 原路径 | 新路径 | 说明 |
|--------|--------|------|
| `tmp/bili_*.mp4` | `downloads/videos/` | 更新 `bilibili_parser.py` |
| `tmp/douyin_*.mp4` | `downloads/videos/` | 更新 `douyin_parser.py` |
| `cache/pdf/{id}.pdf` | `downloads/pdfs/` | 更新 JM 漫画 PDF 输出 |
| `cache/jm_cover_cache/{id}.jpg` | `downloads/images/` | 更新 JM 封面缓存逻辑 |
| `cache/search/*.html`、`cache/rank/*.html` | 保留在 `cache/` | 非用户下载资源 |
| 随机图/视频临时文件 | `downloads/images/` 或 `downloads/videos/` | 更新媒体命令 |

### 10.6 清理策略
- 在 `.env` 中提供 `DOWNLOAD_MAX_AGE_DAYS` 与 `DOWNLOAD_MAX_TOTAL_SIZE_MB`。
- 在 `nbot/utils/paths.py` 或新建 `nbot/utils/download_cleanup.py` 中实现清理。
- 启动时或 APScheduler 定时执行。

---

## 11. 关键实现文件清单

- `nbot/utils/logger.py` — 统一日志设置
- `nbot/config.py` — 唯一的 `.env` 配置入口
- `nbot/utils/paths.py` — 路径与下载目录助手
- `nbot/utils/message_sender.py` — 群/私聊统一发送
- `nbot/utils/sandbox_bridge.py` — QQ 沙盒桥接
- `nbot/commands/__init__.py` — 命令包的兼容导出
- `nbot/web/server.py` — 拆分后的薄协调器
