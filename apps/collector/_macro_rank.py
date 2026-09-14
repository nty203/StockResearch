import sys
sys.stdout.reconfigure(encoding='utf-8')
from src.macro_themes import rank_themes
rows = rank_themes()
print("=== 테마 랭킹 결과 ===")
for i, r in enumerate(rows, 1):
    print(f"{i}위 [{r['score']}점] {r['theme']} | 정렬:{r['aligned']} QP+:{r['qp_pos']} QP-:{r['qp_neg']} 가속:{r['accel']}")
    for c in r['candidates'][:3]:
        print(f"   - {c['ticker']} {c['name']} | 52w:{c['near_52w_high']}% 1M:{c['ret_1m']}% 3M:{c['ret_3m']}% 신호:{c['signal_flag']} 얼리:{c['early_signal_score']}")
    print()
