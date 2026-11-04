import numpy as np, sys, heapq, time, os
S=int(os.environ.get('HL_S',12)); NA=3; DS=int(os.environ.get('HL_DS',24)); DD=48; DX=DS+DD; DZ=int(os.environ.get('HL_DZ',16)); EP=5; H=25

class World:
    def __init__(s,seed,sigma):
        r=np.random.default_rng(1000+seed); s.M=r.normal(size=(S,DS)); s.sd=sigma; s.rng=np.random.default_rng(2000+seed)
        s.T=np.zeros((S,NA),int)
        for st in range(S):
            s.T[st,0]=(st+1)%S                      # ring edge guarantees connectivity
            for a in (1,2):
                t=int(r.integers(S))
                while t==st: t=int(r.integers(S))
                s.T[st,a]=t
        s.s=0; s.D=np.full((S,S),99)
        for src in range(S):
            s.D[src,src]=0;q=[src]
            while q:
                n=q.pop(0)
                for a in range(NA):
                    m=s.T[n,a]
                    if s.D[src,m]==99: s.D[src,m]=s.D[src,n]+1;q.append(m)
    def obs(s,st): return np.concatenate([s.M[st]+0.05*s.rng.normal(size=DS),s.sd*s.rng.normal(size=DD)])
    def step(s,a,sp=0.0):
        if sp>0 and s.rng.random()<sp: a=int(s.rng.integers(NA))
        s.s=int(s.T[s.s,a]);return s.s

def gen(w,n,ra):
    X=np.empty((n,DX));X2=np.empty((n,DX));A=ra.integers(0,NA,size=n);St=np.empty(n,int)
    for i in range(n):
        if i%EP==0: w.s=int(w.rng.integers(S))
        st=w.s;St[i]=st;X[i]=w.obs(st);w.step(A[i]);X2[i]=w.obs(w.s)
    return X,A,X2,St

class Adam:
    def __init__(s,ps,lr): s.ps=ps;s.lr=lr;s.m=[np.zeros_like(p) for p in ps];s.v=[np.zeros_like(p) for p in ps];s.t=0
    def step(s,gs):
        s.t+=1
        for p,g,m,v in zip(s.ps,gs,s.m,s.v):
            m*=.9;m+=.1*g;v*=.999;v+=.001*g*g
            p-=s.lr*(m/(1-.9**s.t))/(np.sqrt(v/(1-.999**s.t))+1e-8)

def train_latent(X,A,X2,seed,iters=6000,B=256,lr=3e-3,lv=1.0,lc=0.1,gam=0.5):
    r=np.random.default_rng(seed);E=r.normal(size=(DZ,DX))*0.1;P=r.normal(size=(NA,DZ,DZ))*0.1;Et=E.copy();opt=Adam([E,P],lr)
    for it in range(iters):
        i=r.integers(0,len(X),B);x=X[i];a=A[i];x2=X2[i]
        z=np.tanh(x@E.T);zt=np.tanh(x2@Et.T);p=np.empty_like(z)
        for k in range(NA): m=a==k;p[m]=z[m]@P[k].T
        dp=2*(p-zt)/B;dP=np.zeros_like(P);dz=np.zeros_like(z)
        for k in range(NA): m=a==k;dP[k]=dp[m].T@z[m];dz[m]=dp[m]@P[k]
        zc=z-z.mean(0);std=np.sqrt((zc**2).sum(0)/(B-1)+1e-4);v=std<gam
        dv=np.zeros_like(z);dv[:,v]=-(lv/DZ)*zc[:,v]/((B-1)*std[v])
        C=zc.T@zc/(B-1);Co=C-np.diag(np.diag(C));dc=lc*(4/DZ)*(zc@Co)/(B-1)
        d=dv+dc;dz+=d-d.mean(0);opt.step([(dz*(1-z**2)).T@x,dP]);Et*=.99;Et+=.01*E
    return E,P

class Model:
    def __init__(s,E,P,protos,rho): s.E,s.P,s.protos,s.rho=E,P,protos,rho
    def enc(s,x): return np.tanh(s.E@x)
    def snap(s,z):
        d=np.linalg.norm(s.protos-z,axis=1);j=int(d.argmin());return j if d[j]<s.rho else -1
    def nearest(s,z): return int(np.linalg.norm(s.protos-z,axis=1).argmin())

def make_protos(Z,rho,rng):
    P=[]
    for z in Z[rng.permutation(len(Z))[:4000]]:
        if P and np.linalg.norm(np.array(P)-z,axis=1).min()<rho: continue
        P.append(z.copy())
    P=np.array(P)
    for _ in range(3):
        d=np.linalg.norm(Z[:,None,:]-P[None],axis=2);j=d.argmin(1);ok=d.min(1)<rho
        for k in range(len(P)):
            m=ok&(j==k)
            if m.sum()>0: P[k]=Z[m].mean(0)
    return P

