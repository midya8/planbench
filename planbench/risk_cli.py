"""Strict bounded JSON CLI, separate from the unchanged seeded simulator."""
import argparse,json,sys
from .risk import analyze


def parse(text):
    if len(text.encode('utf-8'))>131072:raise ValueError('input exceeds128KiB')
    def pairs(rows):
        out={}
        for k,v in rows:
            if k in out:raise ValueError('duplicate JSON key')
            out[k]=v
        return out
    def bad(x):raise ValueError('integer or rational string required')
    try:return json.loads(text,object_pairs_hook=pairs,parse_float=bad,parse_constant=bad)
    except (RecursionError,json.JSONDecodeError)as e:raise ValueError('invalid JSON')from e


def main(argv=None):
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);a=p.parse_args(argv)
    try:
        with open(a.input,encoding='utf-8')as f:text=f.read(131073)
        print(json.dumps(analyze(parse(text)),indent=2));return 0
    except (ValueError,TypeError,KeyError,OSError)as e:print('error: '+str(e),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
