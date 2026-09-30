import sys, time; sys.path.insert(0,'.')
from common import *

def fc_load(load, t, NW=2):
    """t日负载预测：同星期几前NW周的平均曲线（负载有明显星期周期：周五、周六偏低）。"""
    k = [i for i in range(1, NW+1) if t-7*i >= 0]
    return np.mean([load[t-7*i] for i in k], 0) if k else load[t-1]

def fc_pv(pv, t, W=7):
    """t日光伏预测（无预报时）：前W天同一时刻平均。"""
    return pv[max(t-W, 0):t].mean(0)

def run_q2(d, price, mL=0.0, mP=0.0, tvf=0.0, W=7, NW=2, days=range(31, 365), endmin=None, verbose=False):
    load, pv = d['load'], d['pv']
    E = E0_YEAR
    tot = 0; plan = 0; emg = 0; res = []
    for t in range(1, 365):
        p = price[t] if price.ndim == 2 else price
        fl = fc_load(load, t, NW); fp = fc_pv(pv, t, W)
        x, cc, dd, EE = solve_day(p, fl*(1+mL), fp*(1-mP), E, Eend_min=endmin, tv=tvf*p.mean()*ETA*ETA)
        c, dch, Es, em, cu = execute(x, pv[t], load[t], E)
        pc = (p*x).sum(); ec = (5*p*em).sum()
        res.append(dict(t=t, x=x, c=c, d=dch, Es=Es, em=em, E0=E, cost=pc, emg=ec))
        if t in days: tot += pc+ec; plan += pc; emg += ec
        E = Es[-1]
    return tot, plan, emg, res

