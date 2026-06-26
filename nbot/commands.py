from ncatbot.core import BotClient, GroupMessage, PrivateMessage, BotAPI
from nbot.utils.logger import get_logger
from nbot.core.heartbeat import HeartbeatCore

from nbot.web.utils.config_loader import load_config
from nbot.web.secure_store import read_secure_json, write_secure_json
from nbot.services.chat_service import group_messages, user_messages, chat, generate_today_summary, summarize_group_text
from nbot.services.chat_service import delete_session_workspace, get_qq_session_id, WORKSPACE_AVAILABLE
from nbot.services.ai import ai_client
from nbot.services.tts import tts
import base64
import hashlib
import html
import jmcomic
from nbot.utils.http_client import get_sync, post_sync, head_sync
from nbot.utils.message_sender import send_text, send_file
import random
import configparser
import json
import yaml
import re
import os
import asyncio
import time
from jmcomic import *
from typing import Dict, List
from datetime import datetime
from PIL import Image as PILImage
from ncatbot.core import (
    MessageChain,
    Music,
)

# Import infrastructure from the new commands package
from nbot.commands.state import (
    command_handlers,
    admin,
    black_list_comic,
    running,
    tasks,
    user_favorites,
    group_favorites,
    comic_cache,
    api_book,
    schedule_tasks,
    smtp_config,
    user_email,
    at_all_group,
    books,
    if_tts,
)
from nbot.commands.registry import register_command, get_all_help_text_for_prompt
from nbot.commands.dispatch import (
    dispatch_message,
    handle_group_message,
    handle_private_message,
    is_at_bot,
    _normalize_qq_id,
    _get_value,
    _bot_uin_candidates,
    _iter_mention_ids,
    _iter_message_segments,
    _is_at_all_enabled,
    _save_incoming_files_to_workspace,
    _get_project_root,
)
from nbot.commands.shared.data_persistence import (
    normalize_file_path,
    read_at_all_group,
    write_at_all_group,
    write_admin,
    load_admin,
    load_address,
    load_favorites,
    load_smtp_config,
    save_smtp_config,
    load_email_config,
    save_email_config,
    save_favorites,
    write_blak_list,
    load_blak_list,
    write_running,
    normalize_timestamp,
    load_running,
    load_novel_data,
)
from nbot.commands.shared.scheduler import (
    schedule_task,
    schedule_task_by_date,
    schedule_job_task,
)
from nbot.commands.shared.chatter import (
    chatter,
    chat_loop,
    update_user_active_chat_time,
    update_running,
)
from nbot.commands.shared.message_patches import apply_message_patches
from nbot.commands.shared.file_sender import async_send_file, handle_generic_file
from nbot.commands.shared.email import send_comic_email, _send_comic_email_sync
from nbot.commands.help import handle_help
from nbot.commands.bot_api import handle_api, parse_command_string
from nbot.commands.at_all import handle_at_all_group

# Import domain command submodules so @register_command decorators execute
from nbot.commands.jmcomic import rank, search, tag, download, favorites, blacklist, settings
from nbot.commands.novel import search as novel_search, info, hot, download as novel_download
from nbot.commands.media import image, video, music, dice_rps
from nbot.commands.chat import tts, del_message, translate, fortune, remind, task
from nbot.commands import admin as admin_cmds, system, mc, workspace_cmds, other

#----------------------
# region Global setup
#----------------------

_log = get_logger(__name__)

bot_id, admin_id = load_config()  # 加载配置,返回机器人qq号

bot = BotClient()
heartbeat_core = HeartbeatCore(bot.api)

# Apply message patches (records bot-sent messages to history)
apply_message_patches()

# Populate the nbot.commands package with bot and switch so submodules
# can import them via "from nbot.commands import bot, switch".
import nbot.commands as _commands_pkg
_commands_pkg.bot = bot

#-------------------------
#     region Load data
#-------------------------

load_favorites()
load_admin()
load_blak_list()
load_running()
load_novel_data()
read_at_all_group()
load_smtp_config()
load_email_config()

#-------------------------
#     region SwitchManager
#-------------------------

