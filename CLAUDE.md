# NekoBot — 多频道 AI 聊天机器人

## 项目定位

QQ + Telegram + Feishu + Web + CLI 五通道 AI 聊天机器人。基于 [NapCatQQ](https://github.com/NapNeko/NapCatQQ)（OneBot 11 协议）+ [ncatbot](https://github.com/liyihao1110/ncatbot) SDK 驱动 QQ 频道，通义千问 / 兼容 OpenAI 接口的 LLM 作为 AI 引擎，Flask + SocketIO 作为 Web 管理面板。支持角色扮演、定时聊天、漫画/视频下载、小说检索等插件化功能。

- **入口文件**: `bot.py`
- **Python 版本**: 3.13
- **依赖管理**: `requirements.txt` + `requirements-optional.txt`
- **环境变量**: `.env`（`BOT_UIN`、`WS_URI`、`TOKEN`）
- **macOS 环境**: 通过 hard link 桥接 QQ 沙盒（`~/Library/Containers/com.tencent.qq/`）

---

## 顶层文件

| 文件 | 作用 |
|------|------|
| `bot.py` | 启动入口：加载 .env → 应用 sandbox bridge → 初始化 Web 服务器 → 启动 NCatBot → 注册插件 → 阻塞运行。支持 `--cli` / `--no-web` / `--only-web` / `--cli-and-web` 多种模式 |
| `.env` | `BOT_UIN`、`WS_URI=ws://127.0.0.1:30051`、`TOKEN=napcat_token` |
| `config.ini` | Web 服务器配置（host/port/debug 等） |
| `switches.json` | SwitchManager 持久化的功能开关（TTS/jm_send/auto_reply 等） |
| `admin.txt` | 管理员 QQ 号列表，每行一个 |
| `requirements.txt` | 核心依赖（ncatbot、flask、aiohttp、jieba、pydub 等） |
| `requirements-optional.txt` | pikepdf、pynacl |

---

## 目录总览

```
nekobot/
├── bot.py                      # 入口
├── nbot/                       # 主源码（267 个 .py 文件，~52k 行）
│   ├── config.py                # Config 单例（.env 加载器）
│   ├── chat.py                  # 🔗 兼容 shim → nbot/services/chat_service.py
│   ├── heartbeat.py             # 🔗 兼容 shim → nbot/core/heartbeat.py
│   ├── ai_commands.py           # 🔗 兼容 shim → nbot/commands/ai/
│   ├── cli_simple.py            # 🔗 兼容 shim → nbot/cli/simple_app.py
│   ├── cli_cc_style.py          # 🔗 兼容 shim → nbot/cli/cc_app.py
│   ├── commands.py              # 🔗 兼容 shim（命令注册仍在此，逐步迁移中）
│   ├── commands/                # 命令系统（按业务域拆分）
│   │   ├── registry.py          # register_command 装饰器
│   │   ├── state.py             # 共享状态（command_handlers, admin, favorites...）
│   │   ├── dispatch/            # 消息分发（群/私聊路由、@bot 检测、文件保存）
│   │   ├── ai/                  # AI 增强命令（原 ai_commands.py）
│   │   ├── chat/                # 聊天命令（tts/remind/fortune/translate/del_message/task）
│   │   ├── jmcomic/             # 禁漫下载/搜索/排行/收藏/黑名单
│   │   ├── novel/               # 轻小说搜索（4000+ 条目）
│   │   ├── mc/                  # Minecraft 服务器状态
│   │   ├── media/               # 图片/视频/音乐/dice_rps
│   │   ├── shared/              # 共享工具（数据持久化/chatter/scheduler/file_sender/email）
│   │   ├── admin.py             # 管理命令
│   │   ├── at_all.py            # @全体成员
│   │   ├── bot_api.py           # BotAPI 包装层（sandbox bridge + 消息记录）
│   │   ├── system.py            # /restart /shutdown
│   │   ├── workspace_cmds.py    # 工作区命令
│   │   └── other.py             # 杂项命令
│   ├── core/                    # AI 引擎核心
│   │   ├── pipeline/            # AI 处理管道（pipeline/phases/callbacks/tools/attachments）
│   │   ├── workspace/           # 工作区文件管理（manager/file_ops/upload/references/shared_ops）
│   │   ├── memory/              # 记忆管理
│   │   ├── knowledge/           # 知识库
│   │   ├── ai_pipeline.py       # 🔗 兼容 shim → core/pipeline/
│   │   ├── message_middleware.py # 通用消息预处理（附件解析→媒体描述→注入 content）
│   │   ├── agent_service.py     # Agent 服务
│   │   ├── auto_memory.py       # 自动记忆
│   │   ├── chat_models.py       # 聊天数据模型
│   │   ├── file_parser.py       # 文件解析
│   │   ├── model_adapter.py     # LLM 模型适配器
│   │   ├── progress_card.py     # 进度卡片
│   │   ├── prompt.py            # Prompt 构造
│   │   ├── prompt_format.py     # Prompt 格式化工具
│   │   ├── session_store.py     # 会话存储
│   │   ├── skills_manager.py    # 技能管理器
│   │   ├── todo_card.py         # TODO 卡片
│   │   ├── token_stats.py       # Token 统计
│   │   └── workflow.py          # 工作流引擎
│   ├── services/                # 服务层
│   │   ├── ai/tools/            # AI 工具定义与执行（builtins/definitions/exec_tools/executor/memory/misc/news/web/workspace）
│   │   ├── ai.py                # AI 客户端适配层（通义千问 / OpenAI 兼容 API）
│   │   ├── anthropic_adapter.py # Anthropic 适配器
│   │   ├── chat_service.py      # 聊天编排：消息路由、会话管理
│   │   ├── dynamic_executor.py  # 动态执行器
│   │   ├── feishu_service.py    # 飞书 Bot 服务
│   │   ├── feishu_ws_service.py # 飞书 WebSocket 服务
│   │   ├── feishu_chat_service.py # 飞书聊天服务
│   │   ├── telegram_service.py  # Telegram 服务
│   │   ├── react.py             # ReAct 循环
│   │   ├── skills_tools.py      # 技能工具定义
│   │   ├── todo_tools.py        # TODO 工具
│   │   ├── tool_registry.py     # 工具注册表
│   │   ├── tools.py             # 工具聚合导出
│   │   ├── tts.py               # 文本转语音
│   │   └── stt.py               # 语音转文本
│   ├── character/               # 角色扮演引擎
│   │   ├── models.py            # 数据模型
│   │   ├── runtime.py           # 运行时
│   │   ├── compiler.py          # 编译器
│   │   ├── planner.py           # 规划器
│   │   ├── prompt_builder.py    # Prompt 构建器
│   │   ├── prompt_stack.py      # Prompt 栈
│   │   ├── state_machine.py     # 情感状态机
│   │   ├── policies.py          # 策略
│   │   ├── events.py            # 事件系统
│   │   ├── memory.py            # 角色记忆
│   │   ├── repository.py        # 角色仓库
│   │   ├── adapters/            # 适配器（nekobot）
│   │   └── storage/             # 存储后端（json_store）
│   ├── channels/                # 多频道适配
│   │   ├── base.py              # 基类/接口定义
│   │   ├── qq.py                # QQ 频道适配器
│   │   ├── telegram.py          # Telegram 适配器
│   │   ├── feishu.py            # 飞书适配器
│   │   ├── web.py               # Web 频道适配器
│   │   ├── configured.py        # 已配置频道
│   │   └── registry.py          # 频道注册表
│   ├── web/                     # Web 管理面板（Flask + SocketIO）
│   │   ├── server.py            # Web 服务器核心
│   │   ├── socket_events.py     # SocketIO 事件处理
│   │   ├── ai_service.py        # Web AI 服务
│   │   ├── message_adapter.py   # 消息适配器
│   │   ├── persistence.py       # 持久化
│   │   ├── sessions_db.py       # 会话数据库（SQLite）
│   │   ├── secure_store.py      # 安全存储（Fernet 加密）
│   │   ├── push_keys.py         # Push 密钥
│   │   ├── agent_tools.py       # Agent 工具
│   │   ├── ai/                  # AI 子模块（service/models/tools/callbacks/images/progress/trigger）
│   │   ├── routes/              # 路由模块（28 个）
│   │   │   ├── chat/            # 会话路由（sessions/archive/import_export/utils）
│   │   │   ├── persona/         # 角色路由（personality/compile/crud/io/ai/platform）
│   │   │   ├── auth.py          # 认证
│   │   │   ├── ai_config.py     # AI 配置
│   │   │   ├── ai_models.py     # AI 模型管理
│   │   │   ├── channels.py      # 频道管理
│   │   │   ├── characters.py    # 角色管理
│   │   │   ├── files.py         # 文件管理
│   │   │   ├── heartbeat.py     # 心跳
│   │   │   ├── knowledge.py     # 知识库
│   │   │   ├── live2d.py        # Live2D 虚拟形象
│   │   │   ├── memory.py        # 记忆
│   │   │   ├── push.py          # Push 通知
│   │   │   ├── qrcode.py        # 二维码
│   │   │   ├── skills.py        # 技能
│   │   │   ├── voice.py         # 语音
│   │   │   ├── web_agent.py     # Web Agent
│   │   │   ├── workflows.py     # 工作流
│   │   │   └── workspace_*.py   # 工作区（misc/private/shared）
│   │   ├── utils/               # 工具（config_loader）
│   │   ├── static/              # 静态资源（CSS/JS/Live2D/vendor/uploads）
│   │   └── templates/           # Jinja2 模板
│   ├── plugins/                 # 插件系统
│   │   ├── manager.py           # 插件管理器
│   │   ├── dispatcher.py        # Skill 调度器（解析 AI 回复中的 [SKILL:xxx] 调用）
│   │   ├── bilibili_parser.py   # B 站视频解析
│   │   ├── douyin_parser.py     # 抖音视频解析
│   │   └── skills/              # 技能系统
│   │       ├── base.py          # SkillContext / SkillRegistry
│   │       ├── loader.py        # 技能加载器
│   │       ├── dynamic_skill.py # 动态技能
│   │       └── builtin/         # 内置技能（download/search）
│   ├── cli/                     # Rich TUI 交互终端
│   │   ├── app.py               # CLI 应用入口
│   │   ├── simple_app.py        # Simple 模式 App
│   │   ├── simple_handlers.py   # Simple 模式命令处理器
│   │   ├── simple_ai.py         # Simple 模式 AI
│   │   ├── cc_app.py            # CC Style App
│   │   ├── cc_ai.py             # CC Style AI
│   │   ├── cc_commands.py       # CC Style 命令
│   │   ├── cc_display.py        # CC Style 显示
│   │   ├── cc_personality.py    # CC Style 角色
│   │   ├── cc_utils.py          # CC Style 工具
│   │   ├── cc_workspace.py      # CC Style 工作区
│   │   ├── completer.py         # 自动补全
│   │   ├── markdown.py          # Markdown 渲染
│   │   ├── styles.py            # 样式定义
│   │   ├── components/          # UI 组件（layout/panels/input）
│   │   └── screens/             # 界面（main/chat/tools/sessions/config/base）
│   └── utils/                   # 通用工具
│       ├── base64_image.py      # Base64 图片处理
│       ├── http_client.py       # HTTP 客户端
│       ├── logger.py            # 日志配置
│       ├── message_sender.py    # 消息发送器
│       ├── paths.py             # 路径工具
│       └── sandbox_bridge.py    # macOS QQ 沙盒桥接
├── resources/                   # 静态资源
│   └── config/
│       ├── option.yml           # jmcomic 下载器配置
│       ├── urls.ini             # 随机图片/视频/表情 API URL
│       ├── emoji_map.json       # QQ 表情映射
│       └── novel_details2.json  # 4000+ 轻小说元数据
├── tools/                       # 辅助脚本
│   ├── test_jm_upload.py        # sandbox bridge 测试
│   ├── test_commands.py         # 命令测试
│   ├── update_novel.py          # 小说数据更新
│   └── sort_novels_by_res.py    # 小说排序
├── tests/                       # 单元测试
│   ├── test_config.py           # Config 测试
│   └── utils/                   # 工具测试（http_client/base64_image/paths/message_sender/logger/sandbox_bridge）
├── cache/                       # 漫画/搜索/封面缓存（运行时生成）
├── data/                        # 工作区数据
│   └── workspaces/              # 工作区文件（_shared + 各会话目录）
├── tmp/                         # 临时下载目录
├── logs/                        # 日志文件
├── docs/                        # 文档
└── saved_message/               # 保存的消息
```

---

## 核心模块详解

### `nbot/commands/` — 命令系统（已从单文件拆分为子包）

原 `commands.py`（~4700 行）已按业务域拆分为子包，但 `nbot/commands.py` 仍保留为兼容 shim。

**子包结构：**

| 子包 | 内容 |
|------|------|
| `registry.py` | `register_command` 装饰器 + `get_all_help_text_for_prompt`，命令分为 8 个 category |
| `state.py` | 共享可变状态（`command_handlers`, `admin`, `black_list_comic`, `running`, `tasks`, `user_favorites`, `group_favorites`, `comic_cache`, `api_book`, `schedule_tasks`, `smtp_config`, `at_all_group`, `books`, `if_tts`） |
| `dispatch/` | `dispatch_message` → `handle_group_message` / `handle_private_message`，`is_at_bot` 检测，文件自动保存到 workspace |
| `ai/` | AI 增强命令（原 `ai_commands.py`）—— `handlers_chat.py`, `handlers_admin.py`, `handlers_admin_helpers.py`, `registry.py`, `utils.py` |
| `chat/` | 聊天命令：`tts.py`, `remind.py`, `fortune.py`, `translate.py`, `del_message.py`, `task.py` |
| `jmcomic/` | 禁漫命令：`download.py`, `search.py`, `rank.py`, `favorites.py`, `blacklist.py`, `html_builder.py`, `settings.py` |
| `novel/` | 轻小说：`search.py`, `info.py`, `hot.py`, `html_builder.py`, `wenku8_api.py` |
| `mc/` | Minecraft 服务器状态 |
| `media/` | `image.py`, `video.py`, `music.py`, `dice_rps.py` |
| `shared/` | 跨模块共享：`data_persistence.py`（load/save 系列）、`chatter.py`（chat_loop）、`scheduler.py`、`file_sender.py`、`message_patches.py`、`email.py` |

**包入口 `__init__.py`** 统一 re-export 所有公共 API，子模块只需 `from nbot.commands import ...` 即可。

### `nbot/core/` — AI 引擎核心

| 文件/子包 | 作用 |
|------|------|
| `pipeline/` | AI 处理管道——`AIPipeline`（编排）→ `PipelineContext` → phases（prep/chat/tool_loop）→ callbacks |
| `workspace/` | 工作区——`WorkspaceManager`（核心）→ `file_ops.py`（CRUD）、`upload.py`（上传）、`references.py`（引用）、`shared_ops.py`（共享操作）、`utils.py`（工具） |
| `memory/` | 记忆管理 |
| `knowledge/` | 知识库 |
| `message_middleware.py` | 通用消息预处理：AttachmentResolver → MediaDescriber → MessagePreprocessor，统一附件格式 `{type, url, source, source_ref, mime_type, name}` |
| `agent_service.py` | Agent 服务 |
| `auto_memory.py` | 自动记忆 |
| `chat_models.py` | 聊天数据模型 |
| `file_parser.py` | 文件解析 |
| `message.py` | 消息模型 |
| `model_adapter.py` | LLM 模型适配器 |
| `progress_card.py` | 进度卡片（TUI） |
| `prompt.py` | Prompt 构造 |
| `prompt_format.py` | Prompt 格式化 |
| `session_store.py` | 会话持久化存储 |
| `skills_manager.py` | 技能管理器 |
| `todo_card.py` | TODO 卡片（TUI） |
| `token_stats.py` | Token 统计 |
| `workflow.py` | 工作流引擎 |

### `nbot/services/` — 服务层

| 文件/子包 | 作用 |
|------|------|
| `ai.py` | AI 客户端适配层（通义千问 / OpenAI 兼容 API） |
| `anthropic_adapter.py` | Anthropic API 适配器 |
| `chat_service.py` | 聊天编排：用户/群消息路由、会话管理 |
| `react.py` | ReAct 循环（让 LLM 自主使用工具） |
| `ai/tools/` | AI 工具系统——`definitions.py`（定义）、`executor.py`（执行）、`builtins.py`/`memory_tools.py`/`web_tools.py`/`workspace_tools.py`/`news_tools.py`/`misc_tools.py`（各类工具实现） |
| `skills_tools.py` | 技能工具定义与注册 |
| `tool_registry.py` | 工具注册表 |
| `dynamic_executor.py` | 动态代码执行器 |
| `todo_tools.py` | TODO 工具 |
| `tts.py` / `stt.py` | 文本转语音 / 语音转文本 |
| `telegram_service.py` | Telegram Bot 服务 |
| `feishu_service.py` / `feishu_chat_service.py` / `feishu_ws_service.py` | 飞书三件套 |

### `nbot/character/` — 角色扮演引擎

独立运行的拟人层——角色档案 → 情感状态机 → 信号分析 → 反应规划 → 行为输出，与 AI 对话流并行。

| 文件 | 作用 |
|------|------|
| `models.py` | 角色/档案数据模型 |
| `runtime.py` | 运行时核心 |
| `compiler.py` | 角色编译器 |
| `planner.py` | 行为规划器 |
| `prompt_builder.py` | Prompt 构建器 |
| `prompt_stack.py` | Prompt 栈管理 |
| `state_machine.py` | 情感状态机 |
| `policies.py` | 行为策略 |
| `events.py` | 事件系统 |
| `memory.py` | 角色记忆 |
| `repository.py` | 角色持久化仓库 |
| `adapters/nekobot.py` | NekoBot 适配器 |
| `storage/json_store.py` | JSON 存储后端 |

### `nbot/channels/` — 多频道适配

| 文件 | 作用 |
|------|------|
| `base.py` | 基类/接口定义 |
| `qq.py` | QQ 频道适配器 |
| `telegram.py` | Telegram 适配器 |
| `feishu.py` | 飞书适配器 |
| `web.py` | Web 频道适配器 |
| `configured.py` | 已配置频道管理 |
| `registry.py` | 频道注册表 |

### `nbot/web/` — Web 管理面板

Flask + SocketIO 架构，**session 持久化在 SQLite**（`sessions_db.py`），**敏感数据用 Fernet 加密**（`secure_store.py`）。

| 文件/子包 | 作用 |
|------|------|
| `server.py` | Flask app 工厂 + SocketIO 初始化 |
| `socket_events.py` | SocketIO 事件处理（实时聊天） |
| `ai_service.py` | Web AI 服务 |
| `ai/` | AI 子模块——`service.py`（核心服务）、`models.py`（模型）、`tools.py`（工具）、`callbacks.py`（回调）、`images.py`（图片）、`progress.py`（进度）、`trigger.py`（触发器） |
| `routes/` | 28 个路由模块 |
| `routes/chat/` | 会话管理：`sessions.py`（核心）、`sessions_archive.py`（归档）、`sessions_import_export.py`（导入导出）、`sessions_utils.py`（工具） |
| `routes/persona/` | 角色管理：`personality.py`（核心）、`personality_crud.py`（CRUD）、`personality_ai.py`（AI）、`personality_io.py`（导入导出）、`compile.py`（编译）、`platform.py`（平台） |
| `routes/` 其他 | `auth.py`, `ai_config.py`, `ai_models.py`, `api_keys.py`, `channels.py`, `characters.py`, `config_legacy.py`, `files.py`, `heartbeat.py`, `knowledge.py`, `live2d.py`, `memory.py`, `public_sessions.py`, `push.py`, `qq_overview.py`, `qrcode.py`, `skills.py`, `skills_storage.py`, `task_center.py`, `tools.py`, `voice.py`, `web_agent.py`, `workflows.py`, `workspace_*.py` |

### `nbot/plugins/` — 插件系统

| 文件 | 作用 |
|------|------|
| `manager.py` | 插件管理器（加载/卸载/执行） |
| `dispatcher.py` | Skill 调度器——解析 AI 回复中的 `[SKILL:name]params[/SKILL]` 标签，执行并替换结果 |
| `bilibili_parser.py` | B 站视频解析：检测链接 → 封面图(base64) + 文字 → 下载视频 → sandbox bridge |
| `douyin_parser.py` | 抖音视频解析（同上模式） |
| `skills/` | 技能系统——`base.py`（SkillContext/SkillRegistry）、`loader.py`（加载器）、`dynamic_skill.py`（动态技能）、`builtin/`（download/search） |

### `nbot/cli/` — TUI 终端

基于 Rich 库的交互式终端。两种模式：
- **CC Style** (`cc_app.py`)：仿 Claude Code 风格的全功能终端
- **Simple** (`simple_app.py`)：简化终端

| 子包 | 内容 |
|------|------|
| `components/` | UI 组件——`layout.py`（布局）、`panels.py`（面板）、`input.py`（输入框） |
| `screens/` | 界面——`main.py`（主界面）、`chat.py`（聊天）、`tools.py`（工具）、`sessions.py`（会话）、`config.py`（配置）、`base.py`（基类） |

### `nbot/utils/` — 通用工具

| 文件 | 作用 |
|------|------|
| `sandbox_bridge.py` | macOS QQ 沙盒桥接——自动 `os.link()` hard link 文件到沙盒内 |
| `message_sender.py` | 消息发送器（兼容多频道） |
| `base64_image.py` | Base64 图片编解码 |
| `http_client.py` | HTTP 客户端封装 |
| `logger.py` | 日志配置 |
| `paths.py` | 路径工具 |

---

## 关键设计模式

### 1. 命令注册

```python
from nbot.commands import register_command

@register_command("/jm", help_text="/jm <漫画ID> -> 下载漫画", category="1")
async def handle_jmcomic(msg, is_group=True):
    ...
```

命令处理器存储在 `nbot.commands.state.command_handlers` dict，由 `nbot.commands.dispatch.dispatch_message` 统一分发。

**迁移到子包时**，命令 handler 定义在 `nbot/commands/jmcomic/download.py` 等子模块，通过 `nbot/commands.py`（兼容 shim）导入注册。

### 2. macOS QQ Sandbox 桥接

macOS 把 QQ Helper 限制在 `~/Library/Containers/com.tencent.qq/` 容器内。任何容器外文件 `fs.open()` 都返回 EPERM。

桥接实现已从 `commands.py` 提取到 **`nbot/utils/sandbox_bridge.py`**。`bot.py` 在启动时调用 `apply_qq_sandbox_bridge()` 自动包装 BotAPI 的上传方法。**所有文件上传调用点自动受益，无需逐处修改。**

桥接常量：`QQ_SANDBOX_DIR = ~/Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/nekobot_files/`

### 3. 视频发送

B 站/抖音视频的完整链路：
1. 插件检测链接 → 调 API 拿 CDN URL
2. **封面图**：aiohttp 下载 → base64 编码 → `Image(data:image/jpeg;base64,...)` 内联在消息里（bot 后端不拉 URL——B 站 CDN 要求 Referer）
3. **视频**：aiohttp 下载到 `tmp/*.mp4` → `post_group_file(video=path)` → sandbox bridge 自动 hard link → NapCat 以视频消息发出
4. 失败时给用户明确反馈（不会静默失败）

### 4. 错误处理约定

- ncatbot 的 `@report` 装饰器在 API 失败时**只记 WARNING 日志，不抛异常**——返回值是 `{'status': 'failed', 'retcode': ..., 'message': ...}`
- 检查 API 调用结果必须判断 `result.get("status") == "ok"`，不能只依赖 try/except
- 用户可见的失败必须有明确反馈（不能只 log）

### 5. 消息预处理管道

`nbot/core/message_middleware.py` 为所有频道提供统一的附件处理：
1. **AttachmentResolver** — 频道特定 → 可访问 URL / data URL
2. **MediaDescriber** — 媒体类型 → AI 文字描述
3. **MessagePreprocessor** — 编排，注入 content

附件标准格式：`{type, url, source, source_ref, mime_type, name, ...}`

### 6. Skill 调度

AI 回复中可包含 `[SKILL:name]params[/SKILL]` 标签，`SkillDispatcher` 自动解析、执行并替换结果文本。Skill 定义在 `nbot/plugins/skills/`，通过 `PluginsManager` 加载。

---

## 缓存/临时文件路径

| 用途 | 路径 |
|------|------|
| PDF 漫画 | `cache/pdf/{id}.pdf` |
| JM 封面缓存 | `cache/jm_cover_cache/{id}.jpg` |
| 搜索/排行 HTML | `cache/search/`、`cache/rank/`、`cache/fav/` |
| 收藏夹/黑名单 | `cache/list/`、`cache/black_list/` |
| 定时聊天状态 | `cache/running/` |
| B 站/抖音视频 | `tmp/bili_*.mp4`、`tmp/douyin_*.mp4` |
| QQ Sandbox 桥接 | `~/Library/Containers/com.tencent.qq/Data/Library/Application Support/QQ/nekobot_files/` |
| 工作区文件 | `data/workspaces/`（`_shared/` + 各会话子目录） |

---

## 配置资源

| 文件 | 说明 |
|------|------|
| `resources/config/option.yml` | jmcomic 配置（下载目录、img2pdf 插件、文件名规则） |
| `resources/config/urls.ini` | 按 section 组织的图片/视频/表情 API URL 列表 |
| `resources/config/novel_details2.json` | 4000+ 轻小说元数据（标题/作者/分类/封面/下载链接） |
| `resources/config/emoji_map.json` | QQ 表情 ID → 文字描述映射 |

---

## 常用工作流

### 新增命令
1. 根据命令类型在 `nbot/commands/<domain>/` 下找到对应子模块（如禁漫 → `jmcomic/`，聊天 → `chat/`）
2. 用 `@register_command("/xxx", help_text="...", category="N")` 装饰 async 函数
3. 函数签名：`async def handler(msg, is_group=True)`，`msg` 是 NCatBot 消息对象
4. 用 `msg.raw_message` 取原始文本，`msg.reply(text=...)` 回复
5. 需要发文件时直接用 `bot.api.post_group_file(video=path)` 等——sandbox bridge 自动生效
6. **仍需在 `nbot/commands.py`（兼容 shim）中 import 以确保注册**

### 调试
- 日志在 `logs/bot_YYYY_MM_DD.log`
- 关键 grep 关键词：`[Bili]`、`[Douyin]`、`[jm]`、`EPERM`、`Forbidden`、`qq-sandbox`
- 测试：`python3 tools/test_jm_upload.py`（验证 sandbox bridge）| `python3 -m pytest tests/`

### 启动方式
- `python3 bot.py` — 默认模式（QQ + Web 面板）
- `python3 bot.py --cli` — CLI 终端模式
- `python3 bot.py --only-web` — 仅 Web 面板
- `python3 bot.py --no-web` — 仅 QQ 机器人
- `python3 bot.py --cli-and-web` — CLI + Web 同时启动
- 管理命令 `/restart`（`os.execv`）和 `/shutdown`（`sys.exit`）
- 修改 `nbot/` 下任何 .py 后需要重启（无热重载）

---

## 架构速览

```
bot.py (入口)
  ├─ apply_qq_sandbox_bridge()        # nbot/utils/sandbox_bridge.py
  ├─ Config 单例                       # nbot/config.py
  ├─ setup_logging()                  # nbot/utils/logger.py
  ├─ run_bot() ────────────────────── # 加载 nbot/commands → NCatBot.run()
  ├─ run_cli() ────────────────────── # nbot/cli/cc_app.py / simple_app.py
  ├─ start_web_server() ───────────── # nbot/web/server.py → Flask + SocketIO
  └─ run_cli_and_web()               # 多线程：Web + CLI

命令流: 用户消息 → dispatch_message() → command_handlers → handler(msg)
聊天流: 非命令消息 → chat_service → AI pipeline → tools loop → 回复
插件流: AI 回复中的 [SKILL:] → SkillDispatcher → 执行 → 替换结果
文件流: 本地文件 → sandbox_bridge hard link → QQ 沙盒 → NapCat 上传
```
