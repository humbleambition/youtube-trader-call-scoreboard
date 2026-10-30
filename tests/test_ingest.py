from ytscore.ingest import ago_to_days, dedupe_cues, fmt_ts, parse_srt, srt_to_text

ROLLING_SRT = """1
00:00:01,000 --> 00:00:03,000
good morning everyone

2
00:00:02,500 --> 00:00:05,000
good morning everyone welcome back

3
00:00:04,800 --> 00:00:07,000
everyone welcome back to the show

4
00:01:02,000 --> 00:01:04,000
the S&P looks heavy today
"""


def test_parse_srt_times_and_text():
    cues = parse_srt(ROLLING_SRT)
    assert cues[0] == (1.0, "good morning everyone")
    assert cues[3][0] == 62.0


def test_rolling_captions_are_deduped():
    text = srt_to_text(ROLLING_SRT)
    words = text.replace("[0:01]", "").replace("[1:02]", "").split()
    assert words == "good morning everyone welcome back to the show the S&P looks heavy today".split()


def test_minute_markers_once_per_minute():
    text = srt_to_text(ROLLING_SRT)
    assert text.startswith("[0:01] good")
    assert "\n[1:02] the S&P" in text
    assert text.count("[") == 2


def test_fully_repeated_cue_adds_nothing():
    assert dedupe_cues([(0, "a b c"), (1, "b c"), (2, "c d")]) == "[0:00] a b c d"


def test_genuine_repetition_kept_when_not_an_overlap():
    # "buy buy" said twice in separate cues where the second is not a suffix-prefix echo
    assert dedupe_cues([(0, "we buy here"), (1, "and we buy again")]).split()[1:] == "we buy here and we buy again".split()


def test_empty_and_malformed_blocks_ignored():
    assert parse_srt("1\nnot a time\nhello\n\n\n") == []
    assert dedupe_cues([(0, "   ")]) == ""


def test_fmt_ts_and_ago():
    assert fmt_ts(3725) == "62:05"
    assert ago_to_days("3 days ago") == 3
    assert ago_to_days("2 weeks ago") == 14
    assert ago_to_days("5 hours ago") == 0
    assert ago_to_days(None) == 999