def plan(m,z0,cur,goal,maxd=8):
    calls=0;prev={cur:None};fr=[cur]
    for d in range(maxd):
        nx=[]
        for n in fr:
            zn=z0 if (n==cur and d==0) else m.protos[n]
            for a in range(NA):
                calls+=1;e=m.nearest(m.P[a]@zn)
                if e not in prev:
                    prev[e]=(n,a);nx.append(e)
                    if e==goal:
                        out=[];k=e
                        while k!=cur: pn,aa=prev[k];out.append((aa,k));k=pn
                        return out[::-1],calls
        fr=nx
    return None,calls

class Library:
    def __init__(s,atomic): s.h={};s.adj={};s.atomic=atomic
    def add_path(s,pr,acts):
        for i in range(len(acts)):
            for j in range(i+1,len(acts)+1):
                if s.atomic and j-i>1: continue
                key=(pr[i],tuple(acts[i:j]))
                if key not in s.h: s.h[key]=dict(acts=tuple(acts[i:j]),path=tuple(pr[i:j+1]),n_exec=0,n_ok=0,uses=0);s.adj.setdefault(pr[i],[]).append(key)
    def chain(s,cur,goal):
        dist={cur:0.0};prev={};hp=[(0.0,cur)];lk=0
        while hp:
            d,n=heapq.heappop(hp)
            if n==goal: break
            if d>dist.get(n,1e9): continue
            for key in s.adj.get(n,()):
                hb=s.h[key]
                if hb['n_exec']>=2 and hb['n_ok']/hb['n_exec']<0.5: continue
                lk+=1;e=hb['path'][-1];nd=d+1+0.01*len(hb['acts'])
                if nd<dist.get(e,1e9): dist[e]=nd;prev[e]=(n,key);heapq.heappush(hp,(nd,e))
        if goal not in prev: return None,lk
        out=[];n=goal
        while n!=cur: pn,key=prev[n];out.append((key,s.h[key]));n=pn
        return out[::-1],lk

class Agent:
    def __init__(s,m,mode): s.m=m;s.mode=mode;s.task={};s.lib=Library(mode=='library_atomic')

def episode(w,ag,s0,g,sp,learn,Hmax=H):
    m=ag.m;gp=m.sproto[g];w.s=s0;z=m.enc(w.obs(s0));cur=m.snap(z)
    st=dict(steps=0,calls=0,lk=0,dec=0,ab=0,delib=0,cf=-1);pp=[cur];pa=[];valid=cur>=0;first=True
    while st['steps']<Hmax and cur!=gp:
        ce=cur if cur>=0 else m.nearest(z);units=None
        if ag.mode=='task_habit' and (ce,gp) in ag.task: units=[(ag.task[(ce,gp)],None)]
        elif ag.mode.startswith('library'):
            ch,lk=ag.lib.chain(ce,gp);st['lk']+=lk
            if first: st['cf']=int(ch is not None)
            if ch is not None: units=[(list(zip(hb['acts'],hb['path'][1:])),key) for key,hb in ch]
        first=False
        if units is None:
            ae,c=plan(m,z,ce,gp);st['calls']+=c;st['delib']+=1
            if ae is None: break
            units=[(ae,None)]
        aborted=False
        for seq,key in units:
            st['dec']+=1
            if key: ag.lib.h[key]['n_exec']+=1
            ok=True
            for a,e in seq:
                if st['steps']>=Hmax: ok=False;break
                s2=w.step(a,sp);st['steps']+=1;z=m.enc(w.obs(s2));cur=m.snap(z);pa.append(a);pp.append(cur)
                if cur<0: valid=False
                if cur==gp: ok=(cur==e);break
                if cur!=e: ok=False;break
            if key and ok: ag.lib.h[key]['n_ok']+=1;ag.lib.h[key]['uses']+=1
            if not ok: aborted=True;break
            if cur==gp: break
        if aborted: st['ab']+=1
    if learn and cur==gp and valid and st['ab']==0 and st['delib']>=1:
        if ag.mode=='task_habit': ag.task[(pp[0],gp)]=list(zip(pa,pp[1:]))
        elif ag.mode.startswith('library'): ag.lib.add_path(pp,pa)
    return [float(w.s==g),st['steps'],st['calls'],st['lk'],st['dec'],st['ab'],st['cf']]

