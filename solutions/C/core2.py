"""C题 v2：两阶段随机规划（第一阶段=购电量x，第二阶段=各情景下储能与紧急购电）+ 滚动调整 + 实时执行。
时间：144格/天，格内能量 kWh = kW/6。净需求 nd = 负载 - 光伏 (kW)。"""
import os
import numpy as np, pandas as pd, scipy.sparse as sp
from scipy.optimize import linprog

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../problems/C/附件')
N = 144; DT = 1/6
EMAX, EMIN, PMAX, E0_YEAR = 10800., 1200., 5000., 6000.
CMAX = PMAX*DT
HOURS = np.arange(1, N+1)/6.0

class Eff:
    """效率口径：'each'=充、放各90%（默认，往返81%）；'roundtrip'=往返90%（充放各√0.9）"""
    c = 0.9; d = 0.9
    @classmethod
    def set(cls, mode):
        cls.c = cls.d = (0.9 if mode == 'each' else 0.9**0.5)

def load_data():
    a1 = pd.read_excel(f'{D}/附件1.xlsx')
    L = pd.read_excel(f'{D}/附件2.xlsx', sheet_name='小区负载', index_col=0)
    P = pd.read_excel(f'{D}/附件2.xlsx', sheet_name='光伏发电实际功率', index_col=0)
    fc = pd.read_excel(f'{D}/附件3.xlsx'); fc['日期'] = fc['日期'].ffill()
    dates = pd.to_datetime(L.index)
    return dict(price1=a1['电价'].values, load1=a1['小区负载'].values, pv1=a1['光伏发电预测功率'].values,
                load=L.values, pv=P.values, price4=pd.read_excel(f'{D}/附件4.xlsx', index_col=0).values,
                fc=fc.iloc[:, 2:].values.reshape(len(dates), 4, 24), dates=dates)

# ---------------- 预测 ----------------
def pv_from_fc(fc, h, anchor):
    """预报时刻h发布的未来24个整点预报 -> 10分钟格(线性插值)，锚点为发布时刻实测光伏"""
    return np.interp(HOURS, np.concatenate([[h], h+np.arange(1, 25)]), np.concatenate([[anchor], fc]))

def fc_load(load, t, NW=2, d=None):
    """同星期几前NW周均值（周五、周六负载偏低）；无足够历史时用附件1典型日/前一日"""
    k = [i for i in range(1, NW+1) if t-7*i >= 0]
    if k: return np.mean([load[t-7*i] for i in k], 0)
    return d['load1'] if (t == 0 and d is not None) else load[t-1]

def fc_price(price, t, NW=2):
    k = [i for i in range(1, NW+1) if t-7*i >= 0]
    return np.mean([price[t-7*i] for i in k], 0) if k else (price[t-1] if t > 0 else price[0])

def fc_pv7(pv, t, W=7, d=None):
    return pv[max(t-W, 0):t].mean(0) if t > 0 else d['pv1']

def build_forecasts(d, wpv=0.5, wv=(0.75, 1.0, 1.0), use_official=True):
    """逐日因果预测数组：负载LF、光伏PV(0:00计划用)、以及各预报时刻的光伏预报PVi[t,i]。
    wpv：0:00计划光伏预报中官方预报所占权重(其余为前7日均值)。"""
    load, pv, F = d['load'], d['pv'], d['fc']; T = len(load)
    LF = np.array([fc_load(load, t, 2, d) for t in range(T)])
    PV7 = np.array([fc_pv7(pv, t, 7, d) for t in range(T)])
    PVO = np.array([[pv_from_fc(F[t, i], 6*i, pv[t, 36*i-1] if i else 0.0) for i in range(4)] for t in range(T)])
    PV0 = wpv*PVO[:, 0]+(1-wpv)*PV7 if use_official else PV7
    # 各预报时刻(6/12/18点)用于调整的光伏预报：官方预报与前7日均值的加权(权重按样本内误差选取，见论文)
    PVB = PVO.copy(); PVB[:, 0] = PV0
    for i, w in enumerate(wv, start=1): PVB[:, i] = w*PVO[:, i]+(1-w)*PV7
    return dict(LF=LF, PV7=PV7, PVO=PVO, PV0=PV0, PVB=PVB)

