"""
AI 命令工具函数

提供历史记录提取、文本转换等辅助函数。
"""


def _extract_history_text_item(item):
    """从历史记录项中提取文本内容。

    Args:
        item: 历史记录项（dict 或对象）

    Returns:
        提取的文本内容
    """
    if isinstance(item, dict):
        message = item.get("message", {})
        if isinstance(message, dict):
            text = message.get("text", "")
            if text:
                return text
            # 处理消息段数组
            segments = message.get("data", [])
            if isinstance(segments, list):
                texts = []
                for seg in segments:
                    if isinstance(seg, dict) and seg.get("type") == "text":
                        seg_data = seg.get("data", {})
                        if isinstance(seg_data, dict):
                            texts.append(seg_data.get("text", ""))
                return " ".join(texts)
        return str(message)
    return (
        getattr(item, "text", None)
        or getattr(item, "content", None)
        or ""
    ).strip()


def _history_items_to_text(items):
    """将历史记录项列表转换为文本格式。

    Args:
        items: 历史记录项列表

    Returns:
        格式化后的文本
    """
    lines = []
    for item in items:
        user_id = None
        nickname = ""
        if isinstance(item, dict):
            user_id = item.get("user_id")
            sender = item.get("sender")
            if isinstance(sender, dict):
                nickname = sender.get("nickname", "") or ""
        else:
            user_id = getattr(item, "user_id", None)
            sender = getattr(item, "sender", None)
            if sender is not None:
                try:
                    nickname = sender.nickname
                except Exception:
                    if isinstance(sender, dict):
                        nickname = sender.get("nickname", "") or ""
        text = _extract_history_text_item(item)
        uid_str = str(user_id) if user_id is not None else ""
        name_part = nickname or uid_str
        lines.append(f"{name_part}: {text}" if name_part else text)
    return "\n".join(lines)


async def get_group_history_items(group_id, count, bot=None):
    """获取群聊历史消息记录。

    Args:
        group_id: 群ID
        count: 获取消息数量
        bot: 可选的 bot 实例

    Returns:
        消息列表
    """
    if not bot:
        return []

    try:
        history = await bot.api.get_group_msg_history(
            group_id,
            message_seq=0,
            count=count,
            reverse_order=True,
        )
        if isinstance(history, list):
            return history
        if isinstance(history, dict):
            data = history.get("data")
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and isinstance(data.get("messages"), list):
                return data["messages"]
        return []
    except Exception:
        return []


def history_items_to_text(items):
    """将历史记录项列表转换为文本格式（模块级公开函数）。"""
    return _history_items_to_text(items)
