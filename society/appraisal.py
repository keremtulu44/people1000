"""Local causal attribution and incremental policy benefits (model v3).

No global prices, actual ruling pole, hidden actor states or topology queries.
Messages are testimony, not facts. Direct signed contract notices are experience.
"""
from .dynamics import clamp

ISSUES = ('economic_security', 'status', 'order')


def enabled(sim):
    return sim.behavior_profile.get('decision_model', 'legacy-v2') == 'attributed-v1'


def state(a):
    return a.behavior.setdefault('appraisal', {
        'responsibility_sources': {}, 'benefit_sources': {},
        'responsibility': {'unknown': 1.}, 'burden_by_pole': {'A': 0., 'B': 0.},
        'unassigned_burden': 0., 'external_burden': 0.,
        'known_alternatives': sorted({v['pole'] for v in a.behavior['known'].values() if v['pole'] in ('A','B')}),
    })


def credibility(a, evidence):
    if evidence.get('direct'):
        return 1.
    if evidence['group'] == 'authority':
        trust = a.behavior['trust'].get(evidence['source'], evidence['channel_trust'])
        return clamp(trust * a.traits['authority_sensitivity'])
    return clamp(evidence['channel_trust'] * (1-a.traits['peer_opinion_resistance']))


def receive(sim, a, m, sender):
    """Called only on read. Same-author repetitions replace, never compound."""
    topic=m['topic']
    if not (topic.startswith('responsibility:') or topic.startswith('benefit:') or topic.startswith('alternative_known:')):
        return False
    s=state(a)
    if topic in ('alternative_known:A','alternative_known:B'):
        pole=topic.split(':')[1]
        s.setdefault('known_alternatives',[])
        if pole not in s['known_alternatives']:
            s['known_alternatives'].append(pole);s['known_alternatives'].sort()
        return True
    if m['claim'] is None:
        return True
    group=sim.behavior_profile['groups'][a.initial_group]
    if group['requires_aligned_authority'] and (m['source_group']!='authority' or m['source_alignment']!=a.alignment):
        return True
    if sim.config.ablation=='peer' and m['source_group']!='authority':
        return True
    channel=sim.edge(sender,a.id)
    evidence={'source':m['original_source'],'group':m['source_group'],
        'channel_trust':channel['trust'],'message_id':m['id'],'learned_at':sim.time,
        'source_pole':m['source_alignment'],'claim':m['claim']/100}
    if topic.startswith('responsibility:'):
        target=topic[len('responsibility:'):]
        if target not in ('A','B','external','unknown'):
            if not target.startswith('leader:') or a.behavior['known'].get(target[7:],{}).get('group')!='authority':
                return True
        evidence['target']=target
        s['responsibility_sources'][evidence['source']]=evidence
    else:
        parts=topic.split(':')
        if len(parts)!=3 or parts[1] not in ('A','B') or parts[2] not in ISSUES:
            return True
        if parts[1] not in s['known_alternatives']:
            s['known_alternatives'].append(parts[1]);s['known_alternatives'].sort()
        evidence.update(pole=parts[1],issue=parts[2])
        key=':'.join((evidence['source'],parts[1],parts[2]))
        s['benefit_sources'][key]=evidence
    sim.record('appraisal_evidence_learned',{'agent':a.id,'topic':topic,'evidence':evidence},m['id'])
    return True


def direct_notice(sim,a,actor,public_pole,loss,cause):
    """Explicit issuer on the agent's own signed revocation notice, not omniscience."""
    s=state(a)
    a.behavior['known'][actor]={'pole':public_pole,'group':'authority','trust':1.}
    s['responsibility_sources']['notice:'+actor]={'source':actor,'target':'leader:'+actor,
        'direct':True,'scope':'income','claim':1.,'learned_at':sim.time,'event_id':cause,'income_loss':loss}
    sim.record('responsibility_direct_experience',{'agent':a.id,'actor':actor,
        'perceived_public_pole':public_pole,'income_loss':loss},cause)


