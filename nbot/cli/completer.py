"""
CLI 命令补全器 - 基于 prompt_toolkit 的命令和文件路径自动补全
"""

import os
import logging

# 尝试导入prompt_toolkit用于实时候选
try:
    from prompt_toolkit.completion import Completer, Completion

    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False
    Completer = object  # 占位基类
    Completion = None


def escape_rich_tags(text: str) -> str:
    """转义Rich标签，防止解析错误
    将 [ 替换为 &#91;，] 替换为 &#93; (HTML实体编码)
    这样Rich不会解析它们，但显示时看起来还是方括号
    """
    if not isinstance(text, str):
        text = str(text)
    # 使用HTML实体编码，Rich不会解析，但显示效果相同
    return text.replace("[", "&#91;").replace("]", "&#93;")


def _silence_cli_loggers():
    """在 CLI 模式下屏蔽所有常见日志输出。"""
    logger_names = [
        "",
        "nbot",
        "werkzeug",
        "urllib3",
        "requests",
        "socketio",
        "engineio",
        "apscheduler",
    ]
    for name in logger_names:
        logger = logging.getLogger(name)
        logger.setLevel(logging.CRITICAL + 1)
        logger.propagate = False
        for handler in logger.handlers:
            handler.setLevel(logging.CRITICAL + 1)


class CommandCompleter(Completer):
    """命令补全器 - 用于prompt_toolkit"""

    def __init__(self, commands, workspace_root=None):
        self.commands = commands
        self.workspace_root = workspace_root or os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )

    def get_completions(self, document, complete_event):
        text = document.text

        if text.startswith("@"):
            for completion in self._get_file_completions(text):
                yield completion
        elif text.startswith("/"):
            cmd_part = text[1:].lower()

            for cmd, info in self.commands.items():
                if cmd.startswith(cmd_part):
                    display = f"/{cmd} - {info['desc']}"
                    yield Completion(cmd, start_position=-len(cmd_part), display=display)
                for alias in info.get("aliases", []):
                    if alias.startswith(cmd_part):
                        display = f"/{alias} - {info['desc']} (alias for /{cmd})"
                        yield Completion(
                            cmd, start_position=-len(cmd_part), display=display
                        )

    def _get_file_completions(self, text):
        """获取文件路径补全"""
        import glob

        file_part = text[1:]

        if "/" in file_part or "\\" in file_part:
            search_dir = os.path.dirname(file_part) if os.path.dirname(file_part) else "."
            prefix = os.path.basename(file_part)
            full_dir = (
                os.path.join(self.workspace_root, search_dir)
                if not os.path.isabs(search_dir)
                else search_dir
            )
        else:
            search_dir = "."
            prefix = file_part
            full_dir = self.workspace_root

        if not os.path.isdir(full_dir):
            return

        try:
            if prefix:
                pattern = os.path.join(full_dir, prefix + "*")
            else:
                pattern = os.path.join(full_dir, "*")

            for path in glob.glob(pattern):
                if os.path.isfile(path):
                    name = os.path.basename(path)
                    rel_path = os.path.relpath(path, self.workspace_root)
                    display = f"📄 {rel_path}"
                    yield Completion(name, start_position=-len(prefix), display=display)
        except Exception:
            pass
