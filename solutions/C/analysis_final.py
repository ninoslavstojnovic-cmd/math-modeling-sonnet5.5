"""后处理：问题1、完全信息下界、预报误差表、敏感性汇总、图表。需先运行 run_all.py 的4个分片。"""
import sys, json, pickle, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core2 import *
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
for f in ('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',):
    if os.path.exists(f): fm.fontManager.addfont(f)
plt.rcParams['font.family'] = ['WenQuanYi Zen Hei', 'DejaVu Sans']; plt.rcParams['axes.unicode_minus'] = False
FIG = '../../results/C/figures'; os.makedirs(FIG, exist_ok=True)
d = load_data(); p1 = d['price1']; p4 = d['price4']; A = {}
o1 = pickle.load(open('out/1.pkl', 'rb')); o3 = pickle.load(open('out/3.pkl', 'rb'))
R = {}
for f in ('1', '2', '3', '4', '5'): R.update(json.load(open(f'out/{f}.json')))

# ---- 问题1
nd1 = d['load1']-d['pv1']
c, x, cc, dd, E = solve_det(p1, d['load1'], d['pv1'], 6000, 6000)
A['Q1'] = dict(cost=c, energy=float(x.sum()), no_storage=float((p1*np.maximum(nd1, 0)*DT).sum()),
               tab1={k: float(x[i]) for i, k in [(59, '10:00-10:10'), (71, '12:00-12:10'), (83, '14:00-14:10'), (95, '16:00-16:10'), (107, '18:00-18:10'), (119, '20:00-20:10')]},
               charge=[float(cc[i*24:(i+1)*24].sum()) for i in range(6)], discharge=[float(dd[i*24:(i+1)*24].sum()) for i in range(6)])
best = min(((solve_det(p1, d['load1'], d['pv1'], e, e)[0], e) for e in np.linspace(1200, 10800, 97)))
A['Q1']['free_E0_cost'] = float(best[0]); A['Q1']['free_E0'] = float(best[1])
Eff.set('roundtrip'); A['Q1']['roundtrip_cost'] = float(solve_det(p1, d['load1'], d['pv1'], 6000, 6000)[0]); Eff.set('each')
A['Q1']['E0_scan'] = {int(e): float(solve_det(p1, d['load1'], d['pv1'], e, e)[0]) for e in (1200, 3000, 6000, 9000, 10800)}
# 图1
fig, ax = plt.subplots(3, 1, figsize=(9, 8), sharex=True); tt = HOURS
ax[0].plot(tt, p1, 'C0'); ax[0].set_ylabel('电价(元/kWh)')
ax[1].plot(tt, d['load1'], 'C1', label='小区负载'); ax[1].plot(tt, d['pv1'], 'C2', label='光伏预测'); ax[1].plot(tt, x*6, 'k', lw=1, label='购电功率'); ax[1].legend(ncol=3); ax[1].set_ylabel('功率(kW)')
ax[2].plot(tt, E, 'C3'); ax[2].axhline(1200, ls=':', c='gray'); ax[2].axhline(10800, ls=':', c='gray'); ax[2].set_ylabel('储电量(kWh)'); ax[2].set_xlabel('时刻(h)'); ax[2].set_xticks(range(0, 25, 4))
fig.suptitle('图1 问题1 典型日最优计划购电与储能轨迹'); fig.tight_layout(); fig.savefig(f'{FIG}/fig1_q1.png', dpi=130); plt.close(fig)

# ---- 完全信息下界（2.1-12.31 连续一年LP，起点=对应方案2月1日0:00储电量）
def bound(price2d, E0):
    pr = price2d[31:].ravel() if np.ndim(price2d) == 2 else np.tile(price2d, 334)
    return float(solve_det(pr, d['load'][31:].ravel(), d['pv'][31:].ravel(), E0)[0])
A['bound_Q2'] = bound(p1, o1['Q2'][31]['E0']); A['bound_Q4'] = bound(p4, o3['Q4_2_fc'][31]['E0'])

# ---- 预报误差表
fc = build_forecasts(d, 0.5); P = d['pv']; L = d['load']; T = range(31, 365)
mae = {}
mae['load'] = {'上一日': float(np.mean([np.abs(L[t-1]-L[t]).mean() for t in T])), '前7日均值': float(np.mean([np.abs(L[t-7:t].mean(0)-L[t]).mean() for t in T])),
               '同星期前1周': float(np.mean([np.abs(L[t-7]-L[t]).mean() for t in T])), '同星期前2周均值(采用)': float(np.mean([np.abs(fc['LF'][t]-L[t]).mean() for t in T]))}
mae['pv'] = {}
for i, s in enumerate((0, 36, 72, 108)):
    seg = slice(s, 144); e = lambda f: float(np.mean([np.abs(f(t)[seg]-P[t][seg]).mean() for t in T]))
    mae['pv'][f'{6*i}:00'] = dict(official=e(lambda t: fc['PVO'][t, i]), mean7=e(lambda t: fc['PV7'][t]), blend_used=e(lambda t: fc['PVB'][t, i]))
