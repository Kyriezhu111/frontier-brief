#!/usr/bin/env python3
"""Build the daily frontier AI/tech brief.

Runs on a GitHub Actions runner (outside the GFW), so every source below is a
first-hand source that the user's own machine cannot reach without a proxy.

Ranking philosophy:
  * a story carried by several independent outlets beats a story only one ran
  * no single outlet may dominate the headline section (per-source cap)
  * general-purpose feeds are filtered down to AI/tech items before ranking
  * arXiv is relevance-filtered, otherwise math papers swamp everything

Output: docs/<date>.html (phone), docs/<date>.md (chat/archive), docs/index.html
"""
import argparse
import concurrent.futures
import html
import json
import os
import re
import socket
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

TZ = timezone(timedelta(hours=8))  # Asia/Shanghai
NS = "{http://www.w3.org/2005/Atom}"
DC = "{http://purl.org/dc/elements/1.1/}"
UA = "Mozilla/5.0 (compatible; frontier-brief/1.0; +https://github.com/Kyriezhu111/frontier-brief)"
ACCEPT = "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8"

# urlopen(timeout=) only bounds connect + first byte. A server that trickles a
# response can stall a read forever - which hung a real CI run. A socket-level
# default timeout applies to every recv, so a stalled feed dies instead of
# freezing the whole job.
SOCKET_TIMEOUT = 25
socket.setdefaulttimeout(SOCKET_TIMEOUT)

# id, display name, url, category, weight, ai_only
FEEDS = [
    # --- labs: first-hand ---------------------------------------------------
    ("openai", "OpenAI", "https://openai.com/news/rss.xml", "lab", 4, False),
    ("google-ai", "Google AI", "https://blog.google/technology/ai/rss/", "lab", 4, False),
    ("deepmind", "DeepMind", "https://deepmind.google/blog/rss.xml", "lab", 4, False),
    ("google-research", "Google Research", "https://research.google/blog/rss/", "lab", 3, False),
    ("huggingface", "Hugging Face", "https://huggingface.co/blog/feed.xml", "lab", 3, False),
    ("nvidia", "NVIDIA", "https://developer.nvidia.com/blog/feed/", "lab", 2, True),
    ("aws-ml", "AWS ML", "https://aws.amazon.com/blogs/machine-learning/feed/", "lab", 2, True),
    # --- tech media ---------------------------------------------------------
    ("techcrunch", "TechCrunch", "https://techcrunch.com/category/artificial-intelligence/feed/", "media", 3, True),
    ("verge", "The Verge", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "media", 3, True),
    ("ars", "Ars Technica", "https://arstechnica.com/ai/feed/", "media", 3, True),
    ("wired", "WIRED", "https://www.wired.com/feed/tag/ai/latest/rss", "media", 3, True),
    ("mit-tr", "MIT Tech Review", "https://www.technologyreview.com/feed/", "media", 3, True),
    ("ieee", "IEEE Spectrum", "https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss", "media", 3, True),
    ("techmeme", "Techmeme", "https://www.techmeme.com/feed.xml", "media", 5, True),
    ("semianalysis", "SemiAnalysis", "https://semianalysis.com/feed/", "media", 4, True),
    ("mit-news", "MIT News AI", "https://news.mit.edu/rss/topic/artificial-intelligence2", "media", 3, True),
    # --- practitioner analysis ---------------------------------------------
    ("simonwillison", "Simon Willison", "https://simonwillison.net/atom/everything/", "analysis", 4, True),
    ("latent", "Latent Space", "https://www.latent.space/feed", "analysis", 4, True),
    ("interconnects", "Interconnects", "https://www.interconnects.ai/feed", "analysis", 4, True),
    ("raschka", "Sebastian Raschka", "https://magazine.sebastianraschka.com/feed", "analysis", 3, True),
    ("github-blog", "GitHub Blog", "https://github.blog/feed/", "analysis", 2, True),
    # --- community ----------------------------------------------------------
    ("hn", "Hacker News", "https://hnrss.org/frontpage?points=150", "community", 3, True),
    ("lobsters", "Lobsters", "https://lobste.rs/rss", "community", 1, True),
    # --- research -----------------------------------------------------------
    ("arxiv-ai", "arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI", "research", 1, False),
    ("arxiv-cl", "arXiv cs.CL", "https://export.arxiv.org/rss/cs.CL", "research", 1, False),
    ("arxiv-lg", "arXiv cs.LG", "https://export.arxiv.org/rss/cs.LG", "research", 1, False),
    # --- Chinese sources (runner reaches them; the user's machine does not) --
    ("qbitai", "量子位", "https://www.qbitai.com/feed", "cn", 3, False),
    ("ithome", "IT之家", "https://www.ithome.com/rss/", "cn", 2, True),
    ("infoq-cn", "InfoQ 中文", "https://www.infoq.cn/feed", "cn", 2, True),
    ("sspai", "少数派", "https://sspai.com/feed", "cn", 2, True),
    ("ruanyifeng", "阮一峰", "https://www.ruanyifeng.com/blog/atom.xml", "cn", 3, False),
]

