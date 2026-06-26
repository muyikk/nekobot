"""工具执行器 - 工具调度逻辑 execute_tool."""
import os
import json
from typing import Dict, Any, List

from nbot.utils.logger import get_logger
from .definitions import TOOL_DEFINITIONS, WORKSPACE_TOOL_DEFINITIONS
from .builtins import ToolExecutor
from .pending_exec import store_pending_execution
from .memory_tools import _execute_save_to_memory, _execute_read_memory
from .workspace_tools import _execute_workspace_tool

_log = get_logger(__name__)

# Web 配置数据目录
WEB_DATA_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'data', 'web')

# 动态执行器（延迟导入避免循环依赖）
_dynamic_executor = None


def get_dynamic_executor():
    """获取动态执行器实例（延迟加载）."""
    global _dynamic_executor
    if _dynamic_executor is None:
        try:
            from nbot.services.dynamic_executor import get_executor
            _dynamic_executor = get_executor()
        except Exception as e:
            _log.error(f"Failed to load dynamic executor: {e}")
            _dynamic_executor = None
    return _dynamic_executor


def load_tools_config() -> List[Dict]:
    """从 web 配置文件加载 tools 配置."""
    tools_file = os.path.join(WEB_DATA_DIR, 'tools.json')
    if os.path.exists(tools_file):
        try:
            with open(tools_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            _log.error(f"Failed to load tools config: {e}")
    return []


def get_enabled_tools() -> List[Dict]:
    """获取启用的工具列表.

    自动从注册表获取所有已注册的工具.
    """
    # 从注册表获取所有装饰器注册的工具
    from nbot.services.tool_registry import get_all_tool_definitions as get_registry_tools
    registered_tools = get_registry_tools()

    web_config = load_tools_config()
    enabled_names = set()
    if web_config:
        enabled_names = {t['name'] for t in web_config if t.get('enabled', True)}

    # 从配置启用工具
    if enabled_names:
        tools = [t for t in TOOL_DEFINITIONS if t['function']['name'] in enabled_names]
    else:
        tools = list(TOOL_DEFINITIONS)

    # 合并所有工具类别
    all_tool_categories = [
        WORKSPACE_TOOL_DEFINITIONS,
    ]

    for category in all_tool_categories:
        tools.extend(category)

    # 添加 Todo 工具
    from nbot.services.todo_tools import TODO_TOOL_DEFINITIONS
    tools.extend(TODO_TOOL_DEFINITIONS)

    # 添加注册表中的工具
    tools.extend(registered_tools)

    return tools


def get_all_tool_definitions(include_workspace: bool = True) -> List[Dict]:
    """获取所有工具定义（包括工作区工具和注册的工具）."""
    tools = list(TOOL_DEFINITIONS)

    # 添加 Todo 工具定义
    from nbot.services.todo_tools import TODO_TOOL_DEFINITIONS
    tools.extend(TODO_TOOL_DEFINITIONS)

    # 导入 Skills 工具以触发装饰器注册
    try:
        from nbot.services import skills_tools
        # 从注册表获取所有装饰器注册的工具
        from nbot.services.tool_registry import get_all_tool_definitions as get_registered_tools
        registered_tools = get_registered_tools()
        _log.info(f"[Tools] 从注册表加载了 {len(registered_tools)} 个工具: {[t.get('function', {}).get('name') for t in registered_tools]}")
        tools.extend(registered_tools)
    except ImportError as e:
        _log.warning(f"[Tools] 注册表工具加载失败: {e}")
    except Exception as e:
        _log.warning(f"[Tools] 注册表工具处理失败: {e}")

    if include_workspace:
        tools.extend(WORKSPACE_TOOL_DEFINITIONS)
    return tools


def execute_tool(tool_name: str, arguments: Dict[str, Any], context: Dict = None) -> Dict[str, Any]:
    """
    执行指定的工具（优先使用注册表，然后是 Web 配置）.

    Args:
        tool_name: 工具名称
        arguments: 工具参数
        context: 可选的上下文信息，包含 session_id 等

    Returns:
        工具执行结果
    """
    # 0. 工作区工具 - 需要 context 中的 session_id
    if tool_name.startswith("workspace_"):
        return _execute_workspace_tool(tool_name, arguments, context)

    # 1. 优先从注册表获取（使用装饰器注册的工具）
    from nbot.services.tool_registry import get_registry
    registry = get_registry()
    executor = registry.get_executor(tool_name)
    if executor:
        try:
            return executor(arguments, context)
        except Exception as e:
            _log.error(f"Tool execution error: {tool_name} - {e}")
            return {"success": False, "error": str(e)}

    # 2. 处理 Todo 工具（优先于 Web 配置检查）
    if tool_name.startswith("todo_"):
        from nbot.services.todo_tools import execute_todo_tool
        return execute_todo_tool(tool_name, arguments, context)

    # 3. 处理记忆工具（需要 context 中的用户信息）
    if tool_name == "save_to_memory":
        return _execute_save_to_memory(arguments, context)

    if tool_name == "read_memory":
        return _execute_read_memory(arguments, context)

    # 3. 从 Web 配置查找
    web_config = load_tools_config()
    tool_config = None

    for config in web_config:
        if config.get('name') == tool_name:
            tool_config = config
            break

    # 4. 如果找到 Web 配置且有 implementation，使用动态执行
    result = None
    if tool_config and tool_config.get('implementation'):
        _log.info(f"Executing dynamic tool: {tool_name}")
        dyn_executor = get_dynamic_executor()
        if dyn_executor:
            result = dyn_executor.execute_tool(tool_config, arguments, context)
        else:
            result = {
                "success": False,
                "error": "Dynamic executor not available"
            }
    else:
        # 5. 否则使用内置 Tool
        _log.info(f"Executing built-in tool: {tool_name}")
        executor = ToolExecutor()

        tool_map = {
            "search_news": executor.search_news,
            "get_weather": executor.get_weather,
            "search_web": executor.search_web,
            "get_date_time": executor.get_date_time,
            "http_get": executor.http_get,
            "exec_command": executor.exec_command,
            "get_session_thinking_history": executor.get_session_thinking_history,
        }

        if tool_name not in tool_map:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}"
            }

        try:
            tool_func = tool_map[tool_name]
            result = tool_func(**arguments)
        except Exception as e:
            _log.error(f"Tool execution error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    # 如果 exec_command 返回需要确认，存储待执行命令并注入 request_id
    if result and result.get('require_confirmation') and context and context.get('session_id'):
        request_id = store_pending_execution(
            context['session_id'],
            result.get('command', ''),
            arguments.get('timeout', 30)
        )
        result['request_id'] = request_id
    return result
