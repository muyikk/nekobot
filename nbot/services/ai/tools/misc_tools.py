"""杂项工具 - 天气、日期时间、HTTP GET、下载文件、发送消息、思考历史."""
import os
import urllib.parse
from datetime import datetime
from typing import Dict, Any

from nbot.utils.http_client import get_sync
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def get_weather(city: str = "北京") -> Dict[str, Any]:
    """
    查询天气
    使用免费的天气 API
    """
    try:
        # 使用 wttr.in 免费天气服务
        url = f"https://wttr.in/{urllib.parse.quote(city)}?format=j1"

        response = get_sync(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.0'
            },
            timeout=10,
        )
        data = response.json()

        current = data.get('current_condition', [{}])[0]
        weather = {
            "city": city,
            "temperature": current.get('temp_C', 'N/A'),
            "feels_like": current.get('FeelsLikeC', 'N/A'),
            "description": current.get('lang_zh', [{}])[0].get('value', current.get('weatherDesc', [{}])[0].get('value', 'N/A')),
            "humidity": current.get('humidity', 'N/A'),
            "wind": current.get('windspeedKmph', 'N/A'),
            "observation_time": current.get('observation_time', 'N/A')
        }

        return {
            "success": True,
            "weather": weather
        }

    except Exception as e:
        _log.error(f"Get weather error: {e}")
        return {
            "success": False,
            "error": str(e),
            "city": city
        }


def get_date_time() -> Dict[str, Any]:
    """获取当前日期和时间"""
    now = datetime.now()
    return {
        "success": True,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "weekday": now.strftime("%A"),
        "weekday_cn": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][now.weekday()],
        "timestamp": now.isoformat()
    }


