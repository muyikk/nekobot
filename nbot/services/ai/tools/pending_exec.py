"""待执行命令管理 - 存储、确认、执行、拒绝待执行命令."""
import os
import time
import uuid
import subprocess
import shlex
from typing import Dict, Any, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# 待执行命令存储（用于确认机制）
# request_id -> {command, timeout, session_id, timestamp}
_pending_executions: Dict[str, Dict] = {}
# session_id -> request_id（用于 QQ 通道通过 session 查找）
_session_pending: Dict[str, str] = {}

# 确认关键词（QQ 通道用于检测用户是否同意执行）
_CONFIRM_KEYWORDS = {'确认', '同意', '确认执行', '是', 'yes', 'y', 'ok', '执行'}
_REJECT_KEYWORDS = {'取消', '拒绝', '否', '不执行', 'no', 'n', 'cancel'}


def store_pending_execution(session_id: str, command: str, timeout: int = 30) -> str:
    """存储待确认的命令，返回 request_id."""
    request_id = uuid.uuid4().hex
    _pending_executions[request_id] = {
        'command': command,
        'timeout': timeout,
        'session_id': session_id,
        'timestamp': time.time(),
    }
    _session_pending[session_id] = request_id
    _log.info(f"[PendingExec] 存储待确认命令: request_id={request_id[:8]}, session={session_id}, cmd={command[:80]}")
    return request_id


def get_pending_by_session(session_id: str) -> Optional[str]:
    """通过 session_id 查找待确认命令的 request_id."""
    return _session_pending.get(session_id)


def get_pending_info(request_id: str) -> Optional[Dict]:
    """查看待执行命令信息."""
    return _pending_executions.get(request_id)


def execute_pending_command(request_id: str) -> Dict[str, Any]:
    """执行待确认的命令，返回执行结果."""
    pending = _pending_executions.pop(request_id, None)
    if not pending:
        return {
            "success": False,
            "error": "未找到待执行的命令，可能已过期或已处理",
            "request_id": request_id
        }

    # 清理 session 映射
    session_id = pending.get('session_id', '')
    if _session_pending.get(session_id) == request_id:
        del _session_pending[session_id]

    command = pending['command']
    timeout = pending.get('timeout', 30)

    _log.info(f"[PendingExec] 用户确认，执行命令: {command}")

    try:
        try:
            cmd_parts = shlex.split(command)
        except Exception:
            cmd_parts = command.split()

        result = subprocess.run(
            cmd_parts,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )

        output = result.stdout
        max_output_length = 10000
        if len(output) > max_output_length:
            output = output[:max_output_length] + f"\n\n... (输出已截断，共 {len(result.stdout)} 字符)"

        return {
            "success": result.returncode == 0,
            "command": command,
            "returncode": result.returncode,
            "stdout": output,
            "stderr": result.stderr[:5000] if result.stderr else "",
            "executed": True,
        }
    except subprocess.TimeoutExpired:
        _log.error(f"[PendingExec] 命令超时: {command}")
        return {
            "success": False,
            "error": f"命令执行超时（{timeout}秒）",
            "command": command,
        }
    except Exception as e:
        _log.error(f"[PendingExec] 执行出错: {e}")
        return {
            "success": False,
            "error": str(e),
            "command": command,
        }


def reject_pending_command(request_id: str) -> Dict[str, Any]:
    """拒绝待确认的命令，清理存储."""
    pending = _pending_executions.pop(request_id, None)
    session_id = pending.get('session_id', '') if pending else ''
    if session_id and _session_pending.get(session_id) == request_id:
        del _session_pending[session_id]

    if pending:
        _log.info(f"[PendingExec] 用户拒绝命令: request_id={request_id[:8]}, cmd={pending.get('command', '')[:80]}")
        return {
            "success": False,
            "rejected": True,
            "command": pending.get('command', ''),
            "message": "用户已拒绝执行该命令"
        }
    else:
        return {
            "success": False,
            "rejected": True,
            "error": "未找到待执行的命令",
            "request_id": request_id
        }
