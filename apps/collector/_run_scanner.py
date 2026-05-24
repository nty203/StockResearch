"""Run hundredx scanner with dotenv."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(level=logging.WARNING, format='%(levelname)s %(name)s %(message)s')

# Suppress overly verbose loggers
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('httpcore').setLevel(logging.ERROR)

print("=== 100배 스캐너 실행 ===")
print("MIN_CONFIDENCE=0.70, 전체 종목 스캔 중...")
print("(시간이 걸릴 수 있습니다 — 3-10분)\n")

from src.hundredx.scanner import run
count = run(0.70)
print(f"\n완료: {count}개 매치 upserted")
