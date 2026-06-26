"""
NekoBot CLI - 简化版命令行界面 - 向后兼容 shim
原始内容已拆分到 nbot/cli/simple_app.py 和 nbot/cli/simple_handlers.py。
"""

from nbot.cli.simple_app import SimpleCLI


def main():
    """CLI入口"""
    cli = SimpleCLI()
    cli.run()


if __name__ == "__main__":
    main()
