"""The published call files must validate and contain only short quotes (never transcripts)."""
from pathlib import Path

from ytscore.schema import VideoCalls

CALLS = Path(__file__).resolve().parents[1] / "data" / "calls"


def test_published_calls_validate_and_quotes_are_short():
    files = sorted(CALLS.glob("*.json"))
    assert files
    for f in files:
        v = VideoCalls.model_validate_json(f.read_text())
        for c in v.calls:
            assert len(c.quote.replace("…", "").split()) <= 25, (f.name, c.ticker)
