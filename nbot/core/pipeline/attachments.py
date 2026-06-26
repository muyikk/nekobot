"""
管道附件处理混入类

提供附件的 MIME 类型判断和处理方法。
作为 AIPipeline 的混入基类使用。
"""

import logging
from typing import Any, Dict, Optional

_log = logging.getLogger(__name__)


class PipelineAttachmentMixin:
    """附件处理混入类。

    提供 MIME 类型常量、附件类型判断和处理方法。
    依赖 cls.TEXT_MIME_TYPES / cls.TEXT_EXTENSIONS / cls.DOCUMENT_MIME_TYPES
    由 AIPipeline 定义。
    """

    _middleware_initialized = False

    @classmethod
    def _ensure_middleware_initialized(cls) -> None:
        """初始化媒体描述中间件。"""
        if cls._middleware_initialized:
            return
        from nbot.core.message_middleware import MediaDescriber
        from nbot.services.ai import ai_client as _ai_client

        def _describe_image(url: str):
            return _ai_client.describe_image(url, "请描述这个图片的内容，仅作描述，不要分析内容")

        def _describe_video(url: str):
            return _ai_client.describe_video(url)

        def _describe_audio(url: str):
            return _ai_client.describe_audio(url) if hasattr(_ai_client, 'describe_audio') else None

        MediaDescriber.register("image", _describe_image)
        MediaDescriber.register("video", _describe_video)
        MediaDescriber.register("audio", _describe_audio)
        cls._middleware_initialized = True

    @staticmethod
    def _looks_like_image(att: Dict[str, Any]) -> bool:
        """判断附件是否像图片。"""
        att_type = str(att.get("type", "")).lower()
        att_name = str(att.get("name", att.get("filename", ""))).lower()
        if att_type.startswith("image/"):
            return True
        image_ext = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"}
        _, ext = "", ""
        if "." in att_name:
            ext = "." + att_name.rsplit(".", 1)[-1]
        return ext in image_ext

    @classmethod
    def _is_text_type(cls, att_type: str, att_name: str) -> bool:
        """判断附件是否为文本类型。"""
        if att_type in cls.TEXT_MIME_TYPES:
            return True
        _, ext = "", ""
        if "." in att_name:
            ext = "." + att_name.rsplit(".", 1)[-1]
        return ext.lower() in cls.TEXT_EXTENSIONS

    @classmethod
    def _is_document_type(cls, att_type: str, att_name: str) -> bool:
        """判断附件是否为文档类型（PDF/DOCX/XLSX/PPT）。"""
        if att_type in cls.DOCUMENT_MIME_TYPES:
            return True
        doc_ext = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt"}
        _, ext = "", ""
        if "." in att_name:
            ext = "." + att_name.rsplit(".", 1)[-1]
        return ext.lower() in doc_ext

    def _handle_image_attachment(
        self,
        ctx: "PipelineContext",
        progress: "ProgressReporter",
        att: Dict[str, Any],
        resolved: Optional[Dict[str, Any]],
    ) -> None:
        """处理图片附件。"""
        name = att.get("name", att.get("filename", "image"))
        progress.on_attachment_item(ctx, name, "image")

        if resolved and resolved.get("data"):
            ctx.image_urls.append(resolved["data"])
            progress.on_attachment_item_done(ctx, name, True)
        elif resolved and resolved.get("path"):
            ctx.image_urls.append(resolved["path"])
            progress.on_attachment_item_done(ctx, name, True)
        else:
            url = att.get("url") or att.get("path") or att.get("data")
            if url:
                ctx.image_urls.append(url)
                progress.on_attachment_item_done(ctx, name, True)
            else:
                progress.on_attachment_item_done(ctx, name, False, "无法解析图片")

    def _handle_text_attachment(
        self,
        ctx: "PipelineContext",
        progress: "ProgressReporter",
        att: Dict[str, Any],
        resolved: Optional[Dict[str, Any]],
    ) -> None:
        """处理文本附件。"""
        name = att.get("name", att.get("filename", "file"))
        progress.on_attachment_item(ctx, name, "file")

        content = None
        if resolved and resolved.get("text_content"):
            content = resolved["text_content"]
        elif resolved and resolved.get("data"):
            content = resolved["data"]

        if content:
            ctx.file_contents.append(
                f"【文件 {name} 内容】:\n{str(content)[:10000]}"
            )
            preview = str(content)[:200].replace("\n", " ")
            progress.on_attachment_item_done(ctx, name, True, preview)
        else:
            progress.on_attachment_item_done(ctx, name, False, "无法读取文件内容")

    def _handle_document_attachment(
        self,
        ctx: "PipelineContext",
        progress: "ProgressReporter",
        att: Dict[str, Any],
        resolved: Optional[Dict[str, Any]],
    ) -> None:
        """处理文档附件（PDF/DOCX/XLSX/PPT）。"""
        name = att.get("name", att.get("filename", "document"))
        progress.on_attachment_item(ctx, name, "document")

        try:
            from nbot.core.file_parser import parse_file

            file_path = None
            if resolved and resolved.get("path"):
                file_path = resolved["path"]

            if file_path:
                parsed = parse_file(file_path)
                if parsed and parsed.get("content"):
                    ctx.file_contents.append(
                        f"【文档 {name} 解析内容】:\n{str(parsed['content'])[:10000]}"
                    )
                    progress.on_attachment_item_done(ctx, name, True, "文档已解析")
                    return
        except Exception:
            pass

        progress.on_attachment_item_done(ctx, name, True, "文档已记录（未提取文本）")
