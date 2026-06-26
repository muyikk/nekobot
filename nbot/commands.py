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

@register_command("/tts",help_text = "/tts -> 开启或关闭TTS(admin)",admin_show = True,category = "4")
async def handle_tts(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "你没有权限使用此命令喵~", is_group=is_group)
        return
    if_tts = switch.toggle_switch('tts', group_id=str(msg.group_id) if is_group else None, user_id=str(msg.user_id) if not is_group else None)

    text = "已开启TTS喵~" if if_tts else "已关闭TTS喵~"
    await send_text(msg, text, is_group=is_group)
    switch.save_switches()

# ---------------漫画类命令----------------
comic_cache = []
JM_RANK_DECODE_LIMIT = 50
@register_command("/jmrank",help_text = "/jmrank <月排行/周排行> -> 获取排行榜",category = "1")
async def handle_jmrank(msg, is_group=True):
    await send_text(msg, "正在获取排行喵~", is_group=is_group)
    select = msg.raw_message[len("/jmrank"):].strip()
    op = JmOption.default()
    cl = op.new_jm_client()
    page: JmCategoryPage = cl.categories_filter(
        page=1,
        time=JmMagicConstants.TIME_ALL,
        category=JmMagicConstants.CATEGORY_ALL,
        order_by=JmMagicConstants.ORDER_BY_LATEST,
    )
    if select == "月排行":
        page: JmCategoryPage = cl.month_ranking(1)
    elif select == "周排行":
        page: JmCategoryPage = cl.week_ranking(1)
    else:
        page: JmCategoryPage = cl.week_ranking(1)
    cache_dir = os.path.join(load_address(),"rank")
    os.makedirs(cache_dir,exist_ok = True)
    # 使用唯一文件名，避免工作区/预览链按同名文件命中旧缓存
    file_token = hashlib.md5(f"{select}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{select}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    build_jm_grid_html(f"{html.escape(select)} · JM 排行", filepath)

    tot = 0
    for aid, atitle in page:
        tot += 1
        append_jm_card(filepath, aid, atitle, tot, client=cl)
        comic_cache.append(aid)
        if tot >= 50:
            break

    close_jm_grid_html(filepath)

    if not os.path.exists(filepath):
        await send_text(msg, "获取排行失败喵~，文件不存在", is_group=is_group)
        return
    await send_file(msg, filepath, is_group=is_group, filename=filename)

@register_command("/jm_search",help_text = "/jm_search <内容> -> 搜索漫画",category = "1")
async def handle_search(msg, is_group=True):
    await send_text(msg, "正在搜索喵~", is_group=is_group)

    cache_dir = os.path.join(load_address(),"search")
    os.makedirs(cache_dir,exist_ok = True)
    client = JmOption.default().new_jm_client()
    content = msg.raw_message[len("/jm_search"):].strip()

    if not content or content == " ":
        await send_text(msg, "搜索内容不能为空喵~", is_group=is_group)
        return

    file_token = hashlib.md5(f"{content}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{content}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    if re.match(r'^\d+$', content):  # 检查是否为纯数字，搜索单个本子
        id = content
        # 直接搜索禁漫车号，生成单本卡片HTML
        album: JmAlbumDetail = client.get_album_detail(id)
        cover_url = fetch_cover_url(id, client=client)
        album_url = f"https://jmcm.la/album/{id}"
        html_head = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(album.title)} - JM 本子</title>
  <style>
    body {{ font-family: 'Segoe UI', 'PingFang SC', sans-serif; background:#111827; color:#f3f4f6; margin:0; padding:24px; }}
    .card {{ background:#1f2937; border:1px solid rgba(255,255,255,0.08); border-radius:16px; overflow:hidden; box-shadow:0 10px 24px rgba(0,0,0,0.22); max-width:400px; margin:0 auto; transition: transform 0.2s, box-shadow 0.2s; cursor:pointer; }}
    .card:hover {{ transform: translateY(-4px); box-shadow:0 14px 28px rgba(0,0,0,0.3); }}
    .cover {{ width:100%; aspect-ratio: 13 / 18; object-fit:cover; display:block; background:#0b1220; }}
    .meta {{ padding:16px 20px 20px; }}
    .title {{ font-size:18px; font-weight:700; line-height:1.4; word-break:break-word; margin-bottom:10px; }}
    .info {{ color:#9ca3af; font-size:13px; line-height:1.8; }}
    .tag {{ display:inline-block; background:#374151; border-radius:6px; padding:2px 8px; margin:2px; font-size:12px; }}
  </style>
</head>
<body>
  <a href="{html.escape(album_url, quote=True)}" target="_blank" style="text-decoration:none; color:inherit;">
  <div class="card">
    <img class="cover" src="{html.escape(cover_url, quote=True)}" alt="{html.escape(album.title, quote=True)}">
    <div class="meta">
      <div class="title">{html.escape(album.title)}</div>
      <div class="info">
        <div>ID: {html.escape(str(id))}</div>
        <div>页数: {album.page_count}</div>
        <div>浏览: {album.views}</div>
        <div>评论: {album.comment_count}</div>
        <div style="margin-top:8px;">{''.join(f'<span class="tag">{html.escape(str(tag))}</span>' for tag in album.tags)}</div>
      </div>
    </div>
  </div>
  </a>
</body>
</html>"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_head)
        await send_file(msg, filepath, is_group=is_group, filename=filename)
        return

    # 多本搜索，生成卡片网格HTML
    build_jm_grid_html(f"{html.escape(content)} · JM 搜索", filepath)

    tot = 0
    for i in range(5):  # 搜索5页
        page: JmSearchPage = client.search_site(search_query=content, page=i+1)
        if len(page) == 0:
            break
        for album_id, title in page:
            tot += 1
            append_jm_card(filepath, album_id, title, tot, client=client)
            comic_cache.append(album_id)
        if tot >= 50:
            break

    close_jm_grid_html(filepath)

    if not os.path.exists(filepath):
        await send_text(msg, "搜索失败喵~，文件不存在", is_group=is_group)
        return

    await send_file(msg, filepath, is_group=is_group, filename=filename)

@register_command("/jm_tag",help_text = "/jm_tag <标签> -> 搜索漫画标签",category = "1")
async def handle_tag(msg, is_group=True):
    await send_text(msg, "正在搜索喵~", is_group=is_group)

    cache_dir = os.path.join(load_address(),"search")
    os.makedirs(cache_dir,exist_ok = True)
    content = msg.raw_message[len("/tag"):].strip()
    client = JmOption.default().new_jm_client()

    file_token = hashlib.md5(f"tag_{content}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{content}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    build_jm_grid_html(f"{html.escape(content)} · JM 标签搜索", filepath)

    tot = 0
    for i in range(5):  # 搜索5页
        page: JmSearchPage = client.search_tag(search_query=content, page=i+1)
        if len(page) == 0:
            break
        for album_id, title in page:
            tot += 1
            append_jm_card(filepath, album_id, title, tot, client=client)
            comic_cache.append(album_id)
        if tot >= 50:
            break

    close_jm_grid_html(filepath)

    await send_file(msg, filepath, is_group=is_group, filename=filename)

@register_command("/get_fav",help_text = "/get_fav <用户名> <密码> -> 获取收藏夹(群聊请私聊)",category = "1")
async def handle_get_fav(msg, is_group=True):
    match = re.match(r'^/get_fav\s+(\S+)\s+(\S+)$', msg.raw_message)
    if not match:
        error_msg = "格式错误喵~ 请输入 /get_fav 用户名 密码"
        await send_text(msg, error_msg, is_group=is_group)
        return

    username = match.group(1)
    password = match.group(2)

    await send_text(msg, "正在获取收藏夹喵~", is_group=is_group)

    cache_dir = os.path.join(load_address(),"fav")
    os.makedirs(cache_dir, exist_ok=True)

    file_token = hashlib.md5(f"fav_{username}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{username}.html"
    filepath = os.path.join(cache_dir, filename)
    comic_cache.clear()

    option = JmOption.default()
    cl = option.new_jm_client()
    try:
        cl.login(username, password)  # 也可以使用login插件/配置cookies
    except Exception as e:
        await send_text(msg, f"登录失败喵~：{e}", is_group=is_group)
        return

    build_jm_grid_html(f"{html.escape(username)} · JM 收藏夹", filepath)

    tot = 0
    # 遍历全部收藏的所有页
    for page in cl.favorite_folder_gen():  # 如果你只想获取特定收藏夹，需要添加folder_id参数
        for aid, atitle in page.iter_id_title():
            tot += 1
            append_jm_card(filepath, aid, atitle, tot, client=cl)
            comic_cache.append(aid)
        if tot >= 50:
            break

    close_jm_grid_html(filepath)

    await send_file(msg, filepath, is_group=is_group, filename=filename)

@register_command("/jm",help_text = "/jm <漫画ID> -> 下载漫画",category = "1")
async def handle_jmcomic(msg, is_group=True):
    match = re.match(r'^/jm\s+(\d+)$', msg.raw_message)
    if match:
        comic_id = match.group(1)
        # 检查是否在全局、群组或用户黑名单中
        if comic_id in black_list_comic["global"]:
            error_msg = "该漫画已被加入黑名单喵~"
            await send_text(msg, error_msg, is_group=is_group)
            return
        if is_group:
            group_id = str(msg.group_id)
            if group_id in black_list_comic["groups"] and comic_id in black_list_comic["groups"][group_id]:
                error_msg = "该漫画已被加入本群黑名单喵~"
                await msg.reply(text=error_msg)
                return
        else:
            user_id = str(msg.user_id)
            if user_id in black_list_comic["users"] and comic_id in black_list_comic["users"][user_id]:
                error_msg = "该漫画已被加入你的黑名单喵~"
                await bot.api.post_private_msg(msg.user_id, text=error_msg)
                return

        pdf_path = normalize_file_path(os.path.join(load_address(),f"pdf/{comic_id}.pdf"))
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            if is_group:
                if switch.get_switch_state('jm_send', group_id=str(msg.group_id)):
                    if switch.get_switch_state('jm_send_user', group_id=str(msg.group_id)):
                        await bot.api.post_private_msg(msg.user_id,text=f"该漫画已存在喵~,文件大小：{file_size:.2f} MB，正在发送喵~")
                        await bot.api.upload_private_file(msg.user_id, pdf_path, f"{comic_id}.pdf")
                    else:
                        await msg.reply(text=f"该漫画已存在喵~,文件大小：{file_size:.2f} MB，正在发送到群组喵~")
                        await bot.api.post_group_file(msg.group_id, file=pdf_path)
                else:
                    await msg.reply(text="群组发送漫画已关闭喵~")
            else:
                if switch.get_switch_state('jm_send', user_id=str(msg.user_id)):
                    await bot.api.post_private_msg(msg.user_id,text=f"该漫画已存在喵~,文件大小：{file_size:.2f} MB，正在发送喵~")
                    await bot.api.upload_private_file(msg.user_id, pdf_path, f"{comic_id}.pdf")
                else:
                    await msg.reply(text="该漫画已下载，但用户私信发送漫画已关闭喵~")
            return

        if int(comic_id) <= len(comic_cache) and len(comic_cache) > 0 :
            try:
                comic_id = comic_cache[int(comic_id)-1]
            except IndexError:
                error_msg = "超出范围了喵~"
                await send_text(msg, error_msg, is_group=is_group)
                return
        
        try:
            client = JmOption.default().new_jm_client()
        except JmcomicException:
            error_msg = "当前禁漫站点接口不可用喵~ 可能是 /setting 接口返回异常，请稍后重试或检查jmcomic配置喵~"
            await send_text(msg, error_msg, is_group=is_group)
            return
        try:
            album: JmAlbumDetail = client.get_album_detail(comic_id)
        except MissingAlbumPhotoException:
            error_msg = "该漫画ID不存在喵~"
            await send_text(msg, error_msg, is_group=is_group)
            return
        
        # 立即回复用户，不等待下载完成
        reply_text = f"已开始下载漫画ID：{comic_id}，下载完成后会自动通知喵~"
        await send_text(msg, reply_text, is_group=is_group)

        # 创建后台任务
        try:
            await asyncio.gather(download_and_send_comic(comic_id, msg, is_group))
        except Exception as e:
            error_msg = f"下载漫画失败喵~: {str(e)}"
            await send_text(msg, error_msg, is_group=is_group)

    else:
        error_msg = "格式错误了喵~，请输入 /jm 后跟漫画ID"
        if not is_group:
            await bot.api.post_private_msg(msg.user_id, text=error_msg)

#后台任务函数
async def download_and_send_comic(comic_id, msg, is_group):
    try:
        # 在线程池中执行阻塞操作
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda:
            jmcomic.download_album(
                comic_id,
                jmcomic.create_option_by_file('./resources/config/option.yml')
            )
        )

        file_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))

        # 检查文件是否真正生成
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF文件未生成：{file_path}")
        encrypt_needed = switch.get_switch_state('pdf_password', group_id=str(msg.group_id) if is_group else None,user_id=str(msg.user_id) if not is_group else None)
        if switch.get_switch_state('jm_send_email', user_id=str(msg.user_id)):
            encrypt_needed = True
        if encrypt_needed:
            try:
                import pikepdf
                with pikepdf.open(file_path,allow_overwriting_input=True) as pdf:
                    pdf.save(file_path, encryption=pikepdf.Encryption(
                        owner=comic_id,
                        user=comic_id,
                        R=4
                    ))
            except ImportError:
                error_msg = "缺少pikepdf库，无法加密PDF文件喵~"
                await msg.reply(text=error_msg)
        email_sent = False
        email_error = None
        try:
            if switch.get_switch_state('jm_send_email', user_id=str(msg.user_id)):
                email_sent = await send_comic_email(str(msg.user_id), comic_id, file_path)
        except Exception as e:
            _log.error(f"发送漫画邮件失败: {e}")
            email_error = e
        if not switch.get_switch_state('jm_send', group_id=str(msg.group_id) if is_group else None,user_id=str(msg.user_id) if not is_group else None):
            text = "漫画已下载，但发送已关闭喵~"
            if email_sent:
                text = "漫画已下载，并已发送到你的邮箱喵~"
            elif email_error is not None:
                err_msg = str(email_error)
                if "552" in err_msg or "mailsize limit" in err_msg.lower():
                    text = "漫画已下载，但发送到邮箱失败喵~，原因是邮件大小超过邮箱限制喵~"
                else:
                    text = "漫画已下载，但发送到邮箱失败喵~，请检查邮箱配置或稍后重试喵~"
            await send_text(msg, text, is_group=is_group)
            return

        file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
        file_text = f"文件大小：{file_size:.2f} MB，正在上传喵~"
        success_text = f"漫画 {comic_id} 下载完成喵~"

        if is_group:
            if switch.get_switch_state('jm_send_user', group_id=str(msg.group_id)):
                await bot.api.post_private_msg(msg.user_id, text=file_text)
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
                await bot.api.post_private_msg(msg.user_id, text=success_text)
            else:
                await msg.reply(text=file_text)
                await bot.api.post_group_file(msg.group_id, file=file_path)
                await msg.reply(text=success_text)
        else:
            await bot.api.post_private_msg(msg.user_id, text=file_text)
            await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
            await bot.api.post_private_msg(msg.user_id, text=success_text)

    except Exception as e:
        file_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))
        error_msg = f"下载失败喵~: {str(e)}"
        await send_text(msg, error_msg, is_group=is_group)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
            file_text = f"文件大小：{file_size:.2f} MB，正在上传喵~"
            if is_group:
                await msg.reply(text="部分下载失败了喵~，正在发送剩余的文件喵~\n"+file_text)
                await bot.api.post_group_file(msg.group_id, file=file_path)
            else:
                await bot.api.post_private_msg(msg.user_id, text="部分下载失败了喵~，正在发送剩余的文件喵~\n"+file_text)
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")

@register_command("/jm_clear",help_text = "/jm_clear -> 清除缓存",category = "1")
async def handle_jm_clear(msg, is_group=True):
    comic_cache.clear()
    await send_text(msg, "缓存已清除喵~", is_group=is_group)

@register_command("/jm_send_user", help_text="/jm_send_user <on|off> -> 开启/关闭群聊用户私信发送漫画(admin)",category = "1",admin_show=True)
async def handle_jm_send_user(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await msg.reply(text="只有管理员才能使用该命令喵~")
        return

    state = msg.raw_message[len("/jm_send_user"):].strip().lower()
    if state not in ['on', 'off']:
        reply = "请输入 on 或 off 喵~"
    else:
        switch.set_switch_state('jm_send_user', state == 'on', group_id=str(msg.group_id) if is_group else None,user_id=str(msg.user_id) if not is_group else None)

        reply = f"用户私信发送漫画已 {'开启' if state == 'on' else '关闭'} 喵~"
    await send_text(msg, reply, is_group=is_group)
    switch.save_switches()

@register_command("/jm_send", help_text="/jm_send <on|off> -> 开启/关闭发送漫画(admin)",category = "1",admin_show=True)
async def handle_jm_send(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await msg.reply(text="只有管理员才能使用该命令喵~")
        return
    state = msg.raw_message[len("/jm_send"):].strip().lower()
    if state not in ['on', 'off']:
        reply = "请输入 on 或 off 喵~"
    else:
        switch.set_switch_state('jm_send', state == 'on', group_id=str(msg.group_id) if is_group else None,user_id=str(msg.user_id) if not is_group else None)

        reply = f"{'群组' if is_group else '用户'}发送漫画已 {'开启' if state == 'on' else '关闭'} 喵~"
    await send_text(msg, reply, is_group=is_group)
    switch.save_switches()

@register_command("/jm_pwd", help_text="/jm_pwd <on|off> -> 开启/关闭密码加密(admin)，密码为漫画id",category = "1",admin_show=True)

async def handle_jm_pwd(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await msg.reply(text="只有管理员才能使用该命令喵~")
        return
    state = msg.raw_message[len("/jm_pwd"):].strip().lower()
    if state not in ['on', 'off']:
        reply = "请输入 on 或 off 喵~"
    else:
        switch.set_switch_state('pdf_password', state == 'on', group_id=str(msg.group_id) if is_group else None,user_id=str(msg.user_id) if not is_group else None)
        reply = f"{'群组' if is_group else '用户'}密码加密已 {'开启' if state == 'on' else '关闭'} 喵~，密码为漫画id"
    await send_text(msg, reply, is_group=is_group)

@register_command("/jm_email", help_text="/jm_email <邮箱> <on|off> -> 配置邮箱并开启或关闭发送漫画到邮箱",category = "1")
async def handle_jm_email(msg, is_group=True):
    user_id = str(msg.user_id)
    raw = msg.raw_message[len("/jm_email"):].strip()
    parts = raw.split() if raw else []
    email = None
    state = None
    if not parts:
        current_email = user_email.get(user_id)
        enabled = switch.get_switch_state('jm_send_email', user_id=user_id)
        text = f"当前邮箱：{current_email or '未设置'}，状态：{'开启' if enabled else '关闭'}"
        await send_text(msg, text, is_group=is_group)
        return
    if len(parts) == 1:
        if parts[0].lower() in ("on", "off"):
            state = parts[0].lower() == "on"
        else:
            email = parts[0]
            state = True
    else:
        email = parts[0]
        if parts[1].lower() in ("on", "off"):
            state = parts[1].lower() == "on"
        else:
            text = "第二个参数请输入 on 或 off 喵~"
            await send_text(msg, text, is_group=is_group)
            return
    if email:
        if "@" not in email:
            text = "请输入正确的邮箱地址喵~"
            await send_text(msg, text, is_group=is_group)
            return
        user_email[user_id] = email
        save_email_config()
    if state is not None:
        switch.set_switch_state('jm_send_email', state, user_id=user_id)
        switch.save_switches()
    text = "邮箱配置已更新喵~"
    if state is not None:
        text = f"邮箱配置已更新喵~，发送到邮箱已{'开启' if state else '关闭'}"
    await send_text(msg, text, is_group=is_group)

# ====下面的收藏夹不是官方的收藏夹，是本地储存的====
@register_command("/add_fav", help_text="/add_fav <漫画ID> -> 添加收藏",category = "1")
async def handle_add_favorite(msg, is_group=True):
    comic_id = msg.raw_message[len("/add_fav"):].strip()
    if not comic_id.isdigit():
        reply = "请输入有效的漫画ID喵~"
    else:
        user_id = str(msg.user_id)
        if is_group:
            group_id = str(msg.group_id)
            if group_id not in group_favorites:
                group_favorites[group_id] = {}
            if user_id not in group_favorites[group_id]:
                group_favorites[group_id][user_id] = []
            if comic_id not in group_favorites[group_id][user_id]:
                group_favorites[group_id][user_id].append(comic_id)
                reply = f"已在群组收藏中添加漫画 {comic_id} 喵~"
            else:
                reply = f"漫画 {comic_id} 已在群组收藏中喵~"
        else:
            if user_id not in user_favorites:
                user_favorites[user_id] = []
            if comic_id not in user_favorites[user_id]:
                user_favorites[user_id].append(comic_id)
                reply = f"已在个人收藏中添加漫画 {comic_id} 喵~"
            else:
                reply = f"漫画 {comic_id} 已在个人收藏中喵~"
        save_favorites()
    
    await send_text(msg, reply, is_group=is_group)

@register_command("/list_fav", help_text="/list_fav -> 查看收藏列表",category = "1")
async def handle_list_favorites(msg, is_group=True):
    user_id = str(msg.user_id)
    if is_group:
        group_id = str(msg.group_id)
        if group_id in group_favorites and user_id in group_favorites[group_id]:
            comics = group_favorites[group_id][user_id]
        else:
            comics = []
    else:
        comics = user_favorites.get(user_id, [])
    
    if comics:
        reply = "收藏的漫画ID:\n" + "\n".join(comics)
    else:
        reply = "收藏夹是空的喵~"
    
    await send_text(msg, reply, is_group=is_group)

@register_command("/del_fav", help_text="/del_fav <漫画ID> -> 删除收藏",category = "1")
async def handle_del_favorite(msg, is_group=True):
    comic_id = msg.raw_message[len("/del_fav"):].strip()
    user_id = str(msg.user_id)
    if is_group:
        group_id = str(msg.group_id)
        if group_id in group_favorites and user_id in group_favorites[group_id]:
            if comic_id in group_favorites[group_id][user_id]:
                group_favorites[group_id][user_id].remove(comic_id)
                reply = f"已从群组收藏中删除漫画 {comic_id} 喵~"
            else:
                reply = f"漫画 {comic_id} 不在群组收藏中喵~"
        else:
            reply = "群组收藏夹是空的喵~"
    else:
        if user_id in user_favorites:
            if comic_id in user_favorites[user_id]:
                user_favorites[user_id].remove(comic_id)
                reply = f"已从个人收藏中删除漫画 {comic_id} 喵~"
            else:
                reply = f"漫画 {comic_id} 不在个人收藏中喵~"
        else:
            reply = "个人收藏夹是空的喵~"
    
    save_favorites()
    await send_text(msg, reply, is_group=is_group)

@register_command("/add_black_list","/abl",help_text = "/add_black_list 或 /abl  <漫画ID> -> 添加黑名单",category = "1")
async def handle_add_black_list(msg, is_group=True):
    comic_id = ""
    if msg.raw_message.startswith("/add_black_list"):
        comic_id = msg.raw_message[len("/add_black_list"):].strip()
    elif msg.raw_message.startswith("/abl"):
        comic_id = msg.raw_message[len("/abl"):].strip()

    if not comic_id.isdigit():
        reply = "请输入有效的漫画ID喵~"
    else:
        if is_group:
            group_id = str(msg.group_id)
            if group_id not in black_list_comic["groups"]:
                black_list_comic["groups"][group_id] = []
            if comic_id in black_list_comic["groups"][group_id]:
                reply = f"漫画 {comic_id} 已在本群黑名单中喵~"
            else:
                black_list_comic["groups"][group_id].append(comic_id)
                write_blak_list()
                reply = f"已在本群黑名单中添加漫画 {comic_id} 喵~"
        else:
            user_id = str(msg.user_id)
            if user_id not in black_list_comic["users"]:
                black_list_comic["users"][user_id] = []
            if comic_id in black_list_comic["users"][user_id]:
                reply = f"漫画 {comic_id} 已在你的黑名单中喵~"
            else:
                black_list_comic["users"][user_id].append(comic_id)
                write_blak_list()
                reply = f"已在你的黑名单中添加漫画 {comic_id} 喵~"
    await send_text(msg, reply, is_group=is_group)

@register_command("/add_global_black_list","/agbl",help_text = "/add_global_black_list 或 /agbl <漫画ID> -> 添加全局黑名单(admin)",category = "1",admin_show=True)
async def handle_add_global_black_list(msg, is_group=True):

    if str(msg.user_id) not in admin:
        reply = "你没有权限喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    comic_id = ""
    if msg.raw_message.startswith("/add_global_black_list"):
        comic_id = msg.raw_message[len("/add_global_black_list"):].strip()
    elif msg.raw_message.startswith("/agbl"):
        comic_id = msg.raw_message[len("/agbl"):].strip()

    if not comic_id.isdigit():
        reply = "请输入有效的漫画ID喵~"
    else:
        if comic_id in black_list_comic["global"]:
            reply = f"漫画 {comic_id} 已在全局黑名单中喵~"
        else:
            black_list_comic["global"].append(comic_id)
            write_blak_list()
            reply = f"已在全局黑名单中添加漫画 {comic_id} 喵~"
    await send_text(msg, reply, is_group=is_group)

@register_command("/del_global_black_list","/dgbl",help_text = "/del_global_black_list 或 /dgbl <漫画ID> -> 删除全局黑名单(admin)",category = "1",admin_show=True)
async def handle_del_global_black_list(msg, is_group=True):

    if str(msg.user_id) not in admin:
        reply = "你没有权限喵~"
        await send_text(msg, reply, is_group=is_group)
        return
    
    comic_id = ""
    if msg.raw_message.startswith("/del_global_black_list"):
        comic_id = msg.raw_message[len("/del_global_black_list"):].strip()
    elif msg.raw_message.startswith("/dgbl"):
        comic_id = msg.raw_message[len("/dgbl"):].strip()

    if not comic_id.isdigit():
        reply = "请输入有效的漫画ID喵~"
    else:
        if comic_id in black_list_comic["global"]:
            black_list_comic["global"].remove(comic_id)
            write_blak_list()
            reply = f"已从全局黑名单中删除漫画 {comic_id} 喵~"
        else:
            reply = f"漫画 {comic_id} 不在全局黑名单中喵~"
    await send_text(msg, reply, is_group=is_group)

@register_command("/del_black_list","/dbl",help_text = "/del_black_list 或 /dbl <漫画ID> -> 删除黑名单",category = "1")
async def handle_del_black_list(msg, is_group=True):
    comic_id = ""
    if msg.raw_message.startswith("/del_black_list"):
        comic_id = msg.raw_message[len("/del_black_list"):].strip()
    elif msg.raw_message.startswith("/dbl"):
        comic_id = msg.raw_message[len("/dbl"):].strip()

    if not comic_id.isdigit():
        reply = "请输入有效的漫画ID喵~"
    else:
        if is_group:
            group_id = str(msg.group_id)
            if group_id in black_list_comic["groups"] and comic_id in black_list_comic["groups"][group_id]:
                black_list_comic["groups"][group_id].remove(comic_id)
                write_blak_list()
                reply = f"已从本群黑名单中删除漫画 {comic_id} 喵~"
            else:
                reply = f"漫画 {comic_id} 不在本群黑名单中喵~"
        else:
            user_id = str(msg.user_id)
            if user_id in black_list_comic["users"] and comic_id in black_list_comic["users"][user_id]:
                black_list_comic["users"][user_id].remove(comic_id)
                await write_blak_list()
                reply = f"已从你的黑名单中删除漫画 {comic_id} 喵~"
            else:
                reply = f"漫画 {comic_id} 不在你的黑名单中喵~"
    await send_text(msg, reply, is_group=is_group)

@register_command("/list_black_list","/lbl",help_text = "/list_black_list 或 /lbl -> 查看黑名单",category = "1")
async def handle_list_black_list(msg, is_group=True):
    if is_group:
        group_id = str(msg.group_id)
        if black_list_comic["global"] or black_list_comic["groups"].get(group_id, []):
            reply = "本群的黑名单中的漫画ID:\n全局：" + "\n".join( black_list_comic["global"]) + "\n本群：" + "\n".join( black_list_comic["groups"].get(group_id, []))
        else:
            reply = "本群黑名单是空的喵~"
    else:
        user_id = str(msg.user_id)
        if black_list_comic["global"] or black_list_comic["users"].get(user_id, []):
            reply = "你的黑名单中的漫画ID:\n全局：" + "\n".join(black_list_comic["global"]) + "\n个人：" + "\n".join(black_list_comic["users"].get(user_id, []))
        else:
            reply = "你的黑名单是空的喵~"
    await send_text(msg, reply, is_group=is_group)
        
#------------------------

@register_command("/agree",help_text="/agree -> 同意好友请求(admin)",category = "4",admin_show=True) # 同意好友请求
async def handle_agree(msg, is_group=True):
    if str(msg.user_id) not in admin:
        reply = "你没有权限喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    if not is_group:
        await bot.api.set_friend_add_request(flag=msg.user_id, approve=True,remark=msg.user_id)
        await bot.api.post_private_msg(msg.user_id, text="已同意好友请求喵~")
    else:
        await bot.api.set_friend_add_request(flag=msg.user_id, approve=True,remark=msg.user_id)
        await msg.reply(text="已同意好友请求喵~")

@register_command("/restart",help_text="/restart -> 重启机器人(admin)",category = "4",admin_show=True)
async def handle_restart(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "只有管理员才能重启机器人喵~", is_group=is_group)
        return
    reply_text = "正在重启喵~"
    await send_text(msg, reply_text, is_group=is_group)
    # 重启逻辑
    os.execv(sys.executable, [sys.executable] + sys.argv)

@register_command("/shutdown",help_text="/shutdown -> 关闭机器人(admin)",category = "4",admin_show=True)
async def handle_shutdown(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "只有管理员才能关闭机器人喵~", is_group=is_group)
        return
    reply_text = "主人，下次再见喵~"
    await send_text(msg, reply_text, is_group=is_group)
    import sys
    sys.exit()

#------以下为调用api发送文件的命令，采用异步方式发送文件------
# 新增后台任务函数



# 修改通用处理函数

# 统一调用
@register_command("/random_image","/ri",help_text = "/random_image 或者 /ri -> 随机图片",category = "3")
async def handle_random_image(msg, is_group=True):
    await handle_generic_file(msg, is_group, 'ri', 'image')

@register_command("/random_emoticons",help_text = "/random_emoticons 或者 /re -> 随机表情包",category = "3")
async def handle_random_emoticons(msg, is_group=True):
    await handle_generic_file(msg, is_group, 're', 'image')

@register_command("/st",help_text = "/st <标签名> -> 发送随机涩图,标签支持与或(& |)",category = "3")
async def handle_st(msg, is_group=True):
    tags = msg.raw_message[len("/st"):].strip()
    res = get_sync(f"https://api.lolicon.app/setu/v2?tag={tags}").json().get("data")[0].get("urls").get("original")
    await handle_generic_file(msg, is_group,"","image",custom_url=res)  # 特殊处理API调用


def _parse_loli_params(raw: str):
    """解析 /loli 和 /r18 命令参数

    纯数字 → num，其他字符 → tag（可用 & 组合）
    示例: "初音未来 3" → tag="初音未来", num=3
          "初音未来&和服" → tag="初音未来&和服", num=1
          "5" → tag="", num=5
    """
    tag = ""
    num = 1
    for p in raw.strip().split():
        if p.isdigit():
            num = max(1, min(int(p), 10))
        else:
            if tag:
                tag += " " + p
            else:
                tag = p
    return tag, num


@register_command("/loli", help_text="/loli [标签] [数量] -> 获取安全涩图(r18=0), 标签可用&组合, 如: /loli 初音未来&和服 3", category="3")
async def handle_loli(msg, is_group=True):
    tag, num = _parse_loli_params(msg.raw_message[len("/loli"):])
    try:
        params = {"r18": 0, "num": num, "size": "original"}
        if tag:
            params["tag"] = tag
        data = get_sync("https://api.lolicon.app/setu/v2", params=params, timeout=30).json()
        if data.get("error"):
            await msg.reply(text=f"获取失败: {data['error']}")
            return
        items = data.get("data") or []
        if not items:
            await msg.reply(text="没有找到匹配的图片喵~")
            return
        for item in items:
            img_url = item.get("urls", {}).get("original")
            if img_url:
                await handle_generic_file(msg, is_group, "", "image", custom_url=img_url)
    except Exception as e:
        _log.error(f"/loli 失败: {e}")
        await msg.reply(text=f"获取失败喵~ {e}")


@register_command("/r18", help_text="/r18 [标签] [数量] -> 获取R18涩图(r18=1), 标签可用&组合, 如: /r18 萝莉 5", category="3")
async def handle_r18(msg, is_group=True):
    tag, num = _parse_loli_params(msg.raw_message[len("/r18"):])
    try:
        params = {"r18": 1, "num": num, "size": "original"}
        if tag:
            params["tag"] = tag
        data = get_sync("https://api.lolicon.app/setu/v2", params=params, timeout=30).json()
        if data.get("error"):
            await msg.reply(text=f"获取失败: {data['error']}")
            return
        items = data.get("data") or []
        if not items:
            await msg.reply(text="没有找到匹配的图片喵~")
            return
        for item in items:
            img_url = item.get("urls", {}).get("original")
            if img_url:
                await handle_generic_file(msg, is_group, "", "image", custom_url=img_url)
    except Exception as e:
        _log.error(f"/r18 失败: {e}")
        await msg.reply(text=f"获取失败喵~ {e}")

@register_command("/random_video","/rv",help_text = "/random_video 或者 /rv -> 随机二次元视频",category = "3")
async def handle_random_video(msg, is_group=True):
    await handle_generic_file(msg, is_group, 'rv', 'video')

@register_command("/dv",help_text="/dv <link> -> 下载视频",category = "3")
async def handle_d(msg, is_group=True):
    link = msg.raw_message[len("/dv"):].strip()
    if not link:
        await send_text(msg, "请输入链接喵~", is_group=is_group)
        return

    if re.match(r'^https?://', link):  # 检查是否为合法链接
        await handle_generic_file(msg, is_group, '', 'video', custom_url=link)  
    else:
        await send_text(msg, "请输入合法的链接喵~", is_group=is_group)

@register_command("/di",help_text="/di <link> -> 下载图片",category = "3")
async def handle_di(msg, is_group=True):
    link = msg.raw_message[len("/di"):].strip()
    if not link:
        await send_text(msg, "请输入链接喵~", is_group=is_group)
        return

    if re.match(r'^https?://', link):  # 检查是否为合法链接
        #await handle_generic_file(msg, is_group, '', 'image', custom_url=link,file_name="download.jpg")
        if is_group:
            await bot.api.post_group_file(group_id=msg.group_id,file=link)
        else:
            await bot.api.upload_private_file(user_id=msg.user_id,file=link,name="download.jpg")
    else:
        await send_text(msg, "请输入合法的链接喵~", is_group=is_group)

@register_command("/df",help_text="/df <link> -> 下载文件",category = "3")
async def handle_df(msg, is_group=True):
    link = msg.raw_message[len("/df"):].strip()
    if not link:
        await send_text(msg, "请输入链接喵~", is_group=is_group)
        return

    if re.match(r'^https?://', link):  # 检查是否为合法链接
        await handle_generic_file(msg, is_group, '', 'file', custom_url=link)
    else:
        await send_text(msg, "请输入合法的链接喵~", is_group=is_group)

#---------------------------------------------

@register_command("/music",help_text = "/music <音乐名/id> -> 发送音乐",category = "3")
async def handle_music(msg, is_group=True):
    music_name = msg.raw_message[len("/music"):].strip()
    if not music_name:
        await msg.reply(text="请输入音乐名喵~")
        return

    if re.match(r'^\d+$', music_name):  # 检查是否为纯数字
        messagechain = MessageChain(
            Music(type="163",id=music_name)
        )
        if is_group:
            await msg.reply(rtf=messagechain)
        else:
            await bot.api.post_private_msg(msg.user_id, rtf=messagechain)
        return
    music_id = None
    url = 'https://music.163.com/api/search/get'
    params = {
        's': music_name,
        'type': 1,  # 1表示歌曲
        'limit': 1  # 获取第一条结果
    }
    response = get_sync(url, params=params)
    data = response.json()
    if data['code'] == 200 and data['result']['songs']:
        music_id = data['result']['songs'][0]['id']
    messagechain = MessageChain(
        Music(type="163",id=music_id)
    )
    if is_group:
        await bot.api.post_group_msg(msg.group_id, rtf=messagechain)
    else:
        await bot.api.post_private_msg(msg.user_id, rtf=messagechain)

@register_command("/random_music","/rm",help_text = "/random_music 或者 /rm -> 发送随机音乐",category = "3")
async def handle_random_music(msg, is_group=True):
    id = get_sync("https://api.mtbbs.top/Music/song/?id=2645495145").json()["data"]["id"]
    messagechain = MessageChain(
        Music(type="163",id=id)
    )
    if is_group:
        await bot.api.post_group_msg(msg.group_id, rtf=messagechain)
    else:
        await bot.api.post_private_msg(msg.user_id, rtf=messagechain)

@register_command("/random_dice","/rd",help_text = "/random_dice 或者 /rd -> 发送随机骰子",category = "3")
async def handle_random_dice(msg, is_group=True):
    if is_group:
        await bot.api.post_group_msg(msg.group_id,dice=True)
    else:
        await bot.api.post_private_msg(msg.user_id,dice=True)

@register_command("/random_rps","/rps",help_text = "/random_rps 或者 /rps -> 发送随机石头剪刀布",category = "3")
async def handle_random_rps(msg, is_group=True):
    if is_group:
        await bot.api.post_group_msg(msg.group_id,rps=True)
    else:
        await bot.api.post_private_msg(msg.user_id,rps=True)

@register_command("/del_message","/dm",help_text = "/del_message 或者 /dm -> 删除对话记录(仅群admin)",category = "3")
async def handle_del_message(msg, is_group=True):
    if (str(msg.user_id) not in admin) and is_group:
        await msg.reply(text="你没有权限喵~")
        return

    if is_group:
        try:
            del group_messages[str(msg.group_id)]
        except KeyError:
            await msg.reply(text="你没有对话记录喵~")
            return
        with open("saved_message/group_messages.json", "w", encoding="utf-8") as f:
            json.dump(group_messages, f, ensure_ascii=False, indent=4)
        # 删除对应的工作区
        delete_session_workspace(group_id=str(msg.group_id), group_user_id=str(msg.user_id))
        await msg.reply(text="主人要离我而去了吗？呜呜呜……好吧，那我们以后再见喵~")
    else:
        try:
            del user_messages[str(msg.user_id)]
        except KeyError:
            await bot.api.post_private_msg(msg.user_id, text="你没有对话记录喵~")
            return
        with open("saved_message/user_messages.json", "w", encoding="utf-8") as f:
            json.dump(user_messages, f, ensure_ascii=False, indent=4)
        # 删除对应的工作区
        delete_session_workspace(user_id=str(msg.user_id))
        await bot.api.post_private_msg(msg.user_id, text="主人要离我而去了吗？呜呜呜……好吧，那我们以后再见喵~")

@register_command("/remind",help_text="/remind <多少小时后> <内容> -> 定时提醒",category = "7")
async def handle_remind(msg, is_group=True):
    match = re.match(r'^/remind\s+(\d+\.?\d*)\s+(.+)$', msg.raw_message) #正则支持小数
    if match:
        hours = float(match.group(1))
        content = match.group(2)
    else:
        if is_group:
            await msg.reply(text="格式错误喵~ 请输入 /remind 时间(小时) 内容")
            return
        else:
            await bot.api.post_private_msg(msg.user_id, text="格式错误喵~ 请输入 /remind 时间(小时) 内容")
            return
    if is_group:
        await msg.reply(text=f"已设置提醒喵~{hours}小时后会提醒你：{content}")
        asyncio.create_task(schedule_task(hours, msg.reply,content))
    else:
        await bot.api.post_private_msg(msg.user_id, text=f"已设置提醒喵~{hours}小时后会提醒你：{content}")
        asyncio.create_task(schedule_task(hours, bot.api.post_private_msg,msg.user_id,content))

@register_command("/premind", help_text="/premind <MM-DD> <HH:MM> <内容> -> 精确时间提醒",category = "7")
async def handle_precise_remind(msg, is_group=True):
    try:
        # 解析日期时间
        parts = msg.raw_message.split(maxsplit=3)

        if len(parts) < 3:
            raise ValueError
        
        now = datetime.now()
        year = str(now.year)

        date_str = f"{year}-" + parts[1]
        time_str = parts[2]
        content = parts[3] if len(parts) > 3 else "提醒时间到了喵~"
        
        target_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        if target_time < now:
            await send_text(msg, "时间已经过去喵~", is_group=is_group)
            return

        reply = f"已设置精确提醒喵~将在 {target_time} 提醒: {content}"
        if is_group:
            await msg.reply(text=reply)
            asyncio.create_task(schedule_task_by_date(target_time, msg.reply, content))
        else:
            await bot.api.post_private_msg(msg.user_id, text=reply)
            asyncio.create_task(schedule_task_by_date(target_time, bot.api.post_private_msg, msg.user_id, content))
            
    except ValueError:
        error_msg = "格式错误喵~ 使用: /precise_remind MM-DD HH:MM 提醒内容"
        await send_text(msg, error_msg, is_group=is_group)

@register_command("/smtp", help_text="/smtp <host> <port> <user> <password> <tls(1/0)> <from> -> 配置当前用户SMTP服务",category = "4")
async def handle_smtp_config_command(msg, is_group=True):
    user_id = str(msg.user_id)
    raw = msg.raw_message[len("/smtp"):].strip()
    parts = raw.split() if raw else []
    if not parts:
        conf = smtp_config.get(user_id) or smtp_config.get("global")
        if conf:
            text = f"当前SMTP已配置喵~ host={conf.get('host')}, port={conf.get('port')}"
        else:
            text = "当前还没有配置SMTP喵~"
        await send_text(msg, text, is_group=is_group)
        return
    if len(parts) < 5:
        text = "格式错误喵~ 应为: /smtp host port user password tls(1/0) [from]"
        await send_text(msg, text, is_group=is_group)
        return
    host = parts[0]
    try:
        port = int(parts[1])
    except ValueError:
        text = "端口必须是数字喵~"
        await send_text(msg, text, is_group=is_group)
        return
    user = parts[2]
    password = parts[3]
    use_tls = parts[4] != "0"
    from_addr = parts[5] if len(parts) > 5 else user
    smtp_config[user_id] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "use_tls": use_tls,
        "from_addr": from_addr
    }
    save_smtp_config()
    text = "SMTP配置已更新喵~"
    await send_text(msg, text, is_group=is_group)

@register_command("/task",help_text="/task </bot.api.xxxx(参数1=值1...)> <时间(小时)> <是否循环(1/0)> -> 设置定时任务(admin)",category = "7",admin_show=True)
async def handle_task(msg,is_group=True):
    if str(msg.user_id) not in admin:
        text = "你没有权限设置定时任务喵~"
        await send_text(msg, text, is_group=is_group)
        return
    
    match = re.match(r'^/task\s+(.+)\s+(\d+\.?\d*)\s+(\d)$', msg.raw_message) #正则支持小数
    if match:
        command_str = match.group(1)
        hours = float(match.group(2))
        loop = int(match.group(3))
    else:
        error_msg = "格式错误喵~ 请输入 /task bot.api.xxxx(参数1=值1...) 时间(小时) 是否循环(1/0)"
        if is_group:
            await msg.reply(text=error_msg)
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg) 
        return
    if loop not in [0,1]:
        error_msg = "格式错误喵~ 请输入 /task bot.api.xxxx(参数1=值1...) 时间(小时) 是否循环(1/0)"
        if is_group:
            await msg.reply(text=error_msg)
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg) 
        return
    
    dict = parse_command_string(command_str)
    command = dict["func"]
    params = dict["params"]
    try:
        func = getattr(bot.api, command.split('.')[-1])
    except Exception as e:
        error_msg = f"发生错误喵~ 请检查命令是否正确。{e}"
        if is_group:
            await msg.reply(text=error_msg)
        else:
            await bot.api.post_private_msg(msg.user_id, text=error_msg) 
        return

    if loop == 0:
        task = asyncio.create_task(schedule_job_task(hours,0,f"{command_str}_{hours}_{loop}",func, **params))
        schedule_tasks[f"{command_str}_{hours}_{loop}"] = task
        await send_text(msg, f"已设置定时任务喵~{hours}小时后会执行：{command_str}", is_group=is_group)
        return

    else:
        task = asyncio.create_task(schedule_job_task(hours,1,f"{command_str}_{hours}_{loop}",func, **params))
        schedule_tasks[f"{command_str}_{hours}_{loop}"] = task
        await send_text(msg, f"已设置循环定时任务喵~{hours}小时后会执行：{command_str}", is_group=is_group)
        return

@register_command("/list_tasks","/lt",help_text = "/list_tasks 或者 /lt -> 查看定时任务(admin)",category = "7",admin_show=True)
async def handle_list_tasks(msg, is_group=True):
    if str(msg.user_id) not in admin:
        text = "你没有权限查看定时任务喵~"
        await send_text(msg, text, is_group=is_group)
        return
    text = "定时任务列表：\n"
    tot = 0
    for i in schedule_tasks.keys():
        tot += 1
        text += f"{tot}. {i}\n"
    await send_text(msg, text, is_group=is_group)
    return

@register_command("/cancel_tasks","/ct",help_text = "/cancel_tasks 或者 /ct <任务名> -> 取消定时任务(admin)",category = "7",admin_show=True)
async def handle_cancel_tasks(msg, is_group=True):
    if str(msg.user_id) not in admin:
        text = "你没有权限取消定时任务喵~"
        await send_text(msg, text, is_group=is_group)
        return
    pre = "/cancel_tasks" if msg.raw_message.startswith("/cancel_tasks") else "/ct"
    name = msg.raw_message[len(pre):].strip()

    if name == "":
        text = "请输入任务名喵~"
        await send_text(msg, text, is_group=is_group)
        return
    
    if name not in schedule_tasks:
        text = "没有这个任务喵~"
        await send_text(msg, text, is_group=is_group)
        return
    
    schedule_tasks[name].cancel()
    del schedule_tasks[name]
    text = "取消成功喵~"
    await send_text(msg, text, is_group=is_group)
    return

@register_command("/set_admin","/sa",help_text = "/set_admin <qq号> 或者 /sa <qq号> -> 设置管理员(root)",category = "4",admin_show=True)
async def handle_set_admin(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id) != str(admin_id):
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置管理员喵~")
        return

    if msg.raw_message.startswith("/set_admin"):
        id = msg.raw_message[len("/set_admin"):].strip()
    else: 
        id = msg.raw_message[len("/sa"):].strip()

    if id in admin:
        await bot.api.post_private_msg(msg.user_id, text="已经是管理员了喵~")
        return

    admin.append(id)
    write_admin()
    await bot.api.post_private_msg(msg.user_id, text="设置成功喵~，现在"+id+"是管理员喵~")

@register_command("/del_admin","/da",help_text = "/del_admin <qq号> 或者 /da <qq号> -> 删除管理员(root)",category = "4",admin_show=True)
async def handle_del_admin(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id)!= str(admin_id):
        await bot.api.post_private_msg(msg.user_id, text="你没有权限删除管理员喵~")
        return

    if msg.raw_message.startswith("/del_admin"):
        id = msg.raw_message[len("/del_admin"):].strip()
    else:
        id = msg.raw_message[len("/da"):].strip()

    if id in admin:
        admin.remove(id)
        write_admin()
        await bot.api.post_private_msg(msg.user_id, text="删除成功喵~，现在"+id+"不是管理员喵~")
    else:
        await bot.api.post_private_msg(msg.user_id, text="没有这个管理员喵~")

@register_command("/get_admin","/ga",help_text = "/get_admin 或者 /ga -> 获取管理员",category = "4")
async def handle_get_admin(msg, is_group=True):
    await send_text(msg, "管理员列表："+str(admin), is_group=is_group)


@register_command("/set_ids",help_text = "/set_ids <昵称> <个性签名> <性别> -> 设置账号信息(管理员)",category = "4",admin_show=True)
async def handle_set(msg, is_group=True):
    """
            nickname: 昵称
            personal_note: 个性签名
            sex: 性别
            :return: 设置账号信息
    """
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置账号信息喵~")
        return
    msgs = msg.raw_message[len("/set_ids"):].split(" ")
    if len(msgs) < 3:
        text = "格式错误喵~ 请输入 /set 昵称 个性签名 性别"
        await send_text(msg, text, is_group=is_group)
        return
    try:
        nickname = msgs[0]
        personal_note = msgs[1]
        sex = msgs[2]
        await bot.api.set_qq_profile(nickname=nickname, personal_note=personal_note, sex=sex)
        text = "设置成功喵~"
        await send_text(msg, text, is_group=is_group)
    except Exception:
        text = "设置失败喵~"
        await send_text(msg, text, is_group=is_group)

@register_command("/set_online_status",help_text = "/set_online_status <在线状态> -> 设置在线状态(管理员)",category = "4",admin_show=True)
async def handle_set_online_status(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return
    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置在线状态喵~")
        return
    msgs = msg.raw_message[len("/set_online_status"):].split(" ")[0]
    await bot.api.set_online_status(msgs)
    text = "设置成功喵~"
    await send_text(msg, text, is_group=is_group)

@register_command("/get_friends",help_text = "/get_friends -> 获取好友列表（管理员）",category = "4",admin_show=True)
async def handle_get_friends(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊获取喵~")
        return
    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限获取好友列表喵~")
    friends = await bot.api.get_friend_list(False)
    await send_text(msg, friends, is_group=is_group)

@register_command("/set_qq_avatar",help_text = "/set_qq_avatar <地址> -> 更改头像（管理员）",category = "4",admin_show=True)
async def handle_set_qq_avatar(msg, is_group=True):
    if is_group:
        await msg.reply(text="只能私聊设置喵~")
        return

    if str(msg.user_id) not in admin:
        await bot.api.post_private_msg(msg.user_id, text="你没有权限设置头像喵~")
        return

    msgs = msg.raw_message[len("/set_qq_avatar"):]
    await bot.api.set_qq_avatar(msgs)
    text = "设置成功喵~"
    await send_text(msg, text, is_group=is_group)

@register_command("/send_like",help_text = "/send_like <目标QQ号> <次数> -> 发送点赞(admin)",category = "4",admin_show=True)
async def handle_send_like(msg, is_group=True):
    if str(msg.user_id) not in admin:
        await send_text(msg, "你没有权限发送点赞喵~", is_group=is_group)
        return

    msgs = msg.raw_message[len("/send_like"):].split(" ")
    if len(msgs) < 2:
        text = "格式错误喵~ 请输入 /send_like 目标QQ号 次数"
        await send_text(msg, text, is_group=is_group)

    target_qq = msgs[0]
    times = msgs[1]
    await bot.api.send_like(target_qq, times)
    text = "发送成功喵~"
    await send_text(msg, text, is_group=is_group)

@register_command("/set_group_admin",help_text = "/set_group_admin <目标QQ号> -> 设置群管理员(admin)",category = "4",admin_show=True)
async def handle_set_group_admin(msg, is_group=True):
    if not is_group:
        await bot.api.post_private_msg(msg.user_id, text="只能在群聊中设置群管理员喵~")
        return

    if str(msg.user_id) not in admin:
        await msg.reply(text="你没有权限设置群管理员喵~")
        return

    msgs = msg.raw_message[len("/set_group_admin"):].split(" ")[0]
    await bot.api.set_group_admin(msg.group_id, msgs,True)
    await msg.reply(text="设置成功喵~")

@register_command("/del_group_admin",help_text = "/del_group_admin <目标QQ号> -> 取消群管理员(admin)",category = "4",admin_show=True)
async def handle_del_group_admin(msg, is_group=True):
    if not is_group:
        await bot.api.post_private_msg(msg.user_id, text="只能在群聊中取消群管理员喵~")
        return

    if str(msg.user_id) not in admin:
        await msg.reply(text="你没有权限设置群管理员喵~")
        return

    msgs = msg.raw_message[len("/del_group_admin"):].split(" ")[0]
    await bot.api.set_group_admin(msg.group_id, msgs,False)
    await msg.reply(text="取消成功喵~")

# 添加临时存储字典
temp_selections = {}
api_book = {}
WENKU8_COOKIE = "" # 去 www.wenku8.net 登录获取
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

load_wenku8_cookie()

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

@register_command("/findbook","/fb",help_text="/findbook 或者 /fb <书名> -> 搜索并选择下载轻小说",category = "6")
async def handle_find_book(msg, is_group=True):
    # 检查 Cookie
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return
    
    search_term = ""
    if msg.raw_message.startswith("/findbook"):
        search_term = msg.raw_message[len("/findbook"):].strip()
    elif msg.raw_message.startswith("/fb"):
        search_term = msg.raw_message[len("/fb"):].strip()
    if not search_term:
        reply = "请输入要搜索的书名喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    # 发送通知
    await send_text(msg, "正在搜索轻小说喵~", is_group=is_group)

    # 创建HTML文件
    cache_dir = os.path.join(load_address(), "novel_search")
    os.makedirs(cache_dir, exist_ok=True)
    file_token = hashlib.md5(f"novel_{search_term}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{search_term}.html"
    filepath = os.path.join(cache_dir, filename)

    build_novel_grid_html(f"{html.escape(search_term)} · 轻小说搜索", filepath)

    # 1. 先搜索本地缓存
    local_matches = search_local_novel_cache(search_term)
    
    # 2. 如果本地结果不够（少于5本），再去网站搜索
    web_matches = []
    if len(local_matches) < 5:
        web_matches = search_wenku8_books(search_term, "articlename")
    
    # 3. 合并结果并去重（以书名作为唯一标识）
    seen_titles = set()
    matches = []
    
    # 先添加本地结果
    for author, title, download_url in local_matches:
        if title not in seen_titles:
            seen_titles.add(title)
            matches.append((author, title, download_url))
    
    # 再添加网站搜索结果（去重）
    for author, title, download_url in web_matches:
        if title not in seen_titles:
            seen_titles.add(title)
            matches.append((author, title, download_url))
    
    # 4. 搜索API书籍
    api_book[msg.user_id] = find_book_from_api(search_term)

    if not matches and not api_book[msg.user_id]:
        close_novel_grid_html(filepath)
        reply = f"没有找到包含'{search_term}'的轻小说喵~"
        if is_group:
            await msg.reply(text=reply)
            await bot.api.post_group_file(msg.group_id, file=filepath)
        else:
            await bot.api.post_private_msg(msg.user_id, text=reply)
            await bot.api.upload_private_file(msg.user_id, filepath, filename)
        return

    # 添加搜索结果到卡片
    for i, (author, title, download_url) in enumerate(matches):
        book_id_match = re.search(r'id=(\d+)', download_url)
        book_id = book_id_match.group(1) if book_id_match else "0"
        append_novel_card(filepath, book_id, title, author, i + 1)
        # 更新全局 books 字典
        if title not in books:
            books[title] = {
                "download_url": download_url,
                "page": f"https://www.wenku8.net/book/{book_id}.htm",
                "author": author
            }

    # 添加 API 结果到卡片
    if api_book[msg.user_id]:
        start_seq = len(matches) + 1
        for i, (_, title) in enumerate(api_book[msg.user_id].items()):
            if title not in seen_titles:  # API结果也去重
                book_id = api_book[msg.user_id][_].get("book_id", "0")
                author = api_book[msg.user_id][_].get("author", "未知")
                append_novel_card(filepath, book_id, title, author, start_seq + i)
                # 更新全局 books 字典
                if title not in books:
                    books[title] = api_book[msg.user_id][_]

    close_novel_grid_html(filepath)

    # 存储匹配结果临时数据
    temp_selections[msg.user_id] = matches

    if is_group:
        await msg.reply(text=f"找到 {len(matches) + len(api_book[msg.user_id]) if api_book[msg.user_id] else len(matches)} 本轻小说喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
        await bot.api.post_group_file(msg.group_id, file=filepath)
    else:
        await bot.api.post_private_msg(msg.user_id, text=f"找到 {len(matches) + len(api_book[msg.user_id]) if api_book[msg.user_id] else len(matches)} 本轻小说喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
        await bot.api.upload_private_file(msg.user_id, filepath, filename)

@register_command("/fa",help_text="/fa <作者> -> 搜索作者",category = "6")
async def handle_find_author(msg, is_group=True):
    # 检查 Cookie
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return
    
    search_term = msg.raw_message[len("/fa"):].strip()
    if not search_term:
        reply = "请输入要搜索的作者喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    matches = search_wenku8_books(search_term, "author")

    if not matches:
        reply = f"没有找到包含'{search_term}'的作者喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    # 生成选择列表
    choices = "\n".join([f"{i+1}. {title} -- {author}" for i, (author,title, _) in enumerate(matches)])
    reply = f"找到以下匹配的作者的轻小说喵~:\n{choices}\n\n请回复'/select 编号'选择要下载的轻小说喵~\n回复'/info 编号'获取轻小说信息喵~"
    # 存储匹配结果临时数据
    temp_selections[msg.user_id] = matches

    await send_text(msg, reply, is_group=is_group)

def search_wenku8_books(search_term: str, search_type: str, max_pages: int = 3) -> list:
    """
    搜索 wenku8 小说，支持分页
    
    :param search_term: 搜索关键词
    :param search_type: 搜索类型 (articlename 或 author)
    :param max_pages: 最大搜索页数，默认为 3 页
    :return: 搜索结果列表
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wenku8.net/",
        "Cookie": WENKU8_COOKIE
    }
    _log.info(f"使用Cookie: {WENKU8_COOKIE[:50]}...")
    import urllib.parse
    try:
        encoded_key = urllib.parse.quote(search_term.encode("gbk"))
    except Exception as e:
        _log.error(f"搜索关键词编码失败: {search_term}, 错误: {e}")
        return []
    
    results = []
    pattern = r'<div style="width:373px;height:136px;float:left;margin:5px 0px 5px 5px;">(.*?)</div>\s*</div>'
    
    for page in range(1, max_pages + 1):
        url = f"https://www.wenku8.net/modules/article/search.php?searchtype={search_type}&searchkey={encoded_key}&page={page}"
        _log.info(f"搜索URL (第{page}页): {url}")
        try:
            response = get_sync(url, headers=headers, timeout=10)
            _log.info(f"搜索响应状态码: {response.status_code}")
        except Exception as e:
            _log.error(f"搜索请求失败: {e}")
            break
        
        # 检查网站是否关闭
        if '有缘再相聚' in response.text or '网站已关闭' in response.text:
            _log.warning("wenku8.net 网站已关闭")
            break
        
        response.encoding = "gbk"
        content = response.text
        
        # 检查HTTP状态码
        if response.status_code == 403:
            _log.warning("搜索返回403错误，Cookie可能已失效或被反爬虫机制拦截")
            break
        # 检查是否需要登录（根据特定错误提示，排除已登录状态下的"退出登录"字样）
        if "出现错误" in content or ("登录" in content and "退出登录" not in content):
            _log.warning("搜索需要登录，Cookie可能已失效")
            break
        
        page_matches = re.findall(pattern, content, re.DOTALL)
        _log.info(f"第{page}页搜索结果数量: {len(page_matches)}")
        
        if not page_matches:
            _log.info(f"第{page}页没有结果，停止搜索")
            break
        
        for match in page_matches:
            title_url_match = re.search(r'<b><a style="font-size:13px;" href="([^"]+)" title="([^"]+)" target="_blank">', match)
            book_url = title_url_match.group(1) if title_url_match else ""
            title = title_url_match.group(2) if title_url_match else "未知"
            book_id = "0"
            id_match = re.search(r'/book/(\d+)\.htm', book_url)
            if id_match:
                book_id = id_match.group(1)
            node = int(book_id) // 1000 if book_id.isdigit() else 0
            author_cat_match = re.search(r'<p>作者:([^/]+)/分类:([^<]+)</p>', match)
            author = author_cat_match.group(1) if author_cat_match else "未知"
            category = author_cat_match.group(2) if author_cat_match else "未知"
            stats_match = re.search(r'<p>更新:([^/]+)/字数:([^/]+)/([^<]+)</p>', match)
            last_date = stats_match.group(1) if stats_match else "未知"
            word_count = stats_match.group(2) if stats_match else "未知"
            is_serialize = stats_match.group(3) if stats_match else "未知"
            tags_match = re.search(r'Tags:<span[^>]*>([^<]+)</span>', match)
            tags = tags_match.group(1) if tags_match else "无"
            intro_match = re.search(r'简介:([^<]+)', match)
            introduction = intro_match.group(1).strip() if intro_match else "暂无简介"
            img_match = re.search(r'<img src="([^"]+)"', match)
            cover_url = img_match.group(1) if img_match else f"https://img.wenku8.com/image/{node}/{book_id}/{book_id}s.jpg"
            download_url = f"https://dl.wenku8.com/down.php?type=txt&node={node}&id={book_id}"
            page_url = f"https://www.wenku8.net/book/{book_id}.htm"
            books[title] = {
                "author": author,
                "category": category,
                "last_date": last_date,
                "word_count": word_count,
                "is_serialize": is_serialize,
                "introduction": introduction,
                "tags": tags,
                "cover_url": cover_url,
                "download_url": download_url,
                "page": page_url,
                "hot": "搜索结果书籍"
            }
            results.append((author, title, download_url))
    
    _log.info(f"总搜索结果数量: {len(results)}")
    return results

def search_local_novel_cache(search_term: str) -> list:
    """
    在本地 novel_details2.json 缓存中搜索小说
    
    :param search_term: 搜索关键词
    :return: 搜索结果列表 [(author, title, download_url), ...]
    """
    results = []
    search_term_lower = search_term.lower()
    
    try:
        cache_file = os.path.join(os.path.dirname(__file__), '..', 'resources', 'config', 'novel_details2.json')
        if not os.path.exists(cache_file):
            _log.warning(f"本地缓存文件不存在: {cache_file}")
            return results
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        for title, info in cache_data.items():
            # 在书名和作者中搜索
            author = info.get('author', '')
            if search_term_lower in title.lower() or search_term_lower in author.lower():
                download_url = info.get('download_url', '')
                results.append((author, title, download_url))
        
        _log.info(f"本地缓存搜索结果: 找到 {len(results)} 本包含 '{search_term}' 的小说")
    except Exception as e:
        _log.error(f"搜索本地缓存失败: {e}")
    
    return results

def get_book_detail_by_url(book_url: str) -> dict:
    """
    通过URL获取小说详情（类似/hotnovel的实现）
    :param book_url: 小说详情页面URL，如 https://www.wenku8.net/book/1234.htm 或 /book/1234.htm
    :return: 包含小说详细信息的字典
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wenku8.net/",
        "Cookie": WENKU8_COOKIE
    }

    # 处理相对路径
    if not book_url.startswith(('http://', 'https://')):
        book_url = 'https://www.wenku8.net' + book_url

    _log.info(f"获取小说详情: {book_url}")
    try:
        response = get_sync(book_url, headers=headers, timeout=10)
        _log.info(f"详情页响应状态码: {response.status_code}")
        
        # 检查网站是否关闭
        if response.status_code == 404 or '网站已关闭' in response.text or '有缘再相聚' in response.text:
            _log.warning("wenku8.net 网站已关闭或页面不存在")
            return None
        
        response.encoding = "gbk"
        content = response.text
        
        # 解析书籍ID
        book_id_match = re.search(r'/book/(\d+)\.htm', book_url)
        book_id = book_id_match.group(1) if book_id_match else "0"
        node = int(book_id) // 1000 if book_id.isdigit() else 0
        
        # 解析标题
        title_match = re.search(r'<span property="v:itemreviewed">([^<]+)</span>', content)
        title = title_match.group(1).strip() if title_match else "未知"
        
        # 解析作者
        author_match = re.search(r'作者：\s*<a[^>]*>([^<]+)</a>', content)
        author = author_match.group(1).strip() if author_match else "未知"
        
        # 解析分类
        category_match = re.search(r'类别：\s*<a[^>]*>([^<]+)</a>', content)
        category = category_match.group(1).strip() if category_match else "未知"
        
        # 解析状态
        status_match = re.search(r'状态：\s*<font[^>]*>([^<]+)</font>', content)
        is_serialize = status_match.group(1).strip() if status_match else "未知"
        
        # 解析字数
        word_count_match = re.search(r'字数：\s*([\d,]+)', content)
        word_count = word_count_match.group(1).replace(',', '') if word_count_match else "未知"
        
        # 解析更新时间
        update_match = re.search(r'更新时间：\s*([\d-]+)', content)
        last_date = update_match.group(1) if update_match else "未知"
        
        # 解析简介
        intro_match = re.search(r'<span class="hottext">内容简介：</span>\s*<br\s*/?>\s*([^<]+)', content, re.DOTALL)
        introduction = intro_match.group(1).strip() if intro_match else "暂无简介"
        
        # 解析封面
        cover_match = re.search(r'<img src="([^"]+)"[^>]*alt="[^"]*封面"', content)
        cover_url = cover_match.group(1) if cover_match else f"https://img.wenku8.com/image/{node}/{book_id}/{book_id}s.jpg"
        
        # 构建下载链接
        download_url = f"https://dl.wenku8.com/down.php?type=txt&node={node}&id={book_id}"
        
        return {
            "title": title,
            "author": author,
            "category": category,
            "word_count": word_count,
            "is_serialize": is_serialize,
            "last_date": last_date,
            "introduction": introduction,
            "cover_url": cover_url,
            "download_url": download_url,
            "page": book_url,
            "hot": "URL获取"
        }
    except Exception as e:
        _log.error(f"获取小说详情失败: {book_url}, 错误: {e}")
        return None

def find_book_from_api(search_term: str) -> list:
    """
    从API搜索小说
    :param search_term: 搜索关键词
    :return: 包含匹配小说信息的列表
    """
    base_url = get_novel_api_base_url()
    if not base_url:
        return {}
    url = f"{base_url}/api/search"
    params = {
        "key": search_term,
        "tab_type": 3,
    }
    try:
        res = get_sync(url, params=params, timeout=10)
    except Exception:
        return {}
    book_ids = {}
    if res.ok:
        data = res.json()
        for tab in data.get("data", {}).get("search_tabs", []):
            if tab.get("tab_type") == 3:  # 书籍类 tab
                for item in tab.get("data", []):
                    book_data = item.get("book_data", [])
                    for book in book_data:
                        book_id = book.get("book_id")
                        book_name = book.get("book_name")
                        if book_id:
                            book_ids[book_id] = book_name
    
    return book_ids


def download_api_book(id,name):
    base_url = get_novel_api_base_url()
    if not base_url:
        _log.error("下载失败：没有可用的API地址")
        return
    url = f"{base_url}/api/content"
    params = {
        "tab":"下载",
        "book_id":id
    }
    try:
        response = get_sync(url, params=params, timeout=30)
    except Exception as e:
        _log.error(f"下载失败：{e}")
        return
    if response.status_code == 200:
        content = response.text
        # 确保目录存在
        path = os.path.join(os.path.dirname(__file__), f"cache/novel/{name}.txt")
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
    params = {
        "book_id":id
    }
    try:
        response = get_sync(url, params=params, timeout=10)
    except Exception as e:
        _log.error(f"获取失败：{e}")
        return None
    if response.status_code == 200:
        raw = json.loads(response.text)
        book  = raw['data']['data']          

        info = {
            'author'       : book['author'],
            'category'     : book['category'],
            'word_count'   : f"{int(book['word_number']):,}",  
            'is_serialize' : '连载中' if int(book['creation_status']) == 1 else '已完结',
            'hot'          : book['read_cnt_text'],            
            'last_date'    : datetime.fromtimestamp(int(book['last_publish_time'])).strftime('%Y-%m-%d'),
            'download_url' : f"https://tomato-novel-downloader.vercel.app/?book_id={book['book_id']}", 
            'page'         : f"https://fanqienovel.com/page/{book['book_id']}",                       
            'cover'        : book['thumb_url'],
            'introduction' : book['abstract'].replace('\n', ''),   
            'title'        : book['book_name'],
        }
        return info

    else:
        _log.error(f"获取失败，状态码：{response.status_code}")
        return None


# 添加选择处理函数
@register_command("/select", help_text="/select <编号> -> 选择要下载的轻小说(先使用/findbook或/fb搜索，再进行选择，重复使用/fb会覆盖之前的搜索结果)",category = "6")
async def handle_select_book(msg, is_group=True):
    if (msg.user_id not in temp_selections) and (msg.user_id not in api_book):
        reply = "没有找到主人的搜索记录喵~请先使用/findbook搜索喵~"
        await send_text(msg, reply, is_group=is_group)
        return
    try:
        selection = int(msg.raw_message[len("/select"):].strip()) - 1
        matches = temp_selections.get(msg.user_id, [])
        api_books = api_book.get(msg.user_id, {})

        if 0 <= selection < len(matches) or (selection >= len(matches) and selection < len(matches) + len(api_books)):
            if selection < len(matches):
                author,title, url = matches[selection]
                reply = f"已选择《{title}》-- {author}喵~\n下载链接: {url}"
                await send_text(msg, reply, is_group=is_group)
                # 注意：这里只发送链接，不直接发送文件，因为URL不是本地文件
                # 如果需要下载文件，需要先下载到本地再发送
            else:
                id, title = list(api_books.items())[selection - len(matches)]
                download_api_book(id,title)
                reply = f"已开始下载《{title}》喵~"
                await msg.reply(text=reply)
                api_book_file_path = os.path.join(os.path.dirname(__file__), f"cache/novel/{title}.txt")
                if os.path.exists(api_book_file_path):
                    if is_group:
                        await bot.api.post_group_file(msg.group_id,file=api_book_file_path)
                    else:
                        await bot.api.upload_private_file(msg.user_id,file=api_book_file_path,name=title+".txt")
                else:
                    await msg.reply(text="文件下载中，请稍后再试喵~")
            
        else:
            reply = "编号无效喵~请选择列表中的编号喵~"
            await send_text(msg, reply, is_group=is_group)
    except ValueError:
        reply = "请输入有效的编号喵~"
        await send_text(msg, reply, is_group=is_group)
    
    # 安全删除，避免KeyError
    temp_selections.pop(str(msg.user_id), None)
    api_book.pop(str(msg.user_id), None)  

@register_command("/info",help_text="/info <书名> -> 获取轻小说信息",category = "6")
async def handle_info(msg, is_group=True):
    # 检查 Cookie
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return
    
    if (msg.user_id not in temp_selections) and (msg.user_id not in api_book):
        reply = "没有找到您的搜索记录喵~请先使用/findbook搜索喵~"
        await send_text(msg, reply, is_group=is_group)
        return 
    try:
        selection = int(msg.raw_message[len("/info"):].strip()) - 1
        matches = temp_selections[msg.user_id]
        api_books = api_book[msg.user_id]

        if 0 <= selection < len(matches) or (selection >= len(matches) and selection < len(matches) + len(api_books)):
            if selection < len(matches):
                author,title, url = matches[selection]
                # 从下载链接提取book_id，构建详情页面URL
                book_id_match = re.search(r'id=(\d+)', url)
                if book_id_match:
                    book_id = book_id_match.group(1)
                    book_url = f"https://www.wenku8.net/book/{book_id}.htm"
                    info = get_book_detail_by_url(book_url)
                else:
                    info = None
                
                if info is None:
                    # 如果URL获取失败，先尝试从JSON/内存字典获取
                    info = books.get(title)
                    if info is None:
                        # 如果JSON也没有，使用搜索时的基本信息
                        info = {
                            'author': author,
                            'category': '未知',
                            'word_count': '未知',
                            'is_serialize': '未知',
                            'hot': '搜索结果',
                            'introduction': '暂无简介',
                            'last_date': '未知',
                            'page': book_url if 'book_url' in locals() else url,
                            'cover_url': f"https://img.wenku8.com/image/{int(book_id)//1000 if 'book_id' in locals() else 0}/{book_id if 'book_id' in locals() else 0}/{book_id if 'book_id' in locals() else 0}s.jpg"
                        }
                    else:
                        _log.info(f"从JSON/内存字典获取到《{title}》的信息")
                
                try:
                    introduction = info['introduction']
                except Exception:
                    introduction = "暂无"
                cover = info['cover_url']
                
                # 创建HTML详情页
                cache_dir = os.path.join(load_address(), "novel_info")
                os.makedirs(cache_dir, exist_ok=True)
                file_token = hashlib.md5(f"info_{title}_{time.time()}".encode("utf-8")).hexdigest()[:8]
                filename = f"{file_token}_{title[:20]}.html"
                filepath = os.path.join(cache_dir, filename)
                
                build_novel_detail_html(title, info, filepath)
                
                # 发送文本消息
                text_reply = f"《{title}》的信息如下喵~\n作者: {author}\n分类: {info['category']}\n字数: {info['word_count']}\n状态: {info['is_serialize']}\n热度：{info['hot']}\n简介：{introduction}\n更新日期: {info['last_date']}\n下载链接: {url}\n详细页面：{info['page']}"
                
                if is_group:
                    await msg.reply(text=text_reply)
                    await bot.api.post_group_file(msg.group_id, file=filepath)
                else:
                    await bot.api.post_private_msg(msg.user_id, text=text_reply)
                    await bot.api.upload_private_file(msg.user_id, filepath, filename)
            else:
                id, title = list(api_books.items())[selection - len(matches)]
                
                info = get_api_book_info(id)
                if(info==None):
                    reply = "没有找到该轻小说的信息喵~"
                    await msg.reply(text=reply)
                    return

                # 创建HTML详情页
                cache_dir = os.path.join(load_address(), "novel_info")
                os.makedirs(cache_dir, exist_ok=True)
                file_token = hashlib.md5(f"info_{title}_{time.time()}".encode("utf-8")).hexdigest()[:8]
                filename = f"{file_token}_{title[:20]}.html"
                filepath = os.path.join(cache_dir, filename)
                
                build_novel_detail_html(title, info, filepath)
                
                # 发送文本消息
                text_reply = f"《{title}》的信息如下喵~\n作者: {info['author']}\n分类: {info['category']}\n字数: {info['word_count']}\n状态: {info['is_serialize']}\n热度：{info['hot']}\n简介：{info['introduction']}\n更新日期: {info['last_date']}\n下载链接: {info['download_url']}\n详细页面：{info['page']}"
                
                if is_group:
                    await msg.reply(text=text_reply)
                    await bot.api.post_group_file(msg.group_id, file=filepath)
                else:
                    await bot.api.post_private_msg(msg.user_id, text=text_reply)
                    await bot.api.upload_private_file(msg.user_id, filepath, filename)

        else:
            reply = "编号无效喵~请选择列表中的编号喵~"
            await send_text(msg, reply, is_group=is_group)
    except ValueError:
        reply = "请输入有效的编号喵~"
        await send_text(msg, reply, is_group=is_group)

def get_random_book_from_hotlist() -> tuple:
    """
    从今日热门榜单获取随机小说
    :return: (title, book_info_dict) 或 (None, None)
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wenku8.net/",
        "Cookie": WENKU8_COOKIE
    }
    url = "https://www.wenku8.net/modules/article/toplist.php?sort=dayvisit&page=1"
    
    _log.info(f"获取热门榜单: {url}")
    try:
        response = get_sync(url, headers=headers, timeout=10)
        _log.info(f"热门榜单响应状态码: {response.status_code}")
        response.encoding = 'gbk'
        content = response.text
        
        pattern = r'<div style="width:373px;height:136px;float:left;margin:5px 0px 5px 5px;">(.*?)</div>\s*</div>'
        page_matches = re.findall(pattern, content, re.DOTALL)
        
        if not page_matches:
            return None, None
        
        # 随机选择一本
        match = random.choice(page_matches)
        
        # 解析标题和URL
        title_url_match = re.search(r'<b><a style="font-size:13px;" href="([^"]+)" title="([^"]+)" target="_blank">', match)
        if not title_url_match:
            return None, None
        
        book_url = title_url_match.group(1)
        title = title_url_match.group(2)
        
        # 获取详细信息
        info = get_book_detail_by_url(book_url)
        if info is None:
            # 如果详情获取失败，使用基本信息
            book_id_match = re.search(r'/book/(\d+)\.htm', book_url)
            book_id = book_id_match.group(1) if book_id_match else "0"
            node = int(book_id) // 1000 if book_id.isdigit() else 0
            
            author_cat_match = re.search(r'<p>作者:([^/]+)/分类:([^<]+)</p>', match)
            author = author_cat_match.group(1) if author_cat_match else "未知"
            
            info = {
                'author': author,
                'category': '未知',
                'word_count': '未知',
                'is_serialize': '未知',
                'last_date': '未知',
                'introduction': '暂无简介',
                'cover_url': f"https://img.wenku8.com/image/{node}/{book_id}/{book_id}s.jpg",
                'download_url': f"https://dl.wenku8.com/down.php?type=txt&node={node}&id={book_id}",
                'page': book_url,
                'hot': '今日热门'
            }
        
        return title, info
    except Exception as e:
        _log.error(f"获取随机小说失败: {e}")
        return None, None

@register_command("/random_novel","/rn",help_text = "/random_novel 或者 /rn -> 发送随机小说",category = "6")
async def handle_random_novel(msg, is_group=True):
    # 检查 Cookie
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return
    
    # 从今日热门榜单获取随机小说
    novel, info = get_random_book_from_hotlist()
    
    # 如果URL获取失败，回退到JSON/内存字典
    if novel is None:
        _log.info("热门榜单获取失败，回退到JSON/内存字典")
        if books:
            novel = random.choice(list(books.keys()))
            info = books[novel]
            _log.info(f"从JSON/内存字典随机选择:《{novel}》")
        else:
            reply = "获取随机小说失败喵~请稍后再试~"
            await send_text(msg, reply, is_group=is_group)
            return
    
    url = info["download_url"]
    hot = info.get('hot', '未知')
    
    # 创建HTML详情页
    cache_dir = os.path.join(load_address(), "novel_random")
    os.makedirs(cache_dir, exist_ok=True)
    file_token = hashlib.md5(f"random_{novel}_{time.time()}".encode("utf-8")).hexdigest()[:8]
    filename = f"{file_token}_{novel[:20]}.html"
    filepath = os.path.join(cache_dir, filename)
    
    build_novel_detail_html(novel, info, filepath)
    
    text_reply = f"抽选到了《{novel}》喵~\n"
    text_reply += f"简介如下喵~\n作者：{info['author']}\n字数：{info['word_count']}\n状态：{info['is_serialize']}\n热度：{hot}\n最新更新：{info['last_date']}\n简介：{info['introduction']}\n下载链接：{url}"
    
    if is_group:
        await msg.reply(text=text_reply)
        await bot.api.post_group_file(msg.group_id, file=filepath)
    else:
        await bot.api.post_private_msg(msg.user_id, text=text_reply)
        await bot.api.upload_private_file(msg.user_id, filepath, filename)

@register_command("/hotnovel", help_text="/hotnovel <day|month> [数量] -> 获取今日/本月热门轻小说(支持翻页)", category="6")
async def handle_hotnovel(msg, is_group=True):
    # 检查 Cookie
    cookie_check = check_wenku8_cookie()
    if cookie_check:
        await send_text(msg, cookie_check, is_group=is_group)
        return
    
    parts = msg.raw_message.split()
    if len(parts) < 2:
        reply = "请输入查询类型喵~ 例如：/hotnovel day 或 /hotnovel month"
        await send_text(msg, reply, is_group=is_group)
        return

    rank_type = parts[1].lower()
    base_url = ""
    if rank_type == "day":
        base_url = "https://www.wenku8.net/modules/article/toplist.php?sort=dayvisit"
        type_name = "今日热门"
    elif rank_type in ["month", "mouth"]:
        base_url = "https://www.wenku8.net/modules/article/toplist.php?sort=monthvisit"
        type_name = "本月热门"
    else:
        reply = "目前只支持 day 或 month 喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    requested_count = 10
    if len(parts) >= 3:
        try:
            requested_count = int(parts[2])
            if requested_count <= 0:
                requested_count = 10
            if requested_count > 100:  # 设置一个合理的上限避免滥用
                requested_count = 100
        except ValueError:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://www.wenku8.net/",
        "Cookie": WENKU8_COOKIE
    }

    all_matches = []
    current_page = 1

    try:
        while len(all_matches) < requested_count:
            url = f"{base_url}&page={current_page}"
            response = get_sync(url, headers=headers, timeout=10)
            response.encoding = 'gbk'
            content = response.text
            
            # 检查HTTP状态码
            if response.status_code == 403:
                _log.warning("热门榜单返回403错误，Cookie可能已失效或被反爬虫机制拦截")
                reply = "❌ 榜单获取失败，Cookie 可能已失效喵！\n请管理员使用 `/set_wenku_cookie <新Cookie>` 命令更新 Cookie 喵~"
                await send_text(msg, reply, is_group=is_group)
                return
            
            pattern = r'<div style="width:373px;height:136px;float:left;margin:5px 0px 5px 5px;">(.*?)</div>\s*</div>'
            page_matches = re.findall(pattern, content, re.DOTALL)
            
            if not page_matches:
                if current_page == 1:
                    # 检查是否需要登录（根据特定错误提示，排除已登录状态下的"退出登录"字样）
                    if "出现错误" in content or (("登录" in content and "退出登录" not in content) or "login" in content.lower()):
                        reply = "❌ 榜单获取失败，Cookie 可能已失效喵！\n请管理员使用 `/set_wenku_cookie <新Cookie>` 命令更新 Cookie 喵~"
                    else:
                        reply = "没找到热门榜单喵，可能网页结构变了喵~"
                    
                    await send_text(msg, reply, is_group=is_group)
                    return
                else:
                    # 如果不是第一页没结果，说明到底了
                    break
            
            all_matches.extend(page_matches)
            if len(page_matches) < 20: # 每一页通常是20个，如果少于20说明是最后一页
                break
            
            current_page += 1
            if current_page > 5: # 最多翻5页(100条)，防止无限循环
                break

        results = []
        for match in all_matches[:requested_count]:
            # 提取基本信息
            title_url_match = re.search(r'<b><a style="font-size:13px;" href="([^"]+)" title="([^"]+)" target="_blank">', match)
            book_url = title_url_match.group(1) if title_url_match else ""
            title = title_url_match.group(2) if title_url_match else "未知"
            
            # 提取 ID
            book_id = "0"
            id_match = re.search(r'/book/(\d+)\.htm', book_url)
            if id_match:
                book_id = id_match.group(1)
            
            node = int(book_id) // 1000
            
            # 提取其他详细信息以供 /info 使用
            author_cat_match = re.search(r'<p>作者:([^/]+)/分类:([^<]+)</p>', match)
            author = author_cat_match.group(1) if author_cat_match else "未知"
            category = author_cat_match.group(2) if author_cat_match else "未知"
            
            stats_match = re.search(r'<p>更新:([^/]+)/字数:([^/]+)/([^<]+)</p>', match)
            last_date = stats_match.group(1) if stats_match else "未知"
            word_count = stats_match.group(2) if stats_match else "未知"
            is_serialize = stats_match.group(3) if stats_match else "未知"
            
            tags_match = re.search(r'Tags:<span[^>]*>([^<]+)</span>', match)
            tags = tags_match.group(1) if tags_match else "无"
            
            intro_match = re.search(r'简介:([^<]+)', match)
            introduction = intro_match.group(1).strip() if intro_match else "暂无简介"
            
            img_match = re.search(r'<img src="([^"]+)"', match)
            cover_url = img_match.group(1) if img_match else f"https://img.wenku8.com/image/{node}/{book_id}/{book_id}s.jpg"

            # 构造下载链接
            download_url = f"https://dl.wenku8.com/down.php?type=txt&node={node}&id={book_id}"
            page_url = f"https://www.wenku8.net/book/{book_id}.htm"

            # 更新全局 books 字典
            books[title] = {
                "author": author,
                "category": category,
                "last_date": last_date,
                "word_count": word_count,
                "is_serialize": is_serialize,
                "introduction": introduction,
                "tags": tags,
                "cover_url": cover_url,
                "download_url": download_url,
                "page": page_url,
                "hot": "热门榜单书籍"
            }
            
            results.append((author, title, download_url))

        # 存储到临时选择列表
        temp_selections[msg.user_id] = results
        # 同时清空 api_book 避免干扰
        api_book[msg.user_id] = {}

        # 创建HTML文件
        cache_dir = os.path.join(load_address(), "novel_hot")
        os.makedirs(cache_dir, exist_ok=True)
        file_token = hashlib.md5(f"hotnovel_{rank_type}_{time.time()}".encode("utf-8")).hexdigest()[:8]
        filename = f"{file_token}_{type_name}.html"
        filepath = os.path.join(cache_dir, filename)

        build_novel_grid_html(f"{type_name} · 轻小说排行", filepath)

        # 添加到卡片
        for i, (author, title, download_url) in enumerate(results):
            book_id_match = re.search(r'id=(\d+)', download_url)
            book_id = book_id_match.group(1) if book_id_match else "0"
            append_novel_card(filepath, book_id, title, author, i + 1)

        close_novel_grid_html(filepath)

        if is_group:
            await msg.reply(text=f"✨ {type_name}前{len(results)}名喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
            await bot.api.post_group_file(msg.group_id, file=filepath)
        else:
            await bot.api.post_private_msg(msg.user_id, text=f"✨ {type_name}前{len(results)}名喵~ 点击卡片查看详情或使用 /info 编号 获取信息喵~")
            await bot.api.upload_private_file(msg.user_id, filepath, filename)

    except Exception as e:
        _log.error(f"Error in handle_hotnovel: {e}")
        reply = "获取热门榜单失败了喵，请稍后再试喵~"
        await send_text(msg, reply, is_group=is_group)

@register_command("/novel_res", help_text="/novel_res <res值> -> 根据res编号下载轻小说", category="6")
async def handle_novel_by_res(msg, is_group=True):
    res_value = msg.raw_message[len("/novel_res"):].strip()
    if not res_value:
        reply = "请输入要下载的res编号喵~例如：/novel_res 1121"
        await send_text(msg, reply, is_group=is_group)
        return

    target_title = None
    target_info = None
    for title, info in books.items():
        if str(info.get("res")) == res_value:
            target_title = title
            target_info = info
            break

    if not target_info:
        download_url = f"https://dl.wenku8.com/down.php?type=txt&node=1&id={res_value}"
        reply = f"已开始下载res为 {res_value} 的轻小说喵~"
        if is_group:
            await msg.reply(text=reply)
            await bot.api.post_group_file(msg.group_id, file=download_url)
        else:
            await bot.api.post_private_msg(msg.user_id, text=reply)
            await bot.api.upload_private_file(msg.user_id, file=download_url, name=f"{res_value}.txt")
        return

    download_url = target_info.get("download_url")
    if not download_url:
        reply = "该轻小说没有可用的下载链接喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    reply = f"已开始下载《{target_title}》喵~"
    if is_group:
        await msg.reply(text=reply)
        await bot.api.post_group_file(msg.group_id, file=download_url)
    else:
        await bot.api.post_private_msg(msg.user_id, text=reply)
        await bot.api.upload_private_file(msg.user_id, file=download_url, name=target_title + ".txt")

@register_command("/set_wenku_cookie", help_text="/set_wenku_cookie <Cookie> -> 更新文库8的Cookie(仅限管理员)", category="6", admin_show=True)
async def handle_set_wenku_cookie(msg, is_group=True):
    if str(msg.user_id) not in admin:
        reply = "主人，这个功能只有管理员才能使用喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    new_cookie = msg.raw_message[len("/set_wenku_cookie"):].strip()
    if not new_cookie:
        reply = "请输入新的 Cookie 喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    save_wenku8_cookie(new_cookie)
    reply = "✅ Cookie 更新成功喵！现在可以尝试使用 /hotnovel 喵~"
    await send_text(msg, reply, is_group=is_group)

mc = {}
@register_command("/mc",help_text = "/mc <服务器地址> -> 发送mc服务器状态",category = "3")
async def handle_mc(msg, is_group=True):
    if os.path.exists("mc.txt"):
        with open("mc.txt", "r") as f:
            for line in f:
                parts = line.strip().split(":")
                if len(parts) >= 2:
                    id = parts[0]
                    server = ":".join(parts[1:])
                    mc[id] = server
    else:
        with open("mc.txt", "w") as f:
            pass
    server = msg.raw_message[len("/mc"):].strip()
    if not server:
        if str(msg.user_id) in mc:
            server = mc[str(msg.user_id)]
        else:
            reply = "请输入服务器地址或使用/mc_bind进行绑定喵~"
            await send_text(msg, reply, is_group=is_group)
            return
    
    try:
        import mcstatus
        server = mcstatus.JavaServer.lookup(server)
        status = server.status()
        reply = f"服务器状态如下喵~\n服务器描述：{status.description}\n版本: {status.version.name}\n在线人数: {status.players.online}\n最大人数: {status.players.max}\n延迟: {int(status.latency)}ms"
        await send_text(msg, reply, is_group=is_group)
    except ImportError:
        reply = "未安装mcstatus库喵~请使用pip install mcstatus进行安装喵~"
        await send_text(msg, reply, is_group=is_group)
    except Exception:
        reply = "获取服务器状态失败喵~"
        await send_text(msg, reply, is_group=is_group)

@register_command("/mc_bind",help_text = "/mc_bind <服务器地址> -> 绑定mc服务器",category = "3")
async def handle_mc_bind(msg, is_group=True):
    server = msg.raw_message[len("/mc_bind"):].strip()
    if not server:
        reply = "请输入服务器地址喵~"
        await send_text(msg, reply, is_group=is_group)
        return
    mc[str(msg.user_id)] = server
    with open("mc.txt", "a") as f:
        f.write(f"{msg.user_id}:{server}\n")
    reply = "绑定成功喵~"
    await send_text(msg, reply, is_group=is_group)

@register_command("/mc_unbind",help_text = "/mc_unbind -> 解绑mc服务器",category = "3")
async def handle_mc_unbind(msg, is_group=True):
    if str(msg.user_id) in mc:
        del mc[str(msg.user_id)]
        with open("mc.txt", "r") as f:
            lines = f.readlines()
        with open("mc.txt", "w") as f:
            for line in lines:
                if line.split(":")[0] != str(msg.user_id):
                    f.write(line)
        reply = "解绑成功喵~"
        await send_text(msg, reply, is_group=is_group)
    else:
        reply = "你没有绑定过mc服务器喵~"
        await send_text(msg, reply, is_group=is_group)

@register_command("/mc_show",help_text = "/mc_show -> 查看绑定的mc服务器",category = "3")
async def handle_mc_show(msg, is_group=True):
    if str(msg.user_id) in mc:
        reply = f"你绑定的mc服务器是：{mc[str(msg.user_id)]}"
        await send_text(msg, reply, is_group=is_group)
    else:
        reply = "你没有绑定过mc服务器喵~"
        await send_text(msg, reply, is_group=is_group)

@register_command("/generate_photo","/gf",help_text = "/generate_photo 或 /gf <图片描述(不能有空格)> <大小> -> 生成图片",category = "3")
async def handle_gf(msg,is_group=True):
    text = re.sub(r'\[CQ:[^]]*\]', '', msg.raw_message).strip()
    prefix = "/generate_photo" if text.startswith("/generate_photo") else "/gf"
    default_size = "2k"
    try:
        args = text[len(prefix):].strip().split()
        if not args:
            raise ValueError
        if len(args) == 1:
            prompt = args[0]
            size = default_size
        else:
            size = args[-1]
            prompt = ' '.join(args[:-1])

        if ('x' not in size) and ('k' not in size) :
            size = default_size   
    except Exception:
        error_msg = f"请输入图片描述喵~ 格式: {prefix} <描述> [大小，默认{default_size}]"
        await (msg.reply(text=error_msg) if is_group else bot.api.post_private_msg(msg.user_id, text=error_msg))
        return
    
    if is_group:
        await msg.reply(text="正在绘制喵……")
    else:
        await bot.api.post_private_msg(msg.user_id,text="正在绘制喵……")
    
    if(msg.message[0]["type"] == "reply"):
        id = msg.message[0]["data"]["id"]
        msg_obj = await bot.api.get_msg(message_id=id)
        if msg_obj.get("data").get("message")[0].get("type") == "image": #处理图片
            image = msg_obj.get("data").get("message")[0].get("data").get("url")
    else:
        image = None


    config_parser = configparser.ConfigParser()
    config_parser.read('config.ini')
    api_key = config_parser.get('gf', 'api_key')

    url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"

    payload = {
        "model": "doubao-seedream-4-0-250828",
        "prompt": prompt,
        "sequential_image_generation": "disabled",
        "response_format": "url",
        "size": size,
        "stream": False,
        "watermark": True
    }
    if(image):
        payload["image"] = image

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    response = post_sync(url, json=payload, headers=headers)

    try:
        url = response.json().get("data")[0].get("url")
    except Exception as e:
        reply = f"绘制失败喵~,{e}\n{response.json()}"

        await send_text(msg, reply, is_group=is_group)
        return
    if is_group:
        await msg.reply(text="绘制完成喵~")
        await bot.api.post_group_file(msg.group_id,image=url)
    else:
        await bot.api.post_private_msg(msg.user_id,text="绘制完成喵~")
        await bot.api.post_private_file(msg.user_id,image=url)

@register_command("/识别人物",help_text = "/识别人物 -> 识别图片中的二次元人物",category = "3")
async def handle_rec(msg, is_group=True):
    if is_group:
        await msg.reply(text="请先发送图片，再回复图片，加上@我，/识别人物")
    else:
        await bot.api.post_private_msg(msg.user_id,text="请先发送图片，再回复图片，加上/识别人物")
    return

@register_command("/at_all",help_text = "/at_all -> 识别@全体成员功能(admin)",category = "2",admin_show=True)

# ========== 工作区命令 ==========
@register_command("/workspace", "/ws", help_text="/workspace 或 /ws -> 查看当前会话工作区文件列表", category="3")
async def handle_workspace(msg, is_group=True):
    """查看当前会话的工作区文件列表"""
    if not WORKSPACE_AVAILABLE:
        reply = "工作区功能不可用喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    from nbot.core.workspace import workspace_manager

    if is_group:
        session_id = get_qq_session_id(group_id=str(msg.group_id), group_user_id=str(msg.user_id))
    else:
        session_id = get_qq_session_id(user_id=str(msg.user_id))

    result = workspace_manager.list_files(session_id)
    files = result.get('files', [])

    if not files:
        reply = "当前工作区没有文件喵~"
    else:
        reply = f"工作区文件列表 ({len(files)} 个文件)：\n"
        for f in files:
            size_kb = f['size'] / 1024
            if size_kb < 1:
                size_str = f"{f['size']} B"
            elif size_kb < 1024:
                size_str = f"{size_kb:.1f} KB"
            else:
                size_str = f"{size_kb/1024:.2f} MB"
            reply += f"  {f['name']} ({size_str})\n"

    await send_text(msg, reply, is_group=is_group)

@register_command("/ws_send", help_text="/ws_send <文件名> -> 发送工作区中的文件", category="3")
async def handle_ws_send(msg, is_group=True):
    """发送工作区中的文件给用户"""
    if not WORKSPACE_AVAILABLE:
        reply = "工作区功能不可用喵~"
        await send_text(msg, reply, is_group=is_group)
        return

    from nbot.core.workspace import workspace_manager

    # 解析文件名
    raw = msg.raw_message
    filename = raw[len("/ws_send"):].strip()
    if not filename:
        reply = "请指定文件名喵~ 用法: /ws_send 文件名"
        await send_text(msg, reply, is_group=is_group)
        return

    if is_group:
        session_id = get_qq_session_id(group_id=str(msg.group_id), group_user_id=str(msg.user_id))
    else:
        session_id = get_qq_session_id(user_id=str(msg.user_id))

    file_path = workspace_manager.get_file_path(session_id, filename)
    if not file_path:
        reply = f"文件不存在喵~: {filename}"
        await send_text(msg, reply, is_group=is_group)
        return

    file_path = normalize_file_path(file_path)
    try:
        await send_file(msg, file_path, is_group=is_group, filename=os.path.basename(file_path))
    except Exception as e:
        reply = f"发送文件失败喵~: {e}"
        await send_text(msg, reply, is_group=is_group)

#将help命令放在最后
@register_command("/help","/h",help_text = "/help 或者 /h -> 查看帮助",category = "8")



@register_command("/translate", "/tr", help_text="/translate <文本> -> 将文本翻译为中文/英文", category="3")
async def handle_translate(msg, is_group=True):
    text = msg.raw_message[len("/translate"):].strip() if msg.raw_message.startswith("/translate") else msg.raw_message[len("/tr"):].strip()
    if not text:
        reply = "请输入要翻译的文本喵~"
        if is_group: await msg.reply(text=reply)
        else: await bot.api.post_private_msg(msg.user_id, text=reply)
        return

    try:
        response = ai_client.chat_completion(
            model=None,
            messages=[
                {"role": "system", "content": "你是一个专业的翻译官。如果输入是中文，请翻译成英文；如果输入是其他语言，请翻译成中文。只返回翻译结果，不要有任何多余的解释。"},
                {"role": "user", "content": text}
            ]
        )
        result = response.choices[0].message.content.strip()
        reply = f"翻译结果如下喵：\n{result}"
        if is_group: await msg.reply(text=reply)
        else: await bot.api.post_private_msg(msg.user_id, text=reply)
    except Exception as e:
        reply = f"翻译出错喵：{e}"
        if is_group: await msg.reply(text=reply)
        else: await bot.api.post_private_msg(msg.user_id, text=reply)

@register_command("/fortune", "/jrrp", help_text="/fortune -> 查看今日运势", category="3")
async def handle_fortune(msg, is_group=True):
    user_id = str(msg.user_id)
    today = datetime.now().strftime("%Y%m%d")
    seed = int(user_id) + int(today)
    random.seed(seed)
    
    luck_score = random.randint(1, 100)
    
    fortunes = [
        "大吉：万事如意，心想事成喵！",
        "中吉：今天会有好事发生喵~",
        "小吉：平平安安就是福喵~",
        "末吉：虽然平淡，但也是充实的一天喵。",
        "凶：出门记得带伞，注意安全喵……",
        "大凶：建议今天宅在家里看漫画喵QAQ"
    ]
    
    if luck_score >= 90: fortune = fortunes[0]
    elif luck_score >= 70: fortune = fortunes[1]
    elif luck_score >= 50: fortune = fortunes[2]
    elif luck_score >= 30: fortune = fortunes[3]
    elif luck_score >= 10: fortune = fortunes[4]
    else: fortune = fortunes[5]
    
    # 恢复随机种子
    random.seed()
    
    reply = f"今日运势：{luck_score}点\n评价：{fortune}"
    if is_group: await msg.reply(text=reply)
    else: await bot.api.post_private_msg(msg.user_id, text=reply)


# 获取机器人QQ号
config_parser = configparser.ConfigParser()
config_parser.read('config.ini', encoding='utf-8')
BOT_UIN = str(config_parser.get('BotConfig', 'bot_uin', fallback="")).strip()











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
