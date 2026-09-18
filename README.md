# frontier-brief

每日自动生成的中文前沿 AI/科技简报，手机直接看：

**https://kyriezhu111.github.io/frontier-brief/**

## 它怎么工作

- GitHub Actions 每天 07:17（北京时间）运行 `scripts/build_brief.py`
- 脚本直连 **30 个墙外一手源**：OpenAI / Google / DeepMind / Google Research /
  Hugging Face / NVIDIA / AWS ML / TechCrunch / The Verge / Ars Technica / WIRED /
  MIT Tech Review / IEEE Spectrum / Techmeme / MIT News / Latent Space / Interconnects /
  Simon Willison / Sebastian Raschka / Hacker News / Lobsters /
  arXiv cs.AI·cs.CL·cs.LG / 量子位 / IT之家 / InfoQ 中文 / 少数派 / 阮一峰 …
- 排序核心是**交叉印证**：同一条新闻被越多独立来源报道，排名越靠前（页面标 `N 家源`）
- 结果写进 `docs/`，由 GitHub Pages 发布，往期自动存档

跑在 GitHub 的服务器上，因此**不需要你自己的电脑开机，也不需要代理**——
而这些源在你本机是连不上的。

## 改什么

| 想做的事 | 改哪里 |
| --- | --- |
| 加自己的关注词（会置顶并标 `关注`） | `config.json` 的 `keywords` |
| 增删信息源 | `scripts/build_brief.py` 顶部的 `FEEDS` |
| 立刻重跑一次 | Actions → daily-brief → Run workflow（可填回看小时数） |
| 调排序手感 | `pick_head()` 的 `per_source_cap` / `threshold`，`FEEDS` 里的权重 |

## 本地验证

```bash
python3 scripts/selftest.py
```

覆盖 RSS/Atom 解析、arXiv 标题清洗、聚类、分类分桶、渲染、以及"慢源不许拖死任务"的超时守卫，
全程不需要联网。
