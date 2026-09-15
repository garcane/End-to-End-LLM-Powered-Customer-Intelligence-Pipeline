# Free News APIs for Developers — 2026 Reference

A consolidated reference of free news API tiers, quotas, and use cases. Compiled from a 2026 comparison of news APIs plus additional sources useful for developer projects (Hacker News, spaceflight, SpaceX launches, and community-maintained aggregators).

> **Note:** Free-tier terms, quotas, and rate limits change frequently. Always verify the current pricing and terms of service on each provider's website before building on top of them.

---

## Quick Comparison Table

| Provider | Free Tier | Rate Limit | Sources | Best For |
|---|---|---|---|---|
| [NewsAPI.org](https://newsapi.org) | 1,000 req/day | Dev use only | 80,000+ | Prototyping, internal tools |
| [GNews.io](https://gnews.io) | 100 req/day | 10/min | 60,000+ | Simple projects |
| [Currents API](https://currentsapi.services) | ~600 req/day (trial) | — | 14,000+ | Real-time global news |
| [TheNewsAPI](https://www.thenewsapi.com) | 100 req/day | — | 50,000+ | Multi-language / multilingual |
| [Mediastack](https://mediastack.com) | 100 req/month | — | 7,500+ | Budget apps, evaluation |
| [Newscatcher](https://newscatcher.com) | 1,000 req/month | 1/sec | 70,000+ | Research |
| [Google News RSS](https://news.google.com/rss) | Unlimited | — | Google | RSS integration |
| [Bing News Search](https://www.microsoft.com/en-us/bing/apis/bing-news-search-api) | 1,000 req/month | 3 req/sec | Bing | Microsoft ecosystem |
| [NewsData.io](https://newsdata.io) | 500 req/day | 10 articles/req | 92,000+ | International monitoring |
| [WorldNewsAPI](https://worldnewsapi.com) | 100 req/day | 1 point/sec | 200+ countries | Rapid validation |
| [The Guardian Open Platform](https://open-platform.theguardian.com) | 5,000 calls/day | 12 calls/sec | Guardian archive | Single-publisher depth |
| [GDELT Project](https://www.gdeltproject.org) | Unlimited (research) | — | 100+ languages | Archival research, AI training |
| [Marketaux](https://www.marketaux.com) | Limited free tier | — | Finance-focused | Financial / stock news |
| [AllNewsAPI](https://allnewsapi.com) | Limited free tier | — | 250,000+ publishers | Proof of concept |
| [NewsMesh](https://newsmesh.co) | Free starter plan | — | Thousands | Dashboards, demos |
| [Hacker News API](https://github.com/HackerNews/API) | Unlimited | — | Hacker News | Tech / startup news |
| [Spaceflight News API](https://api.spaceflightnewsapi.net/v3/documentation) | Unlimited | — | Space news sites | Spaceflight news |
| [SpaceX API](https://github.com/r-spacex/SpaceX-API) | Unlimited | — | SpaceX launches | Rocket launch data |
| [SauravKanchan/NewsAPI](https://github.com/SauravKanchan/NewsAPI) | Self-hosted | — | Google News | Community aggregator |

---

## Part 1 — General News Aggregators

### 1. NewsAPI.org
- **Best for:** Prototyping, internal tools, academic projects
- **Free quota:** 1,000 requests/day
- **Limitations:** "Development use only" — no commercial use, no client-side exposure, no historical data beyond 1 month, attribution required
- **Website:** https://newsapi.org

Endpoints: `everything`, `top-headlines`, `sources`

```bash
curl "https://newsapi.org/v2/everything?q=tesla&from=2026-02-17&sortBy=publishedAt&apiKey=API_KEY"
```

```bash
curl "https://newsapi.org/v2/top-headlines?country=us&category=business&apiKey=API_KEY"
```

---

### 2. GNews.io
- **Best for:** Startups, low-cost apps, multi-language support
- **Free quota:** 100 requests/day
- **Limitations:** Free tier bars commercial use; sources narrower than larger aggregators
- **Website:** https://gnews.io

Endpoints: `search`, `top-headlines`. Filters cover country, language, and category. JSON over HTTPS.

---

### 3. Currents API
- **Best for:** Lightweight real-time monitoring, news tickers, dashboard widgets
- **Free quota:** Trial tier with limited requests (approx. 600/day in some plans)
- **Limitations:** Narrower source breadth; tight trial limits require upgrading for production
- **Website:** https://currentsapi.services

Best fit for "what's new now" apps — immediacy over archival depth.

---

### 4. TheNewsAPI
- **Best for:** Small personal projects, daily data modeling, low-volume tickers
- **Free quota:** 100 requests/day
- **Limitations:** Low daily limit; caps articles per request; historical depth may not suit niche research
- **Website:** https://www.thenewsapi.com

Endpoints: headlines, top stories, all articles. Standard language/source/date parameters.

---

### 5. Mediastack
- **Best for:** Low-volume apps, API evaluation, multi-language projects
- **Free quota:** 100 requests/month
- **Limitations:** 30-minute data delay, no historical data on free tier, non-commercial only, attribution required
- **Website:** https://mediastack.com

7,500+ sources across 50 countries. Free tier is for evaluation, not intensive use.

---

### 6. Newscatcher
- **Best for:** Research
- **Free quota:** 1,000 requests/month
- **Rate limit:** 1 request/second
- **Sources:** 70,000+
- **Website:** https://newscatcher.com

---

### 7. NewsData.io
- **Best for:** Small projects, international news monitoring, multilingual feeds
- **Free quota:** 500 requests/day with up to 10 articles per request
- **Limitations:** Query character limits; historical and real-time endpoints reserved for paid tiers; coverage varies by region
- **Website:** https://newsdata.io

Search historical news data back to January 2018 across 92,000+ sources. JSON or Excel output.

```bash
curl "https://newsdata.io/api/1/news?apikey=YOUR_KEY&q=keyword&country=us"
```

---

### 8. WorldNewsAPI
- **Best for:** Rapid project validation, hobbyist apps, developers new to news APIs
- **Free quota:** 100 requests/day, 1 point/second
- **Limitations:** Daily caps; may lack historical depth and advanced cleaning for BI/AI training
- **Website:** https://worldnewsapi.com

No credit card needed for onboarding. Filter by keyword, date range, source domain. Sources in 86+ languages across 200+ countries.

---

### 9. The Guardian Open Platform (Content API)
- **Best for:** Academic research, content analysis, non-commercial apps needing high-quality journalism
- **Free quota:** 5,000 calls/day, 12 calls/second
- **Limitations:** Non-commercial only, attribution required, single-publisher (no multi-source coverage)
- **Website:** https://open-platform.theguardian.com

Exposes The Guardian's own archive of 2M+ pieces of content, tags, and sections. Excellent for textual analysis or knowledge graphs.

```bash
curl "https://content.guardianapis.com/search?q=climate&api-key=YOUR_KEY"
```

---

### 10. GDELT Project APIs
- **Best for:** Academic research, large-scale data analysis, AI model training
- **Free quota:** Unlimited (research-grade)
- **Limitations:** Complex to implement; not a headline API; scattered documentation
- **Website:** https://www.gdeltproject.org

Monitors news in 100+ languages, identifying people, locations, organizations, themes, and emotions. JSON and GeoJSON APIs.

---

### 11. Marketaux
- **Best for:** Financial dashboards, fintech apps, stock-specific news tracking
- **Free quota:** Limited free tier for evaluation
- **Limitations:** Limited historical data; fewer endpoints; finance-only (not general news)
- **Website:** https://www.marketaux.com

Covers equities, tickers, and economic topics. JSON responses include publisher details, ticker mentions, and precise timestamps — useful for sentiment analysis.

---

### 12. AllNewsAPI
- **Best for:** Mobile applications, budget-conscious projects, proof of concept
- **Free quota:** Limited free tier
- **Limitations:** Newer service — long-term reliability and source breadth less proven
- **Website:** https://allnewsapi.com

Filters for keyword, source, and language. 196 countries, 250,000+ publishers, 29 categories, 22 languages.

---

### 13. NewsMesh
- **Best for:** Dashboards, proofs of concept, API evaluation
- **Free quota:** Free starter plan
- **Limitations:** Newer service; review SLAs and support; source breadth and historical depth may not suit enterprise
- **Website:** https://newsmesh.co

Real-time news coverage with structured JSON. Trending endpoint example:

```bash
curl "https://api.newsmesh.co/v2/trending"
```

Response includes `article_id`, `title`, `description`, `link`, `published_date`, `source`, `category`, `topics`, `people`, `author`.

---

## Part 2 — Additional / Specialized APIs

### 14. Hacker News API
- **Best for:** Tech and startup news, developer dashboards
- **Free quota:** Unlimited
- **Base URL:** https://hacker-news.firebaseio.com/v0
- **Docs:** https://github.com/HackerNews/API

Item endpoint example:

```bash
curl "https://hacker-news.firebaseio.com/v0/item/8863.json"
```

Other useful endpoints:
- `https://hacker-news.firebaseio.com/v0/topstories.json`
- `https://hacker-news.firebaseio.com/v0/newstories.json`
- `https://hacker-news.firebaseio.com/v0/askstories.json`
- `https://hacker-news.firebaseio.com/v0/showstories.json`
- `https://hacker-news.firebaseio.com/v0/jobstories.json`

---

### 15. Spaceflight News API
- **Best for:** Spaceflight news, space industry monitoring
- **Free quota:** Unlimited (no key required)
- **Base URL:** https://api.spaceflightnewsapi.net/v3
- **Docs:** https://api.spaceflightnewsapi.net/v3/documentation

Articles endpoint:

```bash
curl "https://api.spaceflightnewsapi.net/v3/articles"
```

Also supports `/articles/count`, `/articles/{id}`, `/blogs`, and `/reports`.

---

### 16. SpaceX API (r-spacex)
- **Best for:** Rocket launch data, mission tracking, aerospace dashboards
- **Free quota:** Unlimited (no key required)
- **Base URL:** https://api.spacexdata.com/v5
- **Docs:** https://github.com/r-spacex/SpaceX-API

Latest launch endpoint:

```bash
curl "https://api.spacexdata.com/v5/launches/latest"
```

Other endpoints:
- `https://api.spacexdata.com/v5/launches`
- `https://api.spacexdata.com/v5/launches/past`
- `https://api.spacexdata.com/v5/launches/upcoming`
- `https://api.spacexdata.com/v5/rockets`
- `https://api.spacexdata.com/v5/crew`
- `https://api.spacexdata.com/v5/starlink`

---

### 17. SauravKanchan/NewsAPI (Community Aggregator)
- **Best for:** Self-hosted news aggregation, Google News scraping
- **Repository:** https://github.com/SauravKanchan/NewsAPI
- **Type:** Open-source, self-hosted (no hosted free tier; you run it)

Community-maintained News API that aggregates Google News headlines. Useful if you want full control over the deployment and don't want to depend on a hosted free tier.

---

### 18. Google News RSS
- **Best for:** RSS integration, no-key quick feeds
- **Free quota:** Unlimited
- **Format:** RSS/XML

Topic feed example:

```
https://news.google.com/rss/search?q=your+topic&hl=en-US&gl=US&ceid=US:en
```

Top headlines:
```
https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en
```

---

### 19. Bing News Search
- **Best for:** Microsoft ecosystem users
- **Free quota:** 1,000 requests/month
- **Rate limit:** 3 requests/second
- **Docs:** https://www.microsoft.com/en-us/bing/apis/bing-news-search-api

> Note: Microsoft has been retiring several Bing Search APIs. Verify availability and migration path (e.g., to Azure AI services) before adopting.

---

## Part 3 — Choosing the Right API

### By use case

| Use case | Recommended |
|---|---|
| General monitoring (broad coverage) | NewsAPI.org, GNews.io, NewsData.io |
| Single-publisher depth | The Guardian Open Platform |
| Finance / stocks | Marketaux |
| Archival research / AI training | GDELT |
| Real-time tickers / alerts | Currents API |
| Tech / startup news | Hacker News API |
| Space / aerospace | Spaceflight News API, SpaceX API |
| RSS-only, no API key | Google News RSS |
| Self-hosted / full control | SauravKanchan/NewsAPI |
| Multilingual | GNews.io, NewsData.io, WorldNewsAPI |

### Decision checklist

1. **Commercial vs. non-commercial** — Many free tiers (NewsAPI.org, GNews, Mediastack, The Guardian) forbid commercial use or require attribution.
2. **Real-time vs. archival** — GDELT is the archival pick; Currents API and Hacker News are real-time.
3. **Volume** — A proof of concept may fit in a few hundred calls; production usually needs tens of thousands and a paid plan.
4. **Data depth** — Headlines and URLs only, or full article text, author info, and rich metadata? Many free tiers return only a snippet.
5. **Coverage breadth** — Validate source depth for your niche topic or locale; regional coverage varies widely.
6. **Reliability** — Newer services (AllNewsAPI, NewsMesh) may lack proven uptime and SLAs.

---

## Part 4 — Data Freshness Reality Check

A July 2026 sampling of 48 news queries found that **~31% of top-10 results turned over within 8 hours**, and on fast-moving brand/topic queries roughly **half the top 10 was replaced**. Free RSS paths are deep but stale: the median item age in the same sample was about **6.6 days**.

**Implication:** A free plan capped at a daily pull is not a slower version of a paid one — on a brand or crisis query, it may be looking at a substantially different set of articles.

---

## Part 5 — Legal Notes

- Calling a news API with your own key is legal; the limits that bind you are the provider's terms.
- Free tiers typically restrict **commercial use** and may require **attribution**.
- **Republishing full article text** is a separate copyright question from API access.
- Always check the provider's ToS for: commercial-use rights, attribution requirements, caching/storage limits, and redistribution rules.

---

## Appendix — Minimal Python Fetch Examples

```python
import requests

# NewsAPI.org
r = requests.get(
    "https://newsapi.org/v2/top-headlines",
    params={"country": "us", "apiKey": "YOUR_KEY"},
)
print(r.json())

# Hacker News (no key)
r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json")
top_ids = r.json()[:5]
for item_id in top_ids:
    item = requests.get(
        f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
    ).json()
    print(item.get("title"))

# Spaceflight News (no key)
r = requests.get("https://api.spaceflightnewsapi.net/v3/articles")
print(r.json())

# SpaceX latest launch (no key)
r = requests.get("https://api.spacexdata.com/v5/launches/latest")
print(r.json()["name"], r.json()["date_utc"])
```

---

*Compiled September 2026. Verify all quotas and terms on provider websites before use.*
