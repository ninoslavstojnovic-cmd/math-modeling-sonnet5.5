import sys; sys.path.insert(0,'.')
from common import *
from scipy.optimize import minimize_scalar
def q1(E0=None):
    d = load_data()
    f = lambda e0: (d['price1']*solve_day(d['price1'],d['load1'],d['pv1'],e0,Eend_eq=e0)[0]).sum()
    if E0 is None:
        r = minimize_scalar(f, bounds=(EMIN,EMAX), method='bounded', options={'xatol':1e-3}); E0 = r.x
    x,c,dd,E = solve_day(d['price1'],d['load1'],d['pv1'],E0,Eend_eq=E0)
    return d,E0,x,c,dd,E
if __name__=='__main__':
    for e in (6000,None):
        d,E0,x,c,dd,E=q1(e); print(E0, x.sum(), (x*d['price1']).sum())
