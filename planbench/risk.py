"""Bounded exact retry risk. Supplied independent failures, not learned forecasts."""
from fractions import Fraction as F
from copy import deepcopy
import re


def number(x,lo=0,hi=10000):
    if type(x)is int:y=F(x)
    elif type(x)is str and len(x)<=24 and re.fullmatch(r'-?[0-9]+(?:/[1-9][0-9]*)?',x):y=F(x)
    else:raise ValueError('use integer or rational string, not float/bool')
    if not lo<=y<=hi or y.denominator>1000:raise ValueError('rational outside bounds')
    return y


def fields(x,required,optional=()):
    if type(x)is not dict or not set(required)<=set(x) or set(x)-set(required)-set(optional):raise ValueError('missing or unknown fields')


def identifier(x):
    if type(x)is not str or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,23}',x):raise ValueError('invalid identifier')
    return x


def normalize(spec):
    fields(spec,['plan','tools','deadline','budget']);fields(spec['plan'],['steps'],['name'])
    if 'name'in spec['plan']and(type(spec['plan']['name'])is not str or len(spec['plan']['name'])>80):raise ValueError('plan name must be a short string')
    steps=spec['plan']['steps'];tools=spec['tools']
    if type(steps)is not list or not 1<=len(steps)<=6 or type(tools)is not dict or not 1<=len(tools)<=6:raise ValueError('1..6 steps/tools required')
    registry={}
    for name,t in tools.items():
        identifier(name);fields(t,['cost','failure_rate'],['produces']);produces=t.get('produces',[])
        if type(produces)is not list or len(produces)>12 or any(type(p)is not str or len(p)>40 for p in produces):raise ValueError('invalid produces')
        registry[name]={'cost':number(t['cost'],0,100),'failure':number(t['failure_rate'],0,1),'produces':produces}
    by_id={}
    for step in steps:
        fields(step,['id','tool'],['needs','requires','duration','max_retries']);sid=identifier(step['id']);tool=step['tool'];needs=step.get('needs',[]);requires=step.get('requires',[]);r=step.get('max_retries',0)
        if sid in by_id or tool not in registry:raise ValueError('duplicate step or unknown tool')
        if type(needs)is not list or len(needs)>6 or any(type(x)is not str for x in needs)or len(set(needs))!=len(needs):raise ValueError('invalid dependencies')
        if type(requires)is not list or len(requires)>12 or any(type(x)is not str or len(x)>40 for x in requires):raise ValueError('invalid requirements')
        if type(r)is not int or not 0<=r<=2:raise ValueError('retries must be0..2')
        d=number(step.get('duration',1),0,100)
        if not d:raise ValueError('duration must be positive')
        by_id[sid]={'id':sid,'tool':tool,'needs':needs[:],'requires':requires[:],'duration':d,'retries':r,**registry[tool]}
    for s in by_id.values():
        if any(d not in by_id for d in s['needs']):raise ValueError('unknown dependency')
        made={p for dep in s['needs']for p in registry[by_id[dep]['tool']]['produces']}
        if not set(s['requires'])<=made:raise ValueError('unproduced direct-dependency input')
    order=[]
    while len(order)<len(steps):
        ready=sorted(s for s in by_id if s not in order and set(by_id[s]['needs'])<=set(order))
        if not ready:raise ValueError('dependency cycle')
        order.append(ready[0])
    return [by_id[x]for x in order],number(spec['deadline']),number(spec['budget'])


def terminal_options(step):
    q=step['failure'];limit=step['retries']+1
    return [(True,k,q**(k-1)*(1-q))for k in range(1,limit+1)if q**(k-1)*(1-q)]+([(False,limit,q**limit)]if q**limit else [])


def analyze(spec):
    """Exact joint law with a complete positive-mass terminal history witness."""
    steps,deadline,budget=normalize(spec);histories=[];out={}
    def visit(i,mass):
        if i==len(steps):
            rows=[dict(out[s['id']])for s in steps];end=max(r['end']for r in rows);cost=sum((r['cost']for r in rows),F(0));success=all(r['status']=='succeeded'for r in rows)
            histories.append({'probability':mass,'succeeded':success,'makespan':end,'total_cost':cost,'steps':rows});return
        s=steps[i];deps=[out[d]for d in s['needs']];ready=max((d['end']for d in deps),default=F(0))
        if any(d['status']!='succeeded'for d in deps):
            out[s['id']]={'id':s['id'],'status':'skipped','attempts':0,'ready':ready,'start':ready,'end':ready,'cost':F(0)};visit(i+1,mass)
        else:
            for ok,n,p in terminal_options(s):
                out[s['id']]={'id':s['id'],'status':'succeeded'if ok else 'failed','attempts':n,'ready':ready,'start':ready+(n-1)*s['duration'],'end':ready+n*s['duration'],'cost':n*s['cost']};visit(i+1,mass*p)
        del out[s['id']]
    visit(0,F(1));law={}
    for h in histories:
        key=(h['succeeded'],h['makespan'],h['total_cost']);law[key]=law.get(key,F(0))+h['probability']
    def mass(predicate):return sum((h['probability']for h in histories if predicate(h)),F(0))
    def expectation(field,predicate=lambda h:True):return sum((h['probability']*h[field]for h in histories if predicate(h)),F(0))
    success=mass(lambda h:h['succeeded']);within=lambda h:h['makespan']<=deadline and h['total_cost']<=budget
    stats={'mass':mass(lambda h:True),'success_probability':success,'within_probability':mass(within),'success_within_probability':mass(lambda h:h['succeeded']and within(h)),'expected_makespan':expectation('makespan'),'expected_cost':expectation('total_cost'),'success_expected_makespan':expectation('makespan',lambda h:h['succeeded'])/success if success else None,'success_expected_cost':expectation('total_cost',lambda h:h['succeeded'])/success if success else None}
    summaries=[]
    for s in steps:
        sid=s['id'];local=terminal_options(s);summaries.append({'id':sid,'local_outcomes':[{'status':'succeeded'if ok else 'failed','attempts':n,'probability':p}for ok,n,p in local],'status_mass':{status:mass(lambda h:next(r for r in h['steps']if r['id']==sid)['status']==status)for status in ['succeeded','failed','skipped']},'expected_attempts':sum((h['probability']*next(r for r in h['steps']if r['id']==sid)['attempts']for h in histories),F(0))})
    def serial(x):
        if isinstance(x,F):return str(x)
        if isinstance(x,list):return [serial(y)for y in x]
        if isinstance(x,dict):return {k:serial(v)for k,v in x.items()}
        return x
    return serial({'schema':'planbench-risk/1','input':deepcopy(spec),'order':[s['id']for s in steps],'stats':stats,'step_laws':summaries,'joint':[{'succeeded':k[0],'makespan':k[1],'total_cost':k[2],'probability':v}for k,v in sorted(law.items())],'histories':histories})
