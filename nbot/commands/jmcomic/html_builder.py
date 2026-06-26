"""JM comic HTML builders."""
import html
import os
from typing import Optional

from jmcomic import JmOption

from nbot.commands.state import comic_cache
from nbot.commands.shared.data_persistence import load_address


def fetch_cover_url(album_id: str, client=None) -> str:
    """Fetch the cover URL for a JM album."""
    if client is None:
        client = JmOption.default().new_jm_client()
    try:
        album = client.get_album_detail(album_id)
        if album and len(album) > 0:
            photo = album[0]
            if hasattr(photo, 'cover'):
                return photo.cover
    except Exception:
        pass
    return f"https://cdn-msp.jmcomic.me/media/albums/{album_id}.jpg"


def build_jm_grid_html(title: str, filepath: str) -> None:
    """Start a JM comic grid HTML file."""
    head = f"""<!DOCTYPE html>
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


def append_jm_card(filepath: str, album_id: str, title: str, seq: int, client=None) -> None:
    """Append a comic card to the grid HTML."""
    cover_url = fetch_cover_url(album_id, client=client)
    album_url = f"https://jmcm.la/album/{album_id}"
    card = f"""    <a href="{html.escape(album_url, quote=True)}" target="_blank" style="text-decoration:none; color:inherit;">
    <div class="card">
      <img class="cover" src="{html.escape(cover_url, quote=True)}" alt="{html.escape(title, quote=True)}">
      <div class="meta">
        <div class="seq">#{seq}</div>
        <div class="title">{html.escape(title)}</div>
        <div class="info">ID: {html.escape(str(album_id))}</div>
      </div>
    </div>
    </a>
"""
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(card)


def close_jm_grid_html(filepath: str) -> None:
    """Close the JM comic grid HTML file."""
    tail = """  </div>
</body>
</html>"""
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(tail)
