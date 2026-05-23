"""Feature builder — PPTR ML 모델용 feature 추출.

현재 CategoryMatch에서 사용하는 시그널들을 ML feature vector로 변환.
LightGBM이 직접 소화 가능한 수치형 feature만 출력.

Feature groups:
  1. Quant (재무): BCR, backlog YoY, revenue YoY, OPM, OPM delta, gross margin, ROIC, FCF
  2. Event (공시): keyword hits, keyword density, amount_log, filing_count, days_since_filing
  3. Price/volume: volume spike, price momentum (20/60/200d), ATR, idio_vol, beta
  4. Macro: sector dummy, market dummy
  5. Refutation: dilution YoY, debt_ratio, EV/Sales, backlog_quality_jump, goodwill_ratio
  6. Meta: category dummy, pptr_matched_conditions_count
"""
from __future__ import annotations

import math
from typing import Any


QUANT_FEATURES = [
    "bcr",                      # order_backlog / revenue_ttm
    "backlog_yoy_pct",
    "revenue_yoy_pct",
    "opm_ttm",                  # operating margin TTM
    "opm_delta",                # opm_ttm - opm_prev
    "gross_margin_ttm",
    "gross_margin_delta",
    "roic",                     # return on invested capital
    "fcf_yield",                # FCF / market_cap
    "revenue_qoq_acceleration", # 분기 매출 가속도
]

EVENT_FEATURES = [
    "keyword_hits",
    "keyword_density",   # hits / total_keywords
    "amount_log",        # log(계약금액 / 10억)
    "filing_count_90d",
    "days_since_last_filing",
]

PRICE_FEATURES = [
    "volume_spike_60d",   # current_volume / avg_volume_60d
    "price_mom_20d",      # (close - close_20d_ago) / close_20d_ago
    "price_mom_60d",
    "price_mom_200d",
    "above_ma20",         # 1 if close > MA20
    "above_ma60",
    "above_ma200",
    "atr_20d_pct",        # ATR / close — 변동성
    "ann_vol_252d",       # 연환산 변동성
    "beta_252d",
]

REFUTATION_FEATURES = [
    "dilution_yoy_pct",
    "debt_ratio",
    "ev_sales",
    "ev_sales_growth_adj",
    "backlog_quality_jump",   # 1 if backlog/revenue suddenly >3x YoY without revenue growth
    "goodwill_to_assets",
    "composite_issuance",     # Daniel-Titman: log(shares outstanding change)
]

META_FEATURES = [
    "pptr_conditions_matched",
    "fingerprint_score",
    "timeline_stage",          # 0-10 (how far in trigger sequence)
]

ALL_FEATURES = (
    QUANT_FEATURES + EVENT_FEATURES + PRICE_FEATURES + REFUTATION_FEATURES + META_FEATURES
)

# 카테고리 one-hot (LightGBM categorical feature로도 가능하지만 명시적 dummy 사용)
CATEGORY_DUMMIES = [
    "cat_수주잔고_선행",
    "cat_수익성_급전환",
    "cat_빅테크_파트너",
    "cat_플랫폼_독점",
    "cat_정책_수혜",
    "cat_공급_병목",
    "cat_임상_파이프라인",
]

FULL_FEATURE_NAMES = ALL_FEATURES + CATEGORY_DUMMIES


