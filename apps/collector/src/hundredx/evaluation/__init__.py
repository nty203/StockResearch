"""HundredX 평가 인프라.

5개 평가 축:
  A. diagnostics    — 현재 match 분포·결측·미스매치 (즉시 계산)
  B. forward_returns — 과거 match의 N개월 후 수익률 (prices_daily 기반)
  C. calibration    — confidence vs LLM verdict 정합성
  D. library_recall — point-in-time replay로 라이브러리 종목 사전탐지율
  E. summary        — 대시보드용 top-line KPI

모든 결과는 hundredx_evaluation_runs 테이블에 누적 저장 (시계열 추적).
"""
from .orchestrator import run_full_evaluation

__all__ = ["run_full_evaluation"]
