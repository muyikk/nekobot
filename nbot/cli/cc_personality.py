"""
CLI 人格管理 - CCStyleCLI 的人格切换、配置、预设管理
"""

import os
import json
from typing import Dict, List

from rich.table import Table
from rich.box import ROUNDED
from nbot.cli.completer import escape_rich_tags


def get_current_personality(cli) -> Dict:
    """获取当前人格配置"""
    # 从 server 获取
    try:
        from nbot.web import get_web_server

        server = get_web_server()
        if server and hasattr(server, "personality"):
            return server.personality
    except Exception:
        pass

    # 优先从新版 personality.json 获取
    new_personality_file = os.path.join("resources", "prompts", "personality.json")
    if os.path.exists(new_personality_file):
        try:
            with open(new_personality_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # 回退到旧版 personality.json
    old_personality_file = os.path.join("data", "web", "personality.json")
    if os.path.exists(old_personality_file):
        try:
            with open(old_personality_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    # 默认人格
    return {"name": "猫娘助手", "prompt": ""}


def get_neko_prompt() -> str:
    """获取猫娘助手的 prompt"""
    # 优先从 neko.txt 读取
    prompt_file = os.path.join("resources", "prompts", "neko.txt")
    if os.path.exists(prompt_file):
        try:
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read()
            if content.strip():
                return content
        except Exception:
            pass
    # 回退到 personality.json
    personality_file = os.path.join("resources", "prompts", "personality.json")
    if os.path.exists(personality_file):
        try:
            with open(personality_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            prompt = data.get("systemPrompt", "")
            if prompt:
                return prompt
        except Exception:
            pass
    return "你是 NekoBot，一个活泼可爱的猫娘助手。"


def get_personality_presets() -> List[Dict]:
    """获取人格预设列表"""
    # 内置预设
    presets = [
        {
            "id": "1",
            "name": "猫娘助手",
            "description": "活泼可爱的猫娘助手",
            "prompt": get_neko_prompt(),
        },
        {
            "id": "2",
            "name": "学习助手",
            "description": "专注解释、总结和辅导学习问题",
            "prompt": "你是一个耐心、清晰、擅长教学的 AI 助手。",
        },
        {
            "id": "3",
            "name": "代码助手",
            "description": "偏重编程、排错和工程实现",
            "prompt": "你是一个专业的软件开发助手，回答务实、准确、可执行。",
        },
        {
            "id": "4",
            "name": "创意写手",
            "description": "偏重文案、故事和创意表达",
            "prompt": "你是一个富有创意的写作助手，擅长构思、润色和扩展文本。",
        },
    ]

    # 添加自定义预设
    custom_presets_file = os.path.join("data", "web", "custom_personality_presets.json")
    if os.path.exists(custom_presets_file):
        try:
            with open(custom_presets_file, "r", encoding="utf-8") as f:
                custom_presets = json.load(f)
                for preset in custom_presets:
                    presets.append({
                        "id": preset.get("id", ""),
                        "name": preset.get("name", "Custom"),
                        "description": preset.get("description", "Custom preset"),
                        "prompt": preset.get("prompt", ""),
                    })
        except Exception:
            pass

    return presets


def display_personality_list(cli) -> None:
    """显示人格列表"""
    current_personality = get_current_personality(cli)
    current_name = current_personality.get("name", "Unknown")

    cli.console.print(
        f"\n[bold cyan]Current Personality: {escape_rich_tags(current_name)}[/bold cyan]\n"
    )

    presets = get_personality_presets()

    table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="white")

    for i, preset in enumerate(presets, 1):
        name = preset.get("name", "Unknown")
        desc = preset.get("description", "")
        marker = "●" if name == current_name else "○"
        table.add_row(
            f"{marker} {i}",
            escape_rich_tags(name),
            escape_rich_tags(desc),
        )

    cli.console.print(table)
    cli.console.print("\n[dim]Use /personality <number> or /personality <name> to switch[/dim]")

    prompt = current_personality.get("systemPrompt") or current_personality.get("prompt", "")
    if prompt:
        cli.console.print("\n[bold]Current Prompt Preview:[/bold]")
        preview = prompt[:200] + "..." if len(prompt) > 200 else prompt
        cli.console.print(f"[dim]{escape_rich_tags(preview)}[/dim]")


def show_personality(cli, args: str = "") -> None:
    """显示或切换人格配置"""
    if args.strip():
        switch_personality(cli, args.strip())
        return

    display_personality_list(cli)


def switch_personality(cli, choice: str) -> None:
    """切换人格"""
    presets = get_personality_presets()

    # 尝试按编号切换
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(presets):
            preset = presets[idx]
            apply_personality(cli, preset)
            cli.console.print(f"[green]✓ Switched to {preset['name']}[/green]")
            return
    except ValueError:
        pass

    # 尝试按名称切换
    choice_lower = choice.lower()
    for preset in presets:
        if choice_lower in preset["name"].lower():
            apply_personality(cli, preset)
            cli.console.print(f"[green]✓ Switched to {preset['name']}[/green]")
            cli.console.print("[dim]New personality will take effect in the next message[/dim]")
            return

    cli.console.print(f"[red]Personality not found: {choice}[/red]")


def apply_personality(cli, preset: Dict) -> None:
    """应用人格配置"""
    personality = {"name": preset["name"], "prompt": preset["prompt"]}

    # 保存到 personality.json
    personality_file = os.path.join("data", "web", "personality.json")
    try:
        os.makedirs(os.path.dirname(personality_file), exist_ok=True)
        with open(personality_file, "w", encoding="utf-8") as f:
            json.dump(personality, f, ensure_ascii=False, indent=2)
    except Exception as e:
        cli.console.print(f"[red]Failed to save personality: {e}[/red]")

    # 更新 server 的 personality（如果可用）
    try:
        from nbot.web import get_web_server

        server = get_web_server()
        if server and hasattr(server, "personality"):
            server.personality = personality
    except Exception:
        pass

    # 应用人格到当前会话
    apply_personality_to_session(cli, personality)


def apply_personality_to_session(cli, personality: Dict) -> None:
    """将人格应用到当前会话（只添加 system 消息，不修改配置文件）"""
    prompt = personality.get("systemPrompt") or personality.get("prompt", "")
    if not prompt:
        return

    from datetime import datetime

    # 先移除旧的 system 消息
    cli.messages = [msg for msg in cli.messages if msg.get("role") != "system"]
    # 添加新的 system 消息
    cli.messages.insert(
        0,
        {"role": "system", "content": prompt, "timestamp": datetime.now().isoformat()},
    )


def reset_personality_to_default(cli) -> None:
    """重置人格为默认猫娘助手"""
    default_prompt = get_neko_prompt()

    default_personality = {"name": "猫娘助手", "prompt": default_prompt}

    personality_file = os.path.join("data", "web", "personality.json")
    try:
        os.makedirs(os.path.dirname(personality_file), exist_ok=True)
        with open(personality_file, "w", encoding="utf-8") as f:
            json.dump(default_personality, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    try:
        from nbot.web import get_web_server

        server = get_web_server()
        if server and hasattr(server, "personality"):
            server.personality = default_personality
    except Exception:
        pass

    apply_personality_to_session(cli, default_personality)
