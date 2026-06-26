"""
CLI 系统信息显示 - CCStyleCLI 的系统状态、配置、任务等显示方法
"""

import os
import json

from rich.table import Table
from rich.box import ROUNDED
from nbot.cli.completer import escape_rich_tags


def show_memory(cli) -> None:
    """显示记忆列表"""
    memory_file = os.path.join("data", "web", "memories.json")
    if not os.path.exists(memory_file):
        cli.console.print("[dim]no memories[/dim]")
        return

    try:
        with open(memory_file, "r", encoding="utf-8") as f:
            memories = json.load(f)

        if not memories:
            cli.console.print("[dim]no memories[/dim]")
            return

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Title", style="cyan")
        table.add_column("Type", style="blue", width=8)
        table.add_column("Target", style="green", width=10)

        for mem in memories[:20]:
            mid = mem.get("id", "")[:6]
            title = escape_rich_tags(mem.get("title", mem.get("key", "Untitled")))
            mem_type = escape_rich_tags(mem.get("type", "long"))
            target = escape_rich_tags(mem.get("target_id", "global")[:8])
            table.add_row(mid, title, mem_type, target)

        cli.console.print(table)
        cli.console.print(f"\n[dim]Total: {len(memories)} memories[/dim]")
    except Exception as e:
        cli.console.print(f"[red]error loading memories: {e}[/red]")


def show_knowledge(cli) -> None:
    """显示知识库"""
    kb_file = os.path.join("data", "knowledge", "knowledge_base.json")
    if not os.path.exists(kb_file):
        cli.console.print("[dim]no knowledge base[/dim]")
        return

    try:
        with open(kb_file, "r", encoding="utf-8") as f:
            kb_data = json.load(f)

        docs = kb_data.get("documents", [])
        if not docs:
            cli.console.print("[dim]no documents in knowledge base[/dim]")
            return

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Title", style="cyan")
        table.add_column("Source", style="blue")
        table.add_column("Size", style="green", width=8)

        for doc in docs[:20]:
            did = doc.get("id", "")[:6]
            title = escape_rich_tags(doc.get("title", "Untitled"))
            source = escape_rich_tags(doc.get("source", "unknown"))
            size = len(doc.get("content", ""))
            table.add_row(did, title, source, f"{size} chars")

        cli.console.print(table)
        cli.console.print(f"\n[dim]Total: {len(docs)} documents[/dim]")
    except Exception as e:
        cli.console.print(f"[red]error loading knowledge: {e}[/red]")


def show_tasks(cli) -> None:
    """显示定时任务"""
    tasks_file = os.path.join("data", "web", "scheduled_tasks.json")
    if not os.path.exists(tasks_file):
        cli.console.print("[dim]no scheduled tasks[/dim]")
        return

    try:
        with open(tasks_file, "r", encoding="utf-8") as f:
            tasks = json.load(f)

        if not tasks:
            cli.console.print("[dim]no scheduled tasks[/dim]")
            return

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Name", style="cyan")
        table.add_column("Trigger", style="blue", width=10)
        table.add_column("Enabled", style="green", width=8)

        for task in tasks[:20]:
            tid = task.get("id", "")[:6]
            name = escape_rich_tags(task.get("name", "Untitled"))
            trigger = escape_rich_tags(task.get("trigger", "manual"))
            enabled = "✓" if task.get("enabled", True) else "✗"
            table.add_row(tid, name, trigger, enabled)

        cli.console.print(table)
        cli.console.print(f"\n[dim]Total: {len(tasks)} tasks[/dim]")
    except Exception as e:
        cli.console.print(f"[red]error loading tasks: {e}[/red]")


def show_workflows(cli) -> None:
    """显示工作流"""
    workflows_file = os.path.join("data", "web", "workflows.json")
    if not os.path.exists(workflows_file):
        cli.console.print("[dim]no workflows[/dim]")
        return

    try:
        with open(workflows_file, "r", encoding="utf-8") as f:
            workflows = json.load(f)

        if not workflows:
            cli.console.print("[dim]no workflows[/dim]")
            return

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("ID", style="dim", width=8)
        table.add_column("Name", style="cyan")
        table.add_column("Trigger", style="blue", width=10)
        table.add_column("Enabled", style="green", width=8)

        for wf in workflows[:20]:
            wid = wf.get("id", "")[:6]
            name = escape_rich_tags(wf.get("name", "Untitled"))
            trigger = escape_rich_tags(wf.get("trigger", "manual"))
            enabled = "✓" if wf.get("enabled", True) else "✗"
            table.add_row(wid, name, trigger, enabled)

        cli.console.print(table)
        cli.console.print(f"\n[dim]Total: {len(workflows)} workflows[/dim]")
    except Exception as e:
        cli.console.print(f"[red]error loading workflows: {e}[/red]")


def show_config(cli) -> None:
    """显示系统配置"""
    config_file = os.path.join("data", "web", "settings.json")
    if not os.path.exists(config_file):
        cli.console.print("[dim]no config file[/dim]")
        return

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="white")

        for key, value in config.items():
            value_str = escape_rich_tags(str(value))
            if len(value_str) > 50:
                value_str = value_str[:50] + "..."
            table.add_row(key, value_str)

        cli.console.print(table)
    except Exception as e:
        cli.console.print(f"[red]error loading config: {e}[/red]")


def show_status(cli) -> None:
    """显示系统状态"""
    cli.console.print("[bold cyan]System Status[/bold cyan]\n")

    from nbot.cli.cc_utils import get_current_model

    current_model = get_current_model(cli)
    if current_model:
        model_name = escape_rich_tags(current_model.get("name", "Unknown"))
        cli.console.print(f"[green]●[/green] Model: {model_name}")
    else:
        cli.console.print("[red]●[/red] Model: Not configured")

    from nbot.cli.cc_utils import get_all_tool_names

    tool_count = len(get_all_tool_names())
    if tool_count > 0:
        cli.console.print(f"[green]●[/green] Tools: {tool_count} available")
    else:
        cli.console.print("[red]●[/red] Tools: Not available")

    sessions_file = os.path.join("data", "web", "sessions.json")
    if os.path.exists(sessions_file):
        try:
            with open(sessions_file, "r", encoding="utf-8") as f:
                sessions = json.load(f)
            cli.console.print(f"[green]●[/green] Sessions: {len(sessions)}")
        except Exception:
            cli.console.print("[dim]●[/dim] Sessions: Unknown")

    memory_file = os.path.join("data", "web", "memories.json")
    if os.path.exists(memory_file):
        try:
            with open(memory_file, "r", encoding="utf-8") as f:
                memories = json.load(f)
            cli.console.print(f"[green]●[/green] Memories: {len(memories)}")
        except Exception:
            pass

    kb_file = os.path.join("data", "knowledge", "knowledge_base.json")
    if os.path.exists(kb_file):
        try:
            with open(kb_file, "r", encoding="utf-8") as f:
                kb_data = json.load(f)
            docs = kb_data.get("documents", [])
            cli.console.print(f"[green]●[/green] Knowledge: {len(docs)} documents")
        except Exception:
            pass

    cli.console.print()