mae['price_fc'] = {'附件1典型日': float(np.mean([np.abs(p1-p4[t]).mean() for t in T])), '同星期前2周均值': float(np.mean([np.abs(fc_price(p4, t)-p4[t]).mean() for t in T]))}
A['mae'] = mae
# 图2
fig, ax = plt.subplots(figsize=(8, 4)); ks = list(mae['pv']); w = 0.27
for j, (nm, lab) in enumerate((('official', '官方预报'), ('mean7', '前7日均值'), ('blend_used', '加权(采用)'))):
    ax.bar(np.arange(4)+(j-1)*w, [mae['pv'][k][nm] for k in ks], w, label=lab)
ax.set_xticks(range(4)); ax.set_xticklabels([f'{k}发布' for k in ks]); ax.set_ylabel('剩余时段平均绝对误差(kW)'); ax.legend(); ax.set_title('图2 光伏功率预报误差(2.1-12.31)')
fig.tight_layout(); fig.savefig(f'{FIG}/fig2_pvfc.png', dpi=130); plt.close(fig)
# 图3 归因
lv = [('仅0:00计划\n(裕量100,问题2)', R['Q3_none']['total']), ('仅0:00计划\n(裕量0,同口径)', R['Q2_mNd0']['total']), ('+6/12/18点\n状态反馈', R['Q3_adj_old_fb0']['total']), ('+当日负载\n偏差修正', R['Q3_adj_old_fb1']['total']), ('+新光伏预报\n(问题3)', R['Q3']['total'])]
fig, ax = plt.subplots(figsize=(9.5, 4)); ax.bar([a for a, _ in lv], [b/1e4 for _, b in lv], color=['C7', 'C7', 'C0', 'C0', 'C2'])
for i, (_, b) in enumerate(lv): ax.text(i, b/1e4+1, f'{b/1e4:.1f}', ha='center')
ax.set_ylim(1300, 1405); ax.set_ylabel('全年总费用(万元)'); ax.set_title('图3 问题3：调整收益的逐层归因(纵轴自1300起)'); fig.tight_layout(); fig.savefig(f'{FIG}/fig3_attr.png', dpi=130); plt.close(fig)
A['attr'] = {k: R[k]['total'] for k in ('Q3_none', 'Q2_mNd0', 'Q2_S20K30', 'Q3_adj_old_fb0', 'Q3_adj_old_fb1', 'Q3_adj_new_fb0', 'Q3_adj_raw_fb1', 'Q3')}
# 图4 月度费用
dates = d['dates']; mon = lambda o: np.array([sum(x['cost_plan']+x['cost_em'] for x in o if x['t'] >= 31 and dates[x['t']].month == m) for m in range(2, 13)])/1e4
fig, ax = plt.subplots(figsize=(9, 4)); ax.plot(range(2, 13), mon(o1['Q2']), 'o-', label='问题2'); ax.plot(range(2, 13), mon(o1['Q3']), 's-', label='问题3')
ax.plot(range(2, 13), mon(o3['Q4_2_fc']), 'o--', label='问题4-2'); ax.plot(range(2, 13), mon(o3['Q4_3_fc']), 's--', label='问题4-3')
ax.set_xlabel('月份'); ax.set_ylabel('月度总费用(万元)'); ax.legend(); ax.set_title('图4 各问月度总费用'); fig.tight_layout(); fig.savefig(f'{FIG}/fig4_month.png', dpi=130); plt.close(fig)
# 图5 典型日调整过程
t = int((dates == '2025-06-21').nonzero()[0][0]); o = o1['Q3'][t]
fig, ax = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
ax[0].plot(tt, o['plan']*6, label='0:00计划购电功率'); ax[0].plot(tt, o['xf']*6, label='调整后购电功率'); ax[0].plot(tt, d['load'][t]-d['pv'][t], 'k:', label='实际净负载'); ax[0].legend(ncol=3); ax[0].set_ylabel('功率(kW)')
ax[1].plot(tt, o['Es']); ax[1].axhline(1200, ls=':', c='gray'); ax[1].axhline(10800, ls=':', c='gray'); ax[1].set_ylabel('储电量(kWh)'); ax[1].set_xlabel('时刻(h)')
for a in ax:
    for h in (6, 12, 18): a.axvline(h, c='r', ls=':', lw=0.8)
ax[0].set_title('图5 2025-06-21 问题3调整过程(红线为预报时刻)'); fig.tight_layout(); fig.savefig(f'{FIG}/fig5_day.png', dpi=130); plt.close(fig)
def estat(res):
    em = np.array([o['em'].sum() for o in res if o['t'] >= 31])
    return dict(days=int((em > 1e-6).sum()), d100=int((em > 100).sum()), d1000=int((em > 1000).sum()), maxday=float(em.max()), median=float(np.median(em[em > 1e-6])))
o5 = pickle.load(open('out/5.pkl', 'rb'))
A['estat'] = dict(Q2=estat(o1['Q2']), Q3=estat(o1['Q3']), Q2_mNd0=estat(o5['Q2_mNd0']))
A['R'] = R
json.dump(A, open('../../results/C/analysis.json', 'w'), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: v for k, v in A.items() if k not in ('R', 'attr')}, ensure_ascii=False, indent=1, default=float)[:3500])
