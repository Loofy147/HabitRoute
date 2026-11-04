import os,sys,time,copy,heapq,json
import numpy as np
import habit_library as hl
from habit_library import S,NA,H,World,Model
from habit_refine import bfs,rewire,plan2,setup

NTR=int(os.environ.get('HL_NT',16));SIG=float(os.environ.get('HL_SIGMA',2));SEED_START=int(os.environ.get('HL_SEED_START',0));FAIL={};NCHK=[0]
def note(fs):
    NCHK[0]+=1
    for f in fs: FAIL[f]=FAIL.get(f,0)+1

class LibS:
    def __init__(s,cap,policy,rng,lam,dom,coverage_weight=0.5):
        s.h={};s.adj={};s.cap=cap;s.policy=policy;s.rng=rng;s.es={};s.lam=lam;s.dom=dom;s.rev=0;s.cert={}
        s.coverage_weight=float(coverage_weight);s.prune_searches=0;s.prune_expansions=0;s.prune_seconds=0.0;s.capacity_drops=0
    def bad(s,c,a): e=s.es.get((c,a));return e is not None and e[0]>=2 and e[1]/e[0]>0.5
    def _drop(s,key): s.adj[s.h[key]['path'][0]].remove(key);del s.h[key]
    def _purge(s,c,a,n):
        d=0
        for key in list(s.h):
            hb=s.h[key]
            for j,aj in enumerate(hb['acts']):
                if hb['path'][j]==c and aj==a and hb['path'][j+1]!=n: s._drop(key);d+=1;break
        if d: s.rev+=1
    def util(s,hb): return (hb['uses']+1)*(hb['n_ok']+1)/(hb['n_exec']+2)
    def _eligible(s,hb):
        if hb['n_exec']>=2 and hb['n_ok']/hb['n_exec']<0.5: return False
        return not any(s.bad(hb['path'][j],hb['acts'][j]) for j in range(len(hb['acts'])))
    def _shortest_steps(s,src,dst,exclude=None):
        """Shortest verified library route in action steps, optionally omitting one habit."""
        s.prune_searches+=1
        if src==dst: return 0
        dist={src:0};hp=[(0,src)]
        while hp:
            d,n=heapq.heappop(hp);s.prune_expansions+=1
            if d!=dist.get(n): continue
            if n==dst: return d
            for key in s.adj.get(n,()):
                if key==exclude: continue
                hb=s.h.get(key)
                if hb is None or not s._eligible(hb): continue
                e=hb['path'][-1];nd=d+len(hb['acts'])
                if nd<dist.get(e,10**9):
                    dist[e]=nd;heapq.heappush(hp,(nd,e))
        return None
    def step_savings(s,key):
        """Expected marginal value: route-coverage credit plus saved action steps.

        The counterfactual removes this habit and finds the best remaining library
        route between the same endpoints. A unique route earns coverage credit;
        a shorter route earns the action steps it saves over the alternative.
        Both are discounted by the habit's Beta-smoothed execution success rate.
        """
        hb=s.h.get(key)
        if hb is None or not s._eligible(hb): return 0.0
        t0=time.perf_counter()
        src,dst=hb['path'][0],hb['path'][-1]
        with_habit=s._shortest_steps(src,dst)
        if with_habit is None:
            s.prune_seconds+=time.perf_counter()-t0;return 0.0
        without_habit=s._shortest_steps(src,dst,exclude=key)
        coverage=1.0 if without_habit is None else 0.0
        saved=0.0 if without_habit is None else max(0.0,float(without_habit-with_habit))
        reliability=(hb['n_ok']+1)/(hb['n_exec']+2)
        s.prune_seconds+=time.perf_counter()-t0
        return reliability*(s.coverage_weight*coverage+saved)
    def add_path(s,pr,acts):
        for i in range(len(acts)): s.es.pop((pr[i],acts[i]),None);s._purge(pr[i],acts[i],pr[i+1])
        new=set()
        for i in range(len(acts)):
            for j in range(i+1,len(acts)+1):
                key=(pr[i],tuple(acts[i:j]))
                if key in s.h: continue
                s.h[key]=dict(acts=key[1],path=tuple(pr[i:j+1]),n_exec=0,n_ok=0,uses=0);s.adj.setdefault(pr[i],[]).append(key);new.add(key)
        if s.dom: s.prune_dominated()
        s.prune(new)
    def prune_dominated(s):
        if not s.h: return 0
        nodes=sorted({p for hb in s.h.values() for p in hb['path']});ix={p:i for i,p in enumerate(nodes)};n=len(nodes)
        D=np.full((n,n),1e9);np.fill_diagonal(D,0.0)
        for hb in s.h.values(): i,j=ix[hb['path'][0]],ix[hb['path'][-1]];D[i,j]=min(D[i,j],len(hb['acts']))
        for k in range(n): D=np.minimum(D,D[:,k:k+1]+D[k:k+1,:])
        drop=[key for key,hb in s.h.items() if len(hb['acts'])>D[ix[hb['path'][0]],ix[hb['path'][-1]]]+1e-9]
        for key in drop: s._drop(key)
        return len(drop)
    def prune(s,protected):
        while s.cap and len(s.h)>s.cap:
            vs=[k for k in s.h if k not in protected] or list(s.h)
            if s.policy=='fifo': v=vs[0]
            elif s.policy=='random': v=vs[int(s.rng.integers(len(vs)))]
            elif s.policy in ('savings','step_savings'):
                u=[s.step_savings(k) for k in vs];mn=min(u);c=[k for k,x in zip(vs,u) if x==mn];v=c[int(s.rng.integers(len(c)))]
            else:
                u=[s.util(s.h[k]) for k in vs];mn=min(u);c=[k for k,x in zip(vs,u) if x==mn];v=c[int(s.rng.integers(len(c)))]
            s._drop(v);s.capacity_drops+=1
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
                lk+=1;e=hb['path'][-1];nd=d+len(hb['acts'])+s.lam
                if nd<dist.get(e,1e9): dist[e]=nd;prev[e]=(n,key);heapq.heappush(hp,(nd,e))
        if goal not in prev: return None,lk
        out=[];n=goal
        while n!=cur: pn,key=prev[n];out.append((key,s.h[key]));n=pn
        return out[::-1],lk
    def check(s):
        f=[];adjn=sum(len(v) for v in s.adj.values())
        if adjn!=len(s.h): f.append('adj_count')
        for c,ks in s.adj.items():
            if len(set(ks))!=len(ks): f.append('adj_dup')
            for k in ks:
                if k not in s.h: f.append('adj_dangling')
                elif s.h[k]['path'][0]!=c: f.append('adj_cue')
        em={}
        for k,hb in s.h.items():
            if k!=(hb['path'][0],hb['acts']): f.append('key_mismatch')
            if len(hb['path'])!=len(hb['acts'])+1: f.append('path_len')
            for j,a in enumerate(hb['acts']):
                if em.setdefault((hb['path'][j],a),hb['path'][j+1])!=hb['path'][j+1]: f.append('edge_contradiction')
        if s.cap and len(s.h)>s.cap: f.append('cap_exceeded')
        return f

