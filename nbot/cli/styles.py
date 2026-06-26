"""
CLI 样式与显示渲染 - Welcome界面、输入框、思考、工具卡片、用户消息、状态栏
"""

import json
import shutil
from typing import Dict, List, Optional

from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED, HEAVY
from rich.align import Align
from rich import box

from nbot.cli.completer import escape_rich_tags

# 尝试导入pyfiglet用于ASCII艺术字
try:
    from pyfiglet import Figlet

    PYFIGLET_AVAILABLE = True
except ImportError:
    PYFIGLET_AVAILABLE = False


def get_ascii_art_two_lines() -> str:
    """生成两行ASCII艺术字 - Neko在上，Bot在下，使用倾斜实体字体"""
    if PYFIGLET_AVAILABLE:
        # 尝试使用倾斜/实体字体
        for font in ["slant", "lean", "italic", "3-d", "3x5"]:
            try:
                f = Figlet(font=font)
                neko = f.renderText("Neko").rstrip()
                bot = f.renderText("Bot").rstrip()
                # 检查宽度是否合适
                neko_max = max(len(line) for line in neko.split("\n"))
                bot_max = max(len(line) for line in bot.split("\n"))
                if neko_max <= 35 and bot_max <= 35:
                    return f"{neko}\n{bot}"
            except Exception:
                continue
    # 备用艺术字 - 倾斜实体风格
    return r"""
    _   _______      __
   / | / / ___/___  / /______ _
  /  |/ /\__ \/ _ \/ //_/ __ `/
 / /|  /___/ /  __/ ,< / /_/ /
/_/ |_//____/\___/_/|_|\__,_/

    ____        __
   / __ )____  / /__
  / __  / __ \/ //_/
 / /_/ / /_/ / ,<
/_____/\____/_/|_|  """


def print_welcome(console: Console, cli) -> None:
    """打印欢迎界面"""
    console.print()

    # 顶部标题栏
    header = Panel(
        Align.center("[bold cyan]🐱 NekoBot CLI[/bold cyan] [dim]v1.0.0[/dim]"),
        box=HEAVY,
        style="cyan",
        padding=(0, 1),
    )
    console.print(header)

    # 主内容区 - 左右分栏
    left_content = get_ascii_art_two_lines()
    left_panel = Panel(
        Align.center(f"[bold cyan]{left_content}[/bold cyan]", vertical="middle"),
        box=ROUNDED,
        style="cyan",
        padding=(0, 0),
        height=20,
        width=40,
    )

    # 右侧提示信息
    current_model = cli._get_current_model()
    model_name = current_model.get("name", "Unknown") if current_model else "Unknown"
    model_provider = current_model.get("provider_type", "Unknown") if current_model else "Unknown"

    model_name = escape_rich_tags(model_name)
    model_provider = escape_rich_tags(model_provider)

    tips_text = f"""[bold]Tips for getting started[/bold]

Type a message to chat with AI
Press [yellow]/[/yellow] for command mode
Press [yellow]?[/yellow] for help mode
Press [red]Ctrl+C[/red] to interrupt AI

[dim]Current Model:[/dim] [cyan]{model_name}[/cyan]
[dim]Provider:[/dim] [cyan]{model_provider}[/cyan]
[dim]Tools:[/dim] [cyan]{len(cli._get_all_tool_names())} available[/cyan]

[dim]Recent activity[/dim]
No recent activity
"""
    right_panel = Panel(
        tips_text, box=ROUNDED, style="white", padding=(1, 2), height=20
    )

    table = Table(show_header=False, box=None, expand=True)
    table.add_column("left", ratio=1)
    table.add_column("right", ratio=2)
    table.add_row(left_panel, right_panel)

    content_panel = Panel(
        table,
        box=ROUNDED,
        style="cyan",
        padding=(1, 2),
        title="[bold cyan]🐱 Welcome[/bold cyan]",
        title_align="left",
    )

    console.print(content_panel)
    console.print()


def render_input_box(cli, mode: str = "chat") -> str:
    """渲染输入框 - 带动态效果"""
    is_processing = False
    try:
        with cli.queue_lock:
            is_processing = cli.ai_processing
    except Exception:
        pass

    if is_processing:
        return "\033[2m⋯\033[0m"

    if mode == "command":
        return "\033[1;33m/\033[0m"
    elif mode == "help":
        return "\033[1;35m?\033[0m"
    else:
        msg_count = len(cli.messages)
        if msg_count == 0:
            return "\033[1;36m›\033[0m"
        elif msg_count < 10:
            return "\033[1;32m›\033[0m"
        elif msg_count < 20:
            return "\033[1;33m›\033[0m"
        else:
            return "\033[1;35m›\033[0m"


def show_input_hint(console: Console, cli) -> None:
    """显示输入提示 - 根据当前状态动态变化"""
    # 获取当前模型和人格
    current_model = cli._get_current_model()
    model_name = current_model.get("name", "Unknown") if current_model else "Unknown"

    current_personality = cli._get_current_personality()
    personality_name = current_personality.get("name", "Unknown")

    # 获取消息数量
    msg_count = len(cli.messages)

    # 构建动态提示
    text = Text()

    if msg_count == 0:
        text.append("💬 ", style="dim")
        text.append(f"Start chatting with {escape_rich_tags(personality_name)}", style="dim cyan")
    elif msg_count < 5:
        text.append("🐱 ", style="dim")
        text.append("Keep the conversation going", style="dim green")
    elif msg_count < 15:
        text.append("✨ ", style="dim")
        text.append(f"{msg_count} messages so far", style="dim yellow")
    else:
        text.append("📝 ", style="dim")
        text.append(f"Long conversation ({msg_count} msgs)", style="dim magenta")

    text.append("  [", style="dim")
    text.append(escape_rich_tags(model_name[:15]), style="dim cyan")
    text.append("]", style="dim")

    console.print(text)


