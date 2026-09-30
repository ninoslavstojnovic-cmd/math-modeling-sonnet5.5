"""并行分片运行全部实验。用法：python run_all.py <shard>；结果存 out/<shard>.pkl 与 out/<shard>.json"""
import sys, json, pickle, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core2 import *
shard = sys.argv[1]; os.makedirs('out', exist_ok=True)
d = load_data(); p1 = d['price1']; p4 = d['price4']
Q2 = dict(plan_mode='stoch', wpv=0.5, mNd=100., S=10, K=20)                                  # 问题2 (0:00计划，无调整)
Q3 = dict(plan_mode='stoch', wpv=0.5, mNd=0., S=10, K=20, adjust=(6, 12, 18), load_fb=1.0, adj_fc='new')   # 问题3
PF = np.array([fc_price(p4, t) for t in range(365)])                                         # 电价预测：同星期几前两周均值
def go(tag, price_act, price_plan=None, **kw):
    fcs = build_forecasts(d, kw.get('wpv', 0.5)); o = run_year(d, price_act, price_plan, fcs=fcs, **kw)
    r = dict(tag=tag, h1=total(o, 31, 181)['total'], h2=total(o, 181, 365)['total'], **total(o)); res[tag] = r; outs[tag] = o
    print(json.dumps(r, ensure_ascii=False), flush=True)
res = {}; outs = {}
if shard == '1':
    go('Q2', p1, **Q2); go('Q3', p1, **Q3)
elif shard == '2':   # 问题3归因分解
    go('Q3_none', p1, **Q2)
    go('Q3_adj_old_fb0', p1, **dict(Q3, adj_fc='old', load_fb=0.)); go('Q3_adj_old_fb1', p1, **dict(Q3, adj_fc='old'))
    go('Q3_adj_new_fb0', p1, **dict(Q3, load_fb=0.)); go('Q3_adj_raw_fb1', p1, **dict(Q3, adj_fc='raw'))
elif shard == '3':   # 问题4
    go('Q4_2_known', p4, **Q2); go('Q4_2_fc', p4, PF, **Q2); go('Q4_2_typ', p4, p1, **Q2)
    go('Q4_3_known', p4, **Q3); go('Q4_3_fc', p4, PF, **Q3); go('Q4_3_typ', p4, p1, **Q3)
elif shard == '4':   # 效率口径 + 调整时刻子集
    Eff.set('roundtrip'); go('Q2_rt', p1, **Q2); go('Q3_rt', p1, **Q3); Eff.set('each')
    for hs in ((6,), (12,), (18,), (6, 12), (12, 18)): go('Q3_sub_' + '_'.join(map(str, hs)), p1, **dict(Q3, adjust=hs))
elif shard == '5':   # 归因基线口径统一 + 情景数敏感性
    go('Q2_mNd0', p1, **dict(Q2, mNd=0.)); go('Q2_S20K30', p1, **dict(Q2, S=20, K=30))
pickle.dump(outs, open(f'out/{shard}.pkl', 'wb')); json.dump(res, open(f'out/{shard}.json', 'w'), ensure_ascii=False)