def stale_frac(lib,m,w):
    inv={p:s for s,p in enumerate(m.sproto)};ed={}
    for hb in lib.h.values():
        for j,a in enumerate(hb['acts']): ed[(hb['path'][j],a)]=hb['path'][j+1]
    bad=tot=0
    for (c,a),n in ed.items():
        if c in inv and n in inv: tot+=1;bad+=int(w.T[inv[c],a]!=inv[n])
    return bad/tot if tot else 0.0

class AgS:
    def __init__(s,m,kind,rseed,cap=None,policy='utility',lam=0.1,dom=False,coverage_weight=0.5):
        s.m=m;s.kind=kind;s.P=m.P.copy();s.rng=np.random.default_rng(rseed);s.lib=LibS(cap,policy,s.rng,lam,dom,coverage_weight)
        s.learn=True;s.eta=0.0;s.mode='none';s.pf=0.0;s.pu=0.3
    @property
    def stats_on(s): return s.kind=='habit'
def clone(a,kind,rseed,spec):
    b=AgS(a.m,kind,rseed);b.lib=copy.deepcopy(a.lib);b.lib.rng=b.rng;b.P=a.P.copy()
    b.lib.lam=spec.get('lam',0.1);b.lib.dom=spec.get('dom',False);b.lib.cap=spec.get('cap');b.lib.policy=spec.get('policy','utility')
    b.lib.coverage_weight=float(spec.get('coverage_weight',0.5))
    b.mode=spec.get('mode','none');b.pf=spec.get('pf',0.0);b.pu=spec.get('pu',0.3);b.learn=(kind!='skill')
    if b.lib.dom: b.lib.prune_dominated()
    return b

