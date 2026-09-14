import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from src.macro_themes import rank_themes

rows = rank_themes()
theme_map = {r['theme']: r for r in rows}

# 선택된 3개 테마의 후보주 상세 출력
selected = ['AI반도체/HBM', '전자부품/AI기판', '내수소비/유통/명품']

for theme in selected:
    r = theme_map.get(theme)
    if not r:
        continue
    print(f"\n{'='*70}")
    print(f"테마: {theme} | 점수: {r['score']} | 정렬: {r['aligned']} | QP+:{r['qp_pos']} QP-:{r['qp_neg']}")
    print(f"{'='*70}")
    for c in r['candidates']:
        print(f"  [{c['ticker']}] {c['name']} ({c['role']})")
        print(f"    52w고가비: {c['near_52w_high']}% | 1M수익률: {c['ret_1m']}% | 3M수익률: {c['ret_3m']}%")
        print(f"    신호: {c['signal_flag']} | 얼리스코어: {c['early_signal_score']}")
        if c.get('hundredx_match'):
            print(f"    ★ 100배 매치: {c['hundredx_match']}")
        print()
