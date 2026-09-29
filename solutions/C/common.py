"""C题公共模块：数据读取与日内线性规划。时间单位：10分钟一格，共144格；能量kWh=功率kW/6。"""
import numpy as np, pandas as pd
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
import os
D = os.path.join(os.path.dirname(__file__), '../../problems/C/附件')
N = 144; DT = 1/6
EMAX, EMIN, PMAX, ETA = 10800., 1200., 5000., 0.9
EFULL = 12000.; E0_YEAR = 6000.
CMAX = PMAX*DT

def load_data():
    a1 = pd.read_excel(f'{D}/附件1.xlsx')
    price1 = a1['电价'].values; load1 = a1['小区负载'].values; pv1 = a1['光伏发电预测功率'].values
    L = pd.read_excel(f'{D}/附件2.xlsx', sheet_name='小区负载', index_col=0)
    P = pd.read_excel(f'{D}/附件2.xlsx', sheet_name='光伏发电实际功率', index_col=0)
    pr = pd.read_excel(f'{D}/附件4.xlsx', index_col=0)
    fc = pd.read_excel(f'{D}/附件3.xlsx')
    fc['日期'] = fc['日期'].ffill()
    dates = pd.to_datetime(L.index)
    F = fc.iloc[:, 2:].values.reshape(len(dates), 4, 24)   # [day, 预报时刻(0,6,12,18), 未来第1..24小时]
    return dict(price1=price1, load1=load1, pv1=pv1, load=L.values, pv=P.values,
                price4=pr.values, fc=F, dates=dates)

def solve_day(price, load, pv, E0, Eend_min=None, Eend_eq=None, tv=0.0, first=0):
    """从第first格起的日内LP。变量[x,c,d,E]（按格），x购电、c充电(母线侧)、d放电(母线侧)、E格末储电量。
    约束：x+pv/6+d>=load/6+c；E_k=E_{k-1}+ETA*c-d/ETA。目标：min sum price*x - tv*E_end。返回x,c,d,E。"""
    n = N-first
    nv = 4*n
    cost = np.zeros(nv); cost[:n] = price[first:]
    if tv: cost[4*n-1] = -tv
    A = lil_matrix((2*n, nv)); b = np.zeros(2*n)
    Aeq = None
    for k in range(n):
        # -x - d + c <= pv/6 - load/6 ... => x + d - c >= (load-pv)/6
        A[k, k] = -1; A[k, n+k] = 1; A[k, 2*n+k] = -1
        b[k] = (pv[first+k]-load[first+k])*DT
    # 能量递推等式
    Eq = lil_matrix((n, nv)); beq = np.zeros(n)
    for k in range(n):
        Eq[k, 3*n+k] = 1; Eq[k, n+k] = -ETA; Eq[k, 2*n+k] = 1/ETA
        if k > 0: Eq[k, 3*n+k-1] = -1
        else: beq[k] = E0
    bounds = [(0, None)]*n + [(0, CMAX)]*n + [(0, CMAX)]*n + [(EMIN, EMAX)]*n
    if Eend_eq is not None: bounds[4*n-1] = (Eend_eq, Eend_eq)
    elif Eend_min is not None: bounds[4*n-1] = (max(Eend_min, EMIN), EMAX)
    res = linprog(cost, A_ub=A[:n].tocsr(), b_ub=b[:n], A_eq=Eq.tocsr(), b_eq=beq, bounds=bounds, method='highs')
    assert res.status == 0, res.message
    z = res.x
    return z[:n], z[n:2*n], z[2*n:3*n], z[3*n:]

def execute(x, pv, load, E, first=0):
    """实时执行：储能吸收/补足购电与净负载之间的差额（受功率、容量限制），仍不足则紧急购电。
    返回c,d,E_next数组、emergency、curtail。"""
    n = len(x); c = np.zeros(n); d = np.zeros(n); em = np.zeros(n); cu = np.zeros(n); Es = np.zeros(n)
    for k in range(n):
        net = x[k] + (pv[first+k]-load[first+k])*DT
        if net >= 0:
            c[k] = min(net, CMAX, (EMAX-E)/ETA); cu[k] = net-c[k]; E += ETA*c[k]
        else:
            d[k] = min(-net, CMAX, (E-EMIN)*ETA); em[k] = -net-d[k]; E -= d[k]/ETA
        Es[k] = E
    return c, d, Es, em, cu
