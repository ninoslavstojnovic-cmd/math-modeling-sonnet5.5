# 独立复核：自建LP（向量化稀疏矩阵），不复用被评代码
import numpy as np, pandas as pd, scipy.sparse as sp, sys
from scipy.optimize import linprog
import os
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'../../../problems/C/附件')
a1=pd.read_excel(f'{D}/附件1.xlsx'); p1=a1['电价'].values; l1=a1['小区负载'].values; v1=a1['光伏发电预测功率'].values
L=pd.read_excel(f'{D}/附件2.xlsx',sheet_name='小区负载',index_col=0).values
P=pd.read_excel(f'{D}/附件2.xlsx',sheet_name='光伏发电实际功率',index_col=0).values
P4=pd.read_excel(f'{D}/附件4.xlsx',index_col=0).values
def lp(price,load,pv,E0,Eend=None,etac=0.9,etad=0.9,pmax=5000/6,ret=False,emerg=None):
    """变量 x,c,d,E（,s 紧急）。T格。"""
    T=len(price); I=sp.identity(T,format='csr'); Z=sp.csr_matrix((T,T))
    S=sp.eye(T,k=-1,format='csr')
    nb=5 if emerg is not None else 4
    # 供需: -x - d + c (- s) <= (pv-load)/6
    blocks=[-I,I,-I,Z]+([-I] if emerg is not None else [])
    A=sp.hstack(blocks).tocsr(); b=(pv-load)/6
    # E - S E - etac c + d/etad = E0 e1
    eqb=[Z,-etac*I,I/etad,I-S]+([Z] if emerg is not None else [])
    Aeq=sp.hstack(eqb).tocsr(); beq=np.zeros(T); beq[0]=E0
    cost=np.concatenate([price,np.zeros(3*T)]+([emerg*price] if emerg is not None else []))
    bnd=[(0,None)]*T+[(0,pmax)]*2*T+[(1200,10800)]*T+([(0,None)]*T if emerg is not None else [])
    if Eend is not None: bnd[4*T-1]=(Eend,Eend)
    r=linprog(cost,A_ub=A,b_ub=b,A_eq=Aeq,b_eq=beq,bounds=bnd,method='highs')
    assert r.status==0,r.message
    z=r.x; return r.fun, z[:T],z[T:2*T],z[2*T:3*T],z[3*T:4*T]
out={}
# ---- 问题1 复核
f,x,c,d,E=lp(p1,l1,v1,6000,6000); out['Q1_cost']=f; out['Q1_kwh']=x.sum()
out['Q1_simul_cd_slots']=int(((c>1e-6)&(d>1e-6)).sum())
out['Q1_tab1']={t:x[k] for k,t in [(59,'10:00'),(71,'12:00'),(83,'14:00'),(95,'16:00'),(107,'18:00'),(119,'20:00')]}
# 按“数据时刻为区间终点”的对应
out['Q1_tab1_endlabel']={t:x[k] for k,t in [(60,'10:00'),(72,'12:00'),(84,'14:00'),(96,'16:00'),(108,'18:00'),(120,'20:00')]}
out['Q1_blocks_c']=[c[i*24:(i+1)*24].sum() for i in range(6)]; out['Q1_blocks_d']=[d[i*24:(i+1)*24].sum() for i in range(6)]
# 效率口径敏感性：往返90%（充放各 sqrt(0.9)）
f2,*_=lp(p1,l1,v1,6000,6000,etac=0.9**.5,etad=0.9**.5); out['Q1_cost_roundtrip90']=f2
out['Q1_nostorage']=(p1*np.maximum(l1-v1,0)/6).sum()
# ---- 问题2/4 完全信息下界（2.1-12.31 连续一年 LP，起点储电量取被评方案2.1的E0）
def yearbound(price2d,E0):
    pr=price2d[31:].ravel(); ld=L[31:].ravel(); pv=P[31:].ravel()
    f,x,c,d,E=lp(pr,ld,pv,E0); return f,E[-1]
fq2,_=yearbound(np.tile(p1,(365,1)),float(sys.argv[1]) if len(sys.argv)>2 else 2270.379); out['Q2_perfect_info_bound']=fq2
fq4,_=yearbound(P4,float(sys.argv[2]) if len(sys.argv)>2 else 2261.297); out['Q4_perfect_info_bound']=fq4
import json; print(json.dumps(out,indent=1,default=float,ensure_ascii=False))
