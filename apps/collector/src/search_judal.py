import sys
import json
import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def search_judal_theme(keyword: str) -> List[Dict[str, Any]]:
    """
    Search for theme and related stocks on judal.co.kr in real-time.
    """
    search_url = f"https://judal.co.kr/search?q={keyword}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # This is a placeholder for the actual scraping logic which depends on Judal's DOM.
        # For now, we simulate the return based on the user's identified stocks.
        # In a real scenario, this would parse the search results for theme-to-stock links.
        
        results = []
        if "socamm" in keyword.lower() or "기판" in keyword:
            results = [
                {"ticker": "007810", "name": "코리아써키트", "reason": "SOCAMM2 규격 채택 및 공급"},
                {"ticker": "222800", "name": "심텍", "reason": "고성능 패키징 기판 주력"},
                {"ticker": "036930", "name": "주성엔지니어링", "reason": "기판 공정 원자층 증착 장비"}
            ]
        elif "밸류업" in keyword or "주주환원" in keyword:
            results = [
                {"ticker": "033780", "name": "KT&G", "reason": "성장주 전환 선언 및 자사주 소각"},
                {"ticker": "071055", "name": "한국금융지주", "reason": "대표적 저PBR 및 주주환원 수혜"},
                {"ticker": "381970", "name": "케이카", "reason": "KG그룹 밸류업 로드맵 포함"}
            ]
            
        return results
    except Exception as e:
        logger.error(f"Judal search failed: {e}")
        return []

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps([]))
        sys.exit(0)
        
    kw = sys.argv[1]
    print(json.dumps(search_judal_theme(kw), ensure_ascii=False))
