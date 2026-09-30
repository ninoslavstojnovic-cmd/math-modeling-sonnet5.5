"""时间序列样本外检验：前半年(2.1-6.30, t=31..180)/后半年(7.1-12.31, t=181..364)互为调参集与检验集。"""
import sys, json, itertools; sys.path.insert(0, '.')
from core2 import *
d = load_data(); p1 = d['price1']
H1, H2 = (31, 181), (181, 365)
rows = []
def rec(tag, kw, **extra):
    fcs = build_forecasts(d, kw.get('wpv', 0.5))
    o = run_year(d, p1, fcs=fcs, **kw)
    r = dict(tag=tag, kw={k: v for k, v in kw.items()}, h1=total(o, *H1)['total'], h2=total(o, *H2)['total'], all=total(o)['total'],
             emerg=total(o)['emergency'], **extra)
    rows.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
# 问题2：确定性+比例裕量
for wpv, mL in itertools.product((0.0, 0.5, 1.0), (0.02, 0.04, 0.06)):
    rec('Q2det', dict(plan_mode='det', mL=mL, wpv=wpv))
# 问题2：随机规划
for wpv, mNd, tvf in itertools.product((0.0, 0.5), (0.0, 100.0), (0.0, 1.0)):
    rec('Q2stoch', dict(plan_mode='stoch', wpv=wpv, mNd=mNd, tvf=tvf, S=10, K=20))
json.dump(rows, open('cv_grid.json', 'w'), ensure_ascii=False)
