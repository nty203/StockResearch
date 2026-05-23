"""안전한 웹 크롤링 유틸리티.

rate limit, retry, User-Agent 처리를 통합.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# 다양한 User-Agent 풀 — 최신 브라우저 위주
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

_DEFAULT_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
}

_JSON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


def random_ua() -> str:
    """무작위 User-Agent 반환."""
    return random.choice(_USER_AGENTS)


def fetch_json(
    url: str,
    *,
    params: dict | None = None,
    data: dict | None = None,
    method: str = "GET",
    headers: dict | None = None,
    referer: str | None = None,
    timeout: float = 15.0,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    encoding: str | None = None,
) -> Any:
    """JSON을 반환하는 엔드포인트에 안전하게 요청.

    Args:
        url: 요청 URL
        params: GET 파라미터
        data: POST 폼 데이터
        method: HTTP 메서드
        headers: 추가 헤더
        referer: Referer 헤더
        timeout: 요청 타임아웃 (초)
        max_retries: 최대 재시도 횟수
        retry_delay: 재시도 간격 (초, 지수 백오프)
        encoding: 응답 디코딩 인코딩 (None=자동)

    Returns:
        파싱된 JSON 또는 None (실패 시)
    """
    req_headers = {**_DEFAULT_HEADERS, **_JSON_HEADERS}
    req_headers["User-Agent"] = random_ua()
    if referer:
        req_headers["Referer"] = referer
    if headers:
        req_headers.update(headers)

    for attempt in range(max_retries):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers=req_headers,
            ) as client:
                if method.upper() == "POST" or data:
                    resp = client.post(url, params=params, data=data)
                else:
                    resp = client.get(url, params=params)

                if resp.status_code == 429:
                    # Rate limited — 더 오래 대기
                    wait = retry_delay * (2 ** attempt) + random.uniform(1, 3)
                    logger.warning("Rate limited by %s, waiting %.1fs", url, wait)
                    time.sleep(wait)
                    continue

                if resp.status_code == 403:
                    logger.warning("403 Forbidden: %s (attempt %d)", url, attempt + 1)
                    time.sleep(retry_delay)
                    continue

                resp.raise_for_status()

                if not resp.content:
                    logger.debug("Empty response from %s", url)
                    return None

                try:
                    return resp.json()
                except Exception:
                    # Not JSON — try text parsing
                    text = resp.text
                    import json
                    text = text.strip()
                    if text.startswith(("{", "[")):
                        return json.loads(text)
                    logger.debug("Non-JSON response from %s: %s...", url, text[:100])
                    return None

        except httpx.TimeoutException:
            wait = retry_delay * (attempt + 1)
            logger.warning("Timeout fetching %s (attempt %d), retry in %.1fs", url, attempt + 1, wait)
            time.sleep(wait)
        except httpx.HTTPStatusError as e:
            logger.warning("HTTP %d fetching %s: %s", e.response.status_code, url, e)
            if e.response.status_code >= 500:
                time.sleep(retry_delay * (attempt + 1))
            else:
                break  # 4xx는 재시도 의미 없음
        except Exception as e:
            logger.warning("Error fetching %s (attempt %d): %s", url, attempt + 1, e)
            time.sleep(retry_delay)

    return None


def fetch_text(
    url: str,
    *,
    params: dict | None = None,
    headers: dict | None = None,
    referer: str | None = None,
    encoding: str | None = None,
    timeout: float = 15.0,
    max_retries: int = 3,
) -> str | None:
    """텍스트를 반환하는 엔드포인트에 안전하게 요청."""
    req_headers = {**_DEFAULT_HEADERS}
    req_headers["User-Agent"] = random_ua()
    if referer:
        req_headers["Referer"] = referer
    if headers:
        req_headers.update(headers)

    for attempt in range(max_retries):
        try:
            with httpx.Client(
                timeout=timeout,
                follow_redirects=True,
                headers=req_headers,
            ) as client:
                resp = client.get(url, params=params)

                if resp.status_code == 429:
                    wait = 5.0 * (2 ** attempt)
                    logger.warning("Rate limited, waiting %.1fs", wait)
                    time.sleep(wait)
                    continue

                resp.raise_for_status()

                if encoding:
                    return resp.content.decode(encoding, errors="replace")
                return resp.text

        except Exception as e:
            logger.warning("Error fetching %s (attempt %d): %s", url, attempt + 1, e)
            time.sleep(2.0 * (attempt + 1))

    return None


def sleep_polite(base: float = 1.0, jitter: float = 0.5) -> None:
    """서버 부하 분산을 위한 예의 있는 딜레이."""
    time.sleep(base + random.uniform(0, jitter))
