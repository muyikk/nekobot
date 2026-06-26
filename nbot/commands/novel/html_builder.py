"""Novel HTML builders."""
import html
import os
from typing import Optional

from nbot.commands.shared.data_persistence import load_address


def build_novel_grid_html(title: str, filepath: str) -> None:
    """Start a novel grid HTML file."""
    head = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: 'Segoe UI', 'PingFang SC', sans-serif; background:#111827; color:#f3f4f6; margin:0; padding:24px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:20px; max-width:1200px; margin:0 auto; }}
    .card {{ background:#1f2937; border:1px solid rgba(255,255,255,0.08); border-radius:16px; overflow:hidden; box-shadow:0 10px 24px rgba(0,0,0,0.22); transition: transform 0.2s, box-shadow 0.2s; cursor:pointer; }}
    .card:hover {{ transform: translateY(-4px); box-shadow:0 14px 28px rgba(0,0,0,0.3); }}
    .cover {{ width:100%; aspect-ratio: 13 / 18; object-fit:cover; display:block; background:#0b1220; }}
    .meta {{ padding:14px 16px 18px; }}
    .seq {{ font-size:12px; color:#9ca3af; margin-bottom:6px; }}
    .title {{ font-size:15px; font-weight:700; line-height:1.4; word-break:break-word; margin-bottom:8px; }}
    .info {{ color:#9ca3af; font-size:12px; line-height:1.6; }}
  </style>
</head>
<body>
  <h2 style="text-align:center; margin-bottom:28px; font-weight:600;">{html.escape(title)}</h2>
  <div class="grid">
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(head)


def append_novel_card(filepath: str, book_id: str, title: str, author: str, seq: int) -> None:
    """Append a novel card to the grid HTML."""
    cover_url = f"https://img.wenku8.com/image/{int(book_id) // 1000 if book_id.isdigit() else 0}/{book_id}/{book_id}s.jpg"
    book_url = f"https://www.wenku8.net/book/{book_id}.htm"
    card = f"""    <a href="{html.escape(book_url, quote=True)}" target="_blank" style="text-decoration:none; color:inherit;">
    <div class="card">
      <img class="cover" src="{html.escape(cover_url, quote=True)}" alt="{html.escape(title, quote=True)}">
      <div class="meta">
        <div class="seq">#{seq}</div>
        <div class="title">{html.escape(title)}</div>
        <div class="info">作者: {html.escape(author)}</div>
      </div>
    </div>
    </a>
"""
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(card)


def close_novel_grid_html(filepath: str) -> None:
    """Close the novel grid HTML file."""
    tail = """  </div>
</body>
</html>"""
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(tail)


def build_novel_detail_html(title: str, info: dict, filepath: str) -> None:
    """Build a novel detail HTML file."""
    cover = info.get("cover_url", info.get("cover", ""))
    author = info.get("author", "未知")
    category = info.get("category", "未知")
    word_count = info.get("word_count", "未知")
    is_serialize = info.get("is_serialize", "未知")
    last_date = info.get("last_date", "未知")
    introduction = info.get("introduction", "暂无简介")
    page = info.get("page", "")
    download_url = info.get("download_url", "")
    hot = info.get("hot", "未知")

    html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)} - 轻小说详情</title>
  <style>
    body {{ font-family: 'Segoe UI', 'PingFang SC', sans-serif; background:#111827; color:#f3f4f6; margin:0; padding:24px; }}
    .card {{ background:#1f2937; border:1px solid rgba(255,255,255,0.08); border-radius:16px; overflow:hidden; box-shadow:0 10px 24px rgba(0,0,0,0.22); max-width:600px; margin:0 auto; }}
    .cover {{ width:100%; aspect-ratio: 13 / 18; object-fit:cover; display:block; background:#0b1220; }}
    .meta {{ padding:20px 24px 24px; }}
    .title {{ font-size:22px; font-weight:700; line-height:1.4; word-break:break-word; margin-bottom:12px; }}
    .info {{ color:#9ca3af; font-size:14px; line-height:1.8; }}
    .info div {{ margin-bottom:4px; }}
    .intro {{ margin-top:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.08); color:#d1d5db; font-size:14px; line-height:1.6; }}
    .link {{ margin-top:12px; }}
    .link a {{ color:#60a5fa; text-decoration:none; }}
    .link a:hover {{ text-decoration:underline; }}
  </style>
</head>
<body>
  <div class="card">
    <img class="cover" src="{html.escape(cover, quote=True)}" alt="{html.escape(title, quote=True)}">
    <div class="meta">
      <div class="title">{html.escape(title)}</div>
      <div class="info">
        <div>作者: {html.escape(author)}</div>
        <div>分类: {html.escape(category)}</div>
        <div>字数: {html.escape(word_count)}</div>
        <div>状态: {html.escape(is_serialize)}</div>
        <div>热度: {html.escape(hot)}</div>
        <div>更新日期: {html.escape(last_date)}</div>
      </div>
      <div class="intro">{html.escape(introduction)}</div>
      <div class="link">
        <div><a href="{html.escape(download_url, quote=True)}" target="_blank">下载链接</a></div>
        <div><a href="{html.escape(page, quote=True)}" target="_blank">详情页面</a></div>
      </div>
    </div>
  </div>
</body>
</html>"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
