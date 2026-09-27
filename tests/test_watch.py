import watch


def test_campaign_windows_exclude_unrelated_dates_and_retain_evidence():
    rows = [{"url": "https://x.com/a/status/1", "text": "Launching our new product #launch", "date_posted": "2026-09-25T12:00:00Z", "likes": 10, "replies": 2}, {"url": "https://x.com/a/status/2", "text": "old launch", "date_posted": "2020-01-01T00:00:00Z", "likes": 100}]
    report = watch.compare_campaign(rows, "2026-09-24", "2026-09-27", "2026-09-28", "2026-09-30")
    assert report["periods"]["before"]["posts"] == 1
    assert report["periods"]["after"]["posts"] == 0
    assert report["observations"][0]["source_url"].endswith("/1")


def test_bad_dates_are_not_silently_included():
    report = watch.compare_campaign([{"url": "https://x.com/a/status/3", "text": "launch", "date_posted": "unknown"}], "2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04")
    assert report["unplaced_timestamps"] == 1


def test_offset_timestamps_are_compared_as_utc_dates():
    row = {"url": "https://x.com/a/status/4", "text": "launch", "date_posted": "2026-09-25T00:30:00+14:00"}
    report = watch.compare_campaign([row], "2026-09-24", "2026-09-24", "2026-09-26", "2026-09-27")
    assert report["periods"]["before"]["posts"] == 1


def test_naive_timestamps_are_explicitly_utc():
    assert watch.parse_day("2026-09-25T00:30:00") == watch.date(2026, 9, 25)


def test_normalizes_documented_x_description_field():
    post = watch.normalize({"url": "https://x.com/a/status/5", "description": "Launch day announcement", "date_posted": "2026-09-10T10:00:00Z", "likes": 3})
    assert post["text"] == "Launch day announcement"


def test_csv_output(tmp_path):
    report = watch.compare_campaign([{"url": "https://x.com/a/status/1", "text": "launch", "date_posted": "2026-01-02", "likes": 1}], "2026-01-01", "2026-01-03", "2026-01-04", "2026-01-05")
    watch.write_comparison_csv(tmp_path / "out.csv", report)
    assert "source_url" in (tmp_path / "out.csv").read_text()


def test_malformed_json_record_fails_as_cli_error(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text('[{"url":"https://x.com/a/status/1"}, 7]')
    assert watch.main([str(source), str(tmp_path / "out.json"), "--before-start", "2026-01-01", "--before-end", "2026-01-02", "--after-start", "2026-01-03", "--after-end", "2026-01-04"]) == 2


def test_sync_collection_limit_is_explicit():
    try:
        watch.collect(["https://x.com/a/status/1"] * 21, "token")
    except ValueError as exc:
        assert "20" in str(exc)
    else:
        assert False, "sync collector must reject more than 20 URLs"


def test_live_csv_rejects_rows_without_urls(tmp_path, capsys):
    source = tmp_path / "posts.csv"
    source.write_text("url,note\nhttps://x.com/a/status/1,valid\n,missing\n")
    assert watch.main([str(source), str(tmp_path / "out.json"), "--live", "--before-start", "2026-01-01", "--before-end", "2026-01-02", "--after-start", "2026-01-03", "--after-end", "2026-01-04"]) == 2
    assert "URL" in capsys.readouterr().err


def test_rejects_lookalike_hosts_and_non_post_routes():
    for url in ("https://x.com.evil.example/user/status/123", "https://x.com/user", "https://x.com/user/other/status/123", "https://user@x.com/user/status/1"):
        try:
            watch.validate_post_url(url)
        except ValueError:
            continue
        assert False, f"non-post X URL accepted: {url}"


def test_before_after_comparison_reports_campaign_level_deltas():
    rows = [
        {"url": "https://x.com/a/status/1", "text": "teaser", "date_posted": "2026-09-01T10:00:00Z", "likes": 10, "replies": 2, "reposts": 1},
        {"url": "https://x.com/a/status/2", "text": "launch", "date_posted": "2026-09-10T10:00:00Z", "likes": 20, "replies": 4, "reposts": 3},
    ]
    report = watch.compare_campaign(rows, "2026-09-01", "2026-09-03", "2026-09-09", "2026-09-11")
    assert report["periods"]["before"]["posts"] == 1
    assert report["periods"]["after"]["posts"] == 1
    assert report["comparison"]["likes"]["delta"] == 10
    assert report["comparison"]["likes"]["percent_change"] == 100.0
    assert "causal" in report["caveat"]


def test_date_windows_validated_before_dry_run(tmp_path, capsys):
    source = tmp_path / "urls.csv"
    source.write_text("url\nhttps://x.com/a/status/1\n")
    assert watch.main([str(source), "--live", "--dry-run", "--before-start", "bad", "--before-end", "2026-01-02", "--after-start", "2026-01-03", "--after-end", "2026-01-04"]) == 2
    assert "isoformat" in capsys.readouterr().err.lower()


def test_malformed_counter_fails_instead_of_silently_disappearing():
    import pytest
    with pytest.raises(ValueError, match="likes"):
        watch.compare_campaign([{"date_posted": "2026-01-01", "likes": "many"}], "2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02")


def test_csv_formula_values_are_neutralized(tmp_path):
    report = watch.compare_campaign([{"text": "=cmd", "date_posted": "2026-01-01"}], "2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02")
    watch.write_comparison_csv(tmp_path / "safe.csv", report)
    assert "'=cmd" in (tmp_path / "safe.csv").read_text()


def test_live_mode_is_explicit_and_validates_before_request(tmp_path, monkeypatch, capsys):
    source = tmp_path / "urls.csv"
    source.write_text("url\nhttps://x.com/a/status/1\nhttps://x.com.evil.test/a/status/2\n")
    monkeypatch.setattr(watch, "collect", lambda *args: (_ for _ in ()).throw(AssertionError("request happened before validation")))
    args = [str(source), "--live", "--dry-run", "--before-start", "2026-01-01", "--before-end", "2026-01-02", "--after-start", "2026-01-03", "--after-end", "2026-01-04"]
    assert watch.main(args) == 2


def test_offline_csv_with_url_and_metrics_is_not_treated_as_url_list(tmp_path):
    source = tmp_path / "records.csv"
    source.write_text("url,date_posted,likes\nhttps://x.com/a/status/1,2026-01-01,5\n")
    assert watch.main([str(source), str(tmp_path / "out.json"), "--before-start", "2026-01-01", "--before-end", "2026-01-01", "--after-start", "2026-01-02", "--after-end", "2026-01-02"]) == 0


def test_collect_request_contract(monkeypatch):
    import json
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self): return b'[]'
    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data)
        return Response()
    monkeypatch.setattr(watch, "urlopen", fake_urlopen)
    watch.collect(["https://x.com/a/status/1"], "token")
    assert "dataset_id=" + watch.DATASET in captured["url"]
    assert captured["payload"] == {"input": [{"url": "https://x.com/a/status/1"}]}
