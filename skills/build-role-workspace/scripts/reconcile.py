"""Exact decimal file calculations. Explicit grain; blanks and unknown are not zero."""
import argparse
import csv
from decimal import Decimal, InvalidOperation, localcontext
import json


def number(value):
    if value is None or not str(value).strip():
        raise ValueError('Missing numeric input')
    try:
        result=Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError('Invalid numeric input') from error
    if not result.is_finite():
        raise ValueError('Non-finite numeric input')
    return result


def rows(path, required, keys):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader=csv.DictReader(f)
        headers=reader.fieldnames or []
        if any(not h.strip() for h in headers) or len(headers)!=len(set(headers)):
            raise ValueError('Blank or duplicate CSV column names')
        if not set(required).issubset(reader.fieldnames or []):
            raise ValueError('Missing required columns: '+','.join(required))
        data=list(reader)
    if not data:
        raise ValueError('Empty dataset')
    seen=set()
    for row in data:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('CSV row has more or fewer fields than its header')
        identity=tuple(row.get(k) for k in keys)
        if any(v is None or not v.strip() for v in identity) or identity in seen:
            raise ValueError('Missing or duplicate business grain: '+repr(identity))
        seen.add(identity)
    return data


def rate(n, d):
    if d == 0:
        return None
    with localcontext() as c:
        c.prec=50
        return str((n/d).quantize(Decimal('0.00000001')))


def aggregate_rates(path, numerator='conversions', denominator='clicks', key=('sku',), context=('currency','period')):
    data=rows(path,[numerator,denominator,*key,*context],key)
    for field in context:
        values={row[field] for row in data}
        if len(values)!=1 or not next(iter(values)).strip():
            raise ValueError('Mixed or missing context: '+field)
    ns=[];ds=[];items=[]
    for row in data:
        n=number(row[numerator]);d=number(row[denominator])
        if n<0 or d<0:
            raise ValueError('Negative counts require a different metric contract')
        ns.append(n);ds.append(d)
        items.append(dict(key={k:row[k] for k in key},numerator=str(n),denominator=str(d),rate=rate(n,d)))
    with localcontext() as c:
        c.prec=50;n=sum(ns,Decimal(0));d=sum(ds,Decimal(0))
    return dict(numerator=str(n),denominator=str(d),rate=rate(n,d),rows=items,
                context={k:data[0][k] for k in context},metric={'numerator':numerator,'denominator':denominator,'grain':list(key)},
                limitation='Observed aggregate only; no causal or profit conclusion')


def compare_amounts(left,right,key=('id',),amount='amount',currency='currency'):
    required=[*key,amount,currency]
    datasets=[]
    for file in [left,right]:
        dataset=rows(file,required,[*key,currency])
        datasets.append({tuple(r[k] for k in [*key,currency]):number(r[amount]) for r in dataset})
    a,b=datasets;result=[]
    for identity in sorted(set(a)|set(b)):
        x,y=a.get(identity),b.get(identity)
        status='missing_left' if x is None else 'missing_right' if y is None else 'matched' if x==y else 'difference'
        with localcontext() as c:
            c.prec=50;delta=str(x-y) if x is not None and y is not None else None
        result.append(dict(key=dict(zip([*key,currency],identity)),left=str(x) if x is not None else None,
                           right=str(y) if y is not None else None,difference=delta,status=status))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    a=s.add_parser('rate');a.add_argument('input');a.add_argument('--numerator',default='conversions');a.add_argument('--denominator',default='clicks');a.add_argument('--key',default='sku');a.add_argument('--context',default='currency,period')
    b=s.add_parser('compare');b.add_argument('left');b.add_argument('right');b.add_argument('--key',default='id');b.add_argument('--amount',default='amount');b.add_argument('--currency',default='currency')
    a=p.parse_args()
    try:
        out=aggregate_rates(a.input,a.numerator,a.denominator,tuple(a.key.split(',')),tuple(filter(None,a.context.split(',')))) if a.command=='rate' else compare_amounts(a.left,a.right,tuple(a.key.split(',')),a.amount,a.currency)
        print(json.dumps(out,ensure_ascii=False,indent=2))
    except (ValueError,OSError) as error:p.exit(2,str(error)+'\n')