def epS(w,ag,s0,g,sp=0.0,Hmax=H):
    m=ag.m;L=ag.lib;gp=m.sproto[g];w.s=s0;z=m.enc(w.obs(s0));cur=m.snap(z)
    st=dict(steps=0,calls=0,lk=0,ab=0,au=0,rp=0);pp=[cur];pa=[];first=True;pend=None
    while st['steps']<Hmax and cur!=gp:
        ce=cur if cur>=0 else m.nearest(z);units=None
        if ag.kind!='delib' and not (ag.kind=='skill' and st['ab']>0):
            ch,lk=L.chain(ce,gp,ag.stats_on);st['lk']+=lk
            if ch is not None:
                units=[(list(zip(hb['acts'],hb['path'][1:])),key) for key,hb in ch]
                if first and ag.kind=='habit':
                    p=ag.pf if ag.mode=='fixed' else (ag.pu if (ag.mode=='adaptive' and L.cert.get((ce,gp))!=L.rev) else 0.0)
                    if p>0 and ag.rng.random()<p:
                        ae,c=plan2(ag.P,m,z,ce,gp);st['calls']+=c;st['au']+=1
                        if ae is not None and len(ae)<sum(len(u[0]) for u in units): units=[(ae,None)];st['rp']+=1;pend=(ce,gp)
                        elif ae is not None: L.cert[(ce,gp)]=L.rev
        first=False
        if units is None:
            ae,c=plan2(ag.P,m,z,ce,gp);st['calls']+=c
            if ae is None: break
            units=[(ae,None)]
        aborted=False
        for seq,key in units:
            if key: L.h[key]['n_exec']+=1
            i0=len(pa);ok=True
            for a,e in seq:
                if st['steps']>=Hmax: ok=False;break
                pc=cur;zb=z;s2=w.step(a,sp);st['steps']+=1;z=m.enc(w.obs(s2));cur=m.snap(z);pa.append(a);pp.append(cur)
                if ag.eta>0: ag.P[a]-=ag.eta*np.outer(ag.P[a]@zb-z,zb)/(zb@zb+1e-6)
                if ag.stats_on and pc>=0:
                    was=L.bad(pc,a);es=L.es.setdefault((pc,a),[0,0]);es[0]+=1;es[1]+=int(cur!=e)
                    if L.bad(pc,a) and not was: L.rev+=1
                if cur==gp: ok=(cur==e);break
                if cur!=e: ok=False;break
            if key and ok: L.h[key]['n_ok']+=1;L.h[key]['uses']+=1
            if key is None and ok and ag.learn and ag.kind!='delib' and min(pp[i0:])>=0:
                L.add_path(pp[i0:],pa[i0:])
                if pend: L.cert[pend]=L.rev;pend=None
            if not ok: aborted=True;break
            if cur==gp: break
        if aborted: st['ab']+=1
    return [float(w.s==g),st['steps'],st['calls'],st['lk'],st['ab'],st['au'],st['rp']]

def final(w,ag,tasks,sp=0.0):
    ag.learn=False;ag.mode='none';ag.eta=0.0
    free=np.array([epS(w,ag,s0,g,sp) for (s0,g) in tasks]);tight=np.array([epS(w,ag,s0,g,sp,int(w.D[s0,g])+1) for (s0,g) in tasks])
    return [tight[:,0].mean(),free[:,0].mean(),free[:,1].mean(),free[:,2].mean(),free[:,3].mean()]
def practice(w,ag,train,ra):
    prac=train*2;ra.shuffle(prac)
    for (s0,g) in prac: epS(w,ag,s0,g)
