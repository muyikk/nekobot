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
| `bot.py` | 启动入口：加载 .env → 初始化 Web 服务器 → 启动 NCatBot → 注册插件 → 阻塞运行 |
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
├── bot.py                  # 入口
├── nbot/                   # 主源码（99 个 .py 文件）
│   ├── commands.py          # QQ 命令注册 + BotAPI 包装层（沙盒桥接）
│   ├── ai_commands.py       # AI 增强命令
│   ├── services/            # AI、聊天、TTS、技能工具库
│   ├── core/                # AI 引擎核心（prompt、RAG、消息历史、工具循环）
│   ├── character/           # 角色扮演引擎（档案、情感状态机）
│   ├── channels/            # QQ/Telegram/Feishu/Web 频道适配
│   ├── web/                 # Flask Web 管理面板（28 路由模块）
│   ├── plugins/             # 技能系统 + 抖音/B站解析器 + 小说命令
│   ├── cli/                 # Rich TUI 交互终端
│   ├── chat.py / config.py / heartbeat.py  # 兼容 shim（指向新位置）
├── resources/               # 静态资源
│   └── config/
│       ├── option.yml       # jmcomic 下载器配置
│       ├── urls.ini         # 随机图片/视频/表情 API URL
│       ├── emoji_map.json   # QQ 表情映射
│       └── novel_details2.json  # 4000+ 轻小说元数据
├── tools/                   # 测试脚本
│   └── test_jm_upload.py    # sandbox bridge 测试（12 个用例）
├── cache/                   # 漫画/搜索/封面缓存（运行时生成）
├── data/                    # 工作区数据
├── tmp/                     # 临时下载目录
└── logs/                    # 日志文件
```

---

## 核心模块

### `nbot/commands.py` — 主命令处理器（~4700 行）

- **注册命令**：`@register_command("/cmd", help_text="...", category="1-4")` 装饰器
- **BotAPI 包装层**：模块加载时自动应用 3 层 monkey-patch：
  1. `_nbot_patched`：记录机器人发出的所有消息到历史（`post_private_msg` / `post_group_msg`）
  2. `_nbot_sandbox_wrapped`：自动把本地文件 hard link 到 QQ 沙盒（`post_group_file` / `post_private_file` / `upload_group_file` / `upload_private_file` 的 `file`/`image`/`video`/`record`/`markdown` kwarg）——解决 macOS QQ App Sandbox EPERM 问题
- **SwitchManager**：持久化功能开关（json 文件），支持群/用户级别
- **关键函数**：`load_address()` 返回 `cache/` 绝对路径，所有子目录（pdf/rank/search/fav/jm_cover_cache）建在它下面

### `nbot/services/` — 服务层

| 文件 | 作用 |
|------|------|
| `ai.py` | AI 客户端适配层（通义千问 / OpenAI 兼容 API） |
| `chat_service.py` | 聊天编排：用户/群消息路由、会话管理、每日总结、ReAct 循环 |
| `skills_tools.py` | 94KB 技能工具库——结构化工具定义与注册 |
| `tts.py` | 文本转语音（TTS） |
| `stt.py` | 语音转文本（STT） |

### `nbot/core/` — AI 引擎核心

| 文件 | 作用 |
|------|------|
| `heartbeat.py` | 心跳保持（WebSocket 保活） |
| `prompt.py` | Prompt 构造 |
| `rag.py` | 检索增强生成 |
| `message_history.py` | 消息历史管理 |
| `tool_loop.py` | 工具调用循环（让 LLM 自主使用工具） |
| `workspace.py` | 工作区文件管理 |
| `token_tracker.py` | Token 计数追踪 |
| `file_parser.py` | 文件解析 |
| `knowledge/` | 知识库子模块 |

### `nbot/character/` — 角色扮演引擎

独立运行的拟人层——角色档案 → 情感状态机 → 信号分析 → 反应规划 → 行为输出，与 AI 对话流并行。

### `nbot/channels/` — 多频道适配

| 文件 | 作用 |
|------|------|
| `qq.py` | QQ 频道适配器 |
| `telegram.py` | Telegram 适配器 |
| `feishu.py` | 飞书适配器 |
| `web.py` | Web 频道适配器 |
| `base.py` | 基类 / 接口定义 |

### `nbot/web/` — Web 管理面板（Flask + SocketIO）

33 个文件，28 个路由模块。功能包括：
- 实时聊天界面（WebSocket）
- Live2D 虚拟形象
- 会话管理（SQLite 持久化）
- 安全存储（Fernet 加密）
- PWA 支持
- 角色配置管理

### `nbot/plugins/` — 插件系统

| 文件 | 作用 |
|------|------|
| `bilibili_parser.py` | B 站视频解析：检测 B 站链接 → 封面图(base64) + 文字信息 → 下载视频 → sandbox bridge 发送 |
| `douyin_parser.py` | 抖音视频解析：同 B 站模式 |
| `skills/` | 技能系统（builtin 占位 + external + web 配置型动态技能） |
| `novel_commands.py` | 轻小说检索命令（基于 `novel_details2.json` 的 4000+ 条目） |

### `nbot/ai_commands.py` — AI 增强命令

12+ 额外 slash 命令，包括 /.summary（每日总结）、/.clear（清除会话）等。

### `nbot/cli/` — TUI 终端

基于 Rich 库的交互式终端界面：`CLIApp` → Screen 类（Main/Chat/Tools/Sessions/Config）→ Component 类（Header/Footer/Sidebar/InputBox）。

---

## 关键设计模式

### 1. 命令注册

```python
@register_command("/jm", help_text="/jm <漫画ID> -> 下载漫画", category="1")
async def handle_jmcomic(msg, is_group=True):
    ...
```

命令处理器存储在全局 `command_handlers` dict，由 `dispatch_message` 统一分发。

### 2. macOS QQ Sandbox 桥接

macOS 把 QQ Helper 限制在 `~/Library/Containers/com.tencent.qq/` 容器内。任何容器外文件 `fs.open()` 都返回 EPERM。解决方案：在 BotAPI 类级别用 `_wrap_botapi_upload` 包装 4 个上传方法，自动 `os.link()` hard link 到沙盒内。**所有文件上传调用点自动受益，无需逐处修改。**

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
1. 在 `nbot/commands.py` 用 `@register_command("/xxx", help_text="...", category="N")` 装饰 async 函数
2. 函数签名：`async def handler(msg, is_group=True)`，`msg` 是 NCatBot 消息对象
3. 用 `msg.raw_message` 取原始文本，`msg.reply(text=...)` 回复
4. 需要发文件时直接用 `bot.api.post_group_file(video=path)` 等——sandbox bridge 自动生效

### 调试
- 日志在 `logs/bot_YYYY_MM_DD.log`
- 关键 grep 关键词：`[Bili]`、`[Douyin]`、`[jm]`、`EPERM`、`Forbidden`、`qq-sandbox`
- 测试：`python3 tools/test_jm_upload.py`（验证 sandbox bridge）

### 重启机器人
- 管理命令 `/restart`（`os.execv`）和 `/shutdown`（`sys.exit`）
- 修改 `nbot/` 下任何 .py 后需要重启（无热重载）
