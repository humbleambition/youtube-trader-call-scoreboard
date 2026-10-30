import datetime as dt

import pytest

from ytscore.config import Exclusions
from ytscore.leaderboard import build
from ytscore.prices import complete_cutoff
from ytscore.schema import VideoCalls
from ytscore.score import bias_ok, ref_index, score_all, vol_threshold, yahoo_symbol
from ytscore.stats import binom_p_at_least, summarize

# Mon 5 .. Wed 14 Oct 2026, no weekend bars (futures/stocks)
DATES = ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09",
         "2026-10-12", "2026-10-13", "2026-10-14"]


def bars(closes, highs=None, lows=None):
    highs = highs or closes
    lows = lows or closes
    return [[d, c, h, l, c] for d, c, h, l in zip(DATES, closes, highs, lows)]


def video(date="2026-10-07", when="premarket", **call):
    c = dict(group="indices_futures", ticker="ES", short_term={"bias": "bullish"})
    c.update(call)
    return VideoCalls.model_validate(dict(video_id="vid1", channel="Chan", video_date=date,
                                          recorded_when=when, calls=[c]))


# ---- reference close ----
@pytest.mark.parametrize("when,expected", [
    ("premarket", "2026-10-06"), ("weekend", "2026-10-06"), ("unknown", "2026-10-06"),
    ("intraday", "2026-10-07"), ("after_close", "2026-10-07")])
def test_ref_close_by_recording_time(when, expected):
    rows = bars([100] * 8)
    assert rows[ref_index(rows, "2026-10-07", when)][0] == expected


def test_weekend_video_uses_friday_close():
    rows = bars([100] * 8)
    assert rows[ref_index(rows, "2026-10-11", "weekend")][0] == "2026-10-09"
    # even 'after_close' on a Sunday has no Sunday bar -> Friday
    assert rows[ref_index(rows, "2026-10-11", "after_close")][0] == "2026-10-09"


def test_no_reference_before_first_bar():
    assert ref_index(bars([100] * 8), "2026-10-01", "intraday") is None


# ---- thresholds and hit rules ----
def test_vol_thresholds():
    assert vol_threshold("ES", "indices_futures") == 0.006
    assert vol_threshold("GC", "metals") == 0.006
    assert vol_threshold("SI", "metals") == 0.012
    assert vol_threshold("BTC", "crypto") == 0.012
    assert vol_threshold("DOGE", "crypto") == 0.006   # only the four majors get the crypto threshold
    assert vol_threshold("NVDA", "stocks") == 0.012


@pytest.mark.parametrize("bias,move,ok", [
    ("bullish", 0.0013, True), ("bullish", 0.0011, False), ("bullish", -0.01, False),
    ("bearish", -0.0013, True), ("bearish", -0.0011, False),
    ("neutral", 0.0059, True), ("neutral", -0.0061, False),
    ("mixed", 0.02, None), ("none", 0.02, None)])
def test_bias_ok(bias, move, ok):
    assert bias_ok(bias, move, 0.006) is ok


def test_yahoo_symbols():
    assert yahoo_symbol("ES", "indices_futures") == "ES=F"
    assert yahoo_symbol("TNX", "rates_fx_energy") == "^TNX"
    assert yahoo_symbol("DOGE", "crypto") == "DOGE-USD"
    assert yahoo_symbol("nvda", "stocks") == "NVDA"


# ---- full call scoring ----
def run(v, rows):
    return score_all([v], Exclusions(), lambda s: rows)


def test_next_session_and_week():
    rows = bars([100, 100, 101, 100.5, 102, 103, 104, 105])
    out, dropped = run(video(), rows)  # premarket Oct 7 -> ref Oct 6 close 100
    r = out[0]
    assert (r["ref_date"], r["next_date"], r["next_day_pct"], r["next_day_ok"]) == ("2026-10-06", "2026-10-07", 1.0, True)
    assert r["week_to"] == "2026-10-13" and r["week_pct"] == 4.0 and r["week_ok"] is True


