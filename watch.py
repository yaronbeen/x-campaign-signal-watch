"""Aggregate public X posts in a campaign window; no causal attribution."""
import argparse, csv, json, os, sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DATASET = "gd_lwxkxvnf1cynvib9co"
FIELDS = ["source_url", "text", "posted_at", "likes", "replies", "reposts", "campaign_window"]

def normalize(raw):
    return {"source_url": raw.get("url") or raw.get("post_url") or "", "text": raw.get("text") or raw.get("post_text") or "", "posted_at": raw.get("date_posted") or raw.get("created_at") or None, "likes": raw.get("likes"), "replies": raw.get("replies") or raw.get("num_replies"), "reposts": raw.get("reposts") or raw.get("retweets"), "campaign_window": ""}

def parse_day(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.date() if parsed.tzinfo is None else parsed.astimezone(timezone.utc).date()
    except (ValueError, AttributeError):
        return None

def analyze(raw_rows, start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if last < first: raise ValueError("end date must be on or after start date")
    posts, unplaced = [], 0
    for raw in raw_rows:
        row = normalize(raw); day = parse_day(row["posted_at"])
        if day is None: unplaced += 1; continue
        if first <= day <= last:
            row["campaign_window"] = f"{first.isoformat()}..{last.isoformat()}"; posts.append(row)
    numeric = [int(p["likes"]) for p in posts if str(p["likes"] or "").isdigit()]
    return {"window": {"start": start, "end": end}, "summary": {"posts": len(posts), "observed_likes": sum(numeric) if numeric else None, "likes_coverage": f"{len(numeric)}/{len(posts)}"}, "posts": posts, "unplaced": unplaced, "interpretation": "Aggregated observed public metrics; no causal campaign attribution; absent metrics are unknown."}

def write_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)

def collect(urls, token):
    if len(urls) > 20: raise ValueError("Synchronous X collection supports at most 20 URLs")
    if not token: raise ValueError("Set BRIGHT_DATA_API_KEY for live collection")
    req=Request("https://api.brightdata.com/datasets/v3/scrape?"+urlencode({"dataset_id":DATASET,"format":"json"}),data=json.dumps([{"url":u} for u in urls]).encode(),headers={"Authorization":"Bearer "+token,"Content-Type":"application/json"},method="POST")
    try:
        with urlopen(req,timeout=90) as r: data=json.loads(r.read())
    except HTTPError as e: raise RuntimeError("Bright Data returned HTTP "+str(e.code)) from None
    except (URLError,TimeoutError) as e: raise RuntimeError("Bright Data request failed: "+str(e)) from None
    if not isinstance(data,list): raise RuntimeError("Async snapshot returned; this small demo supports synchronous URL records only")
    return data

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("input",help="JSON records or CSV of public X post URLs"); p.add_argument("output",nargs="?",default="campaign.json"); p.add_argument("--start",required=True); p.add_argument("--end",required=True); p.add_argument("--dry-run",action="store_true"); a=p.parse_args(argv)
    try:
        text=Path(a.input).read_text(encoding="utf-8"); rows=json.loads(text) if a.input.endswith(".json") else list(csv.DictReader(text.splitlines()))
        if not isinstance(rows,list) or any(not isinstance(row,dict) for row in rows): raise ValueError("input must contain an array of JSON objects or CSV rows")
        live=bool(rows) and "url" in rows[0] and not any("text" in r or "post_text" in r for r in rows)
        urls=[str(r.get("url") or "").strip() for r in rows] if live else []
        if live and any(not u.startswith(("https://x.com/","https://twitter.com/")) for u in urls): raise ValueError("Every row must contain a public x.com or twitter.com post URL")
        if a.dry_run: print(f"Dry run: {len(rows)} inputs; 0 requests made"); return 0
        if live: rows=collect(urls,os.getenv("BRIGHT_DATA_API_KEY"))
        report=analyze(rows,a.start,a.end)
        if a.output.endswith(".csv"): write_csv(a.output,report["posts"])
        else: Path(a.output).write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(f"Included {len(report['posts'])} posts; {report['unplaced']} without usable timestamp")
        return 0
    except (ValueError,OSError,RuntimeError,json.JSONDecodeError) as e: print("Error: "+str(e),file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