class SwitchManager:
    """
    开关管理器，支持群聊和个人开关的批量管理
    群聊开关以群为整体
    """

    def __init__(self):
        # 存储所有开关状态
        self.group_switches = {}  # {group_id: {switch_name: bool}}
        self.user_switches = {}   # {user_id: {switch_name: bool}}
        self.switch_configs = {}   # {switch_name: {'default': bool, 'description': str}}

        # 初始化默认开关
        self._init_default_switches()

    def _init_default_switches(self):
        """初始化默认开关配置"""
        self.switch_configs = {

        }

    def add_switch(self, switch_name: str, default_value: bool = False, description: str = ""):
        """添加新的开关类型"""
        self.switch_configs[switch_name] = {
            'default': default_value,
            'description': description
        }
        self.save_switches()

    def get_switch_state(self, switch_name: str, group_id: str = None, user_id: str = None):
        """获取开关状态"""
        if switch_name not in self.switch_configs:
            raise ValueError(f"未知的开关类型: {switch_name}")

        # 优先检查用户开关
        if user_id and user_id in self.user_switches:
            if switch_name in self.user_switches[user_id]:
                return self.user_switches[user_id][switch_name]

        # 检查群聊开关
        if group_id and group_id in self.group_switches:
            if switch_name in self.group_switches[group_id]:
                return self.group_switches[group_id][switch_name]

        # 返回默认值
        return self.switch_configs[switch_name]['default']

    def set_switch_state(self, switch_name: str, state: bool, group_id: str = None, user_id: str = None):
        """设置开关状态"""
        if switch_name not in self.switch_configs:
            raise ValueError(f"未知的开关类型: {switch_name}")

        if user_id:
            if user_id not in self.user_switches:
                self.user_switches[user_id] = {}
            self.user_switches[user_id][switch_name] = state
        elif group_id:
            if group_id not in self.group_switches:
                self.group_switches[group_id] = {}
            self.group_switches[group_id][switch_name] = state
        else:
            raise ValueError("必须提供group_id或user_id")
        self.save_switches()

    def toggle_switch(self, switch_name: str, group_id: str = None, user_id: str = None):
        """切换开关状态"""
        current_state = self.get_switch_state(switch_name, group_id, user_id)
        new_state = not current_state
        self.set_switch_state(switch_name, new_state, group_id, user_id)
        self.save_switches()
        return new_state

    def get_switch_info(self, switch_name: str):
        """获取开关信息"""
        if switch_name not in self.switch_configs:
            return None
        return self.switch_configs[switch_name]

    def list_all_switches(self):
        """列出所有开关类型"""
        return list(self.switch_configs.keys())

    def save_switches(self, file_path: str = "switches.json"):
        """
        保存开关状态到文件
        :param file_path: 保存路径
        """
        data = {
            'group_switches': self.group_switches,
            'user_switches': self.user_switches
        }
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_switches(self, file_path: str = "switches.json"):
        """
        从文件加载开关状态
        :param file_path: 加载路径
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.group_switches = data.get('group_switches', {})
                self.user_switches = data.get('user_switches', {})
        except FileNotFoundError:
            # 文件不存在时使用默认值
            pass

switch = SwitchManager()  # 加载开关
switch.load_switches()
switch.add_switch('tts', default_value=False, description='TTS语音开关')
switch.add_switch('jm_send', default_value=True, description='漫画发送开关')
switch.add_switch('jm_send_user', default_value=False, description='用户私信发送漫画开关')
switch.add_switch('command', default_value=True, description='命令开关')
switch.add_switch('pdf_password', default_value=False, description='PDF密码开关')
switch.add_switch('summary_auto', default_value=False, description='每日自动总结开关')
switch.add_switch('active_chat', default_value=False, description='主动聊天开关')
switch.add_switch('auto_reply', default_value=False, description='群聊智能自动回复开关')
switch.add_switch('jm_send_email', default_value=False, description='漫画邮箱发送开关')
switch.save_switches()

# Export switch to the commands package
_commands_pkg.switch = switch

#----------------------
#     region 命令
#----------------------

# 获取机器人QQ号
from nbot.config import get_config
BOT_UIN = str(get_config().get('BotConfig', 'bot_uin', fallback="")).strip()

from nbot.ai_commands import register_ai_commands

register_ai_commands(
    register_command=register_command,
    bot=bot,
    log=_log,
    project_root=_get_project_root,
    admin=admin,
    read_secure_json=read_secure_json,
    write_secure_json=write_secure_json,
    workspace_available=WORKSPACE_AVAILABLE,
    switch=switch,
    running=running,
    write_running=write_running,
    normalize_timestamp=normalize_timestamp,
    heartbeat_core=heartbeat_core,
    normalize_file_path=normalize_file_path,
    load_address=load_address,
)


# 防止重复注册事件处理器
if not hasattr(bot, '_nbot_handlers_registered'):
    bot.add_group_event_handler(handle_group_message)
    bot.add_private_event_handler(handle_private_message)
    bot._nbot_handlers_registered = True
