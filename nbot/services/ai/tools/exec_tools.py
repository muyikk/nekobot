"""命令执行工具."""
import os
import re
import subprocess
import shlex
from typing import Dict, Any

from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# Exec 工具配置
EXEC_WHITELIST = {
    'ls', 'cat', 'echo', 'pwd', 'whoami', 'date', 'cal', 'df', 'du',
    'head', 'tail', 'wc', 'grep', 'find', 'ps', 'top', 'htop',
    'ping', 'journalctl', 'uname', 'hostname',
    'netstat', 'ss', 'lsof', 'ifconfig', 'ip', 'route',
    'which', 'whereis', 'type', 'file', 'stat', 'md5sum', 'sha256sum',
}

EXEC_BLACKLIST_PATTERNS = [
    r'rm\s+-rf\s+/',
    r'mkfs',
    r'dd\s+if=',
    r'>\s*/dev/',
    r':\(\)\s*\{',
    r'fork\s*\(',
    r'while\s*\(true\)',
]


def exec_command(command: str, timeout: int = 30) -> Dict[str, Any]:
    """
    执行命令行命令

    Args:
        command: 要执行的命令
        timeout: 超时时间（秒），默认30秒

    Returns:
        命令执行结果，如果在白名单外则返回确认请求
    """
    try:
        # 安全检查：检测危险模式
        for pattern in EXEC_BLACKLIST_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return {
                    "success": False,
                    "error": "命令包含危险操作模式，已阻止执行",
                    "command": command,
                    "blocked_reason": "dangerous_pattern"
                }

        # 解析命令获取主命令名
        try:
            cmd_parts = shlex.split(command)
            main_cmd = cmd_parts[0] if cmd_parts else ""
        except Exception:
            main_cmd = command.split()[0] if command else ""
            cmd_parts = command.split() if command else []

        if not cmd_parts:
            return {
                "success": False,
                "error": "命令不能为空",
                "command": command,
            }

        # 检查是否在白名单中
        is_whitelisted = main_cmd in EXEC_WHITELIST

        # 不在白名单：返回确认请求
        if not is_whitelisted:
            return {
                "success": False,
                "error": "需要用户确认",
                "command": command,
                "require_confirmation": True,
                "main_command": main_cmd,
                "is_whitelisted": False,
                "message": f"AI 请求执行命令: `{command}`\n\n该命令不在白名单中，需用户确认后执行。"
            }

        # 白名单命令：直接执行
        _log.info(f"Executing command (whitelisted): {command}")

        result = subprocess.run(
            cmd_parts,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.getcwd()
        )

        # 构建返回结果
        output = result.stdout
        error_output = result.stderr

        # 限制输出长度
        max_output_length = 10000
        if len(output) > max_output_length:
            output = output[:max_output_length] + f"\n\n... (输出已截断，共 {len(result.stdout)} 字符)"

        return {
            "success": result.returncode == 0,
            "command": command,
            "returncode": result.returncode,
            "stdout": output,
            "stderr": error_output[:5000] if error_output else "",
            "is_whitelisted": True
        }

    except subprocess.TimeoutExpired:
        _log.error(f"Command timeout: {command}")
        return {
            "success": False,
            "error": f"命令执行超时（{timeout}秒）",
            "command": command
        }
    except Exception as e:
        _log.error(f"Exec command error: {e}")
        return {
            "success": False,
            "error": str(e),
            "command": command
        }
