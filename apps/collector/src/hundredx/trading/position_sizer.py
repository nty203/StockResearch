"""Half-Kelly + Volatility Targeting 포지션 사이징.

MacLean-Thorp-Ziemba (2010): Full Kelly는 이론 최적이나
confidence 추정 5% 오차만 있어도 ruin 확률 폭증.
Half-Kelly = Sharpe 75% 유지 + 위험 1/4.

포지션 사이즈 결정 순서:
  1. Kelly fraction = (p×(b+1) - 1) / b  → 0.5배 적용
  2. Vol targeting: 종목 기여 vol ≤ 12% annualized
  3. 둘 중 작은 값
  4. Confidence scaling: conf 0.75→0%, 0.95→100% 선형
  5. 단일 종목 max 10%, 카테고리 합산 max 25%

payoff_ratio(b):
  - 백테스트에서 카테고리별 avg win / avg loss 비율
  - 데이터 없으면 category_default_b 사용
"""
from __future__ import annotations

import math
from dataclasses import dataclass


# 카테고리별 기대 payoff ratio (백테스트에서 갱신)
# b = avg_win_multiplier / avg_loss (진 거래 손실은 hard stop -20% 가정)
CATEGORY_DEFAULT_PAYOFF: dict[str, float] = {
    "수주잔고_선행":  6.0,   # 큰 수주 → 큰 upside
    "수익성_급전환":  4.5,
    "빅테크_파트너":  5.0,
    "플랫폼_독점":    5.5,
    "공급_병목":      4.0,
    "정책_수혜":      3.5,
    "임상_파이프라인":7.0,   # 바이너리 — 성공 시 크고 실패 시 작음
    "미분류":          3.0,
}

DEFAULT_PAYOFF = 4.0
MAX_SINGLE_WEIGHT = 0.10         # 단일 종목 최대 비중
MAX_CATEGORY_WEIGHT = 0.25       # 카테고리 합산 최대
MIN_CONFIDENCE_SCALE_LOW = 0.75  # 이 값에서 가중치 = 0%
MIN_CONFIDENCE_SCALE_HIGH = 0.95 # 이 값에서 가중치 = 100%
TARGET_CONTRIBUTION_VOL = 0.12   # 연환산 기여 변동성 상한 (12%)


@dataclass
class SizingResult:
    weight: float              # 포트폴리오 대비 비중 (0.0–0.10)
    shares: int                # 매수 주수 (portfolio_value 주어진 경우)
    kelly_fraction: float
    vol_fraction: float
    confidence_scale: float
    reason: str
    details: dict


def compute_position_size(
    category: str,
    confidence: float,
    ann_vol: float,            # 종목 연환산 변동성 (예: 0.45 = 45%)
    portfolio_value: float = 0.0,
    current_price: float = 0.0,
    category_used_weight: float = 0.0,  # 현재 해당 카테고리가 차지하는 비중
    n_current_positions: int = 0,
    max_positions: int = 15,
    payoff_ratio: float | None = None,
    corr_to_portfolio: float = 0.3,    # 포트폴리오와 상관계수 (기본 0.3)
) -> SizingResult:
    """포지션 비중 계산.

    Args:
        category: PPTR 카테고리
        confidence: calibrated PPTR confidence
        ann_vol: 종목 연환산 변동성 (소수, 예: 0.45)
        portfolio_value: 총 포트폴리오 가치 (원)
        current_price: 현재 주가 (주수 계산용)
        category_used_weight: 이미 해당 카테고리에 투자된 비중
        n_current_positions: 현재 보유 종목 수
    """
    # 포트폴리오 꽉 찼으면 0
    if n_current_positions >= max_positions:
        return SizingResult(
            weight=0.0, shares=0,
            kelly_fraction=0.0, vol_fraction=0.0, confidence_scale=0.0,
            reason="portfolio_full",
            details={"n_positions": n_current_positions, "max": max_positions},
        )

    b = payoff_ratio or CATEGORY_DEFAULT_PAYOFF.get(category, DEFAULT_PAYOFF)
    p = confidence

    # 1. Kelly fraction
    kelly = (p * (b + 1) - 1) / b
    kelly = max(0.0, kelly)
    half_kelly = kelly * 0.5

    # 2. Vol targeting: target 12% annualized contribution
    # contribution = weight × vol × sqrt(corr) → solve for weight
    if ann_vol > 0:
        # Simple version: weight = target_vol / (vol × sqrt(corr_to_portfolio))
        corr_adjusted_vol = ann_vol * max(math.sqrt(corr_to_portfolio), 0.1)
        vol_weight = TARGET_CONTRIBUTION_VOL / corr_adjusted_vol
    else:
        vol_weight = MAX_SINGLE_WEIGHT

    # 3. 둘 중 작은 값
    raw_weight = min(half_kelly, vol_weight, MAX_SINGLE_WEIGHT)

    # 4. Confidence scaling: 선형 0% @ 0.75 → 100% @ 0.95
    conf_scale = max(0.0, (confidence - MIN_CONFIDENCE_SCALE_LOW) /
                     (MIN_CONFIDENCE_SCALE_HIGH - MIN_CONFIDENCE_SCALE_LOW))
    conf_scale = min(1.0, conf_scale)
    scaled_weight = raw_weight * conf_scale

    # 5. 카테고리 집중도 제한
    remaining_cat = max(0.0, MAX_CATEGORY_WEIGHT - category_used_weight)
    final_weight = min(scaled_weight, remaining_cat)
    final_weight = round(final_weight, 4)

    # 6. 주수 계산
    shares = 0
    if portfolio_value > 0 and current_price > 0 and final_weight > 0:
        target_value = portfolio_value * final_weight
        shares = int(target_value // current_price)

    reason = "sized" if final_weight > 0 else (
        "cat_full" if remaining_cat <= 0 else
        "kelly_zero" if kelly <= 0 else
        "conf_too_low" if conf_scale == 0 else "zero"
    )

    return SizingResult(
        weight=final_weight,
        shares=shares,
        kelly_fraction=round(half_kelly, 4),
        vol_fraction=round(vol_weight, 4),
        confidence_scale=round(conf_scale, 4),
        reason=reason,
        details={
            "kelly_raw": round(kelly, 4),
            "half_kelly": round(half_kelly, 4),
            "vol_weight": round(vol_weight, 4),
            "payoff_b": b,
            "conf": confidence,
            "ann_vol": ann_vol,
            "category_used": category_used_weight,
            "category_remaining": remaining_cat,
        },
    )
