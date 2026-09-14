import os
import json
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv("apps/collector/.env")
load_dotenv("apps/web/.env.local")

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")
supabase: Client = create_client(url, key)

idea_id = "ab514427-9c19-484b-b140-dbf7725fcc22"

updated_candidates = [
  {
    "name": "에스앤에스텍",
    "role": "대장주",
    "ret_1m": 25.5,
    "ret_3m": 49.7,
    "ticker": "101490",
    "signal_flag": "✅돌파직후",
    "near_52w_high": 99.7,
    "early_signal_score": 55.0
  },
  {
    "name": "동진쎄미켐",
    "role": "대장주",
    "ret_1m": 35.9,
    "ret_3m": 48.7,
    "ticker": "005290",
    "signal_flag": "✅돌파직후",
    "near_52w_high": 100.0,
    "early_signal_score": 55.0
  },
  {
    "name": "파크시스템스",
    "role": "2차 수혜",
    "ret_1m": 11.4,
    "ret_3m": 6.8,
    "ticker": "140860",
    "signal_flag": "🔺임박",
    "near_52w_high": 92.7,
    "early_signal_score": 61.4
  },
  {
    "name": "에프에스티",
    "role": "밸류체인",
    "ret_1m": -28.7,
    "ret_3m": -46.1,
    "ticker": "036810",
    "signal_flag": "🔵하단",
    "near_52w_high": 46.6,
    "early_signal_score": 20.0
  },
  {
    "name": "엘오티베큠",
    "role": "후행주",
    "ret_1m": -22.9,
    "ret_3m": -36.7,
    "ticker": "083310",
    "signal_flag": "🔵하단",
    "near_52w_high": 52.6,
    "early_signal_score": 20.0
  }
]

updated_data = {
    "causal_chain": "인텔의 High-NA EUV 도입으로 1나노급 초미세공정 경쟁 본격화 -> EUV 펠리클, 블랭크마스크, 포토레지스트 등 국산화 선단공정 소재/장비의 수요(Q) 및 단가(P) 급증 -> 단기 증시 눌림목에서 EUV 밸류체인 핵심주 줍줍 기회.",
    "technical_alignment_reason": "동진쎄미켐, 에스앤에스텍, 파크시스템스 등 주요 EUV 장비/소재 밸류체인의 수급 및 신고가 접근도가 점진적으로 회복되는 추세",
    "candidates": updated_candidates
}

def update_idea():
    res = supabase.table("macro_ideas").update(updated_data).eq("id", idea_id).execute()
    print("Update status:", res)

if __name__ == "__main__":
    update_idea()
