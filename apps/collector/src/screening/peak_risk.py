"""Peak risk penalty — report 2-D red flags.

Triggers -30 point penalty when ALL THREE conditions met:
  1. PSR (P/S ratio) >= 20
  2. FCF negative for 3 consecutive years (proxy: latest FCF < 0)
  3. Insider sells > 5% of float
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


def apply_peak_risk_penalty(stock_data: dict) -> float:
    """Return penalty score (0 or 30) based on peak risk flags.

    Requires keys: ps_ratio, fcf, insider_sell_pct
    """
    ps_ratio = stock_data.get("ps_ratio")
    fcf = stock_data.get("fcf")
    insider_sell = stock_data.get("insider_sell_pct", 0) or 0

    flags = 0
    if ps_ratio is not None and ps_ratio >= 20:
        flags += 1
    if fcf is not None and fcf < 0:
        flags += 1
    if insider_sell > 5.0:
        flags += 1

    if flags == 3:
        logger.info("Peak risk penalty applied: PSR=%.1f, FCF=%.0f, insider=%.1f%%",
                    ps_ratio or 0, fcf or 0, insider_sell)
        return 30.0
    return 0.0
