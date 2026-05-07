from src.upsert import get_client
client = get_client()

test_filings = [
    {
        "ticker": "082740",
        "source": "DART",
        "filing_type": "단일계약체결",
        "filed_at": "2026-05-07T00:00:00+09:00",
        "url": "https://dart.fss.or.kr/test",
        "headline": "데이터센터 비상발전용 중속엔진 공급계약 체결 (힘센엔진)",
        "raw_text": "한화엔진은 글로벌 데이터센터 고객사와 2000억원 규모의 비상발전기용 중속엔진 공급계약을 체결하였습니다. 전력 수요 폭증에 따른 공급 병목 현상으로 납기가 확대되고 있습니다.",
        "keywords": ["발전엔진", "데이터센터", "공급계약"]
    },
    {
        "ticker": "083450",
        "source": "DART",
        "filing_type": "기타경영사항",
        "filed_at": "2026-05-07T00:00:00+09:00",
        "url": "https://dart.fss.or.kr/test2",
        "headline": "AI 데이터센터용 액체냉각 시스템 독점 공급",
        "raw_text": "GST는 하이퍼스케일러 데이터센터에 액체냉각(Liquid Cooling) 솔루션을 독점 공급하기로 하였습니다. 열관리 시장의 병목 현상을 해결하는 혁신 플랫폼입니다.",
        "keywords": ["액체냉각", "데이터센터", "독점"]
    }
]

# Use simple insert to avoid conflict issue for now
try:
    res = client.table("filings").insert(test_filings).execute()
    print(f"Inserted {len(res.data or [])} test filings.")
except Exception as e:
    print(f"Insert failed (likely duplicate): {e}")
