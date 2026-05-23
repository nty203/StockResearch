"""거래비용 + 세금 + 슬리피지 모델.

KR (KOSPI/KOSDAQ):
  - 매수 수수료: 0.015% (키움 기준)
  - 매도 수수료: 0.015%
  - 거래세: 매도 시 0.18% (2024 기준; KOSDAQ 0.18%, KOSPI 0.18%)
  - 시장 임팩트: 20bp + (order / ADV60) × 200bp

US (NYSE/NASDAQ):
  - 수수료: 0 (IBKR Lite 가정)
  - 시장 임팩트: 5bp + (order / ADV60) × 100bp
  - FX 환전: USD↔KRW 30bp

참고:
  - 한국 양도소득세: 대주주(지분 1% 이상 또는 시총 10억+ 보유) 22%
    개인 소액투자자는 현재 면제. 보수적으로 22% 적용 (2025+ 개인 양도세 검토중).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradeCost:
    commission: float     # 수수료
    tax: float            # 세금 (거래세 + 양도세)
    slippage: float       # 시장 임팩트
    total: float          # commission + tax + slippage
    effective_price: float  # 실제 체결가 (slippage 반영)


# ── KR 기본값 ──────────────────────────────────────────────────────────────
KR_COMMISSION_BUY_BPS = 1.5       # 0.015%
KR_COMMISSION_SELL_BPS = 1.5
KR_TRANSACTION_TAX_BPS = 18.0    # 0.18% (매도 전용)
KR_CAPITAL_GAINS_TAX_RATE = 0.22  # 22% (보수적)
KR_BASE_SLIPPAGE_BPS = 20.0      # 고정 20bp
KR_IMPACT_COEFFICIENT = 200.0    # order/ADV × 200bp

# ── US 기본값 ──────────────────────────────────────────────────────────────
US_COMMISSION_BPS = 0.0
US_BASE_SLIPPAGE_BPS = 5.0
US_IMPACT_COEFFICIENT = 100.0
FX_SPREAD_BPS = 30.0


def compute_kr_trade_cost(
    price: float,
    shares: float,
    adv60: float,         # 60일 평균 거래대금 (원)
    side: str = "buy",    # "buy" or "sell"
    entry_price: float = 0.0,  # 매도 시 원가 (양도세 계산용)
    apply_capital_gains: bool = False,  # 개인 소액투자자는 False
) -> TradeCost:
    """KR 종목 거래비용 계산."""
    order_value = price * shares

    # 수수료
    buy_bps = KR_COMMISSION_BUY_BPS if side == "buy" else KR_COMMISSION_SELL_BPS
    commission = order_value * buy_bps / 10000

    # 세금
    tax = 0.0
    if side == "sell":
        tax += order_value * KR_TRANSACTION_TAX_BPS / 10000
        if apply_capital_gains and entry_price > 0:
            profit = (price - entry_price) * shares
            if profit > 0:
                tax += profit * KR_CAPITAL_GAINS_TAX_RATE

    # 슬리피지 (시장 임팩트)
    impact_bps = KR_BASE_SLIPPAGE_BPS
    if adv60 > 0:
        impact_bps += (order_value / adv60) * KR_IMPACT_COEFFICIENT
    impact_bps = min(impact_bps, 200.0)  # cap at 2%
    slippage = order_value * impact_bps / 10000

    # 슬리피지는 체결가에 반영 (buy는 더 비싸게, sell은 더 싸게)
    slip_direction = 1 if side == "buy" else -1
    effective_price = price * (1 + slip_direction * impact_bps / 10000)

    total = commission + tax + slippage
    return TradeCost(
        commission=round(commission, 2),
        tax=round(tax, 2),
        slippage=round(slippage, 2),
        total=round(total, 2),
        effective_price=round(effective_price, 2),
    )


def compute_us_trade_cost(
    price: float,
    shares: float,
    adv60_usd: float,
    side: str = "buy",
    fx_rate: float = 1350.0,   # USD/KRW
    entry_price: float = 0.0,
    apply_capital_gains: bool = False,
) -> TradeCost:
    """US 종목 거래비용 계산."""
    order_value = price * shares

    commission = order_value * US_COMMISSION_BPS / 10000

    impact_bps = US_BASE_SLIPPAGE_BPS
    if adv60_usd > 0:
        impact_bps += (order_value / adv60_usd) * US_IMPACT_COEFFICIENT
    impact_bps = min(impact_bps, 100.0)

    # FX 비용 (KRW로 환전할 때만)
    fx_cost = order_value * FX_SPREAD_BPS / 10000

    slippage = order_value * impact_bps / 10000

    tax = 0.0
    if side == "sell" and apply_capital_gains and entry_price > 0:
        profit = (price - entry_price) * shares
        if profit > 0:
            tax = profit * KR_CAPITAL_GAINS_TAX_RATE

    slip_direction = 1 if side == "buy" else -1
    effective_price = price * (1 + slip_direction * impact_bps / 10000)

    total = commission + tax + slippage + fx_cost
    return TradeCost(
        commission=round(commission + fx_cost, 2),
        tax=round(tax, 2),
        slippage=round(slippage, 2),
        total=round(total, 2),
        effective_price=round(effective_price, 2),
    )


def compute_trade_cost(
    price: float,
    shares: float,
    market: str,
    adv60: float = 0.0,
    side: str = "buy",
    entry_price: float = 0.0,
    apply_capital_gains: bool = False,
) -> TradeCost:
    """시장 자동 감지 통합 인터페이스."""
    if market in ("KOSPI", "KOSDAQ"):
        return compute_kr_trade_cost(price, shares, adv60, side, entry_price, apply_capital_gains)
    return compute_us_trade_cost(price, shares, adv60, side, entry_price=entry_price,
                                 apply_capital_gains=apply_capital_gains)
