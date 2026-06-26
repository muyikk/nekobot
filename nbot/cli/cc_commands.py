"""
CLI 命令处理器 - CCStyleCLI 的所有 slash 命令处理方法
包含 _handle_command、_show_* 系列方法。
"""

import os
import json
from datetime import datetime
from typing import Dict

from rich.table import Table
from rich.box import ROUNDED
from nbot.cli.completer import escape_rich_tags
from nbot.cli.cc_display import (
    show_memory,
    show_knowledge,
    show_tasks,
    show_workflows,
    show_config,
    show_status,
)

try:
    from nbot.core import build_cli_session_id
except ImportError:
    import uuid

    def build_cli_session_id():
        return f"cli_{uuid.uuid4().hex}"


def handle_command(cli, cmd_line: str) -> bool:
    """处理命令，返回 True 表示命令已处理"""
    parts = cmd_line.strip().split(None, 1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    if not cmd:
        show_help_text = """[bold cyan]NekoBot CLI Help[/bold cyan]

[bold]Commands (/):[/bold]
  /quit, /exit    Exit CLI
  /clear          Clear screen
  /model          Switch model
  /models         List all models
  /tools          List available tools
  /sessions       List recent sessions
  /thinking       Toggle thinking display
  /reset          Reset current session
  /new            Create new session
  /personality    View/switch personality (e.g., /p 2 or /p code)
  /help           Show this help

[bold]Shortcuts:[/bold]
  Ctrl+C          Interrupt AI / Exit
  ↑/↓             Navigate history

[bold]Tips:[/bold]
  Start with / for commands
  Just type to chat with AI
  Press Ctrl+C during AI response to interrupt
"""
        cli.console.print(show_help_text)
        return True

    if cmd in ["quit", "exit", "q"]:
        cli.running = False
        return True
    elif cmd == "clear":
        cli.console.clear()
        from nbot.cli.styles import print_welcome

        print_welcome(cli.console, cli)
        return True
    elif cmd == "model":
        _show_model_switcher(cli)
        return True
    elif cmd == "models":
        _show_models(cli)
        return True
    elif cmd == "tools":
        _show_tools(cli)
        return True
    elif cmd == "sessions":
        _show_sessions(cli)
        return True
    elif cmd == "thinking":
        cli.show_thinking = not cli.show_thinking
        status = "on" if cli.show_thinking else "off"
        cli.console.print(f"[dim]thinking {status}[/dim]")
        return True
    elif cmd == "reset":
        cli.messages = []
        cli.session_id = build_cli_session_id()
        cli.console.print("[dim]session reset[/dim]")
        return True
    elif cmd == "new" or cmd == "n":
        from nbot.cli.cc_utils import save_session

        if cli.session_id and cli.messages:
            save_session(cli)
        cli.messages = []
        cli.session_id = build_cli_session_id()
        current_personality = cli._get_current_personality()
        cli._apply_personality_to_session(current_personality)
        cli.console.clear()
        from nbot.cli.styles import print_welcome

        print_welcome(cli.console, cli)
        personality_name = current_personality.get("name", "Unknown")
        cli.console.print(
            f"[green]✓ Created new session with personality: {personality_name}[/green]\n"
        )
        return True
    elif cmd == "memory" or cmd == "mem":
        _show_memory(cli)
        return True
    elif cmd == "knowledge" or cmd == "kb" or cmd == "know":
        _show_knowledge(cli)
        return True
    elif cmd == "personality" or cmd == "persona" or cmd == "p":
        cli._show_personality(args)
        return True
    elif cmd == "tasks" or cmd == "task":
        _show_tasks(cli)
        return True
    elif cmd == "workflows" or cmd == "flow" or cmd == "wf":
        _show_workflows(cli)
        return True
    elif cmd == "config" or cmd == "cfg":
        _show_config(cli)
        return True
    elif cmd == "status" or cmd == "st":
        _show_status(cli)
        return True
    elif cmd == "model" and args:
        _switch_model_by_name(cli, args.strip())
        return True
    else:
        cli.console.print(f"[red]unknown command: {cmd}[/red]")
        cli.console.print("[dim]type /help for available commands[/dim]")
        return True


def _show_command_help(cli) -> None:
    """显示命令帮助"""
    table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
    table.add_column("Command", style="yellow", width=20)
    table.add_column("Description", style="white")

    commands = [
        ("quit, exit, q", "Exit the CLI"),
        ("clear", "Clear the screen"),
        ("model", "Switch to another model"),
        ("models", "List all available models"),
        ("tools", "List available tools"),
        ("sessions", "List recent sessions"),
        ("thinking", "Toggle thinking display"),
        ("reset", "Reset current session"),
        ("model <name>", "Switch to specific model"),
    ]

    for cmd, desc in commands:
        table.add_row(cmd, desc)

    cli.console.print(table)


def _show_model_switcher(cli) -> None:
    """显示模型切换器"""
    if not cli.available_models:
        cli.console.print("[red]no models available[/red]")
        return

    cli.console.print("\n[bold cyan]Available Models:[/bold cyan]\n")

    for i, model in enumerate(cli.available_models, 1):
        marker = "●" if model.get("id") == cli.current_model_id else "○"
        name = escape_rich_tags(model.get("name", "Unknown"))
        provider = escape_rich_tags(model.get("provider_type", "Unknown"))
        cli.console.print(f"  {marker} {i}. {name} ([dim]{provider}[/dim])")

    cli.console.print()
    choice = cli.console.input("[cyan]Select model number (or name):[/cyan] ").strip()

    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(cli.available_models):
            model = cli.available_models[idx]
            from nbot.cli.cc_utils import set_active_model

            set_active_model(cli, model.get("id"))
            model_name = escape_rich_tags(model.get("name", ""))
            cli.console.print(f"[green]✓ switched to {model_name}[/green]")
    else:
        _switch_model_by_name(cli, choice)


def _switch_model_by_name(cli, name: str) -> None:
    """按名称切换模型"""
    name = name.lower()
    for model in cli.available_models:
        if name in model.get("name", "").lower() or name in model.get("model", "").lower():
            from nbot.cli.cc_utils import set_active_model

            set_active_model(cli, model.get("id"))
            model_name = escape_rich_tags(model.get("name", ""))
            cli.console.print(f"[green]✓ switched to {model_name}[/green]")
            return
    cli.console.print(f"[red]model not found: {name}[/red]")


def _show_models(cli) -> None:
    """显示所有模型"""
    if not cli.available_models:
        cli.console.print("[red]no models available[/red]")
        return

    table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Model", style="white")
    table.add_column("Provider", style="blue")
    table.add_column("Tools", style="green", width=6)
    table.add_column("Active", style="yellow", width=8)

    for i, model in enumerate(cli.available_models, 1):
        name = model.get("name", "Unknown")
        model_name = model.get("model", "Unknown")
        provider = model.get("provider_type", "Unknown")
        tools = "✓" if model.get("supports_tools") else "✗"
        active = "●" if model.get("id") == cli.current_model_id else ""

        table.add_row(str(i), name, model_name, provider, tools, active)

    cli.console.print(table)


def _show_tools(cli) -> None:
    """显示可用工具（包括内置和注册表工具）"""
    from nbot.cli.cc_utils import get_tool_definitions

    all_tools = get_tool_definitions()

    if not all_tools:
        cli.console.print("[dim]no tools available[/dim]")
        return

    cli.console.print(f"\n[bold cyan]Available Tools ({len(all_tools)}):[/bold cyan]\n")

    for tool in all_tools:
        func = tool.get("function", {})
        name = escape_rich_tags(func.get("name", "Unknown"))
        desc = escape_rich_tags(func.get("description", ""))
        cli.console.print(f"  [bold]{name}[/bold] - {desc}")

    cli.console.print()


def _show_sessions(cli) -> None:
    """显示会话列表 - 支持交互式选择"""
    from nbot.cli.cc_utils import load_sessions

    sessions = load_sessions()

    if not sessions:
        cli.console.print("[dim]no sessions[/dim]")
        return

    sessions.sort(key=lambda x: x.get("updated_at", ""), reverse=True)

    total = len(sessions)

    if total == 0:
        cli.console.print("[dim]no sessions[/dim]")
        return

    selected_idx = 0

    def render_table():
        """渲染会话列表表格"""
        table = Table(
            show_header=True,
            header_style="bold cyan",
            box=ROUNDED,
            title=f"Recent Sessions ({total} total)",
            title_style="bold cyan",
        )
        table.add_column("", style="dim", width=3)
        table.add_column("#", style="dim", width=4)
        table.add_column("Name", style="cyan", min_width=20)
        table.add_column("Messages", style="green", width=10)
        table.add_column("Updated", style="dim", width=16)

        for i, session in enumerate(sessions):
            sid = session.get("id", "")[:8]
            name = escape_rich_tags(session.get("name", "Untitled"))
            count = len(session.get("messages", []))
            updated = session.get("updated_at", "")

            if updated:
                try:
                    dt = datetime.fromisoformat(updated)
                    updated = dt.strftime("%m-%d %H:%M")
                except Exception:
                    pass

            is_current = session.get("id") == cli.session_id
            is_selected = i == selected_idx

            if is_selected:
                marker = ">>>"
                name_style = f"[bold yellow]{name}[/bold yellow]"
            elif is_current:
                marker = " ● "
                name_style = f"[green]{name}[/green]"
            else:
                marker = "   "
                name_style = name

            table.add_row(marker, str(i + 1), name_style, str(count), updated)

        return table

    cli.console.print("\n[dim]Enter number to select, q to cancel[/dim]\n")
    cli.console.print(render_table())

    try:
        choice = input("\nSelect session (1-{}): ".format(total)).strip()

        if choice.lower() == "q":
            return
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < total:
                switch_session(cli, sessions[idx])
            else:
                cli.console.print("[red]Invalid selection[/red]")
        else:
            cli.console.print("[red]Invalid input[/red]")

    except (KeyboardInterrupt, EOFError):
        return


def switch_session(cli, session: Dict) -> None:
    """切换到指定会话"""
    from nbot.cli.cc_utils import save_session

    if cli.session_id and cli.messages:
        save_session(cli)

    cli.session_id = session.get("id")
    cli.messages = session.get("messages", [])

    system_prompt = session.get("system_prompt", "")
    has_system_msg = any(msg.get("role") == "system" for msg in cli.messages)
    if system_prompt and not has_system_msg:
        cli.messages.insert(
            0,
            {
                "role": "system",
                "content": system_prompt,
                "timestamp": datetime.now().isoformat(),
            },
        )

    cli.console.clear()
    from nbot.cli.styles import print_welcome

    print_welcome(cli.console, cli)
    cli.console.print(
        f"[green]✓ Switched to session: {escape_rich_tags(session.get('name', 'Untitled'))}[/green]\n"
    )

    if cli.messages:
        display_limit = 10
        total = len(cli.messages)
        if total > display_limit:
            cli.console.print(f"[dim]Showing latest {display_limit} of {total} messages[/dim]\n")
        else:
            cli.console.print(f"[dim]Loaded {total} messages[/dim]\n")


def _show_memory(cli) -> None:
    """显示记忆列表（委托到 cc_display）"""
    show_memory(cli)


def _show_knowledge(cli) -> None:
    """显示知识库（委托到 cc_display）"""
    show_knowledge(cli)


def _show_tasks(cli) -> None:
    """显示定时任务（委托到 cc_display）"""
    show_tasks(cli)


def _show_workflows(cli) -> None:
    """显示工作流（委托到 cc_display）"""
    show_workflows(cli)


def _show_config(cli) -> None:
    """显示系统配置（委托到 cc_display）"""
    show_config(cli)


def _show_status(cli) -> None:
    """显示系统状态（委托到 cc_display）"""
    show_status(cli)
