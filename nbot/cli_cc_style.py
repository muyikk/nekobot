"""
NekoBot CLI - Claude Code 风格 - 向后兼容 shim
原始内容已拆分到 nbot/cli/ 目录下的多个子模块：
- nbot/cli/completer.py  - 命令补全器
- nbot/cli/styles.py     - 显示样式与渲染
- nbot/cli/markdown.py   - Markdown 渲染器
- nbot/cli/cc_utils.py   - 工具执行与实用函数
- nbot/cli/cc_commands.py - 命令处理器
- nbot/cli/cc_personality.py - 人格管理
- nbot/cli/cc_app.py     - CCStyleCLI 核心类
"""

from nbot.cli.cc_app import CCStyleCLI, main

__all__ = ["CCStyleCLI", "main"]

if __name__ == "__main__":
    main()
