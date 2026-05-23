"""Bayesian hierarchical Beta-Binomial base rate 추정.

현재 하드코딩된 base rate (수주잔고_선행=0.42 등)을 데이터 기반으로 갱신.
작은 sample에서도 posterior mean + credible interval을 제공.

모델:
  p_cat | α_global, β_global ~ Beta(α_global, β_global)   (카테고리별 base rate)
  hits_cat | p_cat ~ Binomial(n_cat, p_cat)               (카테고리별 관측)

Conjugate update (pymc 없이도 가능):
  Prior: Beta(α, β)
  Posterior: Beta(α + hits, β + (n - hits))

사용법:
  brates = compute_bayesian_base_rates(training_samples)
  brates["수주잔고_선행"]  → {"mean": 0.38, "ci_lower": 0.28, "ci_upper": 0.48, "n": 15}
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# 기존 하드코딩 base rate — posterior prior 역할
_PRIOR_BASE_RATES: dict[str, tuple[float, float]] = {
    # (α, β) — 경험적 prior (기존 0.42 → α=4.2, β=5.8 정도)
    "수주잔고_선행":  (4.2, 5.8),
    "수익성_급전환":  (3.8, 6.2),
    "빅테크_파트너":  (3.5, 6.5),
    "플랫폼_독점":    (3.4, 6.6),
    "공급_병목":      (3.4, 6.6),
    "정책_수혜":      (3.1, 6.9),
    "임상_파이프라인":(2.8, 7.2),
}
_DEFAULT_PRIOR = (3.4, 6.6)   # 미분류 카테고리용


@dataclass
class CategoryBaseRate:
    category: str
    posterior_mean: float
    posterior_std: float
    ci_lower: float    # 5th percentile
    ci_upper: float    # 95th percentile
    n_observed: int    # 관측 샘플 수
    n_hits: int        # 10x 달성 수
    prior_alpha: float
    prior_beta: float


def _beta_mean(alpha: float, beta: float) -> float:
    return alpha / (alpha + beta)


def _beta_std(alpha: float, beta: float) -> float:
    ab = alpha + beta
    return math.sqrt(alpha * beta / (ab * ab * (ab + 1)))


def _beta_quantile(alpha: float, beta: float, p: float) -> float:
    """Beta distribution quantile via Newton's method (no scipy needed)."""
    # 초기값: mean
    x = _beta_mean(alpha, beta)
    # Regularized incomplete beta 근사 — scipy 없을 때 수치 근사
    try:
        from scipy.stats import beta as scipy_beta
        return float(scipy_beta.ppf(p, alpha, beta))
    except ImportError:
        pass
    # Fallback: mean ± z*std
    z = -1.645 if p < 0.5 else 1.645
    return max(0.01, min(0.99, _beta_mean(alpha, beta) + z * _beta_std(alpha, beta)))


def compute_bayesian_base_rates(
    samples: list[dict],
    label_key: str = "label_10x_24m",
    category_key: str = "category",
) -> dict[str, CategoryBaseRate]:
    """학습 샘플에서 카테고리별 Bayesian posterior base rate 계산.

    Args:
        samples: pptr_training_samples rows (dict with 'category', 'label_10x_24m')
        label_key: 사용할 라벨 키
        category_key: 카테고리 키

    Returns:
        {"수주잔고_선행": CategoryBaseRate(...), ...}
    """
    # 카테고리별 집계
    counts: dict[str, list[int]] = {}
    for s in samples:
        cat = s.get(category_key) or "미분류"
        label = int(s.get(label_key, 0))
        counts.setdefault(cat, []).append(label)

    result: dict[str, CategoryBaseRate] = {}

    # 모든 카테고리 (prior에 있는 것 + 관측된 것)
    all_cats = set(_PRIOR_BASE_RATES) | set(counts)
    for cat in all_cats:
        prior_a, prior_b = _PRIOR_BASE_RATES.get(cat, _DEFAULT_PRIOR)
        obs = counts.get(cat, [])
        n = len(obs)
        hits = sum(obs)

        # Conjugate posterior
        post_a = prior_a + hits
        post_b = prior_b + (n - hits)

        result[cat] = CategoryBaseRate(
            category=cat,
            posterior_mean=round(_beta_mean(post_a, post_b), 4),
            posterior_std=round(_beta_std(post_a, post_b), 4),
            ci_lower=round(_beta_quantile(post_a, post_b, 0.05), 4),
            ci_upper=round(_beta_quantile(post_a, post_b, 0.95), 4),
            n_observed=n,
            n_hits=hits,
            prior_alpha=prior_a,
            prior_beta=prior_b,
        )

    return result


def get_base_rate(
    category: str,
    base_rates: dict[str, CategoryBaseRate] | None = None,
) -> float:
    """단일 카테고리의 posterior mean base rate 반환.

    base_rates가 없으면 prior mean 사용 (하드코딩 fallback).
    """
    if base_rates is not None and category in base_rates:
        return base_rates[category].posterior_mean
    prior_a, prior_b = _PRIOR_BASE_RATES.get(category, _DEFAULT_PRIOR)
    return _beta_mean(prior_a, prior_b)


def print_base_rate_report(base_rates: dict[str, CategoryBaseRate]) -> None:
    print(f"\n=== Bayesian Base Rates ===")
    print(f"{'Category':<22} {'Mean':>6} {'Std':>6} {'CI 90%':>16} {'n':>6} {'hits':>6}")
    for cat, br in sorted(base_rates.items(), key=lambda x: -x[1].posterior_mean):
        ci = f"[{br.ci_lower:.3f}, {br.ci_upper:.3f}]"
        overlap_warning = "  ←overlap" if br.ci_upper - br.ci_lower > 0.3 else ""
        print(f"{cat:<22} {br.posterior_mean:>6.3f} {br.posterior_std:>6.3f} "
              f"{ci:>16} {br.n_observed:>6} {br.n_hits:>6}{overlap_warning}")
