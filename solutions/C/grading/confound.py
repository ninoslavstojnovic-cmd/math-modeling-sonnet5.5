import sys; import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import *
import q3
d=load_data(); F=d['fc']; p1=d['price1']
F2=F.copy()
for t in range(365):
    for i,h in enumerate([0,6,12,18]):
        if i==0: continue
        for j in range(24):
            hh=h+j
            F2[t,i,j]=F[t,0,hh] if hh<24 else (F[t+1,0,hh-24] if t+1<365 else 0)
d2=dict(d); d2['fc']=F2
for tag,hs in (('all',(6,12,18)),('18',(18,)),('6_12',(6,12))):
    a=q3.run_year(d,p1,mL=0.03,adjust=hs)[0]; b=q3.run_year(d2,p1,mL=0.03,adjust=hs)[0]
    print(tag,'新预报',round(a/1e4,1),'仅用0:00旧预报重规划',round(b/1e4,1))
