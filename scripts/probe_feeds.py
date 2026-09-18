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
    ("anthropic-openrss", "https://openrss.org/www.anthropic.com/news"),
    ("anthropic-rsshub", "https://rsshub.app/anthropic/news"),
    ("anthropic-feed", "https://www.anthropic.com/news/feed.xml"),
    ("anthropic-openrss-eng", "https://openrss.org/www.anthropic.com/engineering"),
    ("mistral-alt", "https://mistral.ai/feed.xml"),
    ("meta-ai-alt", "https://ai.meta.com/blog/rss.xml"),
    ("google-research", "https://research.google/blog/rss/"),
    ("deeplearningai-batch", "https://www.deeplearning.ai/the-batch/feed/"),
    ("latent-space", "https://www.latent.space/feed"),
    ("interconnects", "https://www.interconnects.ai/feed"),
    ("raschka", "https://magazine.sebastianraschka.com/feed"),
    ("ieee-spectrum-ai", "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss"),
    ("theregister-ai", "https://www.theregister.com/software/ai_ml/headlines.atom"),
    ("semianalysis", "https://semianalysis.com/feed/"),
    ("cloudflare-blog", "https://blog.cloudflare.com/rss/"),
    ("lobsters", "https://lobste.rs/rss"),
    ("arxiv-cs-lg", "https://export.arxiv.org/rss/cs.LG"),
    ("sspai", "https://sspai.com/feed"),
    ("ruanyifeng", "https://www.ruanyifeng.com/blog/atom.xml"),
    ("36kr-newsflash", "https://36kr.com/feed-newsflash"),
    ("hn-100", "https://hnrss.org/newest?points=100"),
    ("hn-llm", "https://hnrss.org/newest?q=LLM+OR+model&points=30"),
    ("huggingface-papers", "https://huggingface.co/papers/rss"),
    ("openai-index", "https://openai.com/index/rss.xml"),
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
