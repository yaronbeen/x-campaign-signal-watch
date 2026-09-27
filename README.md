# X Post Window Comparator

A small evidence-backed CLI for comparing observed public X post activity across two user-selected date windows. It is a bounded URL-sample comparison, not continuous campaign monitoring, profile prospecting, or a causal lift measurement.

## Use cases and architecture

Compare a bounded set of up to 20 public post URLs per synchronous call around an announcement or campaign change. Flow: `explicit --live + CSV post URLs -> Bright Data X Posts dataset -> two explicit date windows -> descriptive totals/deltas -> JSON/CSV`. Fixture JSON runs offline. Python 3.10+ standard library is the only runtime requirement.

## Setup

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Create a Bright Data API key from [account settings](https://brightdata.com/cp/setting/users), then export it as `BRIGHT_DATA_API_KEY`. The CLI reads environment variables only; it never loads or stores credentials. Official docs: [X Scraper API](https://docs.brightdata.com/products/scrapers/twitter/introduction.md), [async requests](https://docs.brightdata.com/products/scrapers/scrapers-library/async-requests.md), [API reference](https://docs.brightdata.com/api-reference/scrapers/synchronous-requests). Dataset `gd_lwxkxvnf1cynvib9co` is the documented X posts collector. This demo takes specific post URLs, not an invented arbitrary keyword-search endpoint.

## Run

```bash
python watch.py sample_posts.json campaign_comparison.json \
  --before-start 2026-09-10 --before-end 2026-09-14 \
  --after-start 2026-09-24 --after-end 2026-09-28
```

For live collection, make CSV with `url` column of public X post URLs:

```bash
python watch.py posts.csv campaign_comparison.json --live \
  --before-start 2026-09-01 --before-end 2026-09-07 \
  --after-start 2026-09-08 --after-end 2026-09-14
python watch.py posts.csv --live --dry-run \
  --before-start 2026-09-01 --before-end 2026-09-07 \
  --after-start 2026-09-08 --after-end 2026-09-14
```

Dry-run makes no HTTP calls. Budget per returned record and check current [Web Scraper API pricing](https://brightdata.com/pricing/web-scraper) before live use. Synchronous collection is capped at the documented 20 URLs per request; the demo reports, rather than hides, async snapshot responses.

## Output contract

The JSON report includes separate `periods.before` and `periods.after` totals for post count, likes, replies, and reposts, per-counter coverage, absolute and percent deltas, linked observations, and a caveat. CSV is evidence-only (one row per included post with its before/after label); aggregate deltas and caveats are in JSON, not repeated in each CSV row. Unknown timestamps are counted separately and excluded. Percent change is null when the before total is zero or unavailable. Missing counters remain unknown; malformed or negative counters fail validation rather than silently disappearing. Naive timestamps are interpreted as UTC.

Illustrative decision: compare the selected posts’ observed counters in the two windows, then inspect their URLs for context. Changed totals do not establish that a campaign caused the difference; this tool does not measure impressions, reach, spend, or audience.

## How this differs from existing tools

This answers “how do the observed post counters and post counts differ between these two windows for my supplied URLs?” It is not a live monitor, campaign-attribution system, or profile/contact prospecting tool like `bright-data-twitter-outreach`. Unlike `social-buyer-intent-finder`, it does not qualify individuals or draft replies. A marketer must source and scope the post URLs; synchronous collection is capped at 20 URLs per request and can be incomplete.

## Ethical limits and caveats

Research only on public URLs the operator is authorized to inspect. No login, private content, access-control bypass, identity enrichment, sensitive profiling, posting, replies, or outreach. Public visibility is not consent. Date windows use returned timestamps and UTC calendar-date comparisons; campaign attribution, impressions, reach, unique authors, and complete coverage are not inferred. Platform terms and retention requirements still apply.

## Troubleshooting and tests

- Missing key: use fixture JSON or dry-run; export `BRIGHT_DATA_API_KEY` for collection.
- URL-only CSV without `--live`: rejected without a request; add `--live` to explicitly opt in to collection.
- 401/403: verify account access, key, and collector permissions.
- 429: pause and lower request rate; avoid immediate retries.
- Bad timestamps are counted as `unplaced`; confirm source record date fields.
- Live async snapshot: use Bright Data's async workflow; this demo currently consumes synchronous responses only.

```bash
python3 -m pytest -q
```

Offline coverage includes date-window boundaries, UTC and naive timestamps, malformed dates/counters, before/after aggregation and deltas, explicit live opt-in, mocked request shape, formula-safe CSV serialization, malformed records, and missing URLs. Sample records are illustrative.

MIT License.