# Lab and analysis blogs publish every few days, not every few hours. With a
# plain 36-48h window they would almost never appear; recency scoring still
# keeps them out of the top section.
WINDOW_MULT = {"lab": 4, "analysis": 4}

CATEGORY_LABEL = {
    "lab": "实验室一手", "media": "科技媒体", "analysis": "从业者分析",
    "community": "社区热度", "research": "研究前沿", "cn": "中文源",
}

WEIGHT = {sid: w for sid, _, _, _, w, _ in FEEDS}
CATEGORY = {sid: cat for sid, _, _, cat, _, _ in FEEDS}
AI_ONLY = {sid: flag for sid, _, _, _, _, flag in FEEDS}

AI_TERMS = [
    "ai", "a.i.", "llm", "gpt", "claude", "gemini", "grok", "qwen", "llama", "deepseek",
    "mistral", "openai", "anthropic", "deepmind", "hugging face", "model", "models",
    "agent", "agents", "agentic", "neural", "machine learning", "deep learning",
    "transformer", "diffusion", "inference", "fine-tune", "fine-tuning", "benchmark",
    "dataset", "embedding", "rag", "prompt", "robotics", "copilot", "chatbot",
    "人工智能", "大模型", "模型", "智能体", "算法", "机器学习", "深度学习",
    "算力", "芯片", "机器人", "语料", "推理",
]

RESEARCH_TERMS = [
    "agent", "llm", "language model", "reasoning", "benchmark", "reinforcement",
    "alignment", "multimodal", "diffusion", "retrieval", "rag", "context", "inference",
    "fine-tun", "quantization", "distill", "evaluation", "safety", "hallucination",
    "tool use", "code generation", "moe", "transformer", "vision-language",
]

STOP = set(
    """a an the of to in on for and or with at by from is are was were be been being
this that these those it its as into about over after before new how why what when
who will can may says said say more most than then them they their there here out
up down off again very just don now use uses used using get gets got make makes
made your you we our us not but all any own some such only also""".split()
)


def matches_ai(text):
    low = (text or "").lower()
    for term in AI_TERMS:
        if re.search(r"[\u4e00-\u9fff]", term):
            if term in low:
                return True
        elif re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", low):
            return True
    return False


def matches_research(text):
    low = (text or "").lower()
    return any(t in low for t in RESEARCH_TERMS)


# --------------------------------------------------------------------------- #
# fetching and parsing
# --------------------------------------------------------------------------- #
def fetch(url, timeout=SOCKET_TIMEOUT):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": ACCEPT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def text_of(node):
    if node is None:
        return ""
    return html.unescape("".join(node.itertext())).strip()


def find_child(node, *names):
    for name in names:
        found = node.find(name)
        if found is not None:
            return found
    return None


