"""DART quarterly financials collector via OpenDartReader."""
import logging
import os
import time

import OpenDartReader as DartReader

from .upsert import get_client, upsert_batch, pipeline_run

logger = logging.getLogger(__name__)

DART_API_KEY = os.environ.get("DART_API_KEY", "")

# Map DART reprt_code to quarters: 11013=Q1, 11012=Q2, 11014=Q3, 11011=Q4/Annual
REPRT_CODES = {
    "11013": "Q1",
    "11012": "Q2",
    "11014": "Q3",
    "11011": "Q4",
}

# DART 수주잔고 계정명 후보 목록 (사업보고서마다 표기가 다름)
_BACKLOG_ACCOUNT_NAMES = [
    "수주잔액",
    "수주잔고",
    "수주 잔액",
    "수주 잔고",
    "수주잔량",
    "order backlog",
    "미이행 계약",
    "이행 예정 수주",
]


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


def _parse_backlog(df) -> float | None:
    """DART 재무제표 df에서 수주잔고 추출 — 계정명 다수 시도."""
    for name in _BACKLOG_ACCOUNT_NAMES:
        mask = df["account_nm"].str.contains(name, case=False, na=False)
        rows = df[mask]
        if not rows.empty:
            val = rows.iloc[0].get("thstrm_amount", rows.iloc[0].get("당기"))
            result = _safe_float(val)
            if result is not None and result > 0:
                logger.debug("order_backlog found via '%s': %s", name, result)
                return result
    return None


def collect_dart_financials(tickers: list[str], years: list[int]) -> list[dict]:
    if not DART_API_KEY:
        logger.error("DART_API_KEY not set")
        return []

    dart = DartReader(DART_API_KEY)
    rows = []

    for ticker in tickers:
        for year in years:
            for reprt_code, quarter_suffix in REPRT_CODES.items():
                fq = f"{year}{quarter_suffix}"
                try:
                    # finstate_all returns full XBRL statements (CF/IS/BS w/ 매출원가, 매출총이익).
                    # finstate only returns 단일회사 주요 재무 (limited 6-row IS, no CF).
                    df = dart.finstate_all(ticker, year, reprt_code=reprt_code)
                    if df is None or df.empty:
                        continue
                    # Parse key metrics from IFRS statements
                    row = _parse_dart_df(df, ticker, fq)
                    if row:
                        rows.append(row)
                    time.sleep(0.1)  # DART rate limit: stay well under 20k/day
                except Exception as e:
                    logger.warning("DART error %s %s: %s", ticker, fq, e)
    return rows


def _get_stmt_df(df, sj_div: str):
    """Filter DataFrame by statement division (BS/IS/CIS/CF/SCE).

    DART finstate() returns all financial statements in one DataFrame.
    sj_div values: 'BS'=재무상태표, 'IS'=손익계산서, 'CIS'=포괄손익, 'CF'=현금흐름표.
    Falls back to full df if sj_div column is absent (older API responses).
    """
    if "sj_div" in df.columns:
        sub = df[df["sj_div"].str.upper() == sj_div.upper()]
        return sub if not sub.empty else df
    # Fallback: filter by statement name keyword
    _sj_keywords = {"BS": "재무상태표", "CF": "현금흐름"}
    if "sj_nm" in df.columns and sj_div in _sj_keywords:
        sub = df[df["sj_nm"].str.contains(_sj_keywords[sj_div], na=False)]
        return sub if not sub.empty else df
    return df