def corrupt(ag,m,w,frac,rng):
    ed=[(s,a) for s in range(S) for a in range(NA)];rng.shuffle(ed)
    for (s,a) in ed[:int(frac*len(ed))]:
        zs=m.protos[m.sproto[s]];wr=int(rng.integers(S))
        while wr==w.T[s,a]: wr=int(rng.integers(S))
        ag.P[a]+=np.outer(m.protos[m.sproto[wr]]-ag.P[a]@zs,zs)/(zs@zs)
def ms(x): x=np.asarray(x,float);return f"{x.mean():.2f}+-{x.std():.2f}"

BASIC=dict(kind='habit',lam=0.1)
E1CFG=[('delib',dict(kind='delib')),('skill (frozen, lam=.1)',dict(kind='skill',lam=0.1)),('habit basic, OLD cost lam=100',dict(kind='habit',lam=100)),('habit basic lam=.1',BASIC),
 ('habit fixed audit .3',dict(kind='habit',lam=0.1,mode='fixed',pf=0.3)),('habit adaptive audit (no prune)',dict(kind='habit',lam=0.1,mode='adaptive',pu=0.3)),
 ('habit FULL (adaptive+dominated prune)',dict(kind='habit',lam=0.1,mode='adaptive',pu=0.3,dom=True))]

def selftest():
    ok=[0,0]
    def T(c,n):
        ok[1]+=1;ok[0]+=bool(c)
        if not c: print('  SELFTEST FAIL:',n)
    rng=np.random.default_rng(0);L=LibS(None,'utility',rng,0.1,False);L.add_path((0,1,2,3),(5,6,7))
    T(len(L.h)==6,'subpath count');ch,_=L.chain(0,3,False);T(ch is not None and sum(len(h['acts']) for _,h in ch)==3,'chain is step-optimal');T(not L.check(),'healthy library passes invariants')
    L.cert[(0,3)]=L.rev;r0=L.rev;L.add_path((0,9),(5,))
    T(L.h[(0,(5,))]['path']==(0,9),'contradicting edge replaced');T(not any(hb['path'][0]==0 and hb['acts'][0]==5 and hb['path'][1]==1 for hb in L.h.values()),'stale chunks purged')
    T(L.rev>r0,'revision counter bumped');T(L.cert[(0,3)]!=L.rev,'certificate invalidated by contradiction');T(not L.check(),'invariants hold after revision')
    L2=LibS(None,'utility',rng,0.1,True);L2.add_path((0,4,5,2),(1,2,3));L2.add_path((0,6,2),(8,9))
    T((0,(1,2,3)) not in L2.h,'dominated detour chunk pruned');T(all((c,(a,)) in L2.h for c,a in [(0,1),(4,2),(5,3),(0,8),(6,9)]),'atomic edges never pruned');T((0,(8,9)) in L2.h,'non-dominated chunk kept')
    L3=LibS(5,'utility',rng,0.1,False);L3.add_path((0,1,2,3),(5,6,7));T(len(L3.h)==5,'capacity enforced strictly')
    L.adj[0].append(('x',));T(any(x in L.check() for x in ('adj_dangling','adj_count')),'invariant checker detects corruption')
    L4=LibS(None,'utility',rng,100.0,False);L4.add_path((0,1,2),(1,2));L4.add_path((0,3,4,2),(3,4,5));ch,_=L4.chain(0,2,False)
    L5=LibS(None,'utility',rng,0.1,False);L5.add_path((0,1,2),(1,2));L5.add_path((0,3,2),(8,9));L5.h[(0,(8,9))]['n_ok']=0
    ch5,_=L5.chain(0,2,False);T(ch5 is not None,'chain finds route')
    L6=LibS(1,'savings',np.random.default_rng(6),0.1,False,coverage_weight=2.0)
    det=(0,(4,5,6,7));short=(0,(1,2))
    L6.h[det]=dict(acts=det[1],path=(0,4,5,6,3),n_exec=100,n_ok=100,uses=100)
    L6.h[short]=dict(acts=short[1],path=(0,2,3),n_exec=1,n_ok=1,uses=1)
    L6.adj={0:[det,short]}
    T(L6.util(L6.h[det])>L6.util(L6.h[short]),'legacy utility prefers frequent use')
    T(L6.step_savings(short)>L6.step_savings(det),'saved steps outrank raw usage')
    L6.prune(set())
    T(short in L6.h and det not in L6.h,'capacity retains the shorter verified route')
    L7=LibS(None,'savings',np.random.default_rng(7),0.1,False,coverage_weight=2.0)
    unique=(0,(9,));L7.h[unique]=dict(acts=unique[1],path=(0,1),n_exec=0,n_ok=0,uses=0);L7.adj={0:[unique]}
    T(L7.step_savings(unique)>0,'unique route receives coverage credit')
    L7.h[unique]['n_exec']=2;L7.h[unique]['n_ok']=0;L7.es[(0,9)]=[2,2]
    T(L7.step_savings(unique)==0,'known-bad route is not rewarded')
    def retained(seed):
        q=LibS(2,'savings',np.random.default_rng(seed),0.1,False,coverage_weight=2.0)
        specs=[((0,(1,2)),(0,4,9)),((0,(3,4,5)),(0,5,6,9)),((0,(6,7,8,9)),(0,7,8,10,9))]
        for key,path in specs:
            q.h[key]=dict(acts=key[1],path=path,n_exec=4,n_ok=4,uses=4)
            q.adj.setdefault(0,[]).append(key)
        q.prune(set())
        return tuple(sorted(q.h)),q.check()
    T(retained(88)==retained(88),'step-savings pruning is deterministic')
    T(L6.check()==[],'capacity pruning preserves structural invariants')
    L8=LibS(None,'savings',np.random.default_rng(8),0.1,False,coverage_weight=4.0)
    L9=LibS(None,'savings',np.random.default_rng(9),0.1,False,coverage_weight=1.0)
    for q in (L8,L9):
        k=(0,(2,));q.h[k]=dict(acts=k[1],path=(0,1),n_exec=0,n_ok=0,uses=0);q.adj={0:[k]}
    T(L8.step_savings((0,(2,)))>L9.step_savings((0,(2,))),'coverage weight is an active parameter')
    return ok

