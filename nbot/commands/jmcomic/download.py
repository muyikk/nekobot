"""JM comic download command."""
import asyncio
import hashlib
import html
import os
import re
import time

import jmcomic
from jmcomic import JmOption, JmcomicException
from jmcomic.jmcomic import JmAlbumDetail, MissingAlbumPhotoException

from nbot.commands import bot, switch
from nbot.commands.registry import register_command
from nbot.commands.shared.data_persistence import (
    load_address,
    normalize_file_path,
)
from nbot.commands.shared.email import send_comic_email
from nbot.utils.message_sender import send_text
from nbot.utils.logger import get_logger
from nbot.commands.state import black_list_comic, comic_cache

_log = get_logger(__name__)


@register_command("/jm", help_text="/jm <漫画ID> -> 下载漫画", category="1")
async def handle_jmcomic(msg, is_group=True):
    match = re.match(r'^/jm\s+(\d+)$', msg.raw_message)
    if match:
        comic_id = match.group(1)
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

        pdf_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            if is_group:
                if switch.get_switch_state('jm_send', group_id=str(msg.group_id)):
                    if switch.get_switch_state('jm_send_user', group_id=str(msg.group_id)):
                        await bot.api.post_private_msg(msg.user_id, text=f"该漫画已存在喵~,文件大小：{file_size:.2f} MB，正在发送喵~")
                        await bot.api.upload_private_file(msg.user_id, pdf_path, f"{comic_id}.pdf")
                    else:
                        await msg.reply(text=f"该漫画已存在喵~,文件大小：{file_size:.2f} MB，正在发送到群组喵~")
                        await bot.api.post_group_file(msg.group_id, file=pdf_path)
                else:
                    await msg.reply(text="群组发送漫画已关闭喵~")
            else:
                if switch.get_switch_state('jm_send', user_id=str(msg.user_id)):
                    await bot.api.post_private_msg(msg.user_id, text=f"该漫画已存在喵~,文件大小：{file_size:.2f} MB，正在发送喵~")
                    await bot.api.upload_private_file(msg.user_id, pdf_path, f"{comic_id}.pdf")
                else:
                    await msg.reply(text="该漫画已下载，但用户私信发送漫画已关闭喵~")
            return

        if int(comic_id) <= len(comic_cache) and len(comic_cache) > 0:
            try:
                comic_id = comic_cache[int(comic_id) - 1]
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

        reply_text = f"已开始下载漫画ID：{comic_id}，下载完成后会自动通知喵~"
        await send_text(msg, reply_text, is_group=is_group)

        try:
            await asyncio.gather(download_and_send_comic(comic_id, msg, is_group))
        except Exception as e:
            error_msg = f"下载漫画失败喵~: {str(e)}"
            await send_text(msg, error_msg, is_group=is_group)

    else:
        error_msg = "格式错误了喵~，请输入 /jm 后跟漫画ID"
        if not is_group:
            await bot.api.post_private_msg(msg.user_id, text=error_msg)


async def download_and_send_comic(comic_id, msg, is_group):
    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, lambda:
            jmcomic.download_album(
                comic_id,
                jmcomic.create_option_by_file('./resources/config/option.yml')
            )
        )

        file_path = normalize_file_path(os.path.join(load_address(), f"pdf/{comic_id}.pdf"))

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PDF文件未生成：{file_path}")
        encrypt_needed = switch.get_switch_state('pdf_password', group_id=str(msg.group_id) if is_group else None, user_id=str(msg.user_id) if not is_group else None)
        if switch.get_switch_state('jm_send_email', user_id=str(msg.user_id)):
            encrypt_needed = True
        if encrypt_needed:
            try:
                import pikepdf
                with pikepdf.open(file_path, allow_overwriting_input=True) as pdf:
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
        if not switch.get_switch_state('jm_send', group_id=str(msg.group_id) if is_group else None, user_id=str(msg.user_id) if not is_group else None):
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

        file_size = os.path.getsize(file_path) / (1024 * 1024)
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
            file_size = os.path.getsize(file_path) / (1024 * 1024)
            file_text = f"文件大小：{file_size:.2f} MB，正在上传喵~"
            if is_group:
                await msg.reply(text="部分下载失败了喵~，正在发送剩余的文件喵~\n" + file_text)
                await bot.api.post_group_file(msg.group_id, file=file_path)
            else:
                await bot.api.post_private_msg(msg.user_id, text="部分下载失败了喵~，正在发送剩余的文件喵~\n" + file_text)
                await bot.api.upload_private_file(msg.user_id, file_path, f"{comic_id}.pdf")
