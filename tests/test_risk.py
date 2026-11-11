import copy,heapq,itertools,json,random,subprocess,sys,tempfile,unittest
from collections import defaultdict
from fractions import Fraction as F
from pathlib import Path
from planbench.risk import analyze,normalize


def spec(steps,tools=None,deadline=6,budget=6):
    return {'plan':{'steps':steps},'tools':tools or {'x':{'cost':1,'failure_rate':'1/2'}},'deadline':deadline,'budget':budget}


def bits_oracle(s):
    """All potential per-attempt Bernoulli bits, including unused latent bits.

    Event queue contains attempt completions, not native terminal step choices.
    """
    steps=s['plan']['steps'];by={x['id']:x for x in steps};order=[];positions=[]
    while len(order)<len(steps):order.append(min(k for k in by if k not in order and set(by[k].get('needs',[]))<=set(order)))
    for x in steps:
        for a in range(x.get('max_retries',0)+1):positions.append((x['id'],a))
    law=defaultdict(F);hist=defaultdict(F)
    for bits in itertools.product((False,True),repeat=len(positions)):
        draws=dict(zip(positions,bits));mass=F(1)
        for (sid,a),failed in draws.items():
            q=F(s['tools'][by[sid]['tool']]['failure_rate']);mass*=q if failed else 1-q
        if not mass:continue
        done={};started=set();events=[];ready={}
        def launch():
            for sid in sorted(by):
                x=by[sid];deps=x.get('needs',[])
                if sid in started or any(d not in done for d in deps):continue
                started.add(sid);t=max((done[d][3]for d in deps),default=F(0));ready[sid]=t
                if any(done[d][0]!='succeeded'for d in deps):done[sid]=('skipped',0,t,t,F(0));launch()
                else:heapq.heappush(events,(t+F(x.get('duration',1)),sid,0))
        launch()
        while events:
            end,sid,a=heapq.heappop(events);x=by[sid];d=F(x.get('duration',1));cost=F(s['tools'][x['tool']]['cost'])
            if draws[sid,a]and a<x.get('max_retries',0):heapq.heappush(events,(end+d,sid,a+1))
            else:done[sid]=('failed'if draws[sid,a]else 'succeeded',a+1,end-d,end,cost*(a+1));launch()
        key=tuple((sid,*done[sid],ready[sid])for sid in order);hist[key]+=mass
        law[(all(v[0]=='succeeded'for v in done.values()),max(v[3]for v in done.values()),sum((v[4]for v in done.values()),F(0)))]+=mass
    return law,hist


