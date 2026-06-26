"""
工作区工具函数

路径解析与文本编辑辅助函数。
"""

import os


def _resolve_within(base_path: str, *parts: str) -> str | None:
    """解析子路径并拒绝越出 base_path 的路径穿越。

    Args:
        base_path: 基准路径
        *parts: 路径组成部分

    Returns:
        解析后的绝对路径，若路径越界则返回 None
    """
    base_abs = os.path.abspath(base_path)
    target = os.path.abspath(os.path.join(base_abs, *[p for p in parts if p]))
    try:
        if os.path.commonpath([base_abs, target]) != base_abs:
            return None
    except ValueError:
        return None
    return target


def _normalize_edit_block(text: str) -> str:
    """规范化文本块，统一换行符并去除行尾空白。

    Args:
        text: 原始文本

    Returns:
        规范化后的文本
    """
    return "\n".join(
        line.rstrip() for line in (text or "").replace("\r\n", "\n").strip().split("\n")
    )


def _replace_content_block(content: str, old_content: str, new_content: str):
    """在文本中查找并替换内容块，支持多种匹配模式。

    依次尝试精确匹配、统一换行符匹配、宽松块匹配。

    Args:
        content: 原始文件内容
        old_content: 要替换的旧内容
        new_content: 替换后的新内容

    Returns:
        (替换后的文本, 匹配模式) 或 (None, None)
    """
    if old_content in content:
        return content.replace(old_content, new_content, 1), "exact"

    normalized_content = content.replace("\r\n", "\n")
    normalized_old = (old_content or "").replace("\r\n", "\n")
    if normalized_old and normalized_old in normalized_content:
        return normalized_content.replace(normalized_old, new_content, 1), "normalized_newlines"

    relaxed_old = _normalize_edit_block(old_content)
    if not relaxed_old:
        return None, None

    content_lines = content.replace("\r\n", "\n").split("\n")
    old_lines = relaxed_old.split("\n")
    old_len = len(old_lines)
    for start in range(0, len(content_lines) - old_len + 1):
        candidate = "\n".join(content_lines[start : start + old_len])
        if _normalize_edit_block(candidate) == relaxed_old:
            new_lines = new_content.replace("\r\n", "\n").split("\n")
            updated_lines = content_lines[:start] + new_lines + content_lines[start + old_len :]
            return "\n".join(updated_lines), "relaxed_block"

    return None, None