def strip_html(raw):
    raw = re.sub(r"<[^>]+>", " ", raw or "")
    return html.unescape(re.sub(r"\s+", " ", raw)).strip()


def parse_date(value):
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        pass
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def clean_title(title):
    title = strip_html(title)
    title = re.sub(r"\s*\(arXiv:[\d.]+v?\d*\s*\[[^\]]*\]\)\s*$", "", title)
    title = re.sub(r"\s*\((?:www\.)?[a-z0-9.-]+\.[a-z]{2,}\)\s*$", "", title)
    title = re.sub(r"^(Show HN|Ask HN):\s*", "", title, flags=re.I)
    return title.strip()


def parse_feed(source_id, data):
    root = ElementTree.fromstring(data)
    entries = []
    nodes = list(root.iter("item")) or list(root.iter(NS + "entry"))
    for node in nodes:
        title = clean_title(text_of(find_child(node, "title", NS + "title")))
        link = ""
        link_node = find_child(node, "link", NS + "link")
        if link_node is not None:
            link = (link_node.get("href") or "").strip() or text_of(link_node)
        if not link:
            for cand in node.findall(NS + "link"):
                if cand.get("rel") in (None, "alternate"):
                    link = (cand.get("href") or "").strip()
                    break
        published = None
        for tag in ("pubDate", NS + "published", NS + "updated",
                    "published", "updated", DC + "date"):
            published = parse_date(text_of(find_child(node, tag)))
            if published:
                break
        summary = strip_html(text_of(
            find_child(node, "description", NS + "summary", NS + "content", "content")))[:400]
        if title and link:
            entries.append({
                "source": source_id, "title": title, "link": link,
                "published": published, "summary": summary,
            })
    return entries


def gather(hours, per_feed_cap=40, budget=150):
    now = datetime.now(timezone.utc)
    items, health = [], []
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=10)
    started = {}
    futures = {}
    for sid, name, url, _, _, _ in FEEDS:
        fut = pool.submit(fetch, url)
        futures[fut] = (sid, name, url)
        started[fut] = time.monotonic()

    done, pending = concurrent.futures.wait(futures, timeout=budget)
    for fut in pending:
        sid, name, url = futures[fut]
        fut.cancel()
        health.append({"source": sid, "name": name, "ok": False, "parsed": 0, "dated": 0,
                       "fresh": 0, "count": 0, "ms": int(budget * 1000),
                       "error": f"Timeout: exceeded {budget}s budget"})
    pool.shutdown(wait=False, cancel_futures=True)

    for fut in done:
        sid, name, url = futures[fut]
        ms = int((time.monotonic() - started[fut]) * 1000)
        try:
            entries = parse_feed(sid, fut.result())
        except Exception as exc:  # noqa: BLE001 - one bad feed must not kill the run
            health.append({"source": sid, "name": name, "ok": False, "parsed": 0,
                           "dated": 0, "fresh": 0, "count": 0, "ms": ms,
                           "error": f"{type(exc).__name__}: {exc}"})
            continue
        dated = [e for e in entries if e["published"]]
        window = hours * WINDOW_MULT.get(CATEGORY.get(sid, ""), 1)
        fresh = [e for e in dated if e["published"] >= now - timedelta(hours=window)]
        pre_filter = len(fresh)
        if AI_ONLY.get(sid):
            fresh = [e for e in fresh if matches_ai(e["title"] + " " + e["summary"])]
        elif CATEGORY.get(sid) == "research":
            fresh = [e for e in fresh if matches_research(e["title"] + " " + e["summary"])]
        fresh = fresh[:per_feed_cap]
        newest = max((e["published"] for e in dated), default=None)
        health.append({"source": sid, "name": name, "ok": True, "count": len(fresh),
                       "parsed": len(entries), "dated": len(dated),
                       "fresh_all": pre_filter, "ms": ms,
                       "newest": newest.astimezone(TZ).strftime("%m-%d %H:%M") if newest else "-"})
        for e in fresh:
            e["url"] = url
            items.append(e)
    items.sort(key=lambda x: x["published"], reverse=True)
    return items, health