def _safe(val: Any, default: float = 0.0) -> float:
    """None / NaN → default."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return default


def _log_safe(val: Any, floor: float = 0.01) -> float:
    """log(max(val, floor)) — 음수/0 안전."""
    v = _safe(val, floor)
    return math.log(max(v, floor))


def build_feature_vector(
    stock_data: dict,
    filings: list[dict],
    match_meta: dict | None = None,  # CategoryMatch 정보 (fingerprint_score 등)
    category: str = "미분류",
) -> dict[str, float]:
    """stock_data + filings → feature dict (FULL_FEATURE_NAMES 키).

    Returns dict with ALL feature names, missing → 0.0.
    LightGBM은 NaN 처리 가능하지만 여기서는 0.0 imputation + indicator 방식.
    """
    feat: dict[str, float] = {k: 0.0 for k in FULL_FEATURE_NAMES}
    match_meta = match_meta or {}

    # ── 1. Quant ────────────────────────────────────────────────────────
    backlog = _safe(stock_data.get("order_backlog"))
    rev_ttm = _safe(stock_data.get("revenue_ttm") or stock_data.get("revenue"))
    rev_prev = _safe(stock_data.get("revenue_prev"))
    opm = _safe(stock_data.get("op_margin_ttm"))
    opm_prev = _safe(stock_data.get("op_margin_prev"))
    backlog_prev = _safe(stock_data.get("order_backlog_prev"))
    gross_margin = _safe(stock_data.get("gross_margin_ttm"))
    gross_margin_prev = _safe(stock_data.get("gross_margin_prev"))
    roic = _safe(stock_data.get("roic") or stock_data.get("return_on_invested_capital"))
    fcf = _safe(stock_data.get("fcf") or stock_data.get("free_cash_flow"))
    mktcap = _safe(stock_data.get("market_cap"))
    rev_qoq = _safe(stock_data.get("revenue_qoq_pct") or stock_data.get("revenue_qoq"))

    feat["bcr"] = backlog / rev_ttm if rev_ttm > 0 else 0.0
    feat["backlog_yoy_pct"] = ((backlog - backlog_prev) / backlog_prev * 100) if backlog_prev > 0 else 0.0
    feat["revenue_yoy_pct"] = ((rev_ttm - rev_prev) / rev_prev * 100) if rev_prev > 0 else 0.0
    feat["opm_ttm"] = opm
    feat["opm_delta"] = opm - opm_prev
    feat["gross_margin_ttm"] = gross_margin
    feat["gross_margin_delta"] = gross_margin - gross_margin_prev
    feat["roic"] = roic
    feat["fcf_yield"] = (fcf / mktcap * 100) if mktcap > 0 else 0.0
    feat["revenue_qoq_acceleration"] = rev_qoq

    # ── 2. Event (공시) ─────────────────────────────────────────────────
    from ..keywords import _extract_amount_krw
    # keyword hits는 match_meta에서 가져오거나 0
    kw_hits = _safe(match_meta.get("keyword_hits") or
                    (len(match_meta.get("best_hits", [])) if "best_hits" in match_meta else 0))
    total_kws = _safe(match_meta.get("total_keywords") or 1, 1.0)
    feat["keyword_hits"] = kw_hits
    feat["keyword_density"] = kw_hits / max(total_kws, 1.0)

    # 최대 계약금액 (log scale)
    best_amount = 0.0
    filing_count = 0
    last_filing_days = 999
    from datetime import date as _date, datetime as _dt, timedelta
    today_str = _date.today().isoformat()
    for f in filings:
        filing_count += 1
        text = (f.get("raw_text") or "") + " " + (f.get("headline") or "")
        amt = _extract_amount_krw(text) or 0.0
        if amt > best_amount:
            best_amount = amt
        filed_str = str(f.get("filed_at", "") or "")[:10]
        if filed_str:
            try:
                days_ago = (_dt.fromisoformat(today_str) - _dt.fromisoformat(filed_str)).days
                last_filing_days = min(last_filing_days, days_ago)
            except Exception:
                pass
    feat["amount_log"] = _log_safe(best_amount, 0.01) if best_amount > 0 else 0.0
    feat["filing_count_90d"] = float(filing_count)
    feat["days_since_last_filing"] = float(min(last_filing_days, 999))

    # ── 3. Price/volume ─────────────────────────────────────────────────
    feat["volume_spike_60d"] = _safe(
        stock_data.get("max_volume_spike_ratio") or stock_data.get("volume_spike_ratio")
    )
    feat["price_mom_20d"] = _safe(stock_data.get("price_mom_20d") or stock_data.get("mom_20d"))
    feat["price_mom_60d"] = _safe(stock_data.get("price_mom_60d") or stock_data.get("mom_60d"))
    feat["price_mom_200d"] = _safe(stock_data.get("price_mom_200d") or stock_data.get("mom_200d"))

    ma20 = _safe(stock_data.get("ma20") or stock_data.get("sma_20"))
    ma60 = _safe(stock_data.get("ma60") or stock_data.get("sma_60"))
    ma200 = _safe(stock_data.get("ma200") or stock_data.get("sma_200"))
    close = _safe(stock_data.get("close") or stock_data.get("price_close"))
    if close > 0:
        feat["above_ma20"] = 1.0 if (ma20 > 0 and close > ma20) else 0.0
        feat["above_ma60"] = 1.0 if (ma60 > 0 and close > ma60) else 0.0
        feat["above_ma200"] = 1.0 if (ma200 > 0 and close > ma200) else 0.0

    feat["atr_20d_pct"] = _safe(stock_data.get("atr_20d_pct") or stock_data.get("atr_pct"))
    feat["ann_vol_252d"] = _safe(stock_data.get("ann_vol_252d") or stock_data.get("annual_vol"))
    feat["beta_252d"] = _safe(stock_data.get("beta_252d") or stock_data.get("beta"))

    # ── 4. Refutation ───────────────────────────────────────────────────
    dilution = _safe(
        stock_data.get("share_count_yoy_pct")
        or stock_data.get("shares_outstanding_yoy_pct")
        or stock_data.get("dilution_yoy_pct")
    )
    debt_ratio = _safe(stock_data.get("debt_ratio"))
    ev_sales = _safe(stock_data.get("ev_sales") or stock_data.get("ev_to_sales"))
    rev_growth = _safe(stock_data.get("revenue_growth_yoy") or stock_data.get("revenue_yoy_pct"))
    goodwill = _safe(stock_data.get("goodwill"))
    total_assets = _safe(stock_data.get("total_assets"))
    shares_change = _safe(stock_data.get("composite_equity_issuance"))

    feat["dilution_yoy_pct"] = dilution
    feat["debt_ratio"] = debt_ratio
    feat["ev_sales"] = ev_sales
    feat["ev_sales_growth_adj"] = ev_sales / max(rev_growth / 20.0, 1.0) if rev_growth > 0 else ev_sales
    # Lev-Thiagarajan: backlog/revenue sudden jump >3x YoY 없으면서 BCR > 3 → manipulation flag
    bcr_yoy_jump = (
        feat["bcr"] > 3.0 and feat["backlog_yoy_pct"] > 200 and feat["revenue_yoy_pct"] < 20
    )
    feat["backlog_quality_jump"] = 1.0 if bcr_yoy_jump else 0.0
    feat["goodwill_to_assets"] = (goodwill / total_assets) if total_assets > 0 else 0.0
    # Daniel-Titman composite issuance: log(current_shares / prev_shares)
    feat["composite_issuance"] = _log_safe(1.0 + shares_change / 100.0, 0.001) if shares_change else 0.0

    # ── 5. Meta ─────────────────────────────────────────────────────────
    conditions = match_meta.get("matched_conditions") or []
    feat["pptr_conditions_matched"] = float(len(conditions))
    feat["fingerprint_score"] = _safe(match_meta.get("fingerprint_score"))
    feat["timeline_stage"] = _safe(match_meta.get("timeline_stage") or
                                   (match_meta.get("timeline_progress") or {}).get("stage", 0))

    # ── 6. Category dummies ─────────────────────────────────────────────
    cat_key = f"cat_{category}"
    if cat_key in feat:
        feat[cat_key] = 1.0

    return feat


def features_to_array(feat_dict: dict[str, float]) -> list[float]:
    """dict → FULL_FEATURE_NAMES 순서의 float list (LightGBM 입력용)."""
    return [feat_dict.get(k, 0.0) for k in FULL_FEATURE_NAMES]


def feature_names() -> list[str]:
    return list(FULL_FEATURE_NAMES)
