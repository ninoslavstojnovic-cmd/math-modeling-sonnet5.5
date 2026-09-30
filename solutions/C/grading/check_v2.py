"""复核修改版：只读 results/C/*.xlsx 中的购电量，用独立执行规则重演全年，重算费用（不复用被评代码）。"""
import os, numpy as np, pandas as pd, openpyxl
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../results/C')
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../problems/C/附件')
L = pd.read_excel(f'{D}/附件2.xlsx', sheet_name='小区负载', index_col=0).values
P = pd.read_excel(f'{D}/附件2.xlsx', sheet_name='光伏发电实际功率', index_col=0).values
p1 = pd.read_excel(f'{D}/附件1.xlsx')['电价'].values; P4 = pd.read_excel(f'{D}/附件4.xlsx', index_col=0).values
def grid(wb, s):
    return np.array([[np.nan if v is None else v for v in r[1:145]] for r in wb[s].iter_rows(min_row=2, values_only=True)], float)
def replay(f, q3, price):
    wb = openpyxl.load_workbook(f'{R}/{f}.xlsx', data_only=True)
    X = grid(wb, '计划购电量'); Xf = np.where(np.isnan(grid(wb, '调整购电量')), X, grid(wb, '调整购电量')) if q3 else X
    E = [r[5] for r in wb['充放电量'].iter_rows(min_row=2, values_only=True)][0]   # 2.1 0:00 储电量
    tot = pl = em_c = em_k = 0; dem = 0
    for i in range(X.shape[0]):
        t = 31+i; p = price[t] if price.ndim == 2 else price; em = np.zeros(144)
        for k in range(144):
            net = Xf[i, k] + (P[t, k]-L[t, k])/6
            if net >= 0: E += 0.9*min(net, 5000/6, (10800-E)/0.9)
            else:
                dd = min(-net, 5000/6, (E-1200)*0.9); em[k] = -net-dd; E -= dd/0.9
        x, y = X[i], Xf[i]
        c = (p*np.minimum(x, y)).sum()+0.5*(p*np.maximum(x-y, 0)).sum()+1.5*(p*np.maximum(y-x, 0)).sum()
        pl += c; em_c += (5*p*em).sum(); em_k += em.sum(); dem += em.sum() > 1e-3
    return dict(total=(pl+em_c)/1e4, plan=pl/1e4, emerg=em_c/1e4, emerg_kwh=em_k, days=int(dem))
for f, q3, pr in (('result2', 0, p1), ('result3', 1, p1), ('result4-2', 0, P4), ('result4-3', 1, P4)):
    print(f, {k: round(v, 2) for k, v in replay(f, q3, pr).items()})
