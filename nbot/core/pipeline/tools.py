"""
工具确认处理

handle_tool_confirmation 检测用户输入是否为确认/拒绝待处理命令，
并在各频道入口处统一调用。
"""

_CONFIRM_KEYWORDS = {"确认", "同意", "确认执行", "是", "yes", "y", "ok", "执行"}
_REJECT_KEYWORDS = {"取消", "拒绝", "否", "不执行", "no", "n", "cancel"}


def handle_tool_confirmation(
    content: str,
    session_id: str,
    *,
    log_prefix: str = "",
) -> str:
    """检测并处理工具确认/拒绝。

    在各频道入口处调用，检测用户输入是否为确认/拒绝关键词。
    如果是确认，则执行待处理命令并返回执行结果文本。
    如果是拒绝，则拒绝待处理命令并返回拒绝文本。
    如果不是确认/拒绝，返回原始 content。

    Args:
        content: 用户输入内容
        session_id: 会话ID
        log_prefix: 日志前缀

    Returns:
        替换后的消息内容（原始内容 或 确认/拒绝结果文本）
    """
    stripped = (content or "").strip().lower()
    is_confirm = stripped in _CONFIRM_KEYWORDS or (
        len(stripped) <= 4 and any(kw in stripped for kw in _CONFIRM_KEYWORDS)
    )
    is_reject = stripped in _REJECT_KEYWORDS or (
        len(stripped) <= 4 and any(kw in stripped for kw in _REJECT_KEYWORDS)
    )

    if not (is_confirm or is_reject):
        return content

    if is_confirm and is_reject:
        return content  # 歧义，不处理

    try:
        from nbot.services.tools import (
            get_pending_by_session,
            execute_pending_command,
            reject_pending_command,
        )

        if not get_pending_by_session:
            return content

        request_id = get_pending_by_session(session_id)
        if not request_id:
            return content

        if is_confirm:
            prefix = f"[{log_prefix}]" if log_prefix else ""
            print(f"{prefix} 用户确认执行待处理命令: session={session_id}")
            exec_result = execute_pending_command(request_id)
            if exec_result.get("executed"):
                cmd = exec_result.get("command", "")
                stdout = exec_result.get("stdout", "")
                stderr = exec_result.get("stderr", "")
                result_msg = f"[系统] 用户已确认执行命令 `{cmd}`。\n\n执行结果:\n{stdout}"
                if stderr:
                    result_msg += f"\n\n错误输出:\n{stderr}"
                return result_msg
            else:
                return f"[系统] 执行命令失败: {exec_result.get('error', '未知错误')}"
        else:
            prefix = f"[{log_prefix}]" if log_prefix else ""
            print(f"{prefix} 用户拒绝执行待处理命令: session={session_id}")
            reject_result = reject_pending_command(request_id)
            cmd = reject_result.get("command", "")
            return f"[系统] 用户已拒绝执行命令 `{cmd}`。"
    except Exception:
        pass

    return content
