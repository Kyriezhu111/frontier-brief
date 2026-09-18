# frontier-brief

每日自动生成的中文简报，手机直接看：

**https://kyriezhu111.github.io/frontier-brief/**

## 它怎么工作

- GitHub Actions 每天 07:17（北京时间）运行 `scripts/build_brief.py`
- 直连 **48 个墙外一手源**，跑在 GitHub 的服务器上，因此**不需要你自己的电脑开机，也不需要代理**
- 排序核心是**交叉印证**：同一条新闻被越多独立来源报道，排名越靠前（标 `N 家源`）
- **英文标题自动译成中文**：中文在上、英文原题在下方小字（保留原题，方便核对与搜索）
- 结果写进 `docs/`，由 GitHub Pages 发布，往期自动存档

## 分区

| 分区 | 内容 | 代表性源 |
| --- | --- | --- |
| **跟你有关** | 命中个人关键词的条目，置顶 | 由 `config.json` 的 `keywords` 决定 |
| **值得看** | 当日头条（只从新闻类源里选） | Techmeme、TechCrunch、The Verge、Ars Technica、OpenAI、HN |
| **中文源** | 中文一手/二手报道 | 量子位、IT之家、InfoQ 中文、少数派、阮一峰 |
| **专业 · 光电/物理/半导体** | 光学、光子、半导体、芯片 | Nature Photonics、Physics World、Phys.org、Semiconductor Engineering、Tom's Hardware、arXiv physics.optics / physics.app-ph |
| **创作 · 影像/剪辑/摄影** | 拍摄、剪辑、后期、器材 | PetaPixel、No Film School、Newsshooter、ProVideo Coalition、Fstoppers、DIYPhotography |
| **开发 · 开源/工具** | 开源项目与开发工具 | GitHub Trending、Hackaday、GitHub Blog |
| **科学** | 物理/生物/数学前沿 | Nature、Quanta Magazine、ScienceDaily |
| **研究前沿** | 论文，按相关性排序 | arXiv cs.AI / cs.CL / cs.LG、BAIR |
| **其他** | 兜底 | 全部剩余条目 |

另有 Hugging Face、NVIDIA、AWS ML、Google AI/DeepMind/Research、WIRED、IEEE Spectrum、
MIT Tech Review、MIT News、Latent Space、Interconnects、Simon Willison、Sebastian Raschka、
Lobsters 等源参与"值得看"与"其他"的排序。

## 改什么

| 想做的事 | 改哪里 |
| --- | --- |
| 加自己的关注词（会进「跟你有关」） | `config.json` 的 `keywords`；中文英文都可以，**词越具体越准**（别写 `AI`/`模型`） |
| 增删信息源、调权重 | `scripts/build_brief.py` 顶部的 `FEEDS`（末位布尔值 = 是否只保留含 AI 关键词的条目） |
| 增删分区 | `SECTION_ORDER`（分区顺序与每区条数上限） |
| 调头条手感 | `pick_head()` 的 `per_source_cap` / `threshold`，`NEWS_CATS` |
| 立刻重跑 | Actions → daily-brief → Run workflow（可填回看小时数） |
| 改译名/术语 | `build_brief.py` 里的 `GLOSSARY`（在渲染时生效，改完无需重新翻译） |
| 提高翻译配额 | 仓库 Secret 加 `MYMEMORY_EMAIL`（填邮箱可把每日额度从匿名档提高） |

## 本地验证

```bash
python3 scripts/selftest.py
```

离线覆盖：RSS 2.0 / RSS 1.0（rdf:RDF）/ Atom 解析、arXiv 标题清洗、频道日期回退、
关键词词边界匹配、聚类、分区不重不漏、渲染、以及"慢源不许拖死任务"的超时守卫。

## 维护须知

- **判断一个源是否死亡要看完整年份**：曾经把"最新条目停在 2025-09"的源误判成"今天没更新"。
- **翻译**用 MyMemory 免费接口（Google 的免费端点在 CI 出口 IP 上恒返回 429）。
  只有真正会显示的约 70 条标题会被翻译，译文按标题原文缓存在 `data/translations.json`，
  跨天复用——所以日常运行通常只需要翻译新增的几条，额度压力很小。
- 新增源前先跑 `scripts/probe_feeds.py`（Actions → probe-feeds），它会打印每个 URL 的
  状态码、条目数和内容类型——**在本地猜是猜不出来的**。
- GitHub 的 cron 在整点最拥堵，所以定在 `17 23 * * *`（UTC）。
