# X Campaign Signal Watch

A small evidence-backed CLI for summarizing public X posts inside a user-selected launch or campaign date window. It reports observed post counts and engagement counters, not campaign causality or lift.

## Use cases and architecture

Compare a bounded set of public campaign posts, retain the primary evidence URLs, and inspect observed engagement in a defined time window. Flow: `CSV post URLs -> Bright Data X Posts dataset -> local date window + aggregation -> JSON/CSV`. Fixture JSON runs offline. Python 3.10+ standard library is the only runtime requirement.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Create a Bright Data API key from [account settings](https://brightdata.com/cp/setting/users), then export it as `BRIGHT_DATA_API_KEY`. The CLI reads environment variables only; it never loads or stores credentials. Official docs: [X Scraper API](https://docs.brightdata.com/products/scrapers/twitter/introduction.md), [async requests](https://docs.brightdata.com/products/scrapers/scrapers-library/async-requests.md), [API reference](https://docs.brightdata.com/api-reference/scrapers/synchronous-requests). Dataset `gd_lwxkxvnf1cynvib9co` is the documented X posts collector. This demo takes specific post URLs, not an invented arbitrary keyword-search endpoint.

## Run

```bash
python watch.py sample_posts.json campaign.json --start 2026-09-24 --end 2026-09-27
python watch.py sample_posts.json campaign.csv --start 2026-09-24 --end 2026-09-27
```

For live collection, make CSV with `url` column of public X post URLs:

```bash
python watch.py posts.csv campaign.json --start 2026-09-01 --end 2026-09-30
python watch.py posts.csv campaign.json --start 2026-09-01 --end 2026-09-30 --dry-run
```

Dry-run makes no HTTP calls. Budget per returned record and check current [Web Scraper API pricing](https://brightdata.com/pricing/web-scraper) before live use. Synchronous collection is capped at the documented 20 URLs per request; the demo reports, rather than hides, async snapshot responses.

## Output contract

The JSON report includes `window.start/end`, `summary.posts`, `summary.observed_likes`, `summary.likes_coverage`, normalized `posts`, `unplaced` (records with unusable timestamps), and an interpretation caveat. Each post has `source_url`, `text`, `posted_at`, observed `likes/replies/reposts`, and `campaign_window`. CSV contains the post rows. Unknown timestamps are excluded from the window and counted separately. Counters can be absent or sampled at collection time.

## Ethical limits and caveats

Research only on public URLs the operator is authorized to inspect. No login, private content, access-control bypass, identity enrichment, sensitive profiling, posting, replies, or outreach. Public visibility is not consent. Date windows use returned timestamps and UTC calendar-date comparisons; campaign attribution, impressions, reach, unique authors, and complete coverage are not inferred. Platform terms and retention requirements still apply.

## Troubleshooting and tests

- Missing key: use fixture JSON or dry-run; export `BRIGHT_DATA_API_KEY` for collection.
- 401/403: verify account access, key, and collector permissions.
- 429: pause and lower request rate; avoid immediate retries.
- Bad timestamps are counted as `unplaced`; confirm source record date fields.
- Live async snapshot: use Bright Data's async workflow; this demo currently consumes synchronous responses only.

```bash
python3 -m pytest -q
```

Offline coverage includes date-window boundaries, unparseable dates, observed metric aggregation, and CSV serialization. Sample records are illustrative.

MIT License.
