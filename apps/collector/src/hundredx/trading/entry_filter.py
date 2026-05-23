"""매수 시점 필터 — detection ≠ buy.

모든 조건이 AND로 통과해야 매수 신호 발생.

조건:
  1. Confidence ≥ threshold (기본 0.75)
  2. 유동성: ADV60 ≥ target_position_value × 100 (시장 임팩트 < 1%)
  3. 가격 모멘텀: MA20 > MA60 > MA200 (CAN SLIM 'M' 변형)
  4. Regime: KOSPI/KOSDAQ은 지수 200d MA 위일 때만
  5. 최근 갭다운 없음: -15% 이내

각 필터는 named reason과 함께 실패/통과를 반환해 audit trail 제공.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EntryDecision:
    should_buy: bool
    reason: str            # 통과 시 "buy", 실패 시 실패한 조건
    failed_filters: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)


def check_entry(
    ticker: str,
    category: str,
    confidence: float,
    stock_data: dict,
    portfolio_state: dict | None = None,
    *,
    min_confidence: float = 0.75,
    target_position_value_krw: float = 5_000_000,   # 500만원 기준 포지션
    min_adv_multiplier: float = 100.0,              # ADV ≥ 포지션 × 100배
    require_momentum: bool = True,
    require_regime: bool = True,
    max_recent_drawdown: float = -0.15,             # 최근 -15% 이상 갭다운 차단
    blocked_categories: set[str] | None = None,
) -> EntryDecision:
    """매수 가능 여부 판단.

    Args:
        ticker: 종목 코드
        category: PPTR 카테고리
        confidence: PPTR calibrated confidence
        stock_data: 재무+가격 데이터 dict
        portfolio_state: 현재 포트폴리오 상태 (집중도 체크용)
    """
    blocked = blocked_categories or {"미분류", "단기_테마_급등"}
    failed: list[str] = []
    details: dict = {}

    # 1. 카테고리 블랙리스트
    if category in blocked:
        return EntryDecision(False, "blocked_category",
                             [f"blocked_category:{category}"], {})

    # 2. Confidence
    details["confidence"] = confidence
    if confidence < min_confidence:
        failed.append(f"low_confidence:{confidence:.3f}<{min_confidence}")

    # 3. 유동성 필터
    adv60 = _safe(stock_data.get("avg_daily_value_60d") or
                  stock_data.get("avg_daily_volume_60d"))
    min_adv = target_position_value_krw * min_adv_multiplier
    details["adv60"] = adv60
    details["min_adv"] = min_adv
    if adv60 > 0 and adv60 < min_adv:
        failed.append(f"illiquid:adv60={adv60:.0f}<{min_adv:.0f}")

    # 4. 가격 모멘텀 (MA 정렬)
    if require_momentum:
        close = _safe(stock_data.get("close") or stock_data.get("price_close"))
        ma20 = _safe(stock_data.get("ma20") or stock_data.get("sma_20"))
        ma60 = _safe(stock_data.get("ma60") or stock_data.get("sma_60"))
        ma200 = _safe(stock_data.get("ma200") or stock_data.get("sma_200"))
        details.update({"close": close, "ma20": ma20, "ma60": ma60, "ma200": ma200})
        # 데이터 없으면 skip (MA 데이터 미수집 종목은 통과)
        if close > 0 and ma20 > 0 and ma60 > 0 and ma200 > 0:
            if not (ma20 > ma60 > ma200):
                failed.append(f"weak_momentum:ma20={ma20:.0f},ma60={ma60:.0f},ma200={ma200:.0f}")

    # 5. Regime filter (KR only)
    if require_regime:
        market = stock_data.get("market", "")
        if market in ("KOSPI", "KOSDAQ"):
            kospi_close = _safe(stock_data.get("kospi_close"))
            kospi_ma200 = _safe(stock_data.get("kospi_ma200"))
            if kospi_close > 0 and kospi_ma200 > 0:
                details["kospi_regime"] = kospi_close > kospi_ma200
                if kospi_close < kospi_ma200:
                    failed.append(f"bear_regime:kospi={kospi_close:.0f}<ma200={kospi_ma200:.0f}")

    # 6. 최근 갭다운 체크
    min_60d_ret = _safe(stock_data.get("min_60d_return") or stock_data.get("min_return_60d"))
    if min_60d_ret < 0:
        details["min_60d_return"] = min_60d_ret
        if min_60d_ret < max_recent_drawdown:
            failed.append(f"recent_crash:{min_60d_ret:.2%}<{max_recent_drawdown:.2%}")

    # 7. 포트폴리오 집중도 체크
    if portfolio_state:
        cat_weight = _safe(portfolio_state.get(f"category_weight_{category}", 0))
        max_cat_weight = _safe(portfolio_state.get("max_category_weight", 0.25), 0.25)
        details["category_current_weight"] = cat_weight
        if cat_weight >= max_cat_weight:
            failed.append(f"category_full:{category}={cat_weight:.1%}>={max_cat_weight:.1%}")

        total_positions = int(portfolio_state.get("n_positions", 0))
        max_positions = int(portfolio_state.get("max_positions", 15))
        details["n_positions"] = total_positions
        if total_positions >= max_positions:
            failed.append(f"portfolio_full:{total_positions}>={max_positions}")

    if failed:
        return EntryDecision(
            should_buy=False,
            reason=failed[0],
            failed_filters=failed,
            details=details,
        )

    return EntryDecision(should_buy=True, reason="buy", details=details)


def _safe(val, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default
