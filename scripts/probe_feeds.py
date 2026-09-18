#!/usr/bin/env python3
"""Probe feed reachability from a GitHub Actions runner.

Prints one line per URL: status, size, content-type, name, url.
Feeds that come back 200 with an XML/HTML body are usable; the rest get dropped.
"""
import concurrent.futures
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; frontier-brief/1.0; +https://github.com/Kyriezhu111/frontier-brief)"
ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8"

FEEDS = [
    ("anthropic-openrss-rss", "https://openrss.org/rss/www.anthropic.com/news"),
    ("anthropic-rsshub-pseudoyu", "https://rsshub.pseudoyu.com/anthropic/news"),
    ("anthropic-rsshub-feeded", "https://rsshub.feeded.xyz/anthropic/news"),
    ("hn-anthropic", "https://hnrss.org/newest?q=Anthropic&points=30"),
    ("hn-grok", "https://hnrss.org/newest?q=Grok&points=30"),
    ("hn-deepseek", "https://hnrss.org/newest?q=DeepSeek&points=20"),
    ("techmeme", "https://www.techmeme.com/feed.xml"),
    ("verge-ai", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("mit-news-ai", "https://news.mit.edu/rss/topic/artificial-intelligence2"),
    ("stanford-hai", "https://hai.stanford.edu/news/rss.xml"),
    ("epoch-ai", "https://epoch.ai/blog/rss.xml"),
    ("github-trending-daily", "https://mshibanami.github.io/GitHubTrendingRSS/daily/python.xml"),
    ("arxiv-stat-ml", "https://export.arxiv.org/rss/stat.ML"),
    ("hn-frontpage-150", "https://hnrss.org/frontpage?points=150"),
]


def probe(item):
    name, url = item
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": ACCEPT})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(6000)
            ctype = resp.headers.get("Content-Type", "?")
            head = body.lstrip()[:80].decode("utf-8", "replace").replace("\n", " ")
            looks_xml = body.lstrip()[:1] == b"<"
            return f"OK   {resp.status}  {len(body):>6}B  xml={str(looks_xml):<5} {ctype:<38} {name:<18} {url}\n     head: {head}"
    except urllib.error.HTTPError as e:
        return f"FAIL {e.code}           HTTPError                        {name:<18} {url}"
    except Exception as e:  # noqa: BLE001 - probe should never raise
        return f"FAIL ---           {type(e).__name__:<32} {name:<18} {url}"


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for line in pool.map(probe, FEEDS):
            print(line, flush=True)


if __name__ == "__main__":
    main()