class RiskTests(unittest.TestCase):
    def compare(self,s):
        r=analyze(s);expected,hist=bits_oracle(s);got={(x['succeeded'],F(x['makespan']),F(x['total_cost'])):F(x['probability'])for x in r['joint']};self.assertEqual(got,expected)
        actual={tuple((v['id'],v['status'],v['attempts'],F(v['start']),F(v['end']),F(v['cost']),F(v['ready']))for v in h['steps']):F(h['probability'])for h in r['histories']};self.assertEqual(actual,dict(hist));self.assertEqual(sum(got.values()),1)
        self.assertEqual(F(r['stats']['mass']),1);self.assertEqual(sum(F(x['probability'])for x in r['histories']),1)
        return r
    def test_single_step_every_boundary_and_retry(self):
        for q in ['0','1/4','1/2','2/3','1']:
            for retry in range(3):
                r=self.compare(spec([{'id':'a','tool':'x','max_retries':retry}],{'x':{'cost':'2/3','failure_rate':q}}));self.assertEqual(F(r['stats']['success_probability']),1-F(q)**(retry+1))
    def test_chain_fork_join_and_shared_ancestor(self):
        for shape in [[],[[],[0]],[[],[],[0,1]],[[],[0],[0],[1,2]]]:
            if not shape:continue
            self.compare(spec([{'id':chr(97+i),'tool':'x','needs':[chr(97+d)for d in deps],'duration':i+1,'max_retries':1}for i,deps in enumerate(shape)]))
    def test_independent_event_bits_seeded_dags(self):
        rng=random.Random(683)
        for _ in range(65):
            n=rng.randrange(1,5);steps=[{'id':chr(97+i),'tool':'x'if i%2 else 'y','needs':[chr(97+j)for j in range(i)if rng.random()<.4],'duration':rng.choice([1,2,'1/2','2/3']),'max_retries':rng.randrange(2)}for i in range(n)]
            self.compare(spec(steps,{'x':{'cost':'1/3','failure_rate':'1/4'},'y':{'cost':2,'failure_rate':'2/3'}},deadline=rng.randrange(8),budget=rng.randrange(8)))
    def test_cheap_failure_is_not_success(self):
        r=self.compare(spec([{'id':'a','tool':'x'},{'id':'b','tool':'x','needs':['a'],'duration':5}],deadline=1,budget=1));self.assertEqual(r['stats']['within_probability'],'1/2');self.assertEqual(r['stats']['success_within_probability'],'0')
    def test_parallel_mean_is_not_mean_critical_path(self):
        r=self.compare(spec([{'id':'a','tool':'x','max_retries':1},{'id':'b','tool':'x','max_retries':1}],deadline=2,budget=4));self.assertEqual(r['stats']['expected_makespan'],'7/4');self.assertEqual(r['stats']['success_expected_makespan'],'14/9')
    def test_always_fail_skips_zero_success_condition(self):
        r=self.compare(spec([{'id':'a','tool':'x','max_retries':2},{'id':'b','tool':'x','needs':['a']}],{'x':{'cost':0,'failure_rate':1}}));self.assertEqual(r['stats']['success_expected_cost'],None);self.assertEqual(r['step_laws'][1]['status_mass']['skipped'],'1')
    def test_order_invariance_and_input_detached(self):
        s=spec([{'id':'c','tool':'x','needs':['b','a']},{'id':'b','tool':'x'},{'id':'a','tool':'x'}]);old=copy.deepcopy(s);r=analyze(s);self.assertEqual(s,old);s['plan']['steps'].reverse();z=analyze(s);self.assertEqual(r['histories'],z['histories']);self.assertEqual(r['order'],['a','b','c'])
    def test_strict_rejects_and_semantics(self):
        from planbench.risk_cli import parse
        good=spec([{'id':'a','tool':'x'}]);bad=[]
        for val in [True,0.5,'1e2','1/0','1/1001','-1','10001',{},None]:
            x=copy.deepcopy(good);x['budget']=val;bad.append(x)
        for steps in [[],[{'id':'a','tool':'x','needs':['z']}],[{'id':'a','tool':'x','needs':['a']}],[{'id':'a','tool':'z'}],[{'id':'a','tool':'x','max_retries':True}],[{'id':'a','tool':'x','max_retries':3}],[{'id':'a','tool':'x','requires':['foo']}],[{'id':'a','tool':'x','duration':0}],[{'id':'a','tool':'x'}]*7]:bad.append(spec(steps))
        for x in bad:
            with self.assertRaises(ValueError):analyze(x)
        for text in ['{"a":1,"a":2}','{"a":1.0}','{"a":NaN}','['*1000,' '*131073]:
            with self.assertRaises(ValueError):parse(text)
    def test_cli(self):
        s=spec([{'id':'a','tool':'x','max_retries':1}])
        with tempfile.TemporaryDirectory()as t:
            p=Path(t)/'input.json';p.write_text(json.dumps(s));r=subprocess.run([sys.executable,'-m','planbench.risk_cli','--input',str(p)],capture_output=True,text=True,check=True);self.assertEqual(json.loads(r.stdout),analyze(s));p.write_text('{}');r=subprocess.run([sys.executable,'-m','planbench.risk_cli','--input',str(p)],capture_output=True,text=True);self.assertEqual(r.returncode,2)

    def test_original_simulator_seed_support_and_saved_fixtures(self):
        from planbench import simulate
        for w in json.loads(Path(__file__).resolve().parents[1].joinpath('examples/risk.json').read_text()):self.assertEqual(analyze(w['input']),w['report'])
        controls=[spec([{'id':'a','tool':'x','max_retries':1},{'id':'b','tool':'x','max_retries':1},{'id':'c','tool':'x','needs':['a','b']}]),spec([{'id':'a','tool':'x'},{'id':'b','tool':'x','needs':['a'],'duration':5}]),spec([{'id':'a','tool':'x','max_retries':2},{'id':'b','tool':'x','needs':['a']}],{'x':{'cost':2,'failure_rate':1}})]
        for s in controls:
            report=analyze(s);tools={k:{'cost':float(F(v['cost'])),'failure_rate':float(F(v['failure_rate'])),'produces':[]}for k,v in s['tools'].items()};keys={tuple((x['id'],x['status'],x['attempts'],F(x['start']),F(x['end']),F(x['cost']))for x in h['steps'])for h in report['histories']}
            for seed in range(100):
                got=simulate(s['plan'],tools,seed);by=got.by_id();key=tuple((sid,by[sid].status,by[sid].attempts,F(by[sid].start),F(by[sid].end),F(by[sid].cost))for sid in report['order']);self.assertIn(key,keys)