if __name__=='__main__':
    NS=int(sys.argv[1]);sigma=float(sys.argv[2]);MODES=['delib','task_habit','library_atomic','library_chunks'];NT=[4,8,16,32];SLIPS=[0.0,0.15]
    R={};diag=[]
    for seed in range(NS):
        t0=time.time();w=World(seed,sigma);ra=np.random.default_rng(4000+seed)
        X,A,X2,St=gen(w,40000,ra);E,P=train_latent(X,A,X2,seed)
        Zs=np.tanh(X[:8000]@E.T);ii=ra.integers(0,len(Zs),(1500,2));rho=0.25*np.median(np.linalg.norm(Zs[ii[:,0]]-Zs[ii[:,1]],axis=1))
        protos=make_protos(Zs,rho,ra);m=Model(E,P,protos,rho)
        zs=np.stack([np.mean([m.enc(w.obs(s)) for _ in range(30)],axis=0) for s in range(S)])
        m.sproto=[m.snap(zs[s]) if m.snap(zs[s])>=0 else m.nearest(zs[s]) for s in range(S)]
        j=np.array([m.snap(z) for z in Zs]);cov=(j>=0).mean();cnt=np.zeros((len(protos),S))
        for k,s_ in zip(j,St[:8000]):
            if k>=0: cnt[k,s_]+=1
        pur=cnt.max(1).sum()/cnt.sum();eacc=np.mean([m.nearest(P[a]@zs[s])==m.sproto[T] for s in range(S) for a,T in enumerate(w.T[s])])
        diag.append([len(protos),len(set(m.sproto)),cov,pur,eacc])
        pairs=[(s,g) for s in range(S) for g in range(S) if w.D[s,g]>=2];ra.shuffle(pairs);novel=pairs[-30:];pool=pairs[:-30]
        for nt in NT:
            train=pool[:nt]
            for mode in MODES:
                ag=Agent(m,mode);prac=train*2;ra.shuffle(prac)
                for (s0,g) in prac: episode(w,ag,s0,g,0.0,True)
                for sp in SLIPS:
                    for cat,tasks in (('repeat',train[:16]),('novel',novel)):
                        res=np.array([episode(w,ag,s0,g,sp,False) for (s0,g) in tasks]);R.setdefault((nt,mode,sp,cat,'free'),[]).append(res.mean(0))
                        rt=np.array([episode(w,ag,s0,g,sp,False,int(w.D[s0,g])+1) for (s0,g) in tasks]);R.setdefault((nt,mode,sp,cat,'tight'),[]).append(rt.mean(0))
                if mode=='library_chunks' and nt==16: nhab=len(ag.lib.h)
        print(f"seed{seed} {time.time()-t0:.0f}s protos={len(protos)} distinct_state_protos={len(set(m.sproto))} coverage={cov:.3f} purity={pur:.3f} model_edge_acc={eacc:.3f} lib16={nhab}",flush=True)
    d=np.array(diag);print(f"\nDIAG sigma={sigma:g} ({NS} seeds) mean: protos={d[:,0].mean():.1f}(true {S}) distinct={d[:,1].mean():.1f} coverage={d[:,2].mean():.3f} purity={d[:,3].mean():.3f} model_edge_acc={d[:,4].mean():.3f}")
    def agg(nt,mode,sp,cat,b):
        a=np.array(R[(nt,mode,sp,cat,b)]);return a.mean(0),a.std(0)
    def f(nt,mode,sp,cat,b='free'):
        mu,sd=agg(nt,mode,sp,cat,b)
        return f"success={mu[0]:.2f} steps={mu[1]:.2f}+-{sd[1]:.2f} model_calls={mu[2]:5.2f}+-{sd[2]:4.2f} lookups={mu[3]:5.1f}+-{sd[3]:4.1f} decisions={mu[4]:.2f} aborts={mu[5]:.2f}"+("" if mode in('delib','task_habit') else f" chain_found={mu[6]:.2f}")
    brief=len(sys.argv)>3
    for sp in SLIPS:
        for cat in (('novel',) if brief else ('repeat','novel')):
            print(f"\n[n_train=16, test={cat}, slip={sp}, step budget=25]")
            for mode in MODES: print(f"  {mode:15s}",f(16,mode,sp,cat))
    print("\n[n_train=16, success within shortest-path+1 steps]")
    for sp in SLIPS:
        for cat in ('repeat','novel'):
            print(f"  slip={sp} {cat:6s} "+"  ".join(f"{mode}={agg(16,mode,sp,cat,'tight')[0][0]:.2f}" for mode in MODES))
    print("\n[novel tasks, slip=0: effect of amount of practice]")
    for nt in NT:
        for mode in (MODES[1:] if not brief else ['library_chunks']):
            mu,sd=agg(nt,mode,0.0,'novel','free');print(f"  n_train={nt:2d} {mode:15s} model_calls={mu[2]:6.2f}+-{sd[2]:4.2f} decisions={mu[4]:5.2f} chain_found={mu[6]:.2f}+-{sd[6]:.2f}"
