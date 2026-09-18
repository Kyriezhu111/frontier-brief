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
    ("openai", "https://openai.com/news/rss.xml"),
    ("openai-blog", "https://openai.com/blog/rss.xml"),
    ("anthropic-news", "https://www.anthropic.com/news.xml"),
    ("anthropic-rss", "https://www.anthropic.com/rss.xml"),
    ("google-ai-blog", "https://blog.google/technology/ai/rss/"),
    ("deepmind", "https://deepmind.google/blog/rss.xml"),
    ("huggingface", "https://huggingface.co/blog/feed.xml"),
    ("meta-ai", "https://ai.meta.com/blog/rss/"),
    ("mistral", "https://mistral.ai/news/feed.xml"),
    ("microsoft-ai", "https://blogs.microsoft.com/ai/feed/"),
    ("nvidia-dev", "https://developer.nvidia.com/blog/feed/"),
    ("aws-ml", "https://aws.amazon.com/blogs/machine-learning/feed/"),
    ("techcrunch-ai", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("venturebeat-ai", "https://venturebeat.com/category/ai/feed/"),
    ("theverge", "https://www.theverge.com/rss/index.xml"),
    ("arstechnica-ai", "https://arstechnica.com/ai/feed/"),
    ("wired-ai", "https://www.wired.com/feed/tag/ai/latest/rss"),
    ("mit-tech-review", "https://www.technologyreview.com/feed/"),
    ("hn-frontpage", "https://hnrss.org/frontpage"),
    ("hn-ai", "https://hnrss.org/newest?q=AI&points=50"),
    ("arxiv-cs-ai", "https://export.arxiv.org/rss/cs.AI"),
    ("arxiv-cs-cl", "https://export.arxiv.org/rss/cs.CL"),
    ("simonwillison", "https://simonwillison.net/atom/everything/"),
    ("importai", "https://importai.substack.com/feed"),
    ("github-blog", "https://github.blog/feed/"),
    ("syncedreview", "https://syncedreview.com/feed/"),
    ("bair", "https://bair.berkeley.edu/blog/feed.xml"),
    ("jiqizhixin", "https://www.jiqizhixin.com/rss"),
    ("qbitai", "https://www.qbitai.com/feed"),
    ("36kr", "https://36kr.com/feed"),
    ("ithome", "https://www.ithome.com/rss/"),
    ("infoq-cn", "https://www.infoq.cn/feed"),
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
