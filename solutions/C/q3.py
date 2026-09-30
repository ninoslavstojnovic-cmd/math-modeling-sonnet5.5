import sys; sys.path.insert(0,'.')
from common import *
from q2 import fc_load, fc_pv
HOURS = np.arange(1, N+1)/6.0      # 每格末时刻(小时)

def pv_from_fc(fc, h, pv_anchor):
    """预报时刻h(0/6/12/18)发布的未来24个整点预报 -> 10分钟格上的光伏功率(线性插值)，锚点为发布时刻实测功率。"""
    xs = np.concatenate([[h], h+np.arange(1, 25)]); ys = np.concatenate([[pv_anchor], fc])
    return np.interp(HOURS, xs, ys)

def solve_adj(price, load, pv, E0, xplan, first, tv=0.0, up=1.5, down=0.5):
    """调整LP：x=xplan+u-w，超出计划部分单价up*p，缩减部分节省仅(1-down)*p（违约电价down*p）。"""
    n = N-first; p = price[first:]; xp = xplan[first:]
    nv = 5*n   # u,w,c,d,E
    cost = np.concatenate([up*p, -down*p, np.zeros(3*n)]); cost[5*n-1] = -tv
    # 目标中 Σ p*xplan 为常数(省略)
    A = lil_matrix((n, nv)); b = np.zeros(n); Eq = lil_matrix((n, nv)); beq = np.zeros(n)
    for k in range(n):
        # x+d-c >= (load-pv)/6 , x=xplan+u-w  ->  -u + w - d + c <= xplan + (pv-load)/6
        A[k, k] = -1; A[k, n+k] = 1; A[k, 2*n+k] = 1; A[k, 3*n+k] = -1
        b[k] = xp[k] + (pv[first+k]-load[first+k])*DT
        Eq[k, 4*n+k] = 1; Eq[k, 2*n+k] = -ETA; Eq[k, 3*n+k] = 1/ETA
        if k > 0: Eq[k, 4*n+k-1] = -1
        else: beq[k] = E0
    bounds = [(0, None)]*n + [(0, x) for x in xp] + [(0, CMAX)]*2*n + [(EMIN, EMAX)]*n
    r = linprog(cost, A_ub=A.tocsr(), b_ub=b, A_eq=Eq.tocsr(), b_eq=beq, bounds=bounds, method='highs')
    assert r.status == 0, r.message
    z = r.x
    return z[:n]-z[n:2*n]   # 相对计划的调整量

def run_year(d, price, mL=0.04, mP=0.0, adjust=(6, 12, 18), mPa=None, blend=0.0, tvf=0.0, NW=2, use_fc=True, days=range(31, 365)):
    load, pv, F = d['load'], d['pv'], d['fc']
    mPa = mP if mPa is None else mPa
    E = E0_YEAR; out = []
    for t in range(1, 365):
        p = price[t] if price.ndim == 2 else price
        fl = fc_load(load, t, NW)*(1+mL)
        pv0 = ((1-blend)*pv_from_fc(F[t, 0], 0, 0.0)+blend*fc_pv(pv, t, 7))*(1-mP)
        x, _, _, _ = solve_day(p, fl, pv0, E, tv=tvf*p.mean()*ETA*ETA)
        plan = x.copy(); xf = x.copy(); adj = np.zeros(N)
        Es = np.zeros(N); c = np.zeros(N); dch = np.zeros(N); em = np.zeros(N); cu = np.zeros(N)
        Ecur = E; start = 0
        bounds = [0, 36, 72, 108, 144] if adjust else [0, 144]
        hrs = [0, 6, 12, 18]
        for i in range(len(bounds)-1):
            s, e = bounds[i], bounds[i+1]
            if i > 0:
                h = hrs[i]
                if h in adjust:
                    anchor = pv[t, s-1]
                    pvf = pv_from_fc(F[t, i], h, anchor)*(1-mPa)
                    # 用当日已观测的负载偏差修正剩余负载预报
                    flx = fl.copy()
                    a = solve_adj(p, flx, pvf, Ecur, plan, s, tv=tvf*p.mean()*ETA*ETA)
                    adj[s:] = a; xf[s:] = plan[s:]+a
            cc, dd_, ee, emm, cuu = execute(xf[s:e], pv[t, :], load[t, :], Ecur, first=s)
            c[s:e] = cc; dch[s:e] = dd_; Es[s:e] = ee; em[s:e] = emm; cu[s:e] = cuu
            Ecur = ee[-1]
        cost_plan = (p*np.minimum(plan, xf)).sum() + 0.5*(p*np.maximum(plan-xf, 0)).sum() + 1.5*(p*np.maximum(xf-plan, 0)).sum()
        cost_em = (5*p*em).sum()
        out.append(dict(t=t, plan=plan, adj=adj, xf=xf, c=c, d=dch, Es=Es, em=em, E0=E, cost_plan=cost_plan, cost_em=cost_em))
        E = Ecur
    tot = sum(o['cost_plan']+o['cost_em'] for o in out if o['t'] in days)
    return tot, sum(o['cost_plan'] for o in out if o['t'] in days), sum(o['cost_em'] for o in out if o['t'] in days), out
