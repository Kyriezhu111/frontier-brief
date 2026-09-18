#!/usr/bin/env python3
"""Offline self-test: parser + clustering + rendering, no network."""
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_brief as b  # noqa: E402

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Hello RSS</title><link>https://example.com/b</link>
<pubDate>Thu, 18 Sep 2026 01:00:00 GMT</pubDate><description>Desc here</description></item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Hello Atom</title><link rel="alternate" href="https://example.com/a"/>
<updated>2026-09-18T01:00:00Z</updated><summary>Some summary</summary></entry></feed>"""

ARXIV = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Scaling Laws Revisited (arXiv:2609.01234v1 [cs.AI])</title>
<link>https://arxiv.org/abs/2609.01234</link>
<pubDate>Thu, 18 Sep 2026 02:00:00 GMT</pubDate><description>abstract text</description></item>
</channel></rss>"""

# Nature serves RSS 1.0 (rdf:RDF) - a format that silently yielded 0 entries
# until the parser learned about the RSS 1.0 namespace.
RSS1_FEED = """<?xml version="1.0"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:dc="http://purl.org/dc/elements/1.1/"
         xmlns="http://purl.org/rss/1.0/">
  <channel rdf:about="https://example.org/"><title>Nature</title>
    <dc:date>2026-09-18T01:00:00Z</dc:date></channel>
  <item rdf:about="https://example.org/a1"><title>Photonic chip breakthrough</title>
    <link>https://example.org/a1</link><dc:date>2026-09-17T20:00:00Z</dc:date>
    <description>desc</description></item>
  <item rdf:about="https://example.org/a2"><title>Undated digest entry</title>
    <link>https://example.org/a2</link><description>desc</description></item>
</rdf:RDF>"""


def expect(cond, label):
    print(("PASS  " if cond else "FAIL  ") + label)
    return bool(cond)


def test_budget_guard():
    """A feed that never returns must not hang the job."""
    orig_feeds, orig_fetch = b.FEEDS, b.fetch
    b.FEEDS = [("slow", "Slow Feed", "http://127.0.0.1:9/never", "media", 1, False)]
    b.fetch = lambda url, timeout=1: (time.sleep(4), b"")[1]
    try:
        items, health = b.gather(24, budget=1)
    finally:
        b.FEEDS, b.fetch = orig_feeds, orig_fetch
    return (items == [] and len(health) == 1 and health[0]["ok"] is False
            and "Timeout" in health[0]["error"])


def main():
    ok = True
    rss = b.parse_feed("techcrunch", RSS)
    atom = b.parse_feed("verge", ATOM)
    arx = b.parse_feed("arxiv-ai", ARXIV)
    r1 = b.parse_feed("nature-main", RSS1_FEED)

    ok &= expect(len(rss) == 1 and rss[0]["title"] == "Hello RSS", "rss 2.0 parses")
    ok &= expect(rss[0]["published"] is not None, "rss pubDate parses")
    ok &= expect(len(atom) == 1, "atom entry parses")
    ok &= expect(atom and atom[0]["title"] == "Hello Atom", "atom title found")
    ok &= expect(atom and atom[0]["link"] == "https://example.com/a", "atom link found")
    ok &= expect(atom and atom[0]["published"] is not None, "atom updated parses")
    ok &= expect(arx and arx[0]["title"] == "Scaling Laws Revisited", "arxiv suffix stripped")
    ok &= expect(len(r1) == 2, "rss 1.0 (rdf:RDF) items parse")
    ok &= expect(r1 and r1[0]["link"] == "https://example.org/a1", "rss 1.0 link found")
    ok &= expect(r1 and r1[0]["published"] is not None, "rss 1.0 dc:date parses")
    ok &= expect(r1[1]["published"] is not None, "undated item falls back to channel date")

    ok &= expect(b.keyword_hit("Anki", "lige-gr ranking to generative recommendation") is False,
                  "ascii keyword does not match inside another word")
    ok &= expect(b.keyword_hit("Anki", "spaced repetition with anki today") is True,
                  "ascii keyword matches on word boundary")
    ok &= expect(b.keyword_hit("Agent", "rogue agents everywhere") is True,
                  "ascii keyword allows plural")
    ok &= expect(b.keyword_hit("光电", "我院光电信息科学与工程专业") is True,
                  "cjk keyword matches as substring")

    now = datetime.now(timezone.utc)

    def mk(source, hours_ago, title):
        return {"source": source, "title": title, "link": "https://x/" + source,
                "published": now - timedelta(hours=hours_ago), "summary": "", "url": ""}

    items = [
        mk("techcrunch", 3, "OpenAI ships GPT-6 Astra to all users"),
        mk("verge", 5, "OpenAI ships GPT-6 Astra to all users worldwide"),
        mk("openai", 20, "Introducing GPT-6 Astra"),
        mk("qbitai", 4, "豆包发布新一代模型"),
        mk("arxiv-ai", 30, "Efficient attention for long context"),
        mk("arxiv-cl", 12, "Long context attention revisited"),
        mk("hn", 6, "Something entirely unrelated about databases"),
    ]
    clusters = [b.score_cluster(c, ["Astra"]) for c in b.cluster(items)]
    personal, head, buckets, other = b.build_sections(clusters, ["Astra"])
    multi = [c for c in clusters if c["distinct"] >= 2 and len(c["categories"]) > 1]

    ok &= expect(len(clusters) < len(items), "clustering merges near-duplicates")
    ok &= expect(any(c["distinct"] >= 2 for c in clusters), "cross-source merge works")
    ok &= expect(all(len(c["categories"]) <= 3 for c in clusters), "categories computed")
    ok &= expect(any(c["keywords"] for c in clusters), "keyword tagging works")
    ok &= expect(all(c["keywords"] for c in personal), "personal section only holds radar hits")
    ok &= expect(all(
        all(len(c["categories"]) == 1 for c in g) for _, g in buckets
    ), "every bucket is single-category")
    placed = [id(c) for c in personal] + [id(c) for c in head]
    placed += [id(c) for _, g in buckets for c in g] + [id(c) for c in other]
    ok &= expect(len(placed) == len(set(placed)), "no cluster is shown twice")
    ok &= expect(set(placed) == {id(c) for c in clusters},
                  "every cluster lands in exactly one section")
    ok &= expect(bool(multi) is False, "no mixed-category cluster leaked into a bucket")

    md = b.render_markdown("2026-09-18", personal, head, buckets, other, len(items), 35, 36)
    ok &= expect(md.startswith("# 前沿简报"), "markdown renders")
    ok &= expect("## 跟你有关" in md, "personal section renders in markdown")
    html_out = b.render_html("2026-09-18", personal, head, buckets, other,
                             [{"source": "x", "name": "X", "ok": True, "count": 1}], len(items))
    ok &= expect("<html" in html_out and "</html>" in html_out, "html renders")
    ok &= expect("{" not in html_out.split("<style>")[0], "no f-string leakage")
    ok &= expect(test_budget_guard(), "slow feed hits the budget guard instead of hanging")

    print("\nALL PASS" if ok else "\nSOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
