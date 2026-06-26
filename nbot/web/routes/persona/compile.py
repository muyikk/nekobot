"""角色卡编译模块——将角色卡JSON编译为系统提示词。"""
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def compile_personality_prompt(personality_data, session_context=None, user_name=None):
    """将角色卡JSON编译成系统提示词，支持 {{user}} 模板变量

    委托给 nbot.character.compiler 实现，保持旧接口签名不变。
    """
    from nbot.character.compiler import compile_personality_prompt as _compile
    return _compile(personality_data, session_context=session_context, user_name=user_name)
