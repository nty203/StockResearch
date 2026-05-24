"""DART 공시 body fetcher.

OpenDART API: https://opendart.fss.or.kr/api/document.xml?crtfc_key=KEY&rcept_no=XXX
→ ZIP 응답 → XML 파일 1개 포함 → XML 텍스트 추출.

rate limit: 일 10,000회. 각 호출은 평균 ~50ms (네트워크 포함).

사용:
    from src.utils.dart_body import fetch_body, extract_rcept_no
    rno = extract_rcept_no(url)
    body = fetch_body(rno)  # str or None
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
import zipfile
import xml.etree.ElementTree as ET
from typing import Iterable

import requests

logger = logging.getLogger(__name__)

DART_DOC_URL = "https://opendart.fss.or.kr/api/document.xml"
RCEPT_NO_RE = re.compile(r"rcpNo=(\d+)|rcept_no=(\d+)")

# XML 태그 중 본문성 정보를 담고 있다고 간주하는 요소
# DART XML 구조는 매우 다양하므로 일단 모든 element text를 모은다.
_NOISE_TAGS = {
    "DOCUMENT-NAME", "FORMULA-VERSION", "COMPANY-NAME", "ENGLISH-COMPANY-NAME",
    "SUMMARY", "EXTRACTION",
}


def extract_rcept_no(url_or_text: str | None) -> str | None:
    """URL 또는 텍스트에서 rcept_no (또는 rcpNo) 추출."""
    if not url_or_text:
        return None
    m = RCEPT_NO_RE.search(str(url_or_text))
    if not m:
        return None
    return m.group(1) or m.group(2)


def _xml_to_text(xml_bytes: bytes, max_chars: int = 20_000) -> str:
    """DART XML → 평문 텍스트. 태그 제거하고 의미 있는 텍스트만 모은다."""
    try:
        text_blocks: list[str] = []
        # XML 파싱 실패 가능성 — 폴백: 정규식으로 태그 제거
        try:
            content = xml_bytes.decode("utf-8", errors="replace")
            # XML 명세보다 관대하게 — 일부 DART 응답은 깨진 entity 포함
            content_cleaned = re.sub(r"&(?!(amp|lt|gt|quot|apos);)", "&amp;", content)
            root = ET.fromstring(content_cleaned)
            for el in root.iter():
                if el.tag in _NOISE_TAGS:
                    continue
                if el.text and el.text.strip():
                    text_blocks.append(el.text.strip())
                if el.tail and el.tail.strip():
                    text_blocks.append(el.tail.strip())
        except ET.ParseError:
            # 폴백: 단순 태그 제거
            text = xml_bytes.decode("utf-8", errors="replace")
            text = re.sub(r"<[^>]+>", " ", text)
            text_blocks = [t for t in text.split() if t.strip()]

        out = " ".join(text_blocks)
        # 다중 공백 정리
        out = re.sub(r"\s+", " ", out).strip()
        return out[:max_chars]
    except Exception as exc:
        logger.warning("xml_to_text failed: %s", exc)
        return ""


def fetch_body(rcept_no: str, api_key: str | None = None, timeout: float = 30.0) -> str | None:
    """단일 rcept_no 의 공시 본문 텍스트 추출.

    Returns:
        본문 텍스트 (최대 20,000자) 또는 실패 시 None.
    """
    key = api_key or os.environ.get("DART_API_KEY")
    if not key:
        logger.error("DART_API_KEY missing — cannot fetch body")
        return None

    try:
        resp = requests.get(
            DART_DOC_URL,
            params={"crtfc_key": key, "rcept_no": rcept_no},
            timeout=timeout,
        )
    except requests.RequestException as exc:
        logger.warning("DART fetch error rcept=%s: %s", rcept_no, exc)
        return None

    if resp.status_code != 200 or not resp.content:
        logger.debug("DART %s returned status=%s", rcept_no, resp.status_code)
        return None

    # ZIP 인지 확인
    if resp.content[:2] != b"PK":
        # JSON 에러 또는 HTML 페이지 — DART error response
        snippet = resp.text[:200] if resp.text else "(binary)"
        logger.debug("DART %s not zip: %s", rcept_no, snippet[:120])
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            names = [n for n in zf.namelist() if n.lower().endswith(".xml")]
            if not names:
                return None
            with zf.open(names[0]) as f:
                xml_bytes = f.read()
        return _xml_to_text(xml_bytes)
    except zipfile.BadZipFile:
        logger.warning("Bad zip from DART %s", rcept_no)
        return None


def fetch_bodies_batch(
    rcept_nos: Iterable[str],
    api_key: str | None = None,
    sleep_between: float = 0.1,
    max_retries: int = 2,
) -> dict[str, str]:
    """여러 rcept_no를 순차 fetch. rate limit 보호용 sleep 삽입.

    Returns:
        {rcept_no: body_text} — 실패한 항목은 결과에서 제외.
    """
    out: dict[str, str] = {}
    key = api_key or os.environ.get("DART_API_KEY")
    if not key:
        return out

    for i, rno in enumerate(rcept_nos):
        body = None
        for attempt in range(max_retries):
            body = fetch_body(rno, key)
            if body is not None:
                break
            time.sleep(0.5)
        if body:
            out[rno] = body
        if sleep_between > 0:
            time.sleep(sleep_between)
        if (i + 1) % 50 == 0:
            logger.info("DART body batch progress: %d/%s", i + 1, "?")

    return out
