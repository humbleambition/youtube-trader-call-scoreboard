"""Pydantic models for one video's extracted calls (see prompts/extract.md and docs/METHODOLOGY.md)."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Bias = Literal["bullish", "bearish", "neutral", "mixed", "none"]
MAX_QUOTE_WORDS = 25


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Horizon(_Base):
    bias: Bias = "none"
    target: Optional[float] = None
    horizon: str = ""


class KeyLevels(_Base):
    support: list[float] = Field(default_factory=list)
    resistance: list[float] = Field(default_factory=list)
    invalidation: Optional[float] = None

    @field_validator("support", "resistance", mode="before")
    @classmethod
    def _none_to_list(cls, v):
        return v or []


class Call(_Base):
    group: Literal["indices_futures", "metals", "crypto", "stocks", "rates_fx_energy"]
    ticker: str
    instrument_quoted: Optional[str] = None
    price_at_call: Optional[float] = None
    short_term: Horizon = Field(default_factory=Horizon)   # next session / 1-5 days (this is what gets scored)
    medium_term: Horizon = Field(default_factory=Horizon)  # weeks to ~3 months
    long_term: Horizon = Field(default_factory=Horizon)    # > 3 months
    key_levels: KeyLevels = Field(default_factory=KeyLevels)
    condition: str = ""
    action: Literal["", "buy", "add", "hold", "take_profit", "sell", "short", "watch"] = ""
    entry: Optional[float] = None
    stop: Optional[float] = None
    method: Literal["technical", "macro", "options_flow", "fundamental", "sentiment", "cycles", "mixed"] = "mixed"
    reason: str = ""
    conviction: Literal["low", "medium", "high"] = "medium"
    timestamp: str = ""
    quote: str = ""

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("quote")
    @classmethod
    def _short_quote(cls, v: str) -> str:
        w = (v or "").split()
        return " ".join(w[:MAX_QUOTE_WORDS]) + (" …" if len(w) > MAX_QUOTE_WORDS else "")


class MacroTheme(_Base):
    theme: str
    view: str = ""


class VideoCalls(_Base):
    video_id: str
    channel: str
    title: str = ""
    video_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    date_source: Literal["transcript", "listing"] = "listing"
    recorded_when: Literal["premarket", "intraday", "after_close", "weekend", "unknown"] = "unknown"
    video_type: Literal["daily_market", "deep_dive_stock", "macro_interview", "crypto_daily", "metals"] = "daily_market"
    speaker: str = ""
    macro_themes: list[MacroTheme] = Field(default_factory=list)
    calls: list[Call] = Field(default_factory=list)
    notes: str = ""

    @field_validator("channel")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()
