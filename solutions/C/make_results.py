"""生成全部结果：运行问题1-4，填写官方result模板，导出汇总JSON。用法：python make_results.py"""
import sys, json
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import openpyxl
from common import *
import q1 as Q1, q2 as Q2, q3 as Q3
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../results/C'); os.makedirs(OUT, exist_ok=True)
CFG2 = dict(mL=0.04, mP=0.0)          # 问题2预测裕量
CFG3 = dict(mL=0.03, mP=0.0)          # 问题3预测裕量
d = load_data(); dates = d['dates']

def fm(m): return f"{m//60 % 24}:{m%60:02d}" + ("+1" if m >= 1440 else "")
def lab(k):
    """第k格(0..143)标签：数据时刻(k+1)*10min为区间起点，与官方模板一致"""
    s = (k+1)*10; return f"{fm(s)}-{fm(s+10)}"
def blocks(arr): return [float(arr[i*24:(i+1)*24].sum()) for i in range(6)]
def emerg_periods(em, thr=1e-6):
    res = []; k = 0
    while k < N:
        if em[k] > thr:
            j = k
            while j+1 < N and em[j+1] > thr: j += 1
            res.append((f"{fm((k+1)*10)}-{fm((j+1)*10+10)}", float(em[k:j+1].sum()))); k = j+1
        else: k += 1
    return res

summ = {}
# ---------- 问题1 ----------
_, E0, x, c, dd, E = Q1.q1(E0_YEAR)
_, E0f, xf_, _, _, _ = Q1.q1(None)
p1 = d['price1']
HL = ('10:00', '12:00', '14:00', '16:00', '18:00', '20:00')
summ['Q1'] = dict(cost=float((p1*x).sum()), energy=float(x.sum()), cost_free_E0=float((p1*xf_).sum()), E0_free=float(E0f),
                  baseline_no_storage=float((p1*np.maximum(d['load1']-d['pv1'], 0)/6).sum()))
summ['Q1']['tab1'] = {lab(k): float(x[k]) for k in range(N) if lab(k).split('-')[0] in HL}
summ['Q1']['tab2'] = dict(charge=blocks(c), discharge=blocks(dd), E0=E0, E24=float(E[-1]))
wb = openpyxl.load_workbook(f'{D}/result1.xlsx')
ws = wb['计划购电量']
for k in range(N): ws.cell(k+2, 2, round(float(x[k]), 4))
ws = wb['充放电量']; cb, db = blocks(c), blocks(dd)
for i in range(6): ws.cell(i+2, 2, round(cb[i], 4)); ws.cell(i+2, 3, round(db[i], 4))
ws.cell(2, 5, E0); ws.cell(3, 5, round(float(E[-1]), 4))
wb.save(f'{OUT}/result1.xlsx')

# ---------- 通用写入 ----------
def write_year(res, name, price, q3=False):
    wb = openpyxl.load_workbook(f'{D}/{"result3" if q3 else "result2"}.xlsx')
    ws = wb['计划购电量']
    for o in res:
        if o['t'] < 31: continue
        r = o['t']-31+2; p = price[o['t']] if price.ndim == 2 else price
        plan = o['plan'] if q3 else o['x']
        for k in range(N): ws.cell(r, k+2, round(float(plan[k]), 3))
        ws.cell(r, N+2, round(float(plan.sum()), 3)); ws.cell(r, N+3, round(float((p*plan).sum()), 3))
    if q3:
        ws = wb['调整购电量']
        for o in res:
            if o['t'] < 31: continue
            for k in range(36, N): ws.cell(o['t']-31+2, k+2, round(float(o['xf'][k]), 3))
    ws = wb['充放电量']
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row: cell.value = None
    r = 2
    for o in res:
        if o['t'] < 31: continue
        cb, db = blocks(o['c']), blocks(o['d'])
        ws.cell(r, 1, dates[o['t']].to_pydatetime())
        for i in range(6):
            ws.cell(r+i, 2, f"{4*i}:00-{4*i+4}:00"); ws.cell(r+i, 3, round(cb[i], 3)); ws.cell(r+i, 4, round(db[i], 3))
        ws.cell(r, 5, "0:00"); ws.cell(r, 6, round(float(o['E0']), 3)); ws.cell(r+1, 5, "24:00"); ws.cell(r+1, 6, round(float(o['Es'][-1]), 3))
        r += 6
    ws = wb['紧急购电量']
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row: cell.value = None
    r = 2
    for o in res:
        if o['t'] < 31: continue
        ps = emerg_periods(o['em']); ws.cell(r, 1, dates[o['t']].to_pydatetime())
        if not ps: r += 1; continue
        for (s, a) in ps: ws.cell(r, 2, s); ws.cell(r, 3, round(a, 3)); r += 1
    wb.save(f'{OUT}/{name}.xlsx')

def tables(res, price, q3):
    out = {}
    for ds in ('2025-03-20', '2025-06-21', '2025-09-23', '2025-12-21'):
        t = int((dates == ds).nonzero()[0][0]); o = res[t-1]; p = price[t] if price.ndim == 2 else price
        plan = o['plan'] if q3 else o['x']; xf = o['xf'] if q3 else plan
        out[ds] = dict(tab1={lab(k): float(plan[k]) for k in range(N) if lab(k).split('-')[0] in HL},
                       plan_total=float(plan.sum()), plan_cost=float((p*plan).sum()), final_total=float(xf.sum()),
                       charge=blocks(o['c']), discharge=blocks(o['d']), E0=float(o['E0']), E24=float(o['Es'][-1]),
                       emergency=emerg_periods(o['em']),
                       day_cost=float(o['cost_plan']+o['cost_em']) if q3 else float((p*plan).sum()+(5*p*o['em']).sum()))
    return out

def sumr(res, q3):
    rr = [o for o in res if o['t'] >= 31]
    if q3:
        a = sum(o['cost_plan'] for o in rr); b = sum(o['cost_em'] for o in rr)
    else:
        a = sum(o['cost'] for o in rr); b = sum(o['emg'] for o in rr)
    return dict(total=float(a+b), plan=float(a), emergency=float(b), emergency_kwh=float(sum(o['em'].sum() for o in rr)),
                days_with_emergency=int(sum(o['em'].sum() > 1e-6 for o in rr)))

for name, price, key in (('result2', p1, 'Q2'), ('result4-2', d['price4'], 'Q4_2')):
    _, _, _, res = Q2.run_q2(d, price, **CFG2)
    write_year(res, name, price, False); summ[key] = sumr(res, False); summ[key]['tables'] = tables(res, price, False)
for name, price, key in (('result3', p1, 'Q3'), ('result4-3', d['price4'], 'Q4_3')):
    _, _, _, res = Q3.run_year(d, price, **CFG3)
    write_year(res, name, price, True); summ[key] = sumr(res, True); summ[key]['tables'] = tables(res, price, True)
    for tag, hs in (('no_adjust', ()), ('adjust_6', (6,)), ('adjust_12', (12,)), ('adjust_18', (18,)), ('adjust_6_12', (6, 12))):
        _, _, _, r1 = Q3.run_year(d, price, adjust=hs, **CFG3); summ[key][tag] = sumr(r1, True)
json.dump(summ, open(f'{OUT}/summary.json', 'w'), ensure_ascii=False, indent=1, default=float)
print(json.dumps({k: {a: b for a, b in v.items() if a not in ('tables', 'tab1', 'tab2')} for k, v in summ.items()}, ensure_ascii=False, indent=1, default=float))
