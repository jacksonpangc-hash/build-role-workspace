"""Small normalized-data checks; no inference of business keys, policies, units or joins."""
from collections import Counter
from decimal import Decimal, localcontext
from reconcile import number


def relation(left,right,key):
    """Warn before a row-expanding join; never merge amounts or guess association."""
    def counts(rows):
        values=[tuple(r.get(k) for k in key) for r in rows]
        if any(any(v is None or v=='' for v in row) for row in values):raise ValueError('Missing join key')
        return Counter(values)
    a,b=counts(left),counts(right)
    return dict(left_rows=len(left),right_rows=len(right),
                projected_inner_rows=sum(n*b.get(k,0) for k,n in a.items()),
                many_to_many=[list(k) for k in a.keys()&b.keys() if a[k]>1 and b[k]>1],
                unmatched_left=[list(k) for k in a.keys()-b.keys()],
                unmatched_right=[list(k) for k in b.keys()-a.keys()],
                action='Aggregate independently at agreed common grain or retain separate tables; projected rows are not new transactions')


def metric(numerator,denominator,kind):
    if kind not in {'share','rate','growth'}:raise ValueError('Explicit metric kind required')
    if numerator is None or denominator is None:return dict(value=None,status='missing')
    n=number(numerator);d=number(denominator)
    if d==0:return dict(value=None,status='zero_denominator')
    with localcontext() as ctx:
        ctx.prec=50;value=n/d
    if kind=='share' and not Decimal(0)<=value<=Decimal(1):return dict(value=str(value),status='invalid_share')
    return dict(value=str(value),status='calculated')


def expand_bundles(lines,recipes):
    totals={};unknown=[];seen=set()
    for line in lines:
        identity=line.get('line_id')
        if not identity or identity in seen:raise ValueError('Unique line identity required')
        seen.add(identity)
        sku=line.get('sku');quantity=line.get('quantity');recipe=recipes.get(sku)
        if quantity is None or not recipe or line.get('mapping_conflict'):
            unknown.append(identity);continue
        q=number(quantity)
        if q<0:raise ValueError('Returns require a separate disposition contract')
        for component,units in recipe.items():
            u=number(units)
            if u<=0:raise ValueError('Positive recipe quantities required')
            totals[component]=totals.get(component,Decimal(0))+q*u
    return dict(known_component_demand={k:str(v) for k,v in totals.items()},unknown_lines=unknown,
                complete=not unknown,limitation='Only actual purchased quantities. Gifts, returns and uninspected receipts separate; unknown lines never become zero demand.')
