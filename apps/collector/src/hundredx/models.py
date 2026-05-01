"""Shared data models for the hundredx module."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CategoryMatch:
    ticker: str
    category: str        # one of the 7 rise_category values
    confidence: float    # 0.0–1.0  (rule-based detector confidence)
    evidence: list[dict] = field(default_factory=list)  # [{source_type, source_id, text_excerpt, date, amount}]
    first_detected_at: datetime | None = None            # None = first time; set by scanner before upsert
    # Fingerprint match — populated by scanner after detector fires
    fingerprint_score: float | None = None               # 0.0–1.0 — similarity to library precedent
    fingerprint_library_ticker: str | None = None        # which library stock matched best
    fingerprint_dims: dict | None = None                 # {matched: [...], missing: [...], details: {...}}
    # Timeline progress — which trigger sequence stage in best library timeline
    timeline_progress: dict | None = None                # full TimelineProgress serialization