# --------------------------------------------------------------------------- #
# clustering: cross-source corroboration is the ranking signal
# --------------------------------------------------------------------------- #
def word_tokens(s):
    s = re.sub(r"\([^)]*\)", " ", s.lower())
    return {w for w in re.findall(r"[a-z0-9][a-z0-9\-\.\+']{2,}", s) if w not in STOP}


def cjk_tokens(s):
    chars = re.findall(r"[\u4e00-\u9fff]", s)
    return {chars[i] + chars[i + 1] for i in range(len(chars) - 1)}


def tokens_of(s):
    return word_tokens(s) | cjk_tokens(s)


def similar(a, b):
    if not a or not b:
        return False
    inter, union = len(a & b), len(a | b)
    if union == 0:
        return False
    j = inter / union
    return j >= 0.45 or (inter >= 3 and j >= 0.28)


def cluster(items):
    clusters = []
    for item in items:
        toks = tokens_of(item["title"])
        for c in clusters:
            if item["source"] in c["sources"]:
                continue
            if similar(toks, c["tokens"]):
                c["items"].append(item)
                c["sources"].add(item["source"])
                c["tokens"] |= toks
                break
        else:
            clusters.append({"items": [item], "sources": {item["source"]}, "tokens": toks})
    return clusters


def primary_source(c):
    return max(c["items"], key=lambda i: WEIGHT.get(i["source"], 1))["source"]


def score_cluster(c, keywords):
    distinct = len(c["sources"])
    score = sum(WEIGHT.get(s, 1) for s in c["sources"]) + 4.0 * (distinct - 1)
    newest = max(i["published"] for i in c["items"])
    age_h = (datetime.now(timezone.utc) - newest).total_seconds() / 3600
    if age_h <= 12:
        score += 1.5
    elif age_h <= 24:
        score += 0.5
    blob = " ".join(i["title"] + " " + i["summary"] for i in c["items"]).lower()
    c["keywords"] = [k for k in keywords if k.lower() in blob]
    if c["keywords"]:
        score += 6.0
    c["score"] = score
    c["distinct"] = distinct
    c["newest"] = newest
    c["primary"] = primary_source(c)
    c["categories"] = {CATEGORY.get(s, "media") for s in c["sources"]}
    return c


def pick_head(clusters, limit=10, per_source_cap=2, threshold=5.5):
    """Corroborated stories first, then strong single-source ones - but no
    outlet may take more than `per_source_cap` slots (kills the
    corporate-blog flood)."""
    ranked = sorted(clusters, key=lambda c: (c["distinct"] >= 2, c["score"]), reverse=True)
    out, used = [], {}
    for c in ranked:
        if c["score"] < threshold:
            continue
        if used.get(c["primary"], 0) >= per_source_cap:
            continue
        used[c["primary"]] = used.get(c["primary"], 0) + 1
        out.append(c)
        if len(out) >= limit:
            break
    return out


def research_rank(c):
    title = c["items"][0]["title"].lower()
    rel = sum(1 for t in RESEARCH_TERMS if t in title)
    return (rel > 0, rel, c["newest"])


