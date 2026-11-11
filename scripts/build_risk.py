from pathlib import Path
import json,random,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from planbench.risk import analyze

def row(sid,needs=(),duration=1,retries=0,tool='x'):
    return {'id':sid,'tool':tool,'needs':list(needs),'duration':duration,'max_retries':retries}
def case(name,steps,q='1/2',deadline=4,budget=5,tools=None):
    v={'plan':{'steps':steps},'tools':tools or {'x':{'cost':1,'failure_rate':q}},'deadline':deadline,'budget':budget}
    return {'name':name,'input':v,'report':analyze(v)}
def build():
    ws=[case('parallel-retry-maximum',[row('a',retries=1),row('b',retries=1)],deadline=2,budget=4),case('cheap-failure-is-not-success',[row('a'),row('b',['a'],5)],deadline=1,budget=1),case('shared-ancestor',[row('a'),row('b',['a']),row('c',['a']),row('d',['b','c'])]),case('serial-retry-cost',[row('a',duration=2,retries=2),row('b',['a'],1,1)]),case('always-fail-skip',[row('a',retries=2),row('b',['a'])],q='1'),case('always-succeed',[row('a'),row('b',['a'],2)],q='0'),case('zero-success-conditioned-null',[row('a')],q='1',deadline=0,budget=0),case('zero-cost-not-zero-time',[row('a',retries=1),row('b',retries=2)],tools={'x':{'cost':0,'failure_rate':'1/4'}},deadline=1,budget=0),case('rational-durations',[row('a',duration='2/3',retries=2),row('b',['a'],'1/2')],tools={'x':{'cost':'1/3','failure_rate':'2/3'}},deadline='7/6',budget='2/3'),case('six-certain-steps',[row(chr(97+i),[chr(96+i)]if i else [],i+1)for i in range(6)],q='0',deadline=21,budget=6),case('three-full-retry-limits',[row('a',retries=2),row('b',retries=2),row('c',['a','b'],retries=2)],deadline=4,budget=6),case('unrelated-branch-still-runs',[row('a',tool='bad'),row('b',['a'],tool='bad'),row('c',duration=7)],tools={'x':{'cost':1,'failure_rate':0},'bad':{'cost':2,'failure_rate':1}},deadline=7,budget=3)]
    rng=random.Random(211)
    for i in range(16):
        steps=[row(chr(97+j),[chr(97+k)for k in range(j)if rng.random()<.45],rng.choice([1,2,'1/2']),rng.randrange(2),'x'if j%2 else 'y')for j in range(rng.randrange(1,5))];ws.append(case('seeded-'+str(i),steps,tools={'x':{'cost':'2/3','failure_rate':'1/4'},'y':{'cost':2,'failure_rate':'2/3'}},deadline=rng.randrange(8),budget=rng.randrange(8)))
    return ws
if __name__=='__main__':
    ws=build();(ROOT/'examples/risk.json').write_text(json.dumps(ws,separators=(',',':'))+'\n');(ROOT/'docs/risk-data.js').write_text('globalThis.RISK_INPUTS='+json.dumps([{'name':w['name'],'input':w['input']}for w in ws],separators=(',',':'))+';\n');print('reports',len(ws),'histories',sum(len(w['report']['histories'])for w in ws),'jointrows',sum(len(w['report']['joint'])for w in ws))