def _parse_dart_df(df, ticker: str, fq: str) -> dict | None:
    """Extract key financial metrics from DART IFRS dataframe.

    DART finstate() returns all statements (IS/BS/CF) in one DataFrame.
    We split by sj_div to avoid account-name collisions across statements.
    """
    def get_amount(src_df, account_nm: str) -> float | None:
        mask = src_df["account_nm"].str.contains(account_nm, na=False)
        rows = src_df[mask]
        if rows.empty:
            return None
        val = rows.iloc[0].get("thstrm_amount", rows.iloc[0].get("당기"))
        return _safe_float(val)

    # Prefer CFS (연결) rows; fall back to OFS (별도)
    for fs_div in ("CFS", "OFS"):
        subset = df[df["fs_div"] == fs_div] if "fs_div" in df.columns else df
        if not subset.empty:
            df = subset
            break

    is_df = _get_stmt_df(df, "IS") or _get_stmt_df(df, "CIS")   # Income Statement
    bs_df = _get_stmt_df(df, "BS")                                # Balance Sheet
    cf_df = _get_stmt_df(df, "CF")                                # Cash Flow

    revenue   = get_amount(is_df, "매출액") or get_amount(is_df, "수익(매출액)")
    op_income = get_amount(is_df, "영업이익")
    net_income = get_amount(is_df, "당기순이익")
    if revenue is None and op_income is None:
        return None

    op_margin = (op_income / revenue * 100) if (revenue and op_income) else None

    # ── FCF = 영업활동현금흐름 − 유형자산 취득 ────────────────────
    # DART cumulates CF ytd: Q1=3mo, Q2=6mo, Q3=9mo, Q4=12mo.
    # Store as-is; db_fetch uses the latest quarter's FCF as the most recent signal.
    fcf = None
    operating_cf = get_amount(cf_df, "영업활동현금흐름") or get_amount(cf_df, "영업활동으로 인한 현금흐름")
    if operating_cf is not None:
        capex_raw = (
            get_amount(cf_df, "유형자산의 취득")
            or get_amount(cf_df, "유형자산 취득")
            or get_amount(cf_df, "유형자산취득")
        )
        # CapEx in CF statement is usually negative (cash outflow).
        # FCF = operating_cf + capex_raw  (capex_raw already negative)
        # If capex_raw is stored as positive absolute: FCF = operating_cf - capex_raw
        # We use the raw value so both signs are handled: negative → correct; positive → still ok
        capex_adj = (capex_raw or 0)
        if capex_raw is not None and capex_raw > 0:
            capex_adj = -capex_raw   # treat positive CapEx as outflow
        fcf = operating_cf + capex_adj

    # ── Balance Sheet ─────────────────────────────────────────────
    total_assets      = get_amount(bs_df, "자산총계")
    total_liabilities = get_amount(bs_df, "부채총계")
    total_equity      = get_amount(bs_df, "자본총계")
    debt_ratio = None
    if total_assets and total_liabilities and total_assets > 0:
        debt_ratio = round(total_liabilities / total_assets * 100, 2)

    # ── Gross profit (Novy-Marx GP/A) ─────────────────────────────
    # DART 손익계산서 표기: '매출총이익' 또는 '매출 총이익'.
    # 없으면 매출원가에서 역산 시도: gross = revenue - cogs
    gross_profit = get_amount(is_df, "매출총이익") or get_amount(is_df, "매출 총이익")
    if gross_profit is None and revenue is not None:
        cogs = get_amount(is_df, "매출원가")
        if cogs is not None:
            gross_profit = revenue - cogs

    # ── CFO (Sloan accruals 분모) ─────────────────────────────────
    cfo = operating_cf  # already extracted above

    # 수주잔고: 별도 계정명으로 다수 시도
    order_backlog = _parse_backlog(df)

    return {
        "ticker": ticker,
        "fq": fq,
        "revenue": revenue,
        "op_income": op_income,
        "net_income": net_income,
        "op_margin": op_margin,
        "order_backlog": order_backlog,
        "roe": None,
        "roic": None,
        "fcf": fcf,
        "debt_ratio": debt_ratio,
        "interest_coverage": None,
        "gross_profit": gross_profit,
        "cfo": cfo,
        "total_assets": total_assets,
        "total_equity": total_equity,
        "total_liab": total_liabilities,
    }


def run(years: list[int] | None = None) -> int:
    from datetime import date
    if years is None:
        y = date.today().year
        years = [y - 2, y - 1, y]

    client = get_client()
    res = client.table("stocks").select("ticker").in_("market", ["KOSPI", "KOSDAQ"]).eq("is_active", True).execute()
    tickers = [r["ticker"] for r in (res.data or [])]

    with pipeline_run(client, "financials") as (rows_out, _):
        rows = collect_dart_financials(tickers, years)
        count = upsert_batch(client, "financials_q", rows, on_conflict="ticker,fq")
        rows_out[0] = count
    logger.info("DART financials upserted %d rows", count)
    return count


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run()
