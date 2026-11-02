import datetime as dt
import json

from ytscore.agree import compare
from ytscore.twins import holm, twin_test


def test_holm_matches_hand_calculation():
    assert holm([0.01, 0.04, 0.03]) == [0.03, 0.06, 0.06]
    assert holm([0.5, 0.9]) == [1.0, 1.0]


def _rows(moves):
    d0, px, rows = dt.date(2026, 1, 1), 100.0, []
    for i, m in enumerate([0.0] + moves):
        px *= 1 + m
        rows.append([(d0 + dt.timedelta(days=i)).isoformat(), px, px, px, px])
    return rows


def _call(ch, bias, ok):
    return dict(channel=ch, ticker="ES", group="indices_futures", st=bias, next_day_ok=ok)


def test_twins_flag_perfect_timing_but_not_a_coin_flipper():
    rows = _rows([0.01, -0.01] * 60)  # half up days, half down days
    scored = [_call("Prophet", "bullish", True) for _ in range(40)] + \
             [_call("Flipper", "bullish", i % 2 == 0) for i in range(40)]
    res = twin_test(scored, lambda s: rows, ["Prophet", "Flipper"], "2027-01-01", n_sets=2000)
    assert res["Prophet"]["twin_p"] < 0.001 and res["Prophet"]["twin_p_holm"] < 0.01
    assert res["Flipper"]["twin_p"] > 0.2
    assert abs(res["Flipper"]["twin_mean"] - 0.5) < 0.05


def _video(path, vid, calls):
    path.mkdir(exist_ok=True)
    (path / f"{vid}.json").write_text(json.dumps(dict(
        video_id=vid, channel="X", video_date="2026-10-07",
        calls=[dict(group="indices_futures", ticker=t, short_term={"bias": b}) for t, b in calls])))


def test_agreement_counts_matches_and_bias(tmp_path):
    _video(tmp_path / "a", "v1", [("ES", "bullish"), ("GC", "bearish"), ("NQ", "none")])
    _video(tmp_path / "b", "v1", [("ES", "bullish"), ("GC", "bullish"), ("BTC", "bearish")])
    r = compare(tmp_path / "a", tmp_path / "b")
    assert (r["a_calls"], r["b_calls"], r["matched"], r["same_bias"]) == (2, 3, 2, 1)
    assert r["per_video"][0]["only_b"] == ["BTC"]