def test_week_uses_medium_bias_when_short_is_none():
    rows = bars([100, 100, 101, 100.5, 102, 103, 97, 105])
    out, _ = run(video(short_term={"bias": "none"}, medium_term={"bias": "bearish"}), rows)
    r = out[0]
    assert r["next_day_ok"] is None
    assert r["week_pct"] == -3.0 and r["week_ok"] is True and r["mt_early_ok"] is True


def test_last_bar_reference_has_no_next_session():
    rows = bars([100] * 8)
    out, _ = run(video(date="2026-10-14", when="after_close"), rows)
    assert "next_day_ok" not in out[0] and out[0]["ref_date"] == "2026-10-14"


def test_price_mismatch_drops_stock_call():
    rows = bars([100] * 8)
    out, dropped = run(video(group="stocks", ticker="SAM", price_at_call=200), rows)
    assert out == [] and dropped == [("Chan", "SAM", 200.0, 100)]


def test_quoted_in_other_units_is_not_dropped():
    # ES call quoted in SPY dollars: 670 vs ES 6700 is fine because SPY != ES
    rows = bars([6700] * 8)
    out, dropped = run(video(instrument_quoted="SPY", price_at_call=670), rows)
    assert len(out) == 1 and not dropped


def test_target_scaled_from_quoted_units_and_hit():
    rows = bars([6700, 6700, 6710, 6720, 6750, 6790, 6800, 6800],
                highs=[6700, 6700, 6720, 6730, 6760, 6800, 6806, 6800])
    v = video(instrument_quoted="SPY", price_at_call=670, short_term={"bias": "bullish", "target": 680})
    r = run(v, rows)[0][0]
    assert r["st_t_dist_pct"] == 1.49   # 680/670 scaled onto 6700 -> 6800
    assert r["st_t_hit_wk"] is True


def test_far_unscaled_target_ignored():
    rows = bars([100] * 8)
    r = run(video(short_term={"bias": "bullish", "target": 200}), rows)[0][0]
    assert "st_t_hit_wk" not in r


def test_exclusions():
    rows = bars([100] * 8)
    v = video()
    assert score_all([v], Exclusions(channels={"Chan"}), lambda s: rows)[0] == []
    assert score_all([v], Exclusions(videos={"vid1"}), lambda s: rows)[0] == []
    assert score_all([v], Exclusions(calls={("vid1", "ES")}), lambda s: rows)[0] == []


def test_missing_prices_kept_unscored():
    out, _ = score_all([video()], Exclusions(), lambda s: None)
    assert len(out) == 1 and "ref_close" not in out[0]


def test_long_quote_trimmed_to_25_words():
    v = video(quote=" ".join(["w"] * 40))
    assert len(v.calls[0].quote.split()) == 26  # 25 words + ellipsis


# ---- incomplete-bar cutoff uses US Eastern, DST-aware ----
def test_complete_cutoff_eastern():
    utc = dt.timezone.utc
    assert complete_cutoff(dt.datetime(2026, 10, 21, 23, 0, tzinfo=utc)) == "2026-10-21"  # 19:00 EDT
    assert complete_cutoff(dt.datetime(2026, 10, 22, 0, 30, tzinfo=utc)) == "2026-10-22"  # 20:30 EDT
    assert complete_cutoff(dt.datetime(2026, 12, 2, 0, 30, tzinfo=utc)) == "2026-12-01"   # 19:30 EST


# ---- stats / leaderboard ----
def test_binomial_p():
    assert binom_p_at_least(0, 10) == pytest.approx(1.0)
    assert binom_p_at_least(10, 10) == pytest.approx(1 / 1024)
    assert binom_p_at_least(8, 10) == pytest.approx(56 / 1024)


def test_summary_and_min_sample():
    recs = [dict(channel="A", date="2026-10-01", next_day_ok=i < 10, next_day_pct=1.0 if i % 2 else -1.0)
            for i in range(16)]
    s = summarize(recs, "next_day_ok", "next_day_pct")
    assert (s["n"], s["hits"], s["long"]) == (16, 10, 0.5)
    assert len(build(recs)) == 1
    assert build(recs[:14]) == []