# ---------------- 单阶段随机LP ----------------
def solve_stage(price, nd, E0, xplan=None, tv=0.0, first=0, recourse=5.0, up=1.5, down=0.5):
    """price:(n,) 剩余格电价；nd:(S,n) 净需求情景(kW)；返回第一阶段决策(购电量x，或相对计划xplan的调整量)。
    xplan给定时 x=xplan+u-w：多买单价 up*p，少买(违约)节省仅 (1-down)*p；紧急购电(缺口)单价 recourse*p。"""
    S, n = nd.shape
    I = sp.identity(n, format='csr'); Z = sp.csr_matrix((n, n)); L1 = sp.eye(n, k=-1, format='csr')
    if xplan is None:
        F1 = -I; nf = n; c1 = price.copy(); b1 = np.zeros(n); bnd1 = [(0, None)]*n
    else:
        F1 = sp.hstack([-I, I]).tocsr(); nf = 2*n; c1 = np.concatenate([up*price, -down*price])
        b1 = xplan; bnd1 = [(0, None)]*n+[(0, float(v)) for v in xplan]
    # 单情景块 [c d E e]
    Ub = sp.hstack([I, -I, Z, -I]).tocsr()
    Eb = sp.hstack([-Eff.c*I, I/Eff.d, I-L1, Z]).tocsr()
    Fp = sp.vstack([F1]*S).tocsr()
    A_ub = sp.hstack([Fp, sp.block_diag([Ub]*S)]).tocsr()
    b_ub = np.concatenate([b1 - nd[s]*DT for s in range(S)])
    A_eq = sp.hstack([sp.csr_matrix((S*n, nf)), sp.block_diag([Eb]*S)]).tocsr()
    b_eq = np.zeros(S*n); b_eq[::n] = E0
    cost = np.concatenate([c1, np.tile(np.concatenate([np.zeros(3*n), recourse*price/S]), S)])
    if tv:
        for s in range(S): cost[nf+s*4*n+2*n+n-1] -= tv/S
    bnd = bnd1 + (([(0, CMAX)]*n + [(0, CMAX)]*n + [(EMIN, EMAX)]*n + [(0, None)]*n)*S)
    r = linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bnd, method='highs')
    assert r.status == 0, r.message
    z = r.x
    return z[:n] if xplan is None else z[:n]-z[n:2*n]

# ---------------- 实时执行 ----------------
def execute(x, pv, load, E, first=0):
    """储能优先吸收/补足购电与净负载差额(受功率、容量限制)，仍不足则紧急购电，富余无法存储则弃置"""
    n = len(x); c = np.zeros(n); d = np.zeros(n); em = np.zeros(n); cu = np.zeros(n); Es = np.zeros(n)
    for k in range(n):
        net = x[k] + (pv[first+k]-load[first+k])*DT
        if net >= 0:
            c[k] = min(net, CMAX, (EMAX-E)/Eff.c); cu[k] = net-c[k]; E += Eff.c*c[k]
        else:
            d[k] = min(-net, CMAX, (E-EMIN)*Eff.d); em[k] = -net-d[k]; E -= d[k]/Eff.d
        Es[k] = E
    return c, d, Es, em, cu

