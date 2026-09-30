"""问题3 参数样本外检验：净需求裕量 mNd 与负载偏差修正强度 load_fb，前/后半年分别统计。用法 python cv_q3.py <0|1|2|3>"""
import sys, json, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core2 import *
i = int(sys.argv[1]); d = load_data(); p1 = d['price1']
base = dict(plan_mode='stoch', wpv=0.5, S=10, K=20, adjust=(6, 12, 18), adj_fc='new')
cfg = [dict(base, mNd=0., load_fb=1.), dict(base, mNd=50., load_fb=1.), dict(base, mNd=100., load_fb=1.), dict(base, mNd=50., load_fb=0.)][i]
fcs = build_forecasts(d, 0.5); o = run_year(d, p1, fcs=fcs, **cfg)
r = dict(kw={k: v for k, v in cfg.items() if k in ('mNd', 'load_fb')}, h1=total(o, 31, 181)['total'], h2=total(o, 181, 365)['total'], **total(o))
os.makedirs('out', exist_ok=True); json.dump(r, open(f'out/cvq3_{i}.json', 'w'), ensure_ascii=False); print(r)
