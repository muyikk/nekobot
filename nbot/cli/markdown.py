"""
CLI Markdown 渲染器 - 将 Markdown 文本渲染为 Rich Text 对象
支持标题、代码块、列表、表格、粗体、斜体、文件链接等。
"""

import re

from rich.console import Console
from rich.text import Text
from rich.table import Table
from rich.box import ROUNDED
from rich.syntax import Syntax

from nbot.cli.completer import escape_rich_tags


def _render_inline_formats(text: Text, content: str) -> None:
    """渲染行内格式（粗体、斜体、删除线等）"""
    if not content:
        return

    # 处理粗体 **text**
    bold_parts = re.split(r"\*\*(.+?)\*\*", content)
    for i, bold_part in enumerate(bold_parts):
        if i % 2 == 1:  # 粗体内容
            text.append(bold_part, style="bold")
        else:
            # 处理斜体 *text*
            italic_parts = re.split(r"\*(.+?)\*", bold_part)
            for j, italic_part in enumerate(italic_parts):
                if j % 2 == 1:  # 斜体内容
                    text.append(italic_part, style="italic")
                else:
                    text.append(italic_part)


def _render_bold_italic(text: Text, content: str) -> None:
    """渲染粗体和斜体"""
    # 处理粗体 **text**
    bold_parts = re.split(r"\*\*(.+?)\*\*", content)
    for i, bold_part in enumerate(bold_parts):
        if i % 2 == 1:  # 粗体内容
            text.append(bold_part, style="bold")
        else:
            # 处理斜体 *text*
            italic_parts = re.split(r"\*(.+?)\*", bold_part)
            for j, italic_part in enumerate(italic_parts):
                if j % 2 == 1:  # 斜体内容
                    text.append(italic_part, style="italic")
                else:
                    text.append(italic_part)


def _render_file_links(text: Text, content: str) -> None:
    """渲染文件链接和普通格式，支持点击打开文件"""
    import os

    # 匹配 Markdown 格式的文件链接: [显示文本](file://路径)
    link_pattern = r"\[([^\]]+)\]\((file://[^)]+)\)"

    last_end = 0
    for match in re.finditer(link_pattern, content):
        if match.start() > last_end:
            _render_bold_italic(text, content[last_end : match.start()])

        display_text = match.group(1)
        file_path = match.group(2)

        actual_path = file_path.replace("file://", "").replace("/", os.sep)
        if not os.path.isabs(actual_path):
            actual_path = os.path.join(os.getcwd(), actual_path)

        if os.path.exists(actual_path):
            link_text = Text(display_text, style="bold blue underline")
            link_text.stylize(f"link file://{actual_path}")
            text.append(link_text)
            text.append(" 📄", style="dim")
        else:
            text.append(display_text, style="dim")

        last_end = match.end()

    if last_end < len(content):
        _render_bold_italic(text, content[last_end:])


def render_inline_formatting(text: Text, content: str) -> None:
    """渲染内联格式（粗体、斜体、代码、文件链接等）"""
    parts = []
    last_end = 0
    for match in re.finditer(r"`([^`]+)`", content):
        if match.start() > last_end:
            parts.append(("text", content[last_end : match.start()]))
        parts.append(("code", match.group(1)))
        last_end = match.end()

    if last_end < len(content):
        parts.append(("text", content[last_end:]))

    if not parts:
        parts = [("text", content)]

    for part_type, part_content in parts:
        if part_type == "code":
            text.append(part_content, style="bold yellow on black")
        else:
            _render_file_links(text, part_content)


def escape_rich_tags_in_markdown(content: str) -> str:
    """在 Markdown 内容中转义 Rich 标签，保留 Markdown 语法"""
    # 匹配 Rich 标签模式
    def replace_tag(match):
        tag = match.group(0)
        return tag.replace("[", "&#91;").replace("]", "&#93;")

    pattern = r"\[/?[a-zA-Z_][a-zA-Z0-9_]*(?:\s*[=:]\s*[^\]]*)?\]"

    protected = []

    # 保护代码块
    code_blocks = re.findall(r"```[\s\S]*?```", content)
    for i, block in enumerate(code_blocks):
        placeholder = f"___CODE_BLOCK_{i}___"
        protected.append((placeholder, block))
        content = content.replace(block, placeholder, 1)

    # 保护行内代码
    inline_codes = re.findall(r"`[^`]+`", content)
    for i, code in enumerate(inline_codes):
        placeholder = f"___INLINE_CODE_{i}___"
        protected.append((placeholder, code))
        content = content.replace(code, placeholder, 1)

    content = re.sub(pattern, replace_tag, content)

    for placeholder, original in protected:
        content = content.replace(placeholder, original, 1)

    return content


