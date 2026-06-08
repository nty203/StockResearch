from src.upsert import get_client
client = get_client()

# Update sector_tag for key watch-list tickers to ensure high-quality detection
sector_updates = {
    "082740": "조선/엔진",      # 한화엔진
    "077970": "조선/엔진",      # STX엔진
    "329180": "조선",          # HD현대중공업
    "267260": "조선/엔진",      # HD현대마린엔진
    "064350": "방산",          # 현대로템
    "012450": "방산",          # 한화에어로스페이스
    "079550": "방산",          # LIG넥스원
    "006220": "전력기기",      # 세명전기
    "010130": "전력기기",      # 제룡산업
    "083450": "열관리/냉각",    # GST
    "053080": "열관리/냉각",    # 케이엔솔
    "042700": "반도체",        # 한미반도체
    "006280": "제약/바이오",    # 녹십자
    "365270": "제약/바이오",    # 큐라클
    "476060": "제약/바이오",    # 온코닉테라퓨틱스
    "001630": "제약/바이오",    # 종근당홀딩스
}

print("=== UPDATING SECTOR TAGS IN DB ===")
updated_count = 0
for ticker, tag in sector_updates.items():
    try:
        res = client.table("stocks").update({"sector_tag": tag}).eq("ticker", ticker).execute()
        if res.data:
            print(f"  [{ticker}] updated to sector: {tag}")
            updated_count += 1
        else:
            print(f"  [{ticker}] not found or update skipped")
    except Exception as e:
        print(f"  [{ticker}] update failed: {e}")

print(f"\nDone: {updated_count} stocks sector_tag updated.")
