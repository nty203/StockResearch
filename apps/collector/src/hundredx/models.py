"""Shared data models for the hundredx module."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CategoryMatch:
    ticker: str
    category: str        # one of the 7 rise_category values
    confidence: float    # 0.0–1.0
    evidence: list[dict] = field(default_factory=list)  # [{source_type, source_id, text_excerpt, date, amount}]
    first_detected_at: datetime | None = None            # None = first time; set by scanner before upsert
