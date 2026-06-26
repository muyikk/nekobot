"""Web 服务器 QQ 同步与飞书长连接相关方法。

提供 QQ 消息同步到 Web 会话、自动启动飞书长连接频道等能力，
以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


class QQSyncMixin:
    """QQ 同步与飞书长连接相关方法 mixin。"""

    def sync_qq_messages(
        self, user_id: str, group_id: str = None, create_if_not_exists: bool = True
    ):
        """同步 QQ 消息到 Web 会话。

        Args:
            user_id: QQ 用户 ID。
            group_id: QQ 群 ID（可选）。
            create_if_not_exists: 会话不存在时是否创建。

        Returns:
            会话 ID 或 None。
        """
        from nbot.services.chat_service import user_messages, group_messages

        target_id = group_id or user_id
        if not target_id:
            return None

        session_type = "qq_group" if group_id else "qq_private"

        existing_session_id = self.session_store.find_session_id(
            lambda sid, session: session.get("qq_id") == target_id
            and session.get("type") == session_type
        )

        if existing_session_id:
            session_id = existing_session_id
        elif create_if_not_exists:
            session_id = str(uuid.uuid4())
            session = {
                "id": session_id,
                "name": f"私聊 {target_id}",
                "type": session_type,
                "qq_id": target_id,
                "created_at": datetime.now().isoformat(),
                "messages": [],
                "system_prompt": "",
            }
            self.session_store.set_session(session_id, session)
        else:
            return None

        msg_store = group_messages if group_id else user_messages
        if target_id in msg_store:
            messages = msg_store[target_id]
            for msg in messages:
                if msg.get("role") == "system":
                    continue

                web_msg = {
                    "id": str(uuid.uuid4()),
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp", datetime.now().isoformat()),
                    "sender": target_id,
                    "source": "qq",
                }
                self.session_store.append_message(session_id, web_msg)

        return session_id

    def _auto_start_feishu_ws_channels(self):
        """自动启动所有已启用的飞书长连接频道。"""
        try:
            from nbot.web.routes.channels import auto_start_feishu_ws_clients
            from nbot.services.feishu_ws_service import feishu_ws_service

            feishu_ws_service.set_server(self)
            auto_start_feishu_ws_clients(self)
        except Exception as e:
            _log.error(f"自动启动飞书长连接频道失败: {e}")
