"""Email helpers for sending comics via SMTP."""

from __future__ import annotations

import asyncio
import os
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from nbot.commands.state import smtp_config, user_email


def _send_comic_email_sync(
    to_addr: str,
    subject: str,
    body: str,
    file_path: str,
    conf: dict,
) -> None:
    """Synchronously send a comic PDF via email.

    Args:
        to_addr: Recipient email address.
        subject: Email subject.
        body: Plain-text body.
        file_path: Path to the PDF attachment.
        conf: SMTP configuration dict with host/port/user/password/use_tls/from_addr.

    Raises:
        ValueError: If SMTP config is missing or incomplete.
    """
    if not conf:
        raise ValueError("smtp未配置")
    host = conf.get("host")
    port = int(conf.get("port", 587))
    user = conf.get("user")
    password = conf.get("password")
    use_tls = bool(conf.get("use_tls", True))
    from_addr = conf.get("from_addr") or user
    if not host or not from_addr:
        raise ValueError("smtp配置不完整")

    msg = MIMEMultipart()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with open(file_path, "rb") as f:
        part = MIMEBase("application", "pdf")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{os.path.basename(file_path)}"',
    )
    msg.attach(part)

    server = smtplib.SMTP(host, port, timeout=30)
    if use_tls:
        server.starttls()
    if user and password:
        server.login(user, password)
    server.sendmail(from_addr, [to_addr], msg.as_string())
    server.quit()


async def send_comic_email(user_id: str, comic_id: str, file_path: str) -> bool:
    """Send a comic PDF to the user's configured email address.

    Args:
        user_id: The user's QQ ID.
        comic_id: The comic identifier.
        file_path: Path to the PDF file.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    uid = str(user_id)
    to_addr = user_email.get(uid)
    if not to_addr:
        return False
    conf = smtp_config.get(uid) or smtp_config.get("global")
    if not conf:
        return False
    subject = f"漫画 {comic_id}"
    body = f"漫画 {comic_id} 已发送喵~"
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: _send_comic_email_sync(to_addr, subject, body, file_path, conf),
    )
    return True
