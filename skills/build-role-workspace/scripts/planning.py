"""Explicit arithmetic conventions for decision drafts. Synthetic constraints are never company policy."""
import argparse
from decimal import Decimal, ROUND_CEILING, localcontext
import json
from pathlib import Path
from reconcile import number


def bridge(items):
    """Per-product volume at budget price; price at actual quantity, including interaction."""
    if not items:raise ValueError('Non-empty comparable product population required')
    seen=set();rows=[]
    with localcontext() as ctx:
        ctx.prec=50
        for item in items:
            if not item.get('id') or item['id'] in seen:raise ValueError('Unique product IDs required')
            seen.add(item['id'])
            bq,bp,aq,ap=[number(item.get(k)) for k in ['budget_quantity','budget_price','actual_quantity','actual_price']]
            delta=aq*ap-bq*bp;volume=(aq-bq)*bp;price=aq*(ap-bp)
            rows.append(dict(id=item['id'],delta=str(delta),volume=str(volume),price=str(price)))
        totals={k:sum((number(r[k]) for r in rows),Decimal(0)) for k in ['delta','volume','price']}
    return dict(**{k:str(v) for k,v in totals.items()},rows=rows,reconciled=totals['delta']==totals['volume']+totals['price'],
                convention='Per-product two-factor bridge; volume includes mix. No separate mix or causal attribution. Same currency/unit/comparable period required upstream.')


def inventory(data):
    required=['demand','buffer','on_hand','inbound','commitments','reservations_already_deducted',
              'lead_days','horizon_days','daily_demand','moq','multiple','unit_cost','budget','sellable_days','unit','as_of','assumption_ref']
    missing=[k for k in required if k not in data or data[k] is None or data[k]=='']
    if missing:return dict(decision='insufficient_data',missing=missing,candidate_quantity=None)
    if not isinstance(data['reservations_already_deducted'],bool):raise ValueError('Explicit reservation convention required')
    numeric=['demand','buffer','on_hand','commitments','lead_days','horizon_days','daily_demand','moq','multiple','unit_cost','budget','sellable_days']
    n={k:number(data[k]) for k in numeric}
    if any(v<0 for v in n.values()) or n['multiple']<=0:raise ValueError('Nonnegative values and positive order multiple required')
    if any(n[k]!=n[k].to_integral_value() for k in ['lead_days','horizon_days','sellable_days']):raise ValueError('Whole-day timeline required')
    if n['horizon_days']>3660 or n['lead_days']>3660:raise ValueError('Timeline limit exceeded')
    if n['horizon_days']<=0:raise ValueError('Positive planning horizon required')
    if n['demand']!=n['daily_demand']*n['horizon_days']:
        raise ValueError('Uniform daily demand must reconcile to the planning-period total; normalize a different demand schedule separately')
    inbound=[]
    for row in data['inbound']:
        day=number(row.get('day'));quantity=number(row.get('quantity'))
        if day<0 or quantity<0 or day!=day.to_integral_value():raise ValueError('Inbound day/quantity invalid')
        inbound.append((int(day),quantity))
    with localcontext() as ctx:
        ctx.prec=50
        eligible=sum((q for d,q in inbound if d<n['horizon_days']),Decimal(0))
        commitment=Decimal(0) if data['reservations_already_deducted'] else n['commitments']
        position=n['on_hand']+eligible-commitment
        raw=max(Decimal(0),n['demand']+n['buffer']-position)
        candidate=Decimal(0) if raw==0 else (max(raw,n['moq'])/n['multiple']).to_integral_value(rounding=ROUND_CEILING)*n['multiple']
        # The horizon is days [0,horizon_days). Receipts (including the
        # hypothetical candidate at lead_days) precede that day's demand.
        # Carry negative balances as backorders, rather than silently resetting.
        balance=n['on_hand']-commitment;shortages=[];projection=[]
        for day in range(int(n['horizon_days'])):
            confirmed=sum((q for d,q in inbound if d==day),Decimal(0))
            proposed=candidate if day==n['lead_days'] else Decimal(0)
            opening=balance
            balance+=confirmed+proposed-n['daily_demand']
            projection.append(dict(day=day,opening_balance=str(opening),confirmed_receipts=str(confirmed),
                                   hypothetical_candidate_receipt=str(proposed),demand=str(n['daily_demand']),closing_balance=str(balance)))
            if balance<0:shortages.append(dict(day=day,shortfall=str(-balance)))
        prearrival=[row for row in shortages if row['day']<n['lead_days']]
        failures=[]
        if candidate*n['unit_cost']>n['budget']:failures.append('budget')
        if candidate>0 and n['lead_days']>=n['horizon_days']:failures.append('late_candidate_arrival')
        # Simplified conservative scenario; expiry is remaining sellable days after receipt.
        if candidate>0 and (n['daily_demand']==0 or candidate>n['daily_demand']*n['sellable_days']):failures.append('sellable_life')
    return dict(position=str(position),raw_gap=str(raw),candidate_quantity=str(candidate),
                prearrival_shortages=prearrival,planning_shortages=shortages,daily_projection=projection,
                candidate_arrival_day=int(n['lead_days']),candidate_timing_feasible=not bool(shortages),
                candidate_quantity_basis='Rounded net gap for the whole period, not an optimized time-feasible procurement schedule',horizon_convention='days 0 through horizon_days-1; receipts before demand; negative balance is backlog',
                constraint_failures=failures,
                decision='needs_review' if failures or shortages else 'draft_only',
                assumptions=dict(unit=data['unit'],as_of=data['as_of'],reference=data['assumption_ref'],daily_demand=str(n['daily_demand'])),
                limitation='Arithmetic scenario only. Demand/buffer must already share unit/period; inbound must be confirmed and quality-released by date. Daily shortages are scenario projections with an unapproved candidate receipt, not observed stockouts or a feasible ordering schedule. No forecast, lot FEFO, warehouse-capacity optimization or order submission.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['bridge','inventory']);p.add_argument('input');a=p.parse_args()
    try:print(json.dumps(globals()[a.command](json.loads(Path(a.input).read_text())),ensure_ascii=False,indent=2))
    except (ValueError,OSError,TypeError,KeyError) as error:p.exit(2,str(error)+'\n')
