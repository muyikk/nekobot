"""新闻搜索工具."""
import re
from datetime import datetime
from typing import Dict, Any

from nbot.utils.http_client import get_sync
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def search_news(query: str = "热点新闻", count: int = 5, source: str = "all") -> Dict[str, Any]:
    """
    搜索新闻
    使用 RSS 源获取新闻，并根据关键词过滤

    Args:
        query: 搜索关键词（用于过滤新闻标题和摘要）
        count: 返回的新闻数量（默认5条）
        source: 新闻来源，可选值：
            - "all": 所有可用源（默认）
            - "36kr": 36氪（科技、创业、投资）
            - "ithome": IT之家（科技数码）
            - "huxiu": 虎嗅（商业、科技）
            - "sspai": 少数派（数码、效率工具）

    注意：由于网络限制，部分 RSS 源可能无法访问
    """
    try:
        import feedparser
        import socket

        # 设置超时
        socket.setdefaulttimeout(5)

        # 所有可用的 RSS 新闻源
        all_sources = {
            "36kr": ("36氪", "https://36kr.com/feed"),
            "ithome": ("IT之家", "https://www.ithome.com/rss/"),
            "huxiu": ("虎嗅", "https://www.huxiu.com/rss/0.xml"),
            "sspai": ("少数派", "https://sspai.com/feed"),
        }

        # 根据参数选择新闻源
        if source.lower() == "all":
            rss_urls = list(all_sources.values())
        elif source.lower() in all_sources:
            rss_urls = [all_sources[source.lower()]]
        else:
            # 尝试模糊匹配
            matched = None
            for key in all_sources:
                if source.lower() in key or key in source.lower():
                    matched = key
                    break
            if matched:
                rss_urls = [all_sources[matched]]
            else:
                return {
                    "success": False,
                    "query": query,
                    "error": f"未知的新闻源: {source}\n可用源: all, 36kr, ithome, huxiu, sspai"
                }

        # 获取更多新闻用于过滤（每个源获取 count * 3 条）
        fetch_count = max(count * 3, 15)
        all_news = []
        failed_sources = []

        for source_name, url in rss_urls:
            try:
                _log.info(f"[SearchNews] 尝试 RSS 源: {source_name}")
                feed = feedparser.parse(url)

                if feed.entries and len(feed.entries) > 0:
                    _log.info(f"[SearchNews] {source_name} 获取成功，共 {len(feed.entries)} 条")
                    for entry in feed.entries[:fetch_count]:
                        # 清理 HTML 标签
                        title = entry.get("title", "").replace("<![CDATA[", "").replace("]]>", "").strip()
                        summary = entry.get("summary", entry.get("description", ""))
                        # 简单清理 HTML
                        summary = re.sub(r'<[^>]+>', '', summary)
                        summary = summary.replace("<![CDATA[", "").replace("]]>", "").strip()[:300]

                        all_news.append({
                            "title": title,
                            "summary": summary,
                            "link": entry.get("link", ""),
                            "published": entry.get("published", datetime.now().isoformat()),
                            "source": source_name
                        })
                else:
                    failed_sources.append(source_name)
                    _log.warning(f"[SearchNews] {source_name} 返回空数据")

            except Exception as e:
                failed_sources.append(source_name)
                _log.warning(f"[SearchNews] RSS 源 {source_name} 失败: {type(e).__name__}: {e}")
                continue

        if not all_news:
            # 如果所有 RSS 都失败，返回友好的错误提示
            error_msg = (
                f"🔍 新闻搜索暂时不可用\n\n"
                f"尝试的 RSS 源: {', '.join(failed_sources) if failed_sources else '无'}\n\n"
                f"可能的原因:\n"
                f"• 网络连接问题\n"
                f"• RSS 源被限制或不可访问\n"
                f"• 需要配置网络代理\n\n"
                f"💡 建议:\n"
                f"1. 检查网络连接是否正常\n"
                f"2. 如果使用代理，确保代理配置正确\n"
                f"3. 或直接让 AI 模型使用其内置的联网搜索功能"
            )
            return {
                "success": False,
                "query": query,
                "error": error_msg,
                "hint": "部分新闻源可能需要网络代理才能访问"
            }

        # 根据关键词过滤新闻
        query_lower = query.lower()
        # 分词处理（支持中文和英文）
        keywords = re.split(r'[\s,，、]+', query_lower)
        keywords = [k for k in keywords if len(k) > 0]

        matched_news = []
        other_news = []

        for news in all_news:
            title_lower = news["title"].lower()
            summary_lower = news["summary"].lower()

            # 计算匹配分数
            score = 0
            for keyword in keywords:
                if keyword in title_lower:
                    score += 10  # 标题匹配权重更高
                if keyword in summary_lower:
                    score += 3   # 摘要匹配

            if score > 0:
                news["match_score"] = score
                matched_news.append(news)
            else:
                other_news.append(news)

        # 按匹配分数排序
        matched_news.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        # 组合结果：优先返回匹配的新闻，不足则补充其他新闻
        news_list = matched_news[:count]

        if len(news_list) < count:
            # 补充其他新闻
            remaining = count - len(news_list)
            news_list.extend(other_news[:remaining])

        # 移除匹配分数字段（不需要返回给用户）
        for news in news_list:
            news.pop("match_score", None)

        # 构建返回结果
        result = {
            "success": True,
            "query": query,
            "source": source,
            "total_fetched": len(all_news),
            "matched_count": len(matched_news),
            "news": news_list[:count]
        }

        # 如果没有匹配的新闻，添加提示
        if len(matched_news) == 0 and news_list:
            result["hint"] = f"未找到与 '{query}' 直接相关的新闻，返回最新新闻"

        return result

    except Exception as e:
        _log.error(f"Search news error: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }
