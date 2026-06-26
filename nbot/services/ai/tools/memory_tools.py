"""记忆工具 - 保存和读取记忆."""
from typing import Dict, Any

from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def _execute_save_to_memory(arguments: Dict[str, Any], context: Dict = None) -> Dict[str, Any]:
    """执行保存到记忆工具."""
    try:
        from nbot.core.prompt import prompt_manager

        if not prompt_manager:
            return {"success": False, "error": "记忆管理系统不可用"}

        title = arguments.get('title', '')
        content = arguments.get('content', '')
        summary = arguments.get('summary', '')
        mem_type = arguments.get('mem_type', 'long')
        expire_days = arguments.get('expire_days', 7)

        if not title or not content:
            return {"success": False, "error": "缺少必需的参数: title 和 content"}

        # 从 context 获取目标ID（用户ID或群ID）
        target_id = ''
        if context:
            target_id = context.get('user_id', '') or context.get('group_id', '')

        # 从 context 获取角色名
        character_name = ''
        if context:
            character_name = context.get('character_name', '')

        # 添加记忆（使用新格式：title, summary, content）
        success = prompt_manager.add_memory(
            title, content, target_id, summary, mem_type, expire_days, character_name
        )

        if success:
            mem_type_desc = "长期记忆" if mem_type == "long" else f"短期记忆（{expire_days}天）"
            char_desc = f" [{character_name}]" if character_name else ""
            return {
                "success": True,
                "message": f"已成功保存到{mem_type_desc}{char_desc}",
                "title": title,
                "type": mem_type,
                "character_name": character_name
            }
        else:
            return {"success": False, "error": "保存记忆失败"}

    except Exception as e:
        _log.error(f"Save to memory error: {e}")
        return {"success": False, "error": f"保存记忆时出错: {str(e)}"}


def _execute_read_memory(arguments: Dict[str, Any], context: Dict = None) -> Dict[str, Any]:
    """执行读取记忆工具."""
    try:
        from nbot.core.prompt import prompt_manager

        if not prompt_manager:
            return {"success": False, "error": "记忆管理系统不可用"}

        # 可选参数
        mem_type = arguments.get('mem_type', None)

        # 从 context 获取目标ID（用户ID或群ID）
        target_id = None
        if context:
            target_id = context.get('user_id', '') or context.get('group_id', '')
            if not target_id:
                target_id = None

        # 从 context 获取角色名
        character_name = None
        if context:
            character_name = context.get('character_name', '')
            if not character_name:
                character_name = None

        # 获取记忆（按 target_id 和 character_name 过滤）
        memories = prompt_manager.get_memories(target_id, mem_type, character_name)

        if not memories:
            char_desc = f" [{character_name}]" if character_name else ""
            return {
                "success": True,
                "message": f"没有找到任何记忆{char_desc}",
                "count": 0,
                "memories": [],
                "character_name": character_name
            }

        # 格式化返回（新格式：title, summary, content）
        formatted_memories = []
        for mem in memories:
            mem_type_val = mem.get('type', 'long')
            mem_type_desc = "长期记忆" if mem_type_val == "long" else "短期记忆"
            created_at = mem.get('created_at', '未知时间')
            formatted_memories.append({
                "title": mem.get('title', ''),
                "summary": mem.get('summary', ''),
                "content": mem.get('content', ''),
                "type": mem_type_desc,
                "created_at": created_at,
                "character_name": mem.get('character_name', '')
            })

        char_desc = f" [{character_name}]" if character_name else ""
        return {
            "success": True,
            "message": f"共找到 {len(memories)} 条记忆{char_desc}",
            "count": len(memories),
            "memories": formatted_memories,
            "character_name": character_name
        }

    except Exception as e:
        _log.error(f"Read memory error: {e}")
        return {"success": False, "error": f"读取记忆时出错: {str(e)}"}