def render_markdown_to_text(content: str) -> Text:
    """将 Markdown 渲染为 Text 对象（用于 Live 更新）"""
    if not content:
        return Text("🐱 ", style="cyan")

    text = Text()
    text.append("🐱 ", style="cyan")

    safe_content = escape_rich_tags_in_markdown(content)

    code_blocks = []

    def protect_code_block(match):
        code_blocks.append(match.group(0))
        return f"___CODE_BLOCK_{len(code_blocks) - 1}___"

    safe_content = re.sub(r"```[\s\S]*?```", protect_code_block, safe_content)

    inline_codes = []

    def protect_inline_code(match):
        inline_codes.append(match.group(1))
        return f"___INLINE_CODE_{len(inline_codes) - 1}___"

    safe_content = re.sub(r"`([^`]+)`", protect_inline_code, safe_content)

    lines = safe_content.split("\n")

    for i, line in enumerate(lines):
        if i > 0:
            text.append("\n")

        if "___CODE_BLOCK_" in line:
            for j, block in enumerate(code_blocks):
                placeholder = f"___CODE_BLOCK_{j}___"
                if placeholder in line:
                    code_content = block.replace("```", "").strip()
                    lines_in_block = code_content.split("\n")
                    if lines_in_block and lines_in_block[0] and not lines_in_block[0].strip().isalpha():
                        code_content = "\n".join(lines_in_block[1:])
                    text.append(code_content, style="bold yellow on black")
                    line = line.replace(placeholder, "")
                    continue

        if "___INLINE_CODE_" in line:
            parts = re.split(r"(___INLINE_CODE_\d+___)", line)
            for part in parts:
                match = re.match(r"___INLINE_CODE_(\d+)___", part)
                if match:
                    idx = int(match.group(1))
                    text.append(inline_codes[idx], style="bold yellow on black")
                else:
                    _render_inline_formats(text, part)
        else:
            if line.strip().startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title_text = line.lstrip("#").strip()
                if level == 1:
                    text.append(title_text, style="bold cyan")
                elif level == 2:
                    text.append(title_text, style="bold green")
                elif level == 3:
                    text.append(title_text, style="bold yellow")
                else:
                    text.append(title_text, style="bold")
            elif line.strip().startswith("- ") or line.strip().startswith("* "):
                item_text = line.strip()[2:]
                text.append("  • ", style="dim")
                _render_inline_formats(text, item_text)
            elif re.match(r"^\s*\d+\.\s+", line):
                match = re.match(r"^(\s*\d+\.\s+)(.+)$", line)
                if match:
                    text.append(f"  {match.group(1)}", style="dim")
                    _render_inline_formats(text, match.group(2))
            else:
                _render_inline_formats(text, line)

    return text


def render_markdown(console: Console, content: str) -> None:
    """渲染Markdown内容，向左对齐（包括标题、表格）"""
    if not content:
        return

    # 检测是否包含可能的 Rich 标签模式
    rich_tag_pattern = r"\[/?[a-zA-Z_][a-zA-Z0-9_]*(?:\s+[^\]]*)?\]"

    if re.search(rich_tag_pattern, content):
        safe_content = escape_rich_tags_in_markdown(content)
    else:
        safe_content = content

    lines = safe_content.split("\n")
    in_code_block = False
    code_lines = []
    code_lang = ""
    in_table = False
    table_rows = []
    table_headers = []

    def _render_table(headers, rows):
        """渲染表格"""
        if not headers:
            return
        table = Table(show_header=True, header_style="bold cyan", box=ROUNDED)
        for header in headers:
            table.add_column(header, style="white")

        for row in rows:
            table.add_row(*row)

        console.print(table)

    for line in lines:
        # 检测代码块
        if line.strip().startswith("```"):
            if in_table:
                _render_table(table_headers, table_rows)
                in_table = False
                table_rows = []

            if in_code_block:
                if code_lines:
                    code_content = "\n".join(code_lines)
                    syntax = Syntax(code_content, code_lang or "text", theme="monokai", line_numbers=False)
                    console.print(syntax)
                    code_lines = []
                in_code_block = False
                code_lang = ""
            else:
                in_code_block = True
                code_lang = line.strip()[3:].strip()
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # 检测表格行
        if line.strip().startswith("|") and line.strip().endswith("|"):
            if "---" in line or ":--" in line or "--:" in line:
                in_table = True
                continue

            cells = [cell.strip() for cell in line.split("|")[1:-1]]

            if not in_table:
                table_headers = cells
                table_rows = []
                in_table = True
            else:
                table_rows.append(cells)
            continue
        else:
            if in_table:
                _render_table(table_headers, table_rows)
                in_table = False
                table_rows = []
                table_headers = []

        # 处理普通行
        if not line.strip():
            console.print()
            continue

        # 处理标题（左对齐）
        if line.strip().startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            title_text = line.lstrip("#").strip()
            text = Text()
            if level == 1:
                text.append(title_text, style="bold cyan")
            elif level == 2:
                text.append(title_text, style="bold green")
            elif level == 3:
                text.append(title_text, style="bold yellow")
            else:
                text.append(title_text, style="bold")
            console.print(text)
            continue

        # 处理列表项
        if line.strip().startswith("- ") or line.strip().startswith("* "):
            item_text = line.strip()[2:]
            text = Text()
            text.append("  • ", style="dim")
            render_inline_formatting(text, item_text)
            console.print(text)
            continue

        # 处理数字列表
        num_list_match = re.match(r"^(\s*)(\d+)\.\s+(.+)$", line)
        if num_list_match:
            indent = num_list_match.group(1)
            num = num_list_match.group(2)
            item_text = num_list_match.group(3)
            text = Text()
            text.append(f"  {num}. ", style="dim")
            render_inline_formatting(text, item_text)
            console.print(text)
            continue

        # 普通文本行，处理内联格式
        text = Text()
        render_inline_formatting(text, line)
        console.print(text)

    # 渲染最后的表格（如果有）
    if in_table:
        _render_table(table_headers, table_rows)
