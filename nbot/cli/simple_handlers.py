"""
NekoBot CLI - 简化版显示与交互处理器
包含 SimpleCLI 的渲染方法、菜单显示、命令处理等。
通过 register_handlers() 将方法绑定到 SimpleCLI 实例。
"""

import os
import json
from datetime import datetime
from typing import Dict, List

from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED, HEAVY
from rich.align import Align
from rich.prompt import Prompt
from rich.markdown import Markdown
from nbot.web.secure_store import read_secure_json, write_secure_json

try:
    from pyfiglet import Figlet

    PYFIGLET_AVAILABLE = True
except ImportError:
    PYFIGLET_AVAILABLE = False


def register_handlers(cli):
    """将显示和交互方法注册到 SimpleCLI 实例上"""

    def _get_ascii_art(self, text: str = "NekoBot", font: str = "small") -> str:
        """生成ASCII艺术字"""
        if PYFIGLET_AVAILABLE:
            try:
                f = Figlet(font=font)
                return f.renderText(text)
            except Exception:
                pass
        return r"""
 _  _     _       ___      _
| \| |___| |_____| _ ) ___| |_
| .` / -_) / / _ \ _ \/ _ \  _|
|_|\_\___|_\_\___/___/\___/\__|
        """

    def print_header(self):
        """打印标题"""
        self.console.print()
        ascii_art = self._get_ascii_art("NekoBot", "small")
        title_text = Text()
        title_text.append(ascii_art, style="bold cyan")
        title_text.append("\n")
        title_text.append("🐱 ", style="yellow")
        title_text.append("智能助手命令行界面", style="dim cyan")

        self.console.print(
            Panel(Align.center(title_text), box=HEAVY, style="cyan", padding=(1, 2))
        )
        self.console.print()

    def print_main_menu(self):
        """打印主菜单"""
        table = Table(show_header=False, box=ROUNDED, style="cyan")
        table.add_column("选项", style="cyan", width=10)
        table.add_column("描述", style="white")

        table.add_row("[bold]1[/bold]", "💬 开始聊天")
        table.add_row("[bold]2[/bold]", "📜 查看会话")
        table.add_row("[bold]3[/bold]", "🔧 管理工具")
        table.add_row("[bold]4[/bold]", "⚙️  系统配置")
        table.add_row("[bold]5[/bold]", "🤖 切换AI模型")
        table.add_row("[bold]6[/bold]", "❓ 帮助信息")
        table.add_row("[bold]0[/bold]", "🚪 退出")

        self.console.print(table)

        current_model = self._get_current_model()
        if current_model:
            self.console.print(
                f"\n[dim]当前模型: [cyan]{current_model.get('name', 'Unknown')}[/cyan] ({current_model.get('model', 'Unknown')})[/dim]"
            )

        try:
            from nbot.cli.simple_app import TOOLS_AVAILABLE, TOOL_DEFINITIONS
        except ImportError:
            TOOLS_AVAILABLE = False
            TOOL_DEFINITIONS = []

        if TOOLS_AVAILABLE:
            self.console.print(
                f"[dim]工具支持: [green]已启用[/green] ({len(TOOL_DEFINITIONS)} 个工具)[/dim]"
            )
        else:
            self.console.print("[dim]工具支持: [yellow]未启用[/yellow][/dim]")

        self.console.print()

    def get_input(self, prompt: str = "请选择") -> str:
        """获取用户输入"""
        try:
            return Prompt.ask(f"[cyan]{prompt}[/cyan]").strip()
        except (KeyboardInterrupt, EOFError):
            return "0"

    def load_sessions(self) -> List[Dict]:
        """加载会话列表"""
        sessions_file = os.path.join("data", "web", "sessions.json")
        if os.path.exists(sessions_file):
            try:
                with open(sessions_file, "r", encoding="utf-8") as f:
                    sessions_data = json.load(f)
                    return list(sessions_data.values())
            except Exception:
                pass
        return []

    def load_tools(self) -> List[Dict]:
        """加载工具列表"""
        tools_file = os.path.join("data", "web", "tools.json")
        if os.path.exists(tools_file):
            try:
                with open(tools_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def _render_markdown(self, content: str):
        """渲染Markdown内容"""
        if not content:
            return

        # 使用Rich的Markdown渲染
        md = Markdown(content, code_theme="monokai")
        self.console.print(md)

    def _render_thinking(self, thinking: str):
        """渲染思考过程"""
        if not thinking or not self.show_thinking:
            return

        # 创建可折叠的思考面板
        thinking_text = Text(thinking, style="dim italic")
        panel = Panel(
            thinking_text,
            title="[dim]💭 思考过程[/dim]",
            box=ROUNDED,
            style="dim",
            padding=(1, 2),
        )
        self.console.print(panel)

    def _render_tool_call(self, tool_name: str, arguments: Dict):
        """渲染工具调用"""
        args_str = json.dumps(arguments, ensure_ascii=False, indent=2)
        content = f"[bold cyan]{tool_name}[/bold cyan]\n{args_str}"

        panel = Panel(
            content,
            title="[yellow]🔧 调用工具[/yellow]",
            box=ROUNDED,
            style="yellow",
            padding=(1, 2),
        )
        self.console.print(panel)

    def _render_tool_result(self, result: Dict):
        """渲染工具执行结果"""
        success = result.get("success", False)
        style = "green" if success else "red"
        icon = "✓" if success else "✗"

        # 格式化结果
        if isinstance(result, dict):
            if "result" in result:
                content = str(result["result"])
            elif "error" in result:
                content = f"[red]错误: {result['error']}[/red]"
            else:
                content = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            content = str(result)

        # 截断过长的结果
        if len(content) > 500:
            content = content[:500] + "\n... (结果已截断)"

        panel = Panel(
            content,
            title=f"[{style}]{icon} 工具结果[/{style}]",
            box=ROUNDED,
            style=style,
            padding=(1, 2),
        )
        self.console.print(panel)

    def _switch_model_in_chat(self):
        """在聊天中切换模型"""
        self.console.print("\n[bold cyan]可用模型：[/bold cyan]")
        for i, model in enumerate(self.available_models, 1):
            marker = "✓" if model.get("id") == self.current_model_id else " "
            self.console.print(
                f"  [{marker}] {i}. {model.get('name', 'Unknown')} - {model.get('model', 'Unknown')}"
            )

        choice = self.get_input("选择模型编号 (或按Enter取消)")
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(self.available_models):
                model = self.available_models[idx]
                self._set_active_model(model.get("id"))
                self.console.print(f"[green]已切换到模型: {model.get('name')}[/green]")
            else:
                self.console.print("[red]无效的选择[/red]")

    def _show_tools_in_chat(self):
        """在聊天中显示可用工具"""
        try:
            from nbot.cli.simple_app import TOOLS_AVAILABLE, TOOL_DEFINITIONS
        except ImportError:
            TOOLS_AVAILABLE = False
            TOOL_DEFINITIONS = []

        if not TOOLS_AVAILABLE or not TOOL_DEFINITIONS:
            self.console.print("[yellow]没有可用的工具[/yellow]")
            return

        self.console.print(f"\n[bold cyan]可用工具 ({len(TOOL_DEFINITIONS)}):[/bold cyan]\n")

        for tool in TOOL_DEFINITIONS:
            func = tool.get("function", {})
            name = func.get("name", "Unknown")
            description = func.get("description", "")
            params = func.get("parameters", {})
            required = params.get("required", [])

            self.console.print(f"  [bold]{name}[/bold]")
            self.console.print(f"    {description}")
            if required:
                self.console.print(f"    [dim]必需参数: {', '.join(required)}[/dim]")
            self.console.print()

    def show_sessions(self):
        """显示会话列表"""
        self.console.clear()
        self.print_header()

        sessions = self.load_sessions()

        if not sessions:
            self.console.print("[dim]暂无会话[/dim]")
        else:
            table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
            table.add_column("ID", style="dim", width=12)
            table.add_column("名称", style="cyan")
            table.add_column("类型", style="blue", width=10)
            table.add_column("消息数", style="green", width=10)
            table.add_column("更新时间", style="dim", width=20)

            for session in sessions[:20]:
                session_id = session.get("id", "")[:8]
                name = session.get("name", "未命名")
                session_type = session.get("type", "unknown")
                message_count = len(session.get("messages", []))
                updated_at = session.get("updated_at", "")

                if updated_at:
                    try:
                        dt = datetime.fromisoformat(updated_at)
                        updated_at = dt.strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        pass

                table.add_row(session_id, name, session_type, str(message_count), updated_at)

            self.console.print(table)

        self.console.print()
        self.get_input("按Enter返回")

    def show_tools(self):
        """显示工具列表"""
        self.console.clear()
        self.print_header()

        try:
            from nbot.cli.simple_app import TOOLS_AVAILABLE, TOOL_DEFINITIONS
        except ImportError:
            TOOLS_AVAILABLE = False
            TOOL_DEFINITIONS = []

        if not TOOLS_AVAILABLE or not TOOL_DEFINITIONS:
            self.console.print("[dim]暂无可用工具[/dim]")
            self.console.print()
            self.get_input("按Enter返回")
            return

        self.console.print(f"[bold cyan]可用工具 ({len(TOOL_DEFINITIONS)}):[/bold cyan]\n")

        for tool in TOOL_DEFINITIONS:
            func = tool.get("function", {})
            name = func.get("name", "Unknown")
            description = func.get("description", "")
            params = func.get("parameters", {})
            properties = params.get("properties", {})
            required = params.get("required", [])

            # 创建工具详情面板
            content = f"[bold]{name}[/bold]\n{description}\n\n"

            if properties:
                content += "[dim]参数:[/dim]\n"
                for param_name, param_info in properties.items():
                    param_type = param_info.get("type", "any")
                    param_desc = param_info.get("description", "")
                    is_required = param_name in required
                    req_marker = "[red]*[/red]" if is_required else ""
                    content += f"  • {param_name}{req_marker}: {param_type} - {param_desc}\n"

            panel = Panel(content, box=ROUNDED, style="cyan", padding=(1, 2))
            self.console.print(panel)
            self.console.print()

        self.get_input("按Enter返回")

    def show_config(self):
        """显示配置"""
        self.console.clear()
        self.print_header()

        configs = {}

        ai_config_file = os.path.join("data", "web", "ai_config.json")
        if os.path.exists(ai_config_file):
            try:
                data_dir = os.path.join("data", "web")
                ai_config, was_plaintext = read_secure_json(ai_config_file, data_dir, {})
                if was_plaintext:
                    write_secure_json(ai_config_file, data_dir, ai_config)
                configs["AI配置"] = ai_config if isinstance(ai_config, dict) else {}
            except Exception:
                pass

        settings_file = os.path.join("data", "web", "settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    configs["系统设置"] = json.load(f)
            except Exception:
                pass

        if not configs:
            self.console.print("[dim]暂无配置信息[/dim]")
        else:
            for category, items in configs.items():
                self.console.print(f"\n[bold cyan]{category}[/bold cyan]")
                table = Table(show_header=False, box=ROUNDED)
                table.add_column("配置项", style="cyan", width=25)
                table.add_column("值", style="white")

                for key, value in items.items():
                    value_str = str(value)
                    if len(value_str) > 50:
                        value_str = value_str[:50] + "..."
                    table.add_row(key, value_str)

                self.console.print(table)

        self.console.print()
        self.get_input("按Enter返回")

    def switch_model(self):
        """切换AI模型"""
        self.console.clear()
        self.print_header()

        if not self.available_models:
            self.console.print("[red]没有可用的AI模型[/red]")
            self.console.print("[dim]请在Web界面配置模型后再试[/dim]")
            self.console.print()
            self.get_input("按Enter返回")
            return

        self.console.print("[bold cyan]可用模型：[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("编号", style="dim", width=6)
        table.add_column("名称", style="cyan")
        table.add_column("模型", style="white")
        table.add_column("提供商", style="blue", width=15)
        table.add_column("工具", style="green", width=8)
        table.add_column("思考", style="magenta", width=8)
        table.add_column("状态", style="green", width=10)

        for i, model in enumerate(self.available_models, 1):
            name = model.get("name", "Unknown")
            model_name = model.get("model", "Unknown")
            provider = model.get("provider_type", model.get("provider", "Unknown"))
            supports_tools = "✓" if model.get("supports_tools", True) else "✗"
            supports_reasoning = "✓" if model.get("supports_reasoning", True) else "✗"
            is_active = model.get("id") == self.current_model_id
            status = "✓ 当前使用" if is_active else ""
            status_style = "bold green" if is_active else ""

            table.add_row(
                str(i),
                f"[bold]{name}[/bold]" if is_active else name,
                model_name,
                provider,
                supports_tools,
                supports_reasoning,
                f"[{status_style}]{status}[/{status_style}]",
            )

        self.console.print(table)
        self.console.print()

        choice = self.get_input("选择模型编号 (或按Enter取消)")
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(self.available_models):
                model = self.available_models[idx]
                self._set_active_model(model.get("id"))
                self.console.print(f"\n[green]✓ 已切换到模型: {model.get('name')}[/green]")
            else:
                self.console.print("[red]无效的选择[/red]")

        self.console.print()
        self.get_input("按Enter返回")

    def show_help(self):
        """显示帮助"""
        self.console.clear()
        self.print_header()

        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        table.add_column("命令", style="cyan", width=15)
        table.add_column("说明", style="white")

        commands = {
            "/help": "显示帮助信息",
            "/quit": "退出CLI",
            "/clear": "清空屏幕",
            "/back": "返回上一级",
            "/model": "切换AI模型（聊天中）",
            "/tools": "查看可用工具",
            "/thinking": "切换思考过程显示",
        }

        for cmd, desc in commands.items():
            table.add_row(cmd, desc)

        self.console.print(table)
        self.console.print()

        self.console.print("[bold cyan]功能特性：[/bold cyan]")
        self.console.print("  • [green]多轮工具调用[/green] - AI可以自动调用多个工具完成任务")
        self.console.print("  • [green]思考过程显示[/green] - 查看AI的推理过程")
        self.console.print("  • [green]Markdown渲染[/green] - 美观的代码块和格式")
        self.console.print("  • [green]会话自动保存[/green] - 对话记录同步到Web端")
        self.console.print()

        self.console.print("[bold cyan]菜单选项说明：[/bold cyan]")
        self.console.print("  [bold]1[/bold] - 进入聊天模式，与AI对话")
        self.console.print("  [bold]2[/bold] - 查看历史会话列表")
        self.console.print("  [bold]3[/bold] - 查看和管理可用工具")
        self.console.print("  [bold]4[/bold] - 查看系统配置")
        self.console.print("  [bold]5[/bold] - 切换AI模型")
        self.console.print("  [bold]6[/bold] - 显示此帮助信息")
        self.console.print("  [bold]0[/bold] - 退出CLI程序")
        self.console.print()

        self.get_input("按Enter返回")

    # 将方法绑定到 cli 实例
    cli._get_ascii_art = _get_ascii_art.__get__(cli, type(cli))
    cli.print_header = print_header.__get__(cli, type(cli))
    cli.print_main_menu = print_main_menu.__get__(cli, type(cli))
    cli.get_input = get_input.__get__(cli, type(cli))
    cli.load_sessions = load_sessions.__get__(cli, type(cli))
    cli.load_tools = load_tools.__get__(cli, type(cli))
    cli._render_markdown = _render_markdown.__get__(cli, type(cli))
    cli._render_thinking = _render_thinking.__get__(cli, type(cli))
    cli._render_tool_call = _render_tool_call.__get__(cli, type(cli))
    cli._render_tool_result = _render_tool_result.__get__(cli, type(cli))
    cli._switch_model_in_chat = _switch_model_in_chat.__get__(cli, type(cli))
    cli._show_tools_in_chat = _show_tools_in_chat.__get__(cli, type(cli))
    cli.show_sessions = show_sessions.__get__(cli, type(cli))
    cli.show_tools = show_tools.__get__(cli, type(cli))
    cli.show_config = show_config.__get__(cli, type(cli))
    cli.switch_model = switch_model.__get__(cli, type(cli))
    cli.show_help = show_help.__get__(cli, type(cli))