def http_get(url: str) -> Dict[str, Any]:
    """HTTP GET 请求"""
    try:
        response = get_sync(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=30,
        )
        content = response.text
        return {
            "success": True,
            "url": url,
            "status": response.status_code,
            "content": content[:5000]  # 限制返回内容长度
        }

    except Exception as e:
        _log.error(f"HTTP GET error: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


def download_file(url: str, filename: str = None, workspace_id: str = None) -> Dict[str, Any]:
    """
    从 URL 下载文件到工作区

    Args:
        url: 文件下载链接
        filename: 保存的文件名（可选，默认从 URL 中提取）
        workspace_id: 工作区 ID（可选，默认使用当前会话的工作区）

    Returns:
        下载结果
    """
    try:
        # 如果没有指定文件名，从 URL 中提取
        if not filename:
            from urllib.parse import urlparse, unquote
            parsed = urlparse(url)
            filename = unquote(os.path.basename(parsed.path))
            if not filename:
                filename = f"downloaded_file_{int(datetime.now().timestamp())}"

        # 确保文件名安全
        filename = os.path.basename(filename)  # 移除路径

        # 下载文件
        _log.info(f"Downloading file from {url} to workspace {workspace_id}")

        response = get_sync(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=60,
        )
        content = response.content
        content_type = response.headers.get('Content-Type', 'application/octet-stream')

        # 确定文件类型
        file_type = 'file'
        if content_type.startswith('image/'):
            file_type = 'image'
        elif content_type.startswith('text/'):
            file_type = 'text'
        elif content_type == 'application/pdf':
            file_type = 'pdf'

        # 保存到工作区
        try:
            from nbot.core.workspace import workspace_manager

            # 如果没有指定 workspace_id，尝试使用默认工作区
            if not workspace_id:
                workspace_id = 'default'

            # 创建工作区目录（如果不存在）
            workspace_path = workspace_manager.get_or_create(workspace_id)
            file_path = os.path.join(workspace_path, filename)

            # 保存文件
            with open(file_path, 'wb') as f:
                f.write(content)

            _log.info(f"File saved to {file_path}")

            return {
                "success": True,
                "url": url,
                "filename": filename,
                "file_path": file_path,
                "file_type": file_type,
                "content_type": content_type,
                "size": len(content),
                "workspace_id": workspace_id,
                "message": f"文件已成功下载到工作区: {filename}"
            }

        except Exception as e:
            _log.error(f"Failed to save file to workspace: {e}")
            return {
                "success": False,
                "error": f"保存文件到工作区失败: {str(e)}",
                "url": url,
                "filename": filename
            }

    except Exception as e:
        _log.error(f"Download file error: {e}")
        return {
            "success": False,
            "error": str(e),
            "url": url
        }


def send_message(content: str, message_type: str = "info", session_id: str = None) -> Dict[str, Any]:
    """
    向用户发送消息（不中断思考流程）

    Args:
        content: 消息内容
        message_type: 消息类型，可选 info/progress/warning/success
        session_id: 会话 ID（从 context 自动获取）

    Returns:
        发送结果
    """
    try:
        _log.info(f"[SendMessage] AI 发送{message_type}消息: {content[:50]}...")

        # 返回特殊标记，让调用者知道需要发送消息
        return {
            "success": True,
            "action": "send_message",
            "content": content,
            "message_type": message_type,
            "session_id": session_id,
            "message": "消息已发送给用户"
        }

    except Exception as e:
        _log.error(f"[SendMessage] 发送消息失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def get_session_thinking_history(limit: int = 10, session_id: str = None) -> Dict[str, Any]:
    """
    查询当前会话的历史思考记录（thinking_cards）

    Args:
        limit: 返回的历史记录数量限制
        session_id: 会话 ID（从 context 自动获取）

    Returns:
        历史思考记录列表
    """
    try:
        import json as _json

        if not session_id:
            return {
                "success": False,
                "error": "未提供 session_id"
            }

        _log.info(f"[ThinkingHistory] 查询会话 {session_id[:8]}... 的历史思考记录，limit={limit}")

        # 尝试从 WebServer 实例获取会话数据
        sessions = None
        try:
            from nbot.web.server import WebServer
            web_server = WebServer.get_instance()
            if web_server:
                sessions = web_server.sessions
        except Exception:
            pass

        # 如果没有实例化的 WebServer，从文件读取
        if not sessions:
            sessions_file = 'data/web/sessions.json'
            if os.path.exists(sessions_file):
                with open(sessions_file, 'r', encoding='utf-8') as f:
                    sessions_data = _json.load(f)
                    sessions = sessions_data

        if not sessions:
            return {
                "success": False,
                "error": "无法获取会话数据"
            }

        # 获取会话
        session = sessions.get(session_id)
        if not session:
            # 尝试在 sessions_data 中查找
            if isinstance(sessions, dict):
                for sid, sess in sessions.items():
                    if sid == session_id or (isinstance(sess, dict) and sess.get('id') == session_id):
                        session = sess
                        break

        if not session:
            return {
                "success": False,
                "error": f"未找到会话: {session_id}"
            }

        # 获取消息
        messages = session.get('messages', [])
        if not messages:
            return {
                "success": True,
                "history": [],
                "count": 0,
                "message": "该会话没有消息历史"
            }

        # 收集 thinking_cards
        thinking_records = []
        for msg in messages:
            thinking_cards = msg.get('thinking_cards', [])
            if thinking_cards:
                for card in thinking_cards:
                    record = {
                        "timestamp": card.get('timestamp', ''),
                        "role": card.get('role', ''),
                        "steps": []
                    }

                    # 处理每个步骤
                    for step in card.get('steps', []):
                        step_info = {
                            "type": step.get('type', ''),
                            "name": step.get('name', ''),
                            "status": step.get('status', ''),
                        }

                        # 添加详细信息（用于工具调用）
                        if step.get('detail'):
                            step_info['detail'] = str(step['detail'])[:200]  # 限制长度

                        # 添加完整参数
                        if step.get('arguments'):
                            step_info['arguments'] = step['arguments']

                        # 添加完整结果
                        if step.get('full_result'):
                            full_result = step['full_result']
                            if isinstance(full_result, dict):
                                # 提取关键信息
                                if full_result.get('success') is not None:
                                    step_info['result'] = full_result.get('success')
                                if full_result.get('content'):
                                    content = full_result['content']
                                    if isinstance(content, str):
                                        step_info['content_preview'] = content[:300]
                                    elif isinstance(content, list):
                                        step_info['items_count'] = len(content)
                                if full_result.get('files'):
                                    step_info['files'] = full_result['files']
                                if full_result.get('query'):
                                    step_info['query'] = full_result.get('query')
                                if full_result.get('results'):
                                    results = full_result['results']
                                    if isinstance(results, list) and len(results) > 0:
                                        step_info['results_count'] = len(results)
                                        step_info['results_preview'] = str(results)[:500]
                            else:
                                step_info['full_result'] = str(full_result)[:500]

                        record['steps'].append(step_info)

                    if record['steps']:
                        thinking_records.append(record)

        # 限制返回数量（按时间倒序）
        thinking_records = thinking_records[-limit:] if limit > 0 else thinking_records

        _log.info(f"[ThinkingHistory] 返回 {len(thinking_records)} 条历史记录")

        return {
            "success": True,
            "history": thinking_records,
            "count": len(thinking_records),
            "message": f"成功获取 {len(thinking_records)} 条历史思考记录"
        }

    except Exception as e:
        _log.error(f"[ThinkingHistory] 查询历史失败: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }
