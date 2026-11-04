import numpy as np, sys, heapq, time, copy
import habit_library as hl
from habit_library import S,NA,H,World,gen,train_latent,Model,make_protos

def bfs(T):
    D=np.full((S,S),99)
    for src in range(S):
        D[src,src]=0;q=[src]
        while q:
            n=q.pop(0)
            for a in range(NA):
                m=T[n,a]
                if D[src,m]==99: D[src,m]=D[src,n]+1;q.append(m)
    return D
def rewire(w,frac,rng):
    for _ in range(200):
        T=w.T.copy();idx=[(s,a) for s in range(S) for a in range(NA)];rng.shuffle(idx)
        for (s,a) in idx[:int(frac*len(idx))]:
            t=int(rng.integers(S))
            while t==s or t==T[s,a]: t=int(rng.integers(S))
            T[s,a]=t
        D=bfs(T)
        if (D<99).all(): w.T=T;w.D=D;return
    raise RuntimeError('rewire failed')

def plan2(P,m,z0,cur,goal,maxd=8):
    calls=0;prev={cur:None};fr=[cur]
    for d in range(maxd):
        nx=[]
        for n in fr:
            zn=z0 if (n==cur and d==0) else m.protos[n]
            for a in range(NA):
                calls+=1;e=m.nearest(P[a]@zn)
                if e not in prev:
                    prev[e]=(n,a);nx.append(e)
                    if e==goal:
                        out=[];k=e
                        while k!=cur: pn,aa=prev[k];out.append((aa,k));k=pn
                        return out[::-1],calls
        fr=nx
    return None,calls

class LibR:
    def __init__(s,cap,policy,rng): s.h={};s.adj={};s.cap=cap;s.policy=policy;s.rng=rng;s.es={}
    def bad(s,c,a): e=s.es.get((c,a));return e is not None and e[0]>=2 and e[1]/e[0]>0.5
    def _drop(s,key): s.adj[s.h[key]['path'][0]].remove(key);del s.h[key]
    def _purge(s,c,a,n):
        for key in list(s.h):
            hb=s.h[key]
            for j,aj in enumerate(hb['acts']):
                if hb['path'][j]==c and aj==a and hb['path'][j+1]!=n: s._drop(key);break
    def util(s,hb): return (hb['uses']+1)*(hb['n_ok']+1)/(hb['n_exec']+2)
    def add_path(s,pr,acts):
        for i in range(len(acts)): s.es.pop((pr[i],acts[i]),None);s._purge(pr[i],acts[i],pr[i+1])
        new=set()
        for i in range(len(acts)):
            for j in range(i+1,len(acts)+1):
                key=(pr[i],tuple(acts[i:j]))
                if key in s.h: continue
                s.h[key]=dict(acts=key[1],path=tuple(pr[i:j+1]),n_exec=0,n_ok=0,uses=0);s.adj.setdefault(pr[i],[]).append(key);new.add(key)
        s.prune(new)
    def prune(s,protected):
        while s.cap and len(s.h)>s.cap:
            vs=[k for k in s.h if k not in protected]
            if not vs: break
            if s.policy=='fifo': v=vs[0]
            elif s.policy=='random': v=vs[int(s.rng.integers(len(vs)))]
            else:
                u=[s.util(s.h[k]) for k in vs];mn=min(u);c=[k for k,x in zip(vs,u) if x==mn];v=c[int(s.rng.integers(len(c)))]
            s._drop(v)
    def chain(s,cur,goal,use_bad):
        dist={cur:0.0};prev={};hp=[(0.0,cur)];lk=0
        while hp:
            d,n=heapq.heappop(hp)
            if n==goal: break
            if d>dist.get(n,1e9): continue
            for key in s.adj.get(n,()):
                hb=s.h[key]
                if use_bad and any(s.bad(hb['path'][k],hb['acts'][k]) for k in range(len(hb['acts']))): continue
                if hb['n_exec']>=2 and hb['n_ok']/hb['n_exec']<0.5: continue
                lk+=1;e=hb['path'][-1];nd=d+1+0.01*len(hb['acts'])
                if nd<dist.get(e,1e9): dist[e]=nd;prev[e]=(n,key);heapq.heappush(hp,(nd,e))
        if goal not in prev: return None,lk
        out=[];n=goal
        while n!=cur: pn,key=prev[n];out.append((key,s.h[key]));n=pn
        return out[::-1],lk

class Ag:
    def __init__(s,m,kind,rseed,cap=None,policy='utility'):
        s.m=m;s.kind=kind;s.P=m.P.copy();s.rng=np.random.default_rng(rseed);s.lib=LibR(cap,policy,s.rng)
        s.learn=True;s.audit=0.0;s.eta=0.0
    @property
    def stats_on(s): return s.kind=='habit'
def clone(a,kind,rseed):
    b=Ag(a.m,kind,rseed);b.lib=copy.deepcopy(a.lib);b.lib.rng=b.rng;b.P=a.P.copy();return b

def ep(w,ag,s0,g,sp=0.0,Hmax=H):
    m=ag.m;gp=m.sproto[g];w.s=s0;z=m.enc(w.obs(s0));cur=m.snap(z)
    st=dict(steps=0,calls=0,lk=0,ab=0,au=0,rp=0);pp=[cur];pa=[];first=True
    while st['steps']<Hmax and cur!=gp:
        ce=cur if cur>=0 else m.nearest(z);units=None
        if ag.kind!='delib' and not (ag.kind=='skill' and st['ab']>0):
            ch,lk=ag.lib.chain(ce,gp,ag.stats_on);st['lk']+=lk
            if ch is not None:
                units=[(list(zip(hb['acts'],hb['path'][1:])),key) for key,hb in ch]
                if first and ag.kind=='habit' and ag.audit>0 and ag.rng.random()<ag.audit:
                    ae,c=plan2(ag.P,m,z,ce,gp);st['calls']+=c;st['au']+=1
                    if ae is not None and len(ae)<sum(len(u[0]) for u in units): units=[(ae,None)];st['rp']+=1
        first=False
        if units is None:
            ae,c=plan2(ag.P,m,z,ce,gp);st['calls']+=c
            if ae is None: break
            units=[(ae,None)]
        aborted=False
        for seq,key in units:
            if key: ag.lib.h[key]['n_exec']+=1
            i0=len(pa);ok=True
            for a,e in seq:
                if st['steps']>=Hmax: ok=False;break
                pc=cur;zb=z;s2=w.step(a,sp);st['steps']+=1;z=m.enc(w.obs(s2));cur=m.snap(z);pa.append(a);pp.append(cur)
                if ag.eta>0: ag.P[a]-=ag.eta*np.outer(ag.P[a]@zb-z,zb)/(zb@zb+1e-6)
                if ag.stats_on and pc>=0:
                    es=ag.lib.es.setdefault((pc,a),[0,0]);es[0]+=1;es[1]+=int(cur!=e)
                if cur==gp: ok=(cur==e);break
                if cur!=e: ok=False;break
            if key and ok: ag.lib.h[key]['n_ok']+=1;ag.lib.h[key]['uses']+=1
            if key is None and ok and ag.learn and ag.kind!='delib' and min(pp[i0:])>=0: ag.lib.add_path(pp[i0:],pa[i0:])
            if not ok: aborted=True;break
            if cur==gp: break
        if aborted: st['ab']+=1
    return [float(w.s==g),st['steps'],st['calls'],st['lk'],st['ab'],st['au'],st['rp']]

def final(w,ag,tasks):
    ag.learn=False;ag.audit=0.0;ag.eta=0.0
    free=np.array([ep(w,ag,s0,g) for (s0,g) in tasks]);tight=np.array([ep(w,ag,s0,g,0.0,int(w.D[s0,g])+1) for (s0,g) in tasks])
    return [tight[:,0].mean(),free[:,0].mean(),free[:,1].mean(),free[:,2].mean()]

def setup(seed,sigma):
    w=World(seed,sigma);ra=np.random.default_rng(4000+seed)
    X,A,X2,St=gen(w,40000,ra);E,P=train_latent(X,A,X2,seed)
    Zs=np.tanh(X[:8000]@E.T);ii=ra.integers(0,len(Zs),(1500,2));rho=0.25*np.median(np.linalg.norm(Zs[ii[:,0]]-Zs[ii[:,1]],axis=1))
    m=Model(E,P,make_protos(Zs,rho,ra),rho)
    zs=np.stack([np.mean([m.enc(w.obs(s)) for _ in range(30)],axis=0) for s in range(S)])
    m.sproto=[m.snap(zs[s]) if m.snap(zs[s])>=0 else m.nearest(zs[s]) for s in range(S)]
    pairs=[(s,g) for s in range(S) for g in range(S) if w.D[s,g]>=2];ra.shuffle(pairs)
    return w,m,pairs[:-30],pairs[-30:]

def practice(w,ag,train,ra):
    prac=train*2;ra.shuffle(prac)
    for (s0,g) in prac: ep(w,ag,s0,g)

if __name__=='__main__':
    NS=int(sys.argv[1]);sigma=2.0;R1={};R3={};R2={}
    for seed in range(NS):
        t0=time.time();w,m,pool,novel=setup(seed,sigma);ra=np.random.default_rng(5000+seed);train=pool[:16]
        uidx=ra.integers(0,len(pool),120)
        base=Ag(m,'habit',9000+seed);practice(w,base,train,ra);nbase=len(base.lib.h)
        # Exp1: refinement in a static world
        cf1=[('delib','delib',0.0,False),('skill (frozen)','skill',0.0,False),('habit audit=0','habit',0.0,True),('habit audit=0.1','habit',0.1,True),('habit audit=0.3','habit',0.3,True),('habit audit=1.0','habit',1.0,True)]
        for k,(name,kind,p,lrn) in enumerate(cf1):
            ag=clone(base,kind,100*seed+k);ag.audit=p;ag.learn=lrn
            use=np.array([ep(w,ag,*pool[i]) for i in uidx]);R1.setdefault(name,[]).append([use[:,2].sum(),use[:,6].sum(),*final(w,ag,novel),len(ag.lib.h)])
        # Exp3: capacity-limited libraries (utility vs random vs fifo pruning)
        for cap in [8,16,24,None]:
            for pol in (['utility','random','fifo'] if cap else ['utility']):
                ag=Ag(m,'habit',777+seed,cap,pol);practice(w,ag,train,ra)
                for i in uidx[:60]: ep(w,ag,*pool[i])
                ag.learn=False;cf=np.mean([ag.lib.chain(m.sproto[s0],m.sproto[g],True)[0] is not None for (s0,g) in novel])
                R3.setdefault((cap,pol),[]).append([cf,*final(w,ag,novel),len(ag.lib.h)])
        # Exp2: 30% of transitions rewired after practice (run last: mutates the world)
        rewire(w,0.3,np.random.default_rng(8000+seed));aidx=ra.integers(0,len(pool),80)
        cf2=[('delib (adaptive model)','delib',0.0,False),('skill (frozen)','skill',0.0,False),('habit audit=0','habit',0.0,True),('habit audit=0.3','habit',0.3,True)]
        for k,(name,kind,p,lrn) in enumerate(cf2):
            ag=clone(base,kind,5000+100*seed+k);ag.eta=0.7;ag.audit=p;ag.learn=lrn
            rows=np.array([ep(w,ag,*pool[i]) for i in aidx]);blk=np.array([[rows[b*20:(b+1)*20,c].mean() for c in (0,1,2,4)] for b in range(4)])
            R2.setdefault(name,[]).append([blk,final(w,ag,novel)])
        print(f"seed{seed} {time.time()-t0:.0f}s base_lib={nbase}",flush=True)
    print(f"\n=== EXP1: refinement, static world ({NS} seeds). 120 'use' episodes with learning, then 30 novel tasks, learning off ===")
    for name,v in R1.items():
        a=np.array(v);print(f"  {name:16s} use_model_calls={a[:,0].mean():6.0f}  routes_replaced={a[:,1].mean():5.1f}  final: success_in_D+1={a[:,2].mean():.2f}+-{a[:,2].std():.2f}  success={a[:,3].mean():.2f}  steps={a[:,4].mean():.2f}+-{a[:,4].std():.2f}  model_calls={a[:,5].mean():5.2f}  library={a[:,6].mean():5.1f}")
    print(f"\n=== EXP2: 30% of transitions rewired after practice ({NS} seeds). 4 blocks of 20 adaptation episodes; per-block success / steps / model_calls / aborts ===")
    for name,v in R2.items():
        B=np.mean([x[0] for x in v],axis=0);F=np.mean([x[1] for x in v],axis=0)
        print(f"  {name}\n    success {' '.join(f'{x:5.2f}' for x in B[:,0])} | steps {' '.join(f'{x:5.2f}' for x in B[:,1])} | calls {' '.join(f'{x:6.1f}' for x in B[:,2])} | aborts {' '.join(f'{x:5.2f}' for x in B[:,3])}\n    final novel: success_in_D+1={F[0]:.2f}+-{np.std([x[1][0] for x in v]):.2f} success={F[1]:.2f} steps={F[2]:.2f}+-{np.std([x[1][2] for x in v]):.2f}  | block4 aborts={B[3,3]:.2f}+-{np.std([x[0][3,3] for x in v]):.2f} calls={B[3,2]:.1f}+-{np.std([x[0][3,2] for x in v]):.1f}")
    print(f"\n=== EXP3: capacity-limited library ({NS} seeds). practice + 60 use episodes, then 30 novel tasks ===")
    for (cap,pol),v in R3.items():
        a=np.array(v);print(f"  cap={str(cap):4s} {pol:8s} chain_found={a[:,0].mean():.2f}+-{a[:,0].std():.2f}  success_in_D+1={a[:,1].mean():.2f}  steps={a[:,3].mean():.2f}  model_calls={a[:,4].mean():5.2f}+-{a[:,4].std():.2f}  library={a[:,5].mean():5.1f}"