def run_E(NS,out):
    R1={};R2={};cyc={};diag=[]
    for seed in range(NS):
        t0=time.time();w,m,pool,novel=setup(seed,SIG);ra=np.random.default_rng(5000+seed);train=pool[:NTR];uidx=ra.integers(0,len(pool),120);aidx=ra.integers(0,len(pool),80)
        base=AgS(m,'habit',9000+seed);practice(w,base,train,ra);note(base.lib.check())
        eacc=np.mean([m.nearest(m.P[a]@m.protos[m.sproto[s]])==m.sproto[w.T[s,a]] for s in range(S) for a in range(NA)]);dstate=len(set(m.sproto));diag.append([len(m.protos),dstate,eacc])
        for k,(name,spec) in enumerate(E1CFG):
            ag=clone(base,spec['kind'],seed*100+k,spec);use=np.array([epS(w,ag,*pool[i]) for i in uidx]);note(ag.lib.check())
            if spec['kind']=='habit' and use[:,4].sum()>0: note(['static_world_abort'])
            R1.setdefault(name,[]).append([use[:,2].sum(),use[:,6].sum(),*final(w,ag,novel),len(ag.lib.h),stale_frac(ag.lib,m,w)])
        for k,(name,spec) in enumerate([E1CFG[0],E1CFG[1],E1CFG[3],E1CFG[6]]):
            w2=copy.deepcopy(w);rewire(w2,0.3,np.random.default_rng(8000+seed))
            ag=clone(base,spec['kind'],5000+seed*100+k,spec);ag.eta=0.7;s0f=stale_frac(ag.lib,m,w2)
            rows=np.array([epS(w2,ag,*pool[i]) for i in aidx]);note(ag.lib.check())
            blk=np.array([[rows[b*20:(b+1)*20,c].mean() for c in (0,1,2,4)] for b in range(4)])
            R2.setdefault(name,[]).append([blk,final(w2,ag,novel),s0f,stale_frac(ag.lib,m,w2)])
        print(f"E seed{seed} {time.time()-t0:.0f}s",flush=True)
    d=np.array(diag);print(f"\nWORLD: S={S} states, sigma={SIG:g}, n_train={NTR}; representation: protos={d[:,0].mean():.1f} distinct_state_protos={d[:,1].mean():.1f} planner-model edge accuracy={d[:,2].mean():.3f}")
    print(f"\n=== E1: static world, refinement + pruning ({NS} seeds): 120 use episodes then 30 novel tasks, learning off ===")
    for name,v in R1.items():
        a=np.array(v);print(f"  {name:38s} use_calls={a[:,0].mean():6.0f} replaced={a[:,1].mean():5.1f} | final D+1={ms(a[:,2])} steps={a[:,4].mean():.2f} calls={a[:,5].mean():5.2f} lookups={a[:,6].mean():5.1f} | library={a[:,7].mean():5.1f} stale={a[:,8].mean():.3f}")
    print(f"\n=== E2: 30% of transitions rewired ({NS} seeds): 4 blocks of 20 adaptation episodes (success | steps | planner calls | aborts), then final ===")
    for name,v in R2.items():
        B=np.mean([x[0] for x in v],axis=0)
        print(f"  {name:38s}\n     succ {' '.join(f'{x:5.2f}' for x in B[:,0])} | steps {' '.join(f'{x:5.2f}' for x in B[:,1])} | calls {' '.join(f'{x:5.1f}' for x in B[:,2])} | aborts {' '.join(f'{x:5.2f}' for x in B[:,3])}\n     final D+1={ms([x[1][0] for x in v])} steps={np.mean([x[1][2] for x in v]):.2f} | library stale: before={np.mean([x[2] for x in v]):.3f} after={np.mean([x[3] for x in v]):.3f}")

