#!/usr/bin/env python3
"""Probe free translation endpoints from a runner.

A 200 is not enough - each probe must return actual Chinese text.
"""
import json
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; frontier-brief/1.0; +https://github.com/Kyriezhu111/frontier-brief)"
SAMPLE = "Wavelength-Multiplexed Nonlinear Computing with a Single-Layer Diffractive Optical Processor"
SAMPLE2 = "Huawei unveils new chip technologies as Chinese firm steps up the AI race with Nvidia"


def show(name, out):
    print(f"  {name:<22} {out}", flush=True)


def probe_gtx_single():
    url = ("https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="
           + urllib.parse.quote(SAMPLE))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(seg[0] for seg in data[0] if seg and seg[0])


def probe_gtx_multi():
    """One request, many texts - drastically fewer round trips."""
    qs = urllib.parse.urlencode(
        [("client", "gtx"), ("sl", "en"), ("tl", "zh-CN"), ("dt", "t")]
        + [("q", SAMPLE), ("q", SAMPLE2)]
    )
    req = urllib.request.Request("https://translate.googleapis.com/translate_a/t?" + qs,
                                 headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode("utf-8")
    return body[:220]


def probe_mymemory():
    url = ("https://api.mymemory.translated.net/get?langpair=en|zh-CN&q="
           + urllib.parse.quote(SAMPLE))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    return str(data.get("responseData", {}).get("translatedText"))[:120]


def probe_lingva():
    url = "https://lingva.ml/api/v1/en/zh/" + urllib.parse.quote(SAMPLE)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return str(json.loads(r.read().decode("utf-8")).get("translation"))[:120]


def probe_simplytranslate():
    url = ("https://simplytranslate.org/api/translate?engine=google&from=en&to=zh&text="
           + urllib.parse.quote(SAMPLE))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return str(json.loads(r.read().decode("utf-8")).get("translated-text"))[:120]


def run(name, fn):
    try:
        out = fn()
        show(name, ("OK   " + out) if out else "OK   but empty")
    except Exception as e:  # noqa: BLE001
        show(name, f"FAIL {type(e).__name__}: {str(e)[:90]}")


if __name__ == "__main__":
    print("translation endpoint probes", flush=True)
    run("gtx-single", probe_gtx_single)
    run("gtx-multi", probe_gtx_multi)
    run("mymemory", probe_mymemory)
    run("lingva.ml", probe_lingva)
    run("simplytranslate", probe_simplytranslate)