def build_sections(clusters, keywords):
    head = pick_head(clusters)
    rest = [c for c in clusters if c not in head]
    cn = [c for c in rest if c["categories"] <= {"cn"}]
    rest = [c for c in rest if c not in cn]
    research = [c for c in rest if c["categories"] <= {"research"}]
    other = [c for c in rest if c not in research]
    cn.sort(key=lambda c: c["score"], reverse=True)
    research.sort(key=research_rank, reverse=True)
    other.sort(key=lambda c: c["score"], reverse=True)
    return head, cn, research, other


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0e1116;color:#e6e9ef;font:16px/1.6 -apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:26px 18px 70px}
header h1{font-size:26px;line-height:1.25;margin:0 0 6px}
.date{color:#8b94a7;font-size:14px}
.back{color:#7aa2f7;text-decoration:none;font-size:14px}
h2{font-size:13px;letter-spacing:.14em;color:#8b94a7;font-weight:600;text-transform:uppercase;
   margin:34px 0 12px;padding-bottom:8px;border-bottom:1px solid #1e2431}
.item{padding:13px 0;border-bottom:1px solid #171d27}
.item:last-child{border-bottom:0}
.item a{color:#e6e9ef;text-decoration:none;font-weight:600;font-size:17px;line-height:1.45}
.item a:visited{color:#c3c9d6}
.meta{margin-top:5px;color:#8b94a7;font-size:12.5px}
.src{color:#9fb0d0}
.badge{display:inline-block;background:#1b2740;color:#7aa2f7;border-radius:4px;
       padding:1px 6px;font-size:11px;margin-right:6px;vertical-align:1px}
.kw{background:#2a2140;color:#c4a8ff}
footer{margin-top:44px;padding-top:16px;border-top:1px solid #1e2431;color:#6b7484;font-size:12.5px}
.empty{color:#8b94a7;font-size:14px}
"""


def esc(s):
    return html.escape(s or "", quote=True)


def render_items(clusters, limit=None):
    out = []
    for c in (clusters[:limit] if limit else clusters):
        primary = max(c["items"], key=lambda i: WEIGHT.get(i["source"], 1))
        badges = []
        if c["distinct"] >= 2:
            badges.append(f'<span class="badge">{c["distinct"]} 家源</span>')
        for k in c["keywords"]:
            badges.append(f'<span class="badge kw">关注：{esc(k)}</span>')
        srcs = " · ".join(sorted(c["sources"], key=lambda s: -WEIGHT.get(s, 1)))
        local = c["newest"].astimezone(TZ).strftime("%m-%d %H:%M")
        out.append(
            '<div class="item">'
            f'<a href="{esc(primary["link"])}" target="_blank" rel="noopener">{esc(primary["title"])}</a>'
            f'<div class="meta">{"".join(badges)}<span class="src">{esc(srcs)}</span> · {local}</div>'
            "</div>"
        )
    return "\n".join(out) or '<p class="empty">这个时间段没有内容。</p>'


def render_html(today, head, cn, research, other, health, total_items):
    parts = [
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\">",
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        '<meta name="theme-color" content="#0e1116">',
        f"<title>前沿简报 {today}</title><style>{CSS}</style></head><body><div class=\"wrap\">",
        "<header>",
        f"<h1>前沿简报</h1><div class=\"date\">{today} · 墙外一手源 · {total_items} 条信号</div>",
        "</header>",
        "<h2>值得看</h2>", render_items(head, limit=10),
    ]
    if cn:
        parts += ["<h2>中文源</h2>", render_items(cn, limit=8)]
    if research:
        parts += ["<h2>研究前沿</h2>", render_items(research, limit=6)]
    if other:
        parts += ["<h2>其他</h2>", render_items(other, limit=16)]
    ok = sum(1 for h in health if h["ok"])
    bad = [h["name"] for h in health if not h["ok"]]
    parts.append("<footer>")
    parts.append(f"采集源 {ok}/{len(health)} 正常。")
    if bad:
        parts.append(f"这次没取到的：{esc('、'.join(bad))}。")
    parts.append("<br>排序：被越多独立来源报道越靠前；同一来源最多占 2 条。")
    parts.append('<br><a class="back" href="./">← 往期</a>')
    parts.append("</footer></div></body></html>")
    return "\n".join(parts)


def render_index(dates):
    rows = "\n".join(f'<div class="item"><a href="./{d}.html">{d}</a></div>' for d in dates) \
        or '<p class="empty">还没有简报。</p>'
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
        f"<title>前沿简报 · 往期</title><style>{CSS}</style></head><body><div class=\"wrap\">"
        "<header><h1>前沿简报</h1><div class=\"date\">往期</div></header>"
        f"<h2>存档</h2>{rows}</div></body></html>"
    )


def render_markdown(today, head, cn, research, other, total_items, ok, total_feeds):
    def line(c):
        primary = max(c["items"], key=lambda i: WEIGHT.get(i["source"], 1))
        tag = f"[{c['distinct']} 家源] " if c["distinct"] >= 2 else ""
        kw = f" ★{','.join(c['keywords'])}" if c["keywords"] else ""
        return f"- {tag}[{primary['title']}]({primary['link']}) — {' / '.join(sorted(c['sources']))}{kw}"

    out = [f"# 前沿简报 · {today}", "",
           f"墙外一手源直采 · {total_items} 条信号 · 采集源 {ok}/{total_feeds} 正常", "",
           "## 值得看", ""]
    out += [line(c) for c in head] or ["- （无）"]
    if cn:
        out += ["", "## 中文源", ""] + [line(c) for c in cn[:8]]
    if research:
        out += ["", "## 研究前沿", ""] + [line(c) for c in research[:6]]
    if other:
        out += ["", "## 其他", ""] + [line(c) for c in other[:16]]
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=36)
    ap.add_argument("--out", default="docs")
    ap.add_argument("--keywords", default="")
    args = ap.parse_args()

    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    cfg = os.path.join(os.path.dirname(__file__), "..", "config.json")
    if os.path.exists(cfg):
        try:
            with open(cfg, encoding="utf-8") as fh:
                keywords += json.load(fh).get("keywords", [])
        except Exception as exc:  # noqa: BLE001
            print(f"config.json ignored: {exc}", file=sys.stderr)
    keywords = sorted(set(keywords))

    os.makedirs(args.out, exist_ok=True)
    items, health = gather(args.hours)
    clusters = [score_cluster(c, keywords) for c in cluster(items)]
    head, cn, research, other = build_sections(clusters, keywords)

    today = datetime.now(TZ).strftime("%Y-%m-%d")
    ok = sum(1 for h in health if h["ok"])

    with open(os.path.join(args.out, f"{today}.html"), "w", encoding="utf-8") as fh:
        fh.write(render_html(today, head, cn, research, other, health, len(items)))
    with open(os.path.join(args.out, f"{today}.md"), "w", encoding="utf-8") as fh:
        fh.write(render_markdown(today, head, cn, research, other, len(items), ok, len(health)))

    dates = sorted(
        (f[:-5] for f in os.listdir(args.out) if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.html", f)),
        reverse=True,
    )
    with open(os.path.join(args.out, "index.html"), "w", encoding="utf-8") as fh:
        fh.write(render_index(dates))

    print(f"items={len(items)} clusters={len(clusters)} head={len(head)} cn={len(cn)} "
          f"research={len(research)} other={len(other)} feeds_ok={ok}/{len(health)}")
    print("head sources: " + ", ".join(c["primary"] for c in head))
    print("per feed (parsed/dated/fresh):")
    for h in sorted(health, key=lambda x: x["source"]):
        flag = "  <-- NOTHING KEPT" if h["ok"] and h["count"] == 0 else ""
        print(f"  {h['source']:<16} parsed={h.get('parsed', 0):<4} dated={h.get('dated', 0):<4} "
              f"in_window={h.get('fresh_all', 0):<4} kept={h.get('count', 0):<4} "
              f"newest={h.get('newest', '-'):<12} {h.get('ms', 0):>6}ms{flag}")
    slow = sorted((h for h in health if h["ok"]), key=lambda x: -x.get("ms", 0))[:5]
    print("slowest feeds: " + ", ".join(f"{h['source']}={h['ms']}ms" for h in slow))
    for h in health:
        if not h["ok"]:
            print(f"  feed failed: {h['name']}: {h['error']}")


if __name__ == "__main__":
    main()