def assess(sim,a,cause,expense_harm=1.,income_harm=0.):
    s=state(a)
    records=list(s['responsibility_sources'].values())
    def distribution(records):
        if not records:
            return {'unknown':1.}
        result={}
        for e in records:
            support=credibility(a,e)*e['claim']
            result[e['target']]=result.get(e['target'],0.)+support/len(records)
            result['unknown']=result.get('unknown',0.)+(1-support)/len(records)
        return result
    generic=distribution([e for e in records if not e.get('direct')])
    income_records=[e for e in records if e.get('scope')=='income']
    income=distribution(income_records) if income_records else generic
    total=expense_harm+income_harm
    price_share=expense_harm/total if total else 1.
    mass={target:price_share*generic.get(target,0.)+(1-price_share)*income.get(target,0.) for target in sorted(set(generic)|set(income))}
    shares={'A':mass.get('A',0.),'B':mass.get('B',0.)}
    for target,value in mass.items():
        if target.startswith('leader:'):
            pole=a.behavior['known'].get(target[7:],{}).get('pole')
            if pole in shares:
                shares[pole]+=value
    s['responsibility']=mass
    # Interests are relative priorities, not a new set of calibrated coefficients.
    experienced=a.beliefs.get('experienced_harm',{}).get('estimate',0.)/100
    interests={'economic_security':a.traits['economic_harm_response']*(1+experienced),
               'status':a.traits['authority_sensitivity'], 'order':a.behavior['core_orientation']}
    denominator=sum(interests.values())
    by_topic={}
    for e in s['benefit_sources'].values():
        key=(e['pole'],e['issue'])
        by_topic.setdefault(key,[]).append((credibility(a,e)*(2*e['claim']-1),e))
    utility={'A':0.,'B':0.}
    for (pole,issue),values in by_topic.items():
        estimate=sum(v for v,e in values)/len(values)
        topic=f'benefit:{pole}:{issue}'
        old=a.beliefs.get(topic,{}).get('estimate',50.)
        new=50+50*estimate
        if abs(new-old)/100 < a.traits['topic_change_threshold']:
            new=old
        utility[pole]+=(new-50)/50*interests[issue]/denominator if denominator else 0.
        a.beliefs[topic]={'estimate':new,'evidence':[e.get('message_id') for v,e in values],'updated_at':sim.time}
        if abs(new-old)>1e-12:
            sim.record('belief_updated',{'agent':a.id,'topic':topic,'old':old,'new':new,
                'evidence_ids':[e.get('message_id') for v,e in values]},cause)
    alt='B' if a.alignment=='A' else 'A'
    from . import characters
    if characters.enabled(sim) and a.alignment=='none':
        alt=max(('A','B'),key=lambda p:utility[p]) if utility['A']!=utility['B'] else None
    # Utility means expected incremental improvement over current experienced state.
    # Knowing the alternative or hearing support slogans alone gives zero utility.
    attraction=clamp(utility.get(alt,0.)-max(0.,utility.get(a.alignment,0.)))
    return {'responsibility':dict(mass), 'expense_responsibility':generic, 'income_responsibility':income,'shares_by_pole':shares,'interests':interests,
        'expected_utility':utility,'alternative':alt,'attraction':attraction,
        'benefit_evidence_ids':[e.get('message_id') for e in s['benefit_sources'].values()],
        'responsibility_evidence_ids':[e.get('message_id',e.get('event_id')) for e in records]}


def update_burdens(a,appraisal,harm,response,retention):
    s=state(a)
    for pole in ('A','B'):
        # Historical losses stay with the pole perceived responsible WHEN observed.
        s['burden_by_pole'][pole]=retention*s['burden_by_pole'][pole]+harm*response*appraisal['shares_by_pole'][pole]
    s['external_burden']=retention*s['external_burden']+harm*response*appraisal['responsibility'].get('external',0.)
    unassigned=max(0.,1-sum(appraisal['shares_by_pole'].values())-appraisal['responsibility'].get('external',0.))
    s['unassigned_burden']=retention*s['unassigned_burden']+harm*response*unassigned