# ---------------- 全年滚动 ----------------
def run_year(d, price_act, price_plan=None, plan_mode='stoch', adjust=(), wpv=0.5, K=20, S=10, tvf=0.0,
             mL=0.0, mNd=0.0, days=None, fcs=None, adj_fc='new', load_fb=0.0, verbose=False, t_end=365):
    """price_act: 结算电价(365,144)或(144,)；price_plan: 计划用电价(同形，默认=price_act已知)。
    plan_mode: 'det'(确定性LP+比例裕量mL)或'stoch'(两阶段随机规划，情景=前K天预测残差取S个)。
    adjust: 调整时刻子集(6,12,18)；adj_fc: 'new'用最新预报(与前7日均值加权)，'raw'用官方原始预报，'old'仍用0:00预报(仅做状态反馈，用于归因)。
    load_fb: 用当日已观测负载偏差修正剩余负载预测的强度(0=不修正)。"""
    load, pv, F = d['load'], d['pv'], d['fc']
    if fcs is None: fcs = build_forecasts(d, wpv)
    LF, PV0 = fcs['LF'], fcs['PV0']; PVO = fcs['PVO'] if adj_fc == 'raw' else fcs['PVB']
    ND = load - pv
    NDf0 = LF - PV0                       # 0:00计划用的净需求预测
    R0 = ND - NDf0                         # 0:00预测残差
    # 各预报时刻的残差 (t,i,144)：剩余时段净需求残差
    RES = {i: ND - (LF - PVO[:, i]) for i in range(4)}
    price2 = lambda P, t: P[t] if np.ndim(P) == 2 else P
    E = E0_YEAR; out = []
    hrs = [0, 6, 12, 18]; bounds = [0, 36, 72, 108, 144]
    for t in range(0, t_end):
        pa = price2(price_act, t); pp = pa if price_plan is None else price2(price_plan, t)
        tv = tvf*pp.mean()*Eff.c*Eff.d
        nd0 = NDf0[t]
        # ---- 0:00 计划
        if plan_mode == 'det' or t < 10:
            sc = np.tile((LF[t]*(1+mL)-PV0[t])[None, :], (1, 1))
        else:
            ks = np.arange(max(t-K, 8), t)
            ks = ks[np.linspace(0, len(ks)-1, min(S, len(ks))).round().astype(int)] if len(ks) > S else ks
            sc = nd0[None, :] + R0[ks] + mNd
        x = solve_stage(pp, sc, E, tv=tv)
        plan = x.copy(); xf = x.copy(); adj = np.zeros(N)
        Es = np.zeros(N); c = np.zeros(N); dch = np.zeros(N); em = np.zeros(N); cu = np.zeros(N); Ecur = E
        for i in range(4):
            s, e = bounds[i], bounds[i+1]
            if i > 0 and hrs[i] in adjust:
                pvf = PV0[t] if adj_fc == 'old' else PVO[t, i]
                ndf = LF[t] - pvf
                if load_fb:
                    # 用已观测负载偏差修正剩余负载预测：偏差取过去1小时均值，随时间指数衰减(2小时)
                    dev = (load[t, s-6:s] - LF[t, s-6:s]).mean()
                    ndf = ndf + load_fb*dev*np.exp(-(np.arange(N)-s+1)/12.0)
                if plan_mode == 'det' or t < 10:
                    sc = (ndf + mL*LF[t])[None, s:]
                else:
                    ks = np.arange(max(t-K, 8), t)
                    ks = ks[np.linspace(0, len(ks)-1, min(S, len(ks))).round().astype(int)] if len(ks) > S else ks
                    Rk = R0[ks] if adj_fc == 'old' else RES[i][ks]
                    sc = ndf[None, s:] + Rk[:, s:] + mNd
                a = solve_stage(pp[s:], sc, Ecur, xplan=plan[s:], tv=tv)
                adj[s:] = a; xf[s:] = plan[s:]+a
            cc, dd_, ee, emm, cuu = execute(xf[s:e], pv[t], load[t], Ecur, first=s)
            c[s:e] = cc; dch[s:e] = dd_; Es[s:e] = ee; em[s:e] = emm; cu[s:e] = cuu; Ecur = ee[-1]
        # 结算（实际电价）
        cost_plan = (pa*np.minimum(plan, xf)).sum() + 0.5*(pa*np.maximum(plan-xf, 0)).sum() + 1.5*(pa*np.maximum(xf-plan, 0)).sum()
        cost_em = (5*pa*em).sum()
        out.append(dict(t=t, plan=plan, adj=adj, xf=xf, c=c, d=dch, Es=Es, em=em, cu=cu, E0=E, cost_plan=cost_plan, cost_em=cost_em))
        E = Ecur
        if verbose and t % 60 == 0: print(t, flush=True)
    return out

def total(out, lo=31, hi=365):
    rr = [o for o in out if lo <= o['t'] < hi]
    a = sum(o['cost_plan'] for o in rr); b = sum(o['cost_em'] for o in rr)
    return dict(total=float(a+b), plan=float(a), emergency=float(b), emergency_kwh=float(sum(o['em'].sum() for o in rr)),
                curtail_kwh=float(sum(o['cu'].sum() for o in rr)), days_emerg=int(sum(o['em'].sum() > 1e-6 for o in rr)))

def solve_det(price, load, pv, E0, Eend=None):
    """确定性日内/多日LP（变量 x,c,d,E），用于问题1与完全信息下界。返回 (费用, x, c, d, E)"""
    T = len(price); I = sp.identity(T, format='csr'); Z = sp.csr_matrix((T, T)); L1 = sp.eye(T, k=-1, format='csr')
    A = sp.hstack([-I, I, -I, Z]).tocsr(); b = (pv-load)*DT
    Aeq = sp.hstack([Z, -Eff.c*I, I/Eff.d, I-L1]).tocsr(); beq = np.zeros(T); beq[0] = E0
    bnd = [(0, None)]*T + [(0, CMAX)]*2*T + [(EMIN, EMAX)]*T
    if Eend is not None: bnd[4*T-1] = (Eend, Eend)
    r = linprog(np.concatenate([price, np.zeros(3*T)]), A_ub=A, b_ub=b, A_eq=Aeq, b_eq=beq, bounds=bnd, method='highs')
    assert r.status == 0, r.message
    z = r.x; return r.fun, z[:T], z[T:2*T], z[2*T:3*T], z[3*T:]
