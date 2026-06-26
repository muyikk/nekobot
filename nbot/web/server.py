"""Web 聊天服务后端

提供 REST API 和 WebSocket 接口。
作为薄协调器，通过 mixin 组合继承各职责模块的方法。
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Flask
from flask_socketio import SocketIO

from nbot.utils.logger import get_logger
from nbot.web.ai_service import (
    get_ai_response,
    get_ai_response_with_images,
    get_ai_response_with_tools,
    parse_tool_call_from_text,
    stream_ai_response,
    stream_send_response,
    trigger_ai_response_for_request,
)
from nbot.web.persistence import (
    init_default_data,
    load_all_data,
    save_data,
)
from nbot.web.routes import (
    register_admin_misc_routes,
    register_ai_config_routes,
    register_ai_model_routes,
    register_api_key_routes,
    register_auth_routes,
    register_channel_routes,
    register_character_routes,
    register_config_legacy_routes,
    register_file_routes,
    register_heartbeat_routes,
    register_knowledge_routes,
    register_live2d_routes,
    register_memory_routes,
    register_personality_routes,
    register_public_session_routes,
    register_push_routes,
    register_qq_overview_routes,
    register_qrcode_routes,
    register_session_routes,
    register_skill_routes,
    register_skills_storage_routes,
    register_task_center_routes,
    register_tool_routes,
    register_voice_routes,
    register_web_agent_routes,
    register_workflow_routes,
    register_workspace_misc_routes,
    register_workspace_private_routes,
    register_workspace_shared_routes,
)
from nbot.web.secure_store import read_secure_json, write_secure_json
from nbot.web.socket_events import register_socket_events

from nbot.web.server_ai import AIMixin
from nbot.web.server_auth import AuthMixin
from nbot.web.server_heartbeat import HeartbeatMixin
from nbot.web.server_knowledge import KnowledgeMixin
from nbot.web.server_message import MessageMixin
from nbot.web.server_personality import PersonalityMixin
from nbot.web.server_qq_sync import QQSyncMixin
from nbot.web.server_task import TaskMixin
from nbot.web.server_utils import (
    _format_uptime,
    _resolve_web_adapter,
    parse_document_with_mineru,
)
from nbot.web.server_workflow import WorkflowMixin

_log = get_logger(__name__)

# 尝试导入 APScheduler
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False

# 导入知识库管理器
try:
    from nbot.core.knowledge import get_knowledge_manager, configure_knowledge_embedding

    KNOWLEDGE_MANAGER_AVAILABLE = True
except ImportError:
    get_knowledge_manager = None  # type: ignore[misc,assignment]
    configure_knowledge_embedding = None  # type: ignore[misc,assignment]
    KNOWLEDGE_MANAGER_AVAILABLE = False
    _log.warning("Knowledge manager not available")

# 导入统一消息模块
try:
    from nbot.core import AgentService, ChatResponse, WebSessionStore, message_manager, create_message
    from nbot.channels.registry import get_channel_adapter, register_channel_handler
    from nbot.channels.web import WebChannelAdapter

    MESSAGE_MODULE_AVAILABLE = True
except ImportError:
    MESSAGE_MODULE_AVAILABLE = False
    WebSessionStore = None  # type: ignore[misc,assignment]
    AgentService = None  # type: ignore[misc,assignment]
    WebChannelAdapter = None  # type: ignore[misc,assignment]
    get_channel_adapter = None  # type: ignore[misc,assignment]
    register_channel_handler = None  # type: ignore[misc,assignment]
    message_manager = None  # type: ignore[misc,assignment]
    create_message = None  # type: ignore[misc,assignment]
    _log.warning("Message module not available")

# 导入 Prompt 管理器
try:
    from nbot.core.prompt import prompt_manager

    PROMPT_MANAGER_AVAILABLE = True
except ImportError:
    PROMPT_MANAGER_AVAILABLE = False
    prompt_manager = None  # type: ignore[misc,assignment]
    _log.warning("Prompt manager not available")

# 导入工作区管理器
try:
    from nbot.core.workspace import workspace_manager

    WORKSPACE_AVAILABLE = True
except ImportError:
    WORKSPACE_AVAILABLE = False
    workspace_manager = None  # type: ignore[misc,assignment]

# 导入进度卡片管理器
try:
    from nbot.core.progress_card import progress_card_manager, ProgressCard, StepType

    PROGRESS_CARD_AVAILABLE = True
except ImportError:
    PROGRESS_CARD_AVAILABLE = False
    progress_card_manager = None  # type: ignore[misc,assignment]
    _log.warning("Progress card manager not available")

# 导入 Todo 卡片管理器
try:
    from nbot.core.todo_card import todo_card_manager, TodoCard

    TODO_CARD_AVAILABLE = True
except ImportError:
    TODO_CARD_AVAILABLE = False
    todo_card_manager = None  # type: ignore[misc,assignment]
    _log.warning("Todo card manager not available")

# 导入文件解析器
try:
    from nbot.core.file_parser import file_parser

    FILE_PARSER_AVAILABLE = True
except ImportError:
    FILE_PARSER_AVAILABLE = False
    file_parser = None  # type: ignore[misc,assignment]
    _log.warning("File parser not available")

# 导入配置加载器（支持 .env 环境变量）
try:
    from nbot.web.utils.config_loader import (
        get_api_config,
        get_pic_config,
        get_search_config,
        resolve_runtime_api_key,
        get_video_config,
    )

    CONFIG_LOADER_AVAILABLE = True
except ImportError:
    CONFIG_LOADER_AVAILABLE = False
    get_api_config = None  # type: ignore[misc,assignment]
    get_pic_config = None  # type: ignore[misc,assignment]
    get_search_config = None  # type: ignore[misc,assignment]
    resolve_runtime_api_key = None  # type: ignore[misc,assignment]
    get_video_config = None  # type: ignore[misc,assignment]
    _log.warning("Config loader not available")


class WebChatServer(
    AuthMixin,
    AIMixin,
    HeartbeatMixin,
    WorkflowMixin,
    TaskMixin,
    KnowledgeMixin,
    QQSyncMixin,
    PersonalityMixin,
    MessageMixin,
):
    """Web 聊天服务器（薄协调器）。"""

    _instance = None

    @classmethod
    def get_instance(cls):
        """获取单例实例。"""
        return cls._instance

    def __init__(self, app: Flask, socketio: SocketIO):
        cls = self.__class__
        if cls._instance is not None:
            raise RuntimeError(
                "WebChatServer 只能有一个实例，请使用 get_instance() 获取"
            )
        cls._instance = self

        self.app = app
        self.socketio = socketio
        self.static_folder = os.path.join(os.path.dirname(__file__), "static")
        self.base_dir = os.path.join(os.path.dirname(__file__), "..", "..")
        self.MESSAGE_MODULE_AVAILABLE = MESSAGE_MODULE_AVAILABLE
        self.message_manager = message_manager
        self.create_message = create_message
        self.KNOWLEDGE_MANAGER_AVAILABLE = KNOWLEDGE_MANAGER_AVAILABLE
        self.get_knowledge_manager = get_knowledge_manager
        self.PROMPT_MANAGER_AVAILABLE = PROMPT_MANAGER_AVAILABLE
        self.prompt_manager = prompt_manager
        self.PROGRESS_CARD_AVAILABLE = PROGRESS_CARD_AVAILABLE
        self.progress_card_manager = progress_card_manager
        self.TODO_CARD_AVAILABLE = TODO_CARD_AVAILABLE
        self.todo_card_manager = todo_card_manager
        self.WORKSPACE_AVAILABLE = WORKSPACE_AVAILABLE
        self.workspace_manager = workspace_manager
        self.FILE_PARSER_AVAILABLE = FILE_PARSER_AVAILABLE
        self.file_parser = file_parser

        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.session_store = WebSessionStore(
            self.sessions, save_callback=lambda: self._save_data("sessions")
        )
        self.agent_service = AgentService()
        web_handler = (
            lambda chat_request, adapter=None, server=self: trigger_ai_response_for_request(
                server, chat_request, adapter=adapter
            )
        )
        self.agent_service.register_handler("web", web_handler)
        if register_channel_handler:
            register_channel_handler("web", web_handler)
        self.web_channel_adapter = _resolve_web_adapter(None)

        # 初始化进度卡片管理器
        if PROGRESS_CARD_AVAILABLE and progress_card_manager:
            progress_card_manager.set_socketio(socketio)
            progress_card_manager.set_sessions(self.sessions)
            _log.info("[ProgressCard] 进度卡片管理器已初始化")

        # 初始化 Todo 卡片管理器
        if TODO_CARD_AVAILABLE and todo_card_manager:
            todo_card_manager.set_socketio(socketio)
            todo_card_manager.set_sessions(self.sessions)
            _log.info("[TodoCard] Todo 卡片管理器已初始化")
        self.web_users: Dict[str, str] = {}
        self.active_connections: Dict[str, str] = {}
        self.visible_web_sessions: Dict[str, str] = {}

        # 数据存储目录
        self.data_dir = os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "web"
        )
        os.makedirs(self.data_dir, exist_ok=True)

        # Token 统计管理器（统一持久化，必须最先初始化）
        from nbot.core.token_stats import init_token_stats_manager
        self.token_stats_manager = init_token_stats_manager(self.data_dir)
        self.token_stats: Dict = self.token_stats_manager.data

        # 内存数据存储
        self.workflows: List[Dict] = []
        self.memories: List[Dict] = []
        self.ai_config: Dict = {}
        self.custom_personality_presets: List[Dict] = []
        self.personality: Dict = {}
        self.system_logs: List[Dict] = []
        self.settings: Dict = {}

        # 性能优化：统计缓存
        self._stats_cache: Dict = {}
        self._stats_cache_time: float = 0
        self._stats_cache_ttl: float = 5.0

        # Skills 配置
        self.skills_config: List[Dict] = []

        # Tools 配置
        self.tools_config: List[Dict] = []
        self.channels_config: List[Dict] = []

        # Heartbeat 配置
        self.heartbeat_config: Dict = {
            "enabled": False,
            "interval_minutes": 60,
            "content_file": "heartbeat.md",
            "target_session_id": "",
            "targets": [],
            "last_run": None,
            "next_run": None,
        }

        # Heartbeat 调度器
        self.heartbeat_job = None
        self.scheduled_tasks: List[Dict[str, Any]] = []
        self.scheduled_task_jobs: Dict[str, Any] = {}
        self.running_task_ids: set = set()
        self.running_workflow_ids: set = set()

        # 系统启动时间
        self.start_time = time.time()

        # AI 客户端引用
        self.ai_client = None
        self.ai_model = None
        self.ai_api_key = None
        self.ai_base_url = None

        # 多模型配置管理
        self.ai_models: List[Dict] = []
        self.active_model_id: str = None
        self.active_models_by_purpose: Dict[str, str] = {}

        # 工作流调度器
        self.scheduler = None
        if APSCHEDULER_AVAILABLE:
            try:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                self.scheduler = AsyncIOScheduler(event_loop=loop)
                self.scheduler.start()
            except Exception as e:
                _log.error(f"Failed to start scheduler: {e}")
                self.scheduler = None

        # QQ Bot 引用
        self.qq_bot = None

        # 登录密码
        self.web_password = None
        self._web_password_is_hash = False

        # 登录失败限流
        self._login_fail_records: Dict[str, Dict[str, Any]] = {}
        self._login_rate_limit = 5
        self._login_rate_window = 300

        # 登录 Token 管理
        self.login_tokens: Dict[str, Dict[str, Any]] = {}
        self.token_expire_days = 30

        # 停止事件字典
        self.stop_events: Dict[str, threading.Event] = {}
        self.startup_ready = False
        self.startup_error: Optional[str] = None
        self.startup_thread: Optional[threading.Thread] = None

        self._load_ai_config()
        self._load_web_config()
        self._register_routes()
        self._register_auth_middleware()
        self._register_socket_events()
        self._init_default_data()
        self._load_personality()
        self._load_custom_personality_presets()
        self._start_background_initialization()

    def _load_web_config(self):
        """从配置文件加载 Web 配置。"""
        try:
            import configparser
            config = configparser.ConfigParser()
            config.read("config.ini", encoding="utf-8")

            self.web_password = (
                os.getenv("WEB_PASSWORD")
                or config.get("web", "password", fallback=None)
            )
            if self.web_password:
                if self.web_password.startswith(("$2b$", "$2a$")):
                    self._web_password_is_hash = True
                    _log.info("Web login password is set (bcrypt hash)")
                else:
                    self._web_password_is_hash = False
                    _log.info("Web login password is set (plaintext)")
            else:
                _log.warning(
                    "Web login password is not set; login API will reject all users"
                )
        except Exception as e:
            _log.error(f"Failed to load web config: {e}")

    def _start_background_initialization(self):
        """Load heavier startup data after the server begins accepting requests."""
        def run():
            try:
                self._load_all_data()
                if self.active_model_id:
                    self._apply_ai_model(self.active_model_id)
                elif not self.ai_client:
                    self._initialize_ai_client()
                self._init_workflow_scheduler()
                self._init_custom_task_scheduler()
                self._check_knowledge_index()
                self._auto_start_feishu_ws_channels()
                self.startup_ready = True
                _log.info("Web server background initialization completed")
            except Exception as e:
                self.startup_error = str(e)
                _log.error(f"Web server background initialization failed: {e}")

        self.startup_thread = threading.Thread(
            target=run,
            name="web-startup-init",
            daemon=True,
        )
        self.startup_thread.start()

    def _init_default_data(self):
        return init_default_data(self)

    def _load_all_data(self):
        return load_all_data(self)

    def _invalidate_sessions_cache(self):
        """清理会话列表缓存。"""
        self._sessions_cache = []
        self._sessions_cache_time = 0

    def _save_data(self, data_type: str):
        return save_data(self, data_type)

    def set_qq_bot(self, bot):
        """设置 QQ Bot 引用。"""
        self.qq_bot = bot

    def log_message(self, level: str, message: str, important: bool = False):
        """记录系统日志。"""
        log = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "message": message,
            "important": important,
        }
        self.system_logs.append(log)
        if len(self.system_logs) > 1000:
            self.system_logs = self.system_logs[-1000:]
        self._save_data("logs")

    def _get_ai_response(self, messages: List[Dict]) -> str:
        return get_ai_response(self, messages)

    def _stream_ai_response(self, messages: List[Dict], session_id: str, callback):
        return stream_ai_response(self, messages, session_id, callback)

    def _stream_send_response(
        self, session_id: str, message: Dict, thinking_content: str = None
    ):
        return stream_send_response(self, session_id, message, thinking_content)

    def _get_ai_response_with_images(
        self, messages: List[Dict], image_urls: List[str], user_question: str = None
    ) -> str:
        return get_ai_response_with_images(self, messages, image_urls, user_question)

    def _get_ai_response_with_tools(
        self,
        messages: List[Dict],
        tools: List[Dict],
        use_silicon: bool = False,
        stop_event=None,
    ) -> Dict:
        return get_ai_response_with_tools(
            self,
            messages,
            tools,
            use_silicon,
            stop_event,
        )

    def _parse_tool_call_from_text(self, content: str) -> list:
        return parse_tool_call_from_text(self, content)

    def _register_routes(self):
        """注册 HTTP 路由。"""
        register_admin_misc_routes(self.app, self)
        register_ai_config_routes(self.app, self)
        register_ai_model_routes(self.app, self)
        register_auth_routes(self.app, self)
        register_channel_routes(self.app, self)
        register_character_routes(self.app, self)
        register_heartbeat_routes(self.app, self)
        register_knowledge_routes(self.app, self)
        register_live2d_routes(self.app, self)
        register_memory_routes(self.app, self)
        register_personality_routes(self.app, self)
        register_push_routes(self.app, self)
        register_qq_overview_routes(self.app, self)
        register_qrcode_routes(self.app, self)
        register_public_session_routes(self.app, self)
        register_session_routes(self.app, self)
        register_skill_routes(self.app, self)
        register_task_center_routes(self.app, self)
        register_tool_routes(self.app, self)
        register_workflow_routes(self.app, self)
        register_web_agent_routes(self.app, self)
        register_workspace_private_routes(self.app, self)
        register_workspace_shared_routes(self.app, self)
        register_workspace_misc_routes(self.app, self)
        register_config_legacy_routes(self.app, self)

    def _register_socket_events(self):
        """Register WebSocket handlers."""
        register_socket_events(self)

    def _trigger_ai_response(
        self,
        session_id: str,
        user_content: str,
        sender: str,
        attachments=None,
        parent_message_id=None,
    ):
        """触发 AI 响应。"""
        adapter = _resolve_web_adapter(self.web_channel_adapter)
        chat_request = adapter.build_chat_request(
            conversation_id=session_id,
            content=user_content,
            sender=sender,
            attachments=attachments,
            parent_message_id=parent_message_id,
        )
        self.agent_service.process(chat_request, adapter=adapter)

    def add_message_to_session(
        self, session_id: str, role: str, content: str, sender: str, source: str = "qq"
    ):
        """从外部添加消息到会话（QQ 消息同步）。"""
        if not self.session_store.get_session(session_id):
            return

        adapter = _resolve_web_adapter(self.web_channel_adapter)
        message = adapter.build_message(
            role=role,
            content=content,
            sender=sender,
            conversation_id=session_id,
            source=source,
        )

        self.session_store.append_message(session_id, message)
        self.socketio.emit("new_message", message, room=session_id)

    def create_web_session(self, user_id: str, name: str = None) -> str:
        """创建 Web 会话。"""
        from nbot.core.prompt_format import format_skills_prompt
        from .routes.personality import compile_personality_prompt

        session_id = str(uuid.uuid4())

        _log.info(f"Creating session with personality: {self.personality.get('name', '未命名')}")
        _log.info(f"systemPrompt length: {len(self.personality.get('systemPrompt', ''))}")

        system_prompt = self.personality.get("systemPrompt", "")
        if not system_prompt:
            _log.warning("systemPrompt is empty, compiling from personality data")
            system_prompt = compile_personality_prompt(self.personality, user_name=user_id)
            _log.info(f"Compiled system_prompt length: {len(system_prompt)}")
        else:
            system_prompt = system_prompt.replace('{{user}}', user_id or '')
            system_prompt = system_prompt.replace('{{char}}', self.personality.get("name", ""))

        sender_name = self.personality.get("name", "AI")
        character_id = self.personality.get("id") or sender_name

        features = (self.settings or {}).get("features") or {}
        if features.get("skills_prompt_injection", False):
            enabled_skills = [s for s in self.skills_config if s.get("enabled", True)]
            system_prompt += format_skills_prompt(self.skills_config)
            _log.info(f"已添加 {len(enabled_skills)} 个技能到会话 {session_id[:8]}")
        else:
            _log.info(f"Skills prompt injection disabled for session {session_id[:8]}")

        messages = [{"role": "system", "content": system_prompt}]

        first_message = self.personality.get("firstMessage", "")
        if first_message:
            first_message = first_message.replace('{{user}}', user_id or '')
            messages.append({
                "role": "assistant",
                "content": first_message,
                "sender": sender_name
            })
            _log.info(f"已添加开场白，来自角色: {self.personality.get('name', 'AI')}")

        session = {
            "id": session_id,
            "name": name or f"Web 会话 {session_id[:8]}",
            "type": "web",
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "messages": messages,
            "system_prompt": system_prompt,
            "character_id": character_id,
            "sender_name": sender_name,
            "sender_avatar": self.personality.get("avatar", ""),
            "sender_portrait": self.personality.get("portrait", ""),
        }

        self.session_store.set_session(session_id, session)
        return session_id


def create_web_app(config: Dict[str, Any] = None) -> tuple[Flask, SocketIO, WebChatServer]:
    """创建 Flask 应用。"""
    import secrets

    app = Flask(__name__, static_folder=None)
    app.config["SECRET_KEY"] = (
        os.getenv("NBOT_SECRET_KEY")
        or os.getenv("SECRET_KEY")
        or secrets.token_urlsafe(32)
    )
    app.config.update(config or {})

    cors_origins_env = os.getenv("NBOT_CORS_ORIGINS", "").strip()
    cors_allowed_origins = (
        [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
        if cors_origins_env
        else None
    )

    socketio = SocketIO(
        app,
        async_mode="threading",
        cors_allowed_origins=cors_allowed_origins,
        max_http_buffer_size=100 * 1024 * 1024,
    )

    server = WebChatServer(app, socketio)

    register_file_routes(app, server, WORKSPACE_AVAILABLE, workspace_manager)
    register_skills_storage_routes(app, server)
    register_voice_routes(app, server)
    register_api_key_routes(app, server)

    return app, socketio, server
