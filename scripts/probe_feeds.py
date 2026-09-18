#!/usr/bin/env python3
"""Probe non-AI candidate feeds from a runner."""
import concurrent.futures
import urllib.error
import urllib.request

UA = "Mozilla/5.0 (compatible; frontier-brief/1.0; +https://github.com/Kyriezhu111/frontier-brief)"
ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8"

FEEDS = [
    ("nature-photonics", "https://www.nature.com/nphoton.rss"),
    ("nature-electronics", "https://www.nature.com/nelectr.rss"),
    ("physicsworld", "https://physicsworld.com/feed/"),
    ("photonics-com", "https://www.photonics.com/rss/"),
    ("semiengineering", "https://semiengineering.com/feed/"),
    ("eetimes", "https://www.eetimes.com/feed/"),
    ("tomshardware", "https://www.tomshardware.com/feeds/all"),
    ("phys-org-tech", "https://phys.org/rss-feed/technology-news/"),
    ("arxiv-optics", "https://export.arxiv.org/rss/physics.optics"),
    ("arxiv-appph", "https://export.arxiv.org/rss/physics.app-ph"),
    ("nofilmschool", "https://nofilmschool.com/feed"),
    ("petapixel", "https://petapixel.com/feed/"),
    ("fstoppers", "https://fstoppers.com/feed"),
    ("diyphotography", "https://www.diyphotography.net/feed/"),
    ("provideocoalition", "https://www.provideocoalition.com/feed/"),
    ("newsshooter", "https://www.newsshooter.com/feed"),
    ("redsharknews", "https://www.redsharknews.com/rss"),
    ("github-trending-all", "https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml"),
    ("quantamagazine", "https://www.quantamagazine.org/feed/"),
    ("sciencedaily", "https://www.sciencedaily.com/rss/all.xml"),
    ("voa-learning-english", "https://learningenglish.voanews.com/api/zq$omekvi_"),
    ("nature-main", "https://www.nature.com/nature.rss"),
    ("guardian-education", "https://www.theguardian.com/education/rss"),
    ("hackaday", "https://hackaday.com/blog/feed/"),
    ("musicradar", "https://www.musicradar.com/feeds/all"),
]


def probe(item):
    name, url = item
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": ACCEPT})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(8000)
            ctype = resp.headers.get("Content-Type", "?")
            kind = "FEED" if ("xml" in ctype or "rss" in ctype or "atom" in ctype) else "HTML?"
            n = max(body.count(b"<item"), body.count(b"<entry"))
            newest = b""
            for tag in (b"<pubDate>", b"<updated>", b"<published>"):
                i = body.find(tag)
                if i >= 0:
                    newest = body[i:i + 60]
                    break
            return (f"{kind:<5} {resp.status} {n:>3}items {ctype[:32]:<32} {name:<22} "
                    f"{url}\n      {newest.decode('utf-8', 'replace')}")
    except urllib.error.HTTPError as e:
        return f"FAIL  {e.code}                                  {name:<22} {url}"
    except Exception as e:  # noqa: BLE001
        return f"FAIL  ---  {type(e).__name__:<30} {name:<22} {url}"


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        for line in pool.map(probe, FEEDS):
            print(line, flush=True)


if __name__ == "__main__":
    main()