def show_command_candidates(console: Console, cli, partial: str) -> None:
    """显示命令候选"""
    # 查找匹配的命令
    matches = []
    search_term = partial.lower() if partial else ""

    for cmd, info in cli.COMMANDS.items():
        if cmd.startswith(search_term):
            matches.append((cmd, info["desc"]))
        # 检查别名
        for alias in info.get("aliases", []):
            if alias.startswith(search_term):
                matches.append((f"{cmd} (alias: {alias})", info["desc"]))

    # 显示候选
    if not search_term:
        if matches:
            console.print()
            console.print(f"[bold cyan]Available commands ({len(matches)}):[/bold cyan]")
            sorted_matches = sorted(matches, key=lambda x: x[0])
            for cmd, desc in sorted_matches:
                cmd = escape_rich_tags(cmd)
                desc = escape_rich_tags(desc)
                console.print(f"  [yellow]/{cmd}[/yellow] - {desc}")
            console.print()
    elif len(matches) == 1:
        cmd, desc = matches[0]
        desc = escape_rich_tags(desc)
        console.print(f"[dim]↳ {desc}[/dim]")
    elif len(matches) > 1:
        console.print(f"[dim]Candidates ({len(matches)}):[/dim]")
        for cmd, desc in matches:
            cmd = escape_rich_tags(cmd)
            desc = escape_rich_tags(desc)
            console.print(f"  [yellow]/{cmd}[/yellow] - {desc}")


def render_inline_thinking(console: Console, thinking: str, show_thinking: bool) -> None:
    """内联渲染思考过程"""
    if not thinking or not show_thinking:
        return

    thinking_lines = [line for line in thinking.strip().split("\n") if line.strip()]
    for i, line in enumerate(thinking_lines):
        line = escape_rich_tags(line)
        text = Text()
        text.append("💭 ", style="dim italic")
        text.append(line, style="dim italic")
        console.print(text)


def render_tool_call_and_result(
    console: Console, tool_name: str, arguments: Dict, result: Dict, success: bool
) -> None:
    """以卡片样式渲染工具调用和结果"""
    # 工具名称不截断，完整显示
    tool_name_display = escape_rich_tags(tool_name)

    # 准备参数字符串，限制长度
    args_str = json.dumps(arguments, ensure_ascii=False)
    args_str = escape_rich_tags(args_str)
    if len(args_str) > 30:
        args_str = args_str[:27] + "..."

    # 构建卡片内容
    card_lines = []

    # 工具名称行
    name_line = Text()
    name_line.append("🔧 ", style="yellow")
    name_line.append(tool_name_display, style="bold cyan")
    card_lines.append(name_line)

    # 参数行（如果有参数）
    if args_str and args_str != "{}":
        args_line = Text(f"   {args_str}", style="dim")
        card_lines.append(args_line)

    # 结果行
    result_line = Text()
    if success:
        # 特殊处理 workspace_send_file，显示可点击的文件链接
        if tool_name == "workspace_send_file" and result.get("file_url"):
            file_url = result.get("file_url")
            filename = result.get("filename", "文件")
            size_str = result.get("size_str", "")

            if len(filename) > 25:
                filename = filename[:22] + "..."

            result_line.append("   ✓ ", style="green")
            link_text = Text(filename, style="blue underline")
            link_text.stylize(f"link {file_url}")
            result_line.append(link_text)
            if size_str:
                result_line.append(f" {size_str}", style="dim")
            result_line.append(" 📄", style="dim")
        else:
            result_line.append("   ✓ ", style="green")
            result_line.append("Success", style="green")
    else:
        error_msg = result.get("error", "")
        if error_msg:
            error_msg = escape_rich_tags(error_msg)
            if len(error_msg) > 30:
                error_msg = error_msg[:27] + "..."
            result_line.append("   ✗ ", style="red")
            result_line.append(error_msg, style="red")
        else:
            result_line.append("   ✗ ", style="red")
            result_line.append("Failed", style="red")

    card_lines.append(result_line)

    # 创建卡片面板，使用紧凑样式
    card_content = Group(*card_lines)
    card = Panel(
        card_content,
        border_style="dim" if success else "red",
        padding=(0, 1),
        width=50,
        expand=False,
        box=box.ROUNDED,
    )

    console.print(card)


def display_user_message(console: Console, content: str, attachments: list = None) -> None:
    """显示用户消息 - 带上下边框"""
    line_char = "─"
    width = shutil.get_terminal_size().columns

    console.print(f"[dim]{line_char * width}[/dim]")

    text = Text()
    text.append("> ", style="bold green")
    text.append(content)
    console.print(text)

    if attachments:
        for att in attachments:
            if att.get("type") == "file":
                console.print(f"[dim]📎 {att.get('relative_path', att.get('source'))}[/dim]")

    console.print(f"[dim]{line_char * width}[/dim]")


def print_footer(console: Console, cli) -> None:
    """打印底部状态栏"""
    current_model = cli._get_current_model()
    model_name = current_model.get("name", "Unknown") if current_model else "Unknown"

    model_name = escape_rich_tags(model_name)

    text = Text()
    text.append("? for shortcuts", style="dim")
    text.append(f"  ● {model_name}", style="cyan")

    tool_count = len(cli._get_all_tool_names())
    if tool_count > 0:
        text.append(f"  ● {tool_count} tools", style="green")

    with cli.queue_lock:
        if cli.message_queue:
            text.append(f"  ● {len(cli.message_queue)} queued", style="yellow")

    console.print()
    console.print(text)
