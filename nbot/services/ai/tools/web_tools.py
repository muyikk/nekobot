"""网页搜索工具."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any

from bs4 import BeautifulSoup

from nbot.utils.http_client import get_sync, HTTPClientError
from nbot.utils.logger import get_logger

_log = get_logger(__name__)


def search_web(query: str, num_results: int = 3) -> Dict[str, Any]:
    """
    网页搜索
    使用搜狗搜索（无需 API key），并抓取页面正文获取详细内容
    """
    try:
        _log.info(f"[Search] 发送搜索请求: {query}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }

        # 搜狗搜索
        search_url = "https://www.sogou.com/web"
        search_params = {"query": query, "num": str(num_results * 2)}
        response = get_sync(search_url, headers=headers, params=search_params, timeout=15)
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')
        vrwraps = soup.find_all('div', class_='vrwrap')

        formatted_results = []
        for i, vr in enumerate(vrwraps):
            if len(formatted_results) >= num_results:
                break
            try:
                h3 = vr.find('h3')
                if not h3:
                    continue
                link_tag = h3.find('a')
                if not link_tag:
                    continue
                title = link_tag.get_text(strip=True)
                href = link_tag.get('href', '')

                # 处理搜狗链接：相对路径补全，已有完整 URL 的直接用
                if href.startswith('/link'):
                    href = 'https://www.sogou.com' + href

                # 摘要：找容器内最长的有意义文本
                snippet = ""
                for tag in vr.find_all(['p', 'div', 'span']):
                    text = tag.get_text(strip=True)
                    if len(text) > len(snippet) and len(text) > 30 and text != title:
                        snippet = text

                formatted_results.append({
                    "title": title,
                    "snippet": snippet[:500],
                    "url": href,
                    "content": ""
                })
            except Exception as e:
                _log.warning(f"[Search] 解析结果 {i} 失败: {e}")
                continue

        if not formatted_results:
            return {
                "success": False,
                "error": "未找到搜索结果",
                "query": query
            }

        # 并发抓取每个页面的正文内容
        def resolve_sogou_url(url: str) -> str:
            """解析搜狗跳转链接，提取真实 URL"""
            if 'sogou.com/link' not in url:
                return url
            try:
                import re as _re
                resp = get_sync(url, headers=headers, timeout=5)
                match = _re.search(r'window\.location\.replace("(.*?)")', resp.text)
                if match:
                    return match.group(1)
                match = _re.search(r"content=[\"']0;URL='(.*?)'", resp.text)
                if match:
                    return match.group(1)
            except Exception:
                pass
            return url

        def fetch_page_content(url: str) -> tuple:
            """抓取页面并提取正文文本，返回 (真实URL, 正文内容)"""
            try:
                real_url = resolve_sogou_url(url)
                resp = get_sync(real_url, headers=headers, timeout=8, allow_redirects=True)
                resp.encoding = resp.apparent_encoding or 'utf-8'
                page_soup = BeautifulSoup(resp.text, 'html.parser')

                for tag in page_soup.find_all(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe', 'noscript']):
                    tag.decompose()

                main_content = page_soup.find('article') or page_soup.find('main') or page_soup.find('div', class_=lambda c: c and ('content' in c or 'article' in c or 'post' in c))

                if main_content:
                    paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3', 'li'])
                else:
                    paragraphs = page_soup.find_all('p')

                texts = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 15]
                return (real_url, '\n'.join(texts)[:1500])
            except Exception as e:
                _log.warning(f"[Search] 抓取页面失败 {url}: {e}")
                return (url, "")

        with ThreadPoolExecutor(max_workers=num_results) as executor:
            future_map = {
                executor.submit(fetch_page_content, r['url']): i
                for i, r in enumerate(formatted_results) if r['url']
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    real_url, content = future.result()
                    formatted_results[idx]['url'] = real_url
                    formatted_results[idx]['content'] = content
                except Exception:
                    pass

        # 生成易读的答案摘要
        answer = f"搜索「{query}」找到 {len(formatted_results)} 条结果：\n\n"
        for i, r in enumerate(formatted_results, 1):
            answer += f"【{i}】{r['title']}\n"
            answer += f"链接: {r['url']}\n"
            if r['content']:
                answer += f"正文摘要:\n{r['content'][:600]}\n"
            else:
                answer += f"摘要: {r['snippet']}\n"
            answer += "\n"

        return {
            "success": True,
            "query": query,
            "results": formatted_results,
            "answer": answer.strip()
        }

    except HTTPClientError as e:
        _log.error(f"[Search] 请求错误: {e}")
        return {
            "success": False,
            "error": f"搜索请求失败: {str(e)}",
            "query": query
        }
    except Exception as e:
        _log.error(f"[Search] 搜索错误: {e}")
        return {
            "success": False,
            "error": str(e),
            "query": query
        }
