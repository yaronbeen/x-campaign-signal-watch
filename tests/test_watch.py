import watch


def test_campaign_window_filters_and_aggregates_only_observed_counts():
    rows = [{"url": "https://x.com/a/status/1", "text": "Launching our new product #launch", "date_posted": "2026-09-25T12:00:00Z", "likes": 10, "replies": 2}, {"url": "https://x.com/a/status/2", "text": "old launch", "date_posted": "2020-01-01T00:00:00Z", "likes": 100}]
    report = watch.analyze(rows, "2026-09-24", "2026-09-27")
    assert len(report["posts"]) == 1
    assert report["summary"]["posts"] == 1
    assert report["posts"][0]["source_url"].endswith("/1")


def test_bad_dates_are_not_silently_included():
    assert watch.analyze([{"url": "https://x.com/a/status/3", "text": "launch", "date_posted": "unknown"}], "2026-01-01", "2026-01-02")["unplaced"] == 1


def test_offset_timestamps_are_compared_as_utc_dates():
    row = {"url": "https://x.com/a/status/4", "text": "launch", "date_posted": "2026-09-25T00:30:00+14:00"}
    report = watch.analyze([row], "2026-09-24", "2026-09-24")
    assert len(report["posts"]) == 1


def test_csv_output(tmp_path):
    row = watch.normalize({"url": "https://x.com/a/status/1", "text": "launch", "date_posted": "2026-01-01"})
    watch.write_csv(tmp_path / "out.csv", [row])
    assert "source_url" in (tmp_path / "out.csv").read_text()


def test_malformed_json_record_fails_as_cli_error(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text('[{"url":"https://x.com/a/status/1"}, 7]')
    assert watch.main([str(source), str(tmp_path / "out.json"), "--start", "2026-01-01", "--end", "2026-01-02"]) == 2


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
    assert watch.main([str(source), str(tmp_path / "out.json"), "--start", "2026-01-01", "--end", "2026-01-02"]) == 2
    assert "URL" in capsys.readouterr().err
