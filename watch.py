"""Aggregate public X posts in a campaign window; no causal attribution."""
import argparse, csv, json, os, re, sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

DATASET = "gd_lwxkxvnf1cynvib9co"
COMPARE_FIELDS = ["source_url", "text", "posted_at", "period", "likes", "replies", "reposts"]

def normalize(raw):
    return {"source_url": raw.get("url") or raw.get("post_url") or "", "text": raw.get("text") or raw.get("post_text") or raw.get("description") or "", "posted_at": raw.get("date_posted") or raw.get("created_at") or None, "likes": raw.get("likes"), "replies": raw.get("replies") if raw.get("replies") is not None else raw.get("num_replies"), "reposts": raw.get("reposts") if raw.get("reposts") is not None else raw.get("retweets")}

def csv_safe(value):
    if isinstance(value, str) and value.lstrip(" \t\r\n\x00").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value

def metric_value(value, field):
    if value is None or value == "": return None
    if isinstance(value, bool): raise ValueError(field + " must be a non-negative integer")
    try: number=int(value)
    except (TypeError, ValueError): raise ValueError(field + " must be a non-negative integer") from None
    if str(number) != str(value).strip() or number < 0: raise ValueError(field + " must be a non-negative integer")
    return number

def validate_post_url(url):
    try:
        parsed=urlsplit(url); host=parsed.hostname; port=parsed.port
    except (TypeError,ValueError):
        raise ValueError("URL must be a canonical public X post URL") from None
    post_route=re.fullmatch(r"/[^/]+/status/\d+/?",parsed.path)
    if parsed.scheme!="https" or host not in {"x.com","www.x.com","twitter.com","www.twitter.com"} or parsed.username or parsed.password or port not in {None,443} or not post_route:
        raise ValueError("URL must be a canonical public X post URL")
    return url

def parse_day(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=timezone.utc).date() if parsed.tzinfo is None else parsed.astimezone(timezone.utc).date()
    except (ValueError, AttributeError):
        return None

def compare_campaign(raw_rows, before_start, before_end, after_start, after_end):
    before_first, before_last = date.fromisoformat(before_start), date.fromisoformat(before_end)
    after_first, after_last = date.fromisoformat(after_start), date.fromisoformat(after_end)
    if before_last < before_first or after_last < after_first:
        raise ValueError("each period end must be on or after its start")
    if before_last >= after_first:
        raise ValueError("before and after periods must not overlap and must be chronological")
    periods = {"before": [], "after": []}
    unplaced = 0
    for raw in raw_rows:
        if not isinstance(raw, dict): raise ValueError("each post record must be an object")
        row = normalize(raw)
        for metric in ("likes", "replies", "reposts"):
            row[metric] = metric_value(row[metric], metric)
        day = parse_day(row["posted_at"])
        if day is None:
            unplaced += 1
            continue
        if before_first <= day <= before_last:
            period = "before"
        elif after_first <= day <= after_last:
            period = "after"
        else:
            continue
        row["period"] = period
        row.pop("campaign_window", None)
        periods[period].append(row)

    summaries = {}
    for period, posts in periods.items():
        summaries[period] = {"posts": len(posts)}
        for metric in ("likes", "replies", "reposts"):
            values = [post[metric] for post in posts if post[metric] is not None]
            summaries[period][metric] = sum(values) if values else None
            summaries[period][metric + "_coverage"] = f"{len(values)}/{len(posts)}"
    comparisons = {}
    for metric in ("posts", "likes", "replies", "reposts"):
        before = summaries["before"][metric]
        after = summaries["after"][metric]
        delta = after - before if before is not None and after is not None else None
        comparisons[metric] = {"delta": delta, "percent_change": round(delta * 100 / before, 1) if delta is not None and before else None}
    return {"periods": summaries, "comparison": comparisons, "observations": periods["before"] + periods["after"], "unplaced_timestamps": unplaced, "caveat": "Descriptive differences between selected windows only; not causal campaign lift. Collection coverage, elapsed time, audience, distribution, and platform metrics may differ."}

def write_comparison_csv(path, report):
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMPARE_FIELDS)
        writer.writeheader()
        writer.writerows({key: csv_safe(value) for key, value in row.items()} for row in report["observations"])

def collect(urls, token):
    if len(urls) > 20: raise ValueError("Synchronous X collection supports at most 20 URLs")
    urls=[validate_post_url(url) for url in urls]
    if not token: raise ValueError("Set BRIGHT_DATA_API_KEY for live collection")
    req=Request("https://api.brightdata.com/datasets/v3/scrape?"+urlencode({"dataset_id":DATASET,"format":"json"}),data=json.dumps({"input":[{"url":u} for u in urls]}).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=90) as r: data=json.loads(r.read())
    except HTTPError as e: raise RuntimeError("Bright Data returned HTTP "+str(e.code)) from None
    except (URLError,TimeoutError) as e: raise RuntimeError("Bright Data request failed: "+str(e)) from None
    if not isinstance(data,list): raise RuntimeError("Async snapshot returned; this small demo supports synchronous URL records only")
    return data

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("input",help="JSON records or CSV of public X post URLs"); p.add_argument("output",nargs="?",default="campaign_comparison.json"); p.add_argument("--before-start",required=True); p.add_argument("--before-end",required=True); p.add_argument("--after-start",required=True); p.add_argument("--after-end",required=True); p.add_argument("--live",action="store_true",help="Explicitly collect the supplied public post URLs (may incur charges)"); p.add_argument("--dry-run",action="store_true"); a=p.parse_args(argv)
    try:
        compare_campaign([],a.before_start,a.before_end,a.after_start,a.after_end)
        text=Path(a.input).read_text(encoding="utf-8"); rows=json.loads(text) if a.input.endswith(".json") else list(csv.DictReader(text.splitlines()))
        if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows): raise ValueError("input must contain an array of JSON objects or CSV rows")
        record_fields={"text","post_text","description","date_posted","created_at","likes","replies","num_replies","reposts","retweets"}
        url_only=bool(rows) and "url" in rows[0] and not any(record_fields.intersection(row) for row in rows)
        if a.live:
            if not rows: raise ValueError("live collection requires at least one public X post URL")
            urls=[validate_post_url(str(r.get("url") or "").strip()) for r in rows]
            if a.dry_run: print(f"Dry run: {len(urls)} X URL(s); 0 requests made"); return 0
            rows=collect(urls,os.getenv("BRIGHT_DATA_API_KEY"))
        elif url_only: raise ValueError("URL-only input is not collected automatically; pass --live to explicitly request billable collection")
        elif a.dry_run: print(f"Dry run: {len(rows)} local record(s); 0 requests made"); return 0
        report=compare_campaign(rows,a.before_start,a.before_end,a.after_start,a.after_end)
        report["windows"]={"before":{"start":a.before_start,"end":a.before_end},"after":{"start":a.after_start,"end":a.after_end}}
        if a.output.endswith(".csv"): write_comparison_csv(a.output,report)
        else: Path(a.output).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(f"Compared {report['periods']['before']['posts']} before and {report['periods']['after']['posts']} after posts; {report['unplaced_timestamps']} lacked usable timestamps")
        return 0
    except (ValueError,OSError,RuntimeError,json.JSONDecodeError) as e: print("Error: "+str(e),file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
