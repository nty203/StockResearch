"""LLM 검증 결과를 DB에 반영 (verify-stocks 스킬용).

Usage:
  python _llm_apply_verdicts.py --verdicts '[{"match_id": "...", "verdict": "reject", "reason": "..."}]'
  python _llm_apply_verdicts.py --file verdicts.json

verdict 값:
  "confirm"   → confidence 유지 또는 +0.05 보정, evidence에 LLM 확인 기록
  "reject"    → exited_at 설정 (false positive 제거)
  "uncertain" → evidence에 불확실 기록, confidence -0.05 (scanner 재평가 유도)

출력: 처리 요약 텍스트
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
if sys.stdout.encoding != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()
from supabase import create_client

client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verdicts", type=str, help="JSON 문자열")
    parser.add_argument("--file", type=str, help="JSON 파일 경로")
    args = parser.parse_args()

    if args.file:
        with open(args.file, encoding="utf-8") as f:
            verdicts = json.load(f)
    elif args.verdicts:
        verdicts = json.loads(args.verdicts)
    else:
        print("--verdicts 또는 --file 필요")
        sys.exit(1)

    now = datetime.now(timezone.utc).isoformat()
    confirmed = rejected = uncertain = errors = 0

    for v in verdicts:
        match_id = v.get("match_id")
        verdict = v.get("verdict", "uncertain")
        reason = v.get("reason", "")[:300]
        confidence_delta = v.get("confidence_delta", 0.0)

        try:
            # 현재 row 조회
            row = client.table("hundredx_category_matches").select(
                "id, ticker, category, confidence, evidence"
            ).eq("id", match_id).execute()
            if not row.data:
                print(f"  [SKIP] {match_id} - 찾을 수 없음")
                continue
            r = row.data[0]
            current_conf = float(r.get("confidence") or 0)
            evidence = list(r.get("evidence") or [])

            # LLM 판단 evidence 추가
            llm_ev = {
                "source_type": "llm_verdict",
                "source_id": f"llm_{now[:10]}",
                "text_excerpt": f"LLM {verdict}: {reason}",
                "date": now[:10],
                "amount": None,
            }

            if verdict == "reject":
                client.table("hundredx_category_matches").update({
                    "exited_at": now,
                    "evidence": evidence + [llm_ev],
                }).eq("id", match_id).execute()
                print(f"  [REJECT] {r['ticker']} {r['category']} — {reason[:60]}")
                rejected += 1

            elif verdict == "confirm":
                new_conf = min(0.95, current_conf + max(0.0, confidence_delta))
                client.table("hundredx_category_matches").update({
                    "confidence": new_conf,
                    "evidence": evidence + [llm_ev],
                }).eq("id", match_id).execute()
                print(f"  [CONFIRM] {r['ticker']} {r['category']} conf {current_conf:.3f}→{new_conf:.3f}")
                confirmed += 1

            else:  # uncertain
                new_conf = max(0.70, current_conf + min(0.0, confidence_delta))
                client.table("hundredx_category_matches").update({
                    "confidence": new_conf,
                    "evidence": evidence + [llm_ev],
                }).eq("id", match_id).execute()
                print(f"  [UNCERTAIN] {r['ticker']} {r['category']} conf {current_conf:.3f}→{new_conf:.3f}")
                uncertain += 1

        except Exception as e:
            print(f"  [ERROR] {match_id}: {e}")
            errors += 1

    print(f"\n결과: confirm={confirmed} reject={rejected} uncertain={uncertain} error={errors}")


if __name__ == "__main__":
    main()
