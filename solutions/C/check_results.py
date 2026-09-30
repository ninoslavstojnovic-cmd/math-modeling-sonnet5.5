"""结果文件一致性检查：储能守恒、储电量区间、日间衔接、供需平衡(计入紧急购电)、问题1同格不同时充放。"""
import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pickle
from core2 import *
d = load_data(); o1 = pickle.load(open('out/1.pkl', 'rb')); o3 = pickle.load(open('out/3.pkl', 'rb'))
_, x, c, dd, E = solve_det(d['price1'], d['load1'], d['pv1'], 6000, 6000)
print('Q1 同格既充又放的格数:', int(((c > 1e-6) & (dd > 1e-6)).sum()), ' E范围:', E.min(), E.max())
for name, res in (('Q2', o1['Q2']), ('Q3', o1['Q3']), ('Q4-2', o3['Q4_2_fc']), ('Q4-3', o3['Q4_3_fc'])):
    err_bal = 0; err_link = 0; emin = 1e9; emax = 0; err_sup = 0
    for i, o in enumerate(res):
        t = o['t']
        Ecalc = o['E0']+Eff.c*o['c'].sum()-o['d'].sum()/Eff.d
        err_bal = max(err_bal, abs(Ecalc-o['Es'][-1])); emin = min(emin, o['Es'].min()); emax = max(emax, o['Es'].max())
        if i > 0: err_link = max(err_link, abs(res[i-1]['Es'][-1]-o['E0']))
        sup = o['xf']+d['pv'][t]*DT+o['d']+o['em']-d['load'][t]*DT-o['c']            # 应 >=0 (差额为弃置量)
        err_sup = max(err_sup, -sup.min()); assert abs((sup-o['cu']).max()) < 1e-6
    print(name, f'守恒最大误差 {err_bal:.2e}, 日间衔接误差 {err_link:.2e}, 储电量范围 [{emin:.1f}, {emax:.1f}], 供需缺口最大 {err_sup:.2e}')
