"""Web 服务器知识库相关方法。

提供知识库检索、关键词搜索与索引检查能力，
以 mixin 形式组合到 WebChatServer。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from nbot.utils.logger import get_logger

_log = get_logger(__name__)

# 尝试导入知识库管理器
try:
    from nbot.core.knowledge import get_knowledge_manager

    _KNOWLEDGE_MANAGER_AVAILABLE = True
except ImportError:
    _KNOWLEDGE_MANAGER_AVAILABLE = False
    get_knowledge_manager = None  # type: ignore[misc,assignment]


class KnowledgeMixin:
    """知识库相关方法 mixin。"""

    def _retrieve_knowledge(self, query: str, max_docs: int = 3) -> str:
        """从知识库中检索相关内容（使用 knowledge_manager 向量检索 + 关键词匹配）。

        Args:
            query: 用户查询文本。
            max_docs: 最大返回文档数。

        Returns:
            格式化的知识内容字符串。
        """
        if not _KNOWLEDGE_MANAGER_AVAILABLE:
            return ""

        if not query:
            return ""

        try:
            km = get_knowledge_manager()
            if not km:
                return ""

            results = km.search(query, base_id=None, top_k=max_docs)

            if not results or all(sim < 0.3 for _, sim, _ in results):
                _log.info("[Knowledge] 向量检索无结果，尝试关键词匹配...")
                results = self._keyword_search(km, query, max_docs)

            if not results:
                return ""

            knowledge_parts = ["【知识库参考】"]
            seen_titles = set()

            for doc, similarity, chunk_content in results:
                if doc.title in seen_titles:
                    continue
                seen_titles.add(doc.title)

                content = chunk_content
                if len(content) > 500:
                    content = content[:500] + "..."

                knowledge_parts.append(f"\n📄 {doc.title}\n{content}")

            if seen_titles:
                _log.info(f"[Knowledge] 检索到 {len(seen_titles)} 条相关内容")
                return "\n".join(knowledge_parts)
            return ""

        except Exception as e:
            _log.error(f"[Knowledge] 检索失败: {e}")
            return ""

    def _keyword_search(self, km, query: str, max_docs: int = 3) -> list:
        """关键词搜索知识库文档。

        Args:
            km: 知识库管理器实例。
            query: 查询文本。
            max_docs: 最大返回文档数。

        Returns:
            匹配的文档列表。
        """
        try:
            bases = km.list_knowledge_bases()
            if not bases:
                return []

            query_words = set(re.findall(r"[\w]+", query.lower()))
            all_docs = []
            for kb in bases:
                for doc_id in kb.documents:
                    doc = km.store.load_document(doc_id)
                    if doc:
                        all_docs.append((doc, doc.content))

            scored = []
            for doc, content in all_docs:
                content_lower = content.lower()
                title_lower = doc.title.lower()
                score = 0
                for word in query_words:
                    if word in title_lower:
                        score += 3
                    if word in content_lower:
                        score += 1
                if score > 0:
                    scored.append((doc, score, content))

            scored.sort(key=lambda x: x[1], reverse=True)
            return [(doc, float(score), content) for doc, score, content in scored[:max_docs]]
        except Exception as e:
            _log.error(f"[Knowledge] keyword search failed: {e}")
            return []

    def _check_knowledge_index(self):
        """检查知识库索引状态，如有需要自动重建。"""
        if not _KNOWLEDGE_MANAGER_AVAILABLE:
            return
        try:
            km = get_knowledge_manager()
            if km:
                km.check_and_rebuild_if_needed()
        except Exception as e:
            _log.warning(f"Failed to check knowledge index: {e}")