def run_ST(NS,which):
    S1={};S2={};S3={};S4={};S5={}
    for seed in range(SEED_START,SEED_START+NS):
        t0=time.time();w,m,pool,novel=setup(seed,SIG);ra=np.random.default_rng(6000+seed);train=pool[:NTR];uidx=ra.integers(0,len(pool),120)
        base=AgS(m,'habit',9500+seed);practice(w,base,train,ra);w_base=copy.deepcopy(w)
        if 'ST1' in which:
            for eta in (0.0,0.7):
                for k,(name,spec) in enumerate([E1CFG[0],E1CFG[3],E1CFG[4],E1CFG[6]]):
                    ag=clone(base,spec['kind'],seed*100+k,spec);ag.eta=eta;corrupt(ag,m,w,0.25,np.random.default_rng(8200+seed))
                    use=np.array([epS(w,ag,*pool[i]) for i in uidx]);note(ag.lib.check());st=stale_frac(ag.lib,m,w)
                    S1.setdefault((eta,name),[]).append([use[:,0].mean(),use[:,1].mean(),use[:,2].mean(),use[:,4].mean(),st,*final(w,ag,novel)[:3]])
        if 'ST2' in which:
            for k,(name,spec) in enumerate([E1CFG[0],E1CFG[1],E1CFG[3],E1CFG[6]]):
                w2=copy.deepcopy(w);ag=clone(base,spec['kind'],seed*100+k,spec);ag.eta=0.7;rows=[]
                for c in range(5):
                    rewire(w2,0.3,np.random.default_rng(8100+seed*10+c));ag.learn=(spec['kind']!='skill');ag.mode=spec.get('mode','none')
                    r=np.array([epS(w2,ag,*pool[i]) for i in ra.integers(0,len(pool),60)]);note(ag.lib.check())
                    rows.append([r[:,0].mean(),r[:,1].mean(),r[:,2].mean(),r[:,4].mean(),stale_frac(ag.lib,m,w2)])
                S2.setdefault(name,[]).append(rows)
        if 'ST3' in which:
            for k,(name,spec) in enumerate([E1CFG[3],E1CFG[6]]):
                ag=clone(base,spec['kind'],seed*100+k,spec);ag.eta=0.2
                use=np.array([epS(w,ag,*pool[i],0.15) for i in uidx]);note(ag.lib.check());nbad=sum(1 for e in ag.lib.es if ag.lib.bad(*e))
                S3.setdefault(('static+slips',name),[]).append([use[:,0].mean(),use[:,2].mean(),nbad,stale_frac(ag.lib,m,w),*final(w,ag,novel)[:1]])
                w2=copy.deepcopy(w);rewire(w2,0.3,np.random.default_rng(8000+seed));ag=clone(base,spec['kind'],seed*100+k+50,spec);ag.eta=0.2
                rows=np.array([epS(w2,ag,*pool[i],0.15) for i in ra.integers(0,len(pool),80)]);note(ag.lib.check())
                S3.setdefault(('change+slips',name),[]).append([rows[:,0].mean(),rows[:,2].mean(),sum(1 for e in ag.lib.es if ag.lib.bad(*e)),stale_frac(ag.lib,m,w2),*final(w2,ag,novel)[:1]])
        if 'ST4' in which:
            prac_order=train*2;np.random.default_rng(7000+seed).shuffle(prac_order)
            use_tasks=[pool[i] for i in uidx[:60]]
            for cap in (12,20,28,None):
                for pol in (['utility','savings','random','fifo'] if cap else ['utility','savings']):
                    wt=copy.deepcopy(w_base)
                    ag=AgS(m,'habit',777+seed,cap,pol,0.1,True,float(os.environ.get('HL_COVERAGE_WEIGHT',0.5)))
                    ag.mode='adaptive';ag.pu=0.3
                    for task in prac_order: epS(wt,ag,*task)
                    for task in use_tasks: epS(wt,ag,*task)
                    ag.learn=False;cf=np.mean([ag.lib.chain(m.sproto[s0],m.sproto[g],True)[0] is not None for (s0,g) in novel]);note(ag.lib.check())
                    S4.setdefault((cap,pol),[]).append([cf,*final(wt,ag,novel),len(ag.lib.h),ag.lib.prune_searches,ag.lib.prune_expansions,ag.lib.prune_seconds,ag.lib.capacity_drops])
        if 'ST5' in which:
            task_rng=np.random.default_rng(9900+seed)
            cycle_tasks=[[pool[i] for i in task_rng.integers(0,len(pool),60)] for _ in range(5)]
            for pol in ('utility','savings'):
                spec=dict(kind='habit',lam=0.1,mode='adaptive',pu=0.3,dom=True,cap=28,policy=pol,
                          coverage_weight=float(os.environ.get('HL_COVERAGE_WEIGHT',0.5)))
                ag=clone(base,'habit',9700+seed,spec);ag.lib.prune(set());ag.mode='adaptive';ag.pu=0.3;ag.eta=0.7
                w2=copy.deepcopy(w_base);rows=[]
                for c in range(5):
                    rewire(w2,0.3,np.random.default_rng(9100+seed*10+c))
                    r=np.array([epS(w2,ag,*task) for task in cycle_tasks[c]]);note(ag.lib.check())
                    rows.append([r[:,0].mean(),r[:,1].mean(),r[:,2].mean(),r[:,4].mean(),stale_frac(ag.lib,m,w2),len(ag.lib.h),ag.lib.prune_searches,ag.lib.prune_expansions,ag.lib.prune_seconds,ag.lib.capacity_drops])
                S5.setdefault(pol,[]).append(rows)
        print(f"ST seed{seed} {time.time()-t0:.0f}s",flush=True)
    if S1:
        print(f"\n=== ST1: planner model corrupted on 25% of edges; static world, 120 use episodes ({NS} seeds). eta = whether the model keeps learning ===")
        for (eta,name),v in S1.items():
            a=np.array(v);print(f"  eta={eta:.1f} {name:38s} use: success={a[:,0].mean():.2f} steps={a[:,1].mean():.2f} calls={a[:,2].mean():5.1f} aborts={a[:,3].mean():.2f} | library_stale={a[:,4].mean():.3f} | final D+1={a[:,5].mean():.2f} success={a[:,6].mean():.2f}")
    if S2:
        print(f"\n=== ST2: five regime changes (30% rewired each), 60 episodes per cycle ({NS} seeds): per cycle success / steps / calls / aborts / library_stale ===")
        for name,v in S2.items():
            B=np.mean(v,axis=0);print(f"  {name}")
            for c in range(5): print(f"     cycle{c+1}: success={B[c,0]:.2f} steps={B[c,1]:.2f} calls={B[c,2]:5.1f} aborts={B[c,3]:.2f} stale={B[c,4]:.3f}")
    if S3:
        print(f"\n=== ST3: 15% action slips ({NS} seeds); bad_edges = edges wrongly/rightly flagged as changed ===")
        for (cond,name),v in S3.items():
            a=np.array(v);print(f"  {cond:13s} {name:38s} success={a[:,0].mean():.2f} calls={a[:,1].mean():5.1f} bad_edges_flagged={a[:,2].mean():4.1f} library_stale={a[:,3].mean():.3f} final D+1(no slips)={a[:,4].mean():.2f}")
    if S4:
        print(f"\n=== ST4: capacity-limited FULL system ({NS} seeds): practice + 60 use episodes (adaptive audit), then 30 novel tasks ===")
        for (cap,pol),v in S4.items():
            a=np.array(v);print(f"  cap={str(cap):4s} {pol:8s} chain_found={ms(a[:,0])} final D+1={a[:,1].mean():.2f} success={a[:,2].mean():.2f} steps={a[:,3].mean():.2f} calls={a[:,4].mean():5.2f} library={a[:,6].mean():5.1f} prune_searches={a[:,7].mean():.0f} expansions={a[:,8].mean():.0f} prune_s={a[:,9].mean():.4f} drops={a[:,10].mean():.1f}")
    if S5:
        print(f"\n=== ST5: five 30% regime changes at cap=28; utility control vs step-savings retention ({NS} seeds) ===")
        for pol,v in S5.items():
            B=np.mean(v,axis=0);print(f"  policy={pol}")
            for c in range(5):
                print(f"     cycle{c+1}: success={B[c,0]:.2f} steps={B[c,1]:.2f} calls={B[c,2]:5.1f} aborts={B[c,3]:.2f} stale={B[c,4]:.3f} library={B[c,5]:5.1f} prune_searches={B[c,6]:.0f} expansions={B[c,7]:.0f} prune_s={B[c,8]:.4f} drops={B[c,9]:.1f}")
    result_path=os.environ.get('HL_RESULTS_PATH')
    if result_path:
        payload={
            'world_states':S,'sigma':SIG,'n_train':NTR,
            'coverage_weight':float(os.environ.get('HL_COVERAGE_WEIGHT',0.5)),
            'seed_start':SEED_START,'seeds':list(range(SEED_START,SEED_START+NS)),
            'ST4':{f"{cap if cap is not None else 'uncapped'}|{pol}":np.asarray(v).tolist() for (cap,pol),v in S4.items()},
            'ST5':{pol:np.asarray(v).tolist() for pol,v in S5.items()},
        }
        with open(result_path,'w',encoding='utf-8') as f: json.dump(payload,f,indent=2)
        print(f"\nRAW RESULTS SAVED: {result_path}")

def det_run(seed):
    w,m,pool,novel=setup(seed,SIG);ra=np.random.default_rng(5000+seed);train=pool[:NTR];uidx=ra.integers(0,len(pool),120);ra.integers(0,len(pool),80)
    base=AgS(m,'habit',9000+seed);practice(w,base,train,ra);ag=clone(base,'habit',seed*100+6,E1CFG[6][1])
    use=np.array([epS(w,ag,*pool[i]) for i in uidx]);return np.concatenate([use.ravel(),final(w,ag,novel),[len(ag.lib.h)]])

if __name__=='__main__':
    NS=int(sys.argv[1]);which=sys.argv[2].split(',')
    if 'self' in which: ok=selftest();print(f"SELFTEST: {ok[0]}/{ok[1]} passed")
    if 'E' in which: run_E(NS,None)
    if any(x.startswith('ST') for x in which): run_ST(NS,which)
    if 'det' in which: a=det_run(0);b=det_run(0);print(f"DETERMINISM: identical results on rerun = {np.array_equal(a,b)} ({len(a)} values compared)")
    print(f"\nINVARIANT CHECKS: {NCHK[0]} library checks run, failures by type: {FAIL if FAIL else 'none'}")
