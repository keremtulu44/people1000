"""v3.2 character-local decisions. Assumptions, not empirical psychology laws.

Speech is not an institutional gain. Seeing someone is not endorsing their group.
Temporal reactions use only own expenses, income and direct local disruptions.
"""
from copy import deepcopy
import hashlib
import math

from .dynamics import clamp

ACTIONS=('self_study','compete_position')


def enabled(sim):return sim.behavior_profile.get('character_model')=='local-v1'


def state(a):
    return a.behavior.setdefault('character',{'domains':{},'signals':{},'grievances':{},
        'development':0.,'last_study_day':-1,'source_assessments':{},'verified_failures':[],
        'verified_recoveries':[],'material_stress':False,'financials':{},'decision_reason':'not_evaluated',
        'last_competition_day':-10000,'rival_actions':{},'last_gathering_day':-10000,
        'last_grievance_day':-1,'invited':{},'checked_messages':[],'last_physical_harm':0.})


def prepare_network(sim):
    # Bound initial inward/outward contact without extra RNG draws to other groups.
    cfg=sim.behavior_profile['character_dynamics'];counts={}
    kept=[]
    for e in sim.edges:
        if sim.agents[e['target']].initial_group=='observer':
            if counts.get(e['target'],0)>=cfg['observer_incoming_limit']:continue
            counts[e['target']]=counts.get(e['target'],0)+1
        kept.append(e)
    sim.edges=kept


def initialize(sim):
    for a in sim.agents.values():
        s=state(a)
        if a.initial_group=='observer':
            value=int(hashlib.sha256(f'{sim.config.seed}:{a.id}:development'.encode()).hexdigest()[:12],16)/(16**12-1)
            s['development']=value


def limit(sim,a,kind,default):
    if not enabled(sim) or a.initial_group!='observer':return default
    return min(default,sim.behavior_profile['character_dynamics'][f'observer_{kind}_limit'])


def receive(sim,a,m,sender):
    s=state(a);b=a.behavior;source=m['original_source'];edge=sim.edge(sender,a.id)
    evidence={'source':source,'group':m['source_group'],'source_pole':m['source_alignment'],
        'topic':m['topic'],'claim':m['claim'],'message_id':m['id'],'learned_at':sim.time,
        'channel_trust':edge['trust']}
    if m['topic']=='grievance' and m['claim'] is not None:
        s['grievances'][source]=evidence
    if a.initial_group not in ('authority','observer'):return False
    # Awareness of public identity is not adoption of a political claim.
    b['known'][source]={'pole':m['source_alignment'],'group':m['source_group'],'trust':edge['trust']}
    if m['source_group']=='authority':b['trust'].setdefault(source,edge['trust'])
    s['signals'][source+':'+m['topic']]=evidence
    sim.record('strategic_signal_observed' if a.initial_group=='authority' else 'claim_reserved_for_study',
               {'agent':a.id,'evidence':evidence,'adopted_as_truth':False},m['id'])
    sim.record('social_observation',{'agent':a.id,'message_id':m['id'],'sender':sender,
               'original_source':source,'learned_at':sim.time},m['id'])
    return True


def disruption(sim,a,domain,severity,cause):
    d=state(a)['domains'].setdefault(domain,{'expected':0.,'fatigue':0.,'level':0.,'updated_day':None})
    d['level']=severity
    d['surprise']=max(0.,severity-d['expected'])
    d['reaction']=clamp(d['surprise']+d['fatigue'])
    state(a)['reaction']=1-math.prod(1-x.get('reaction',0.) for x in state(a)['domains'].values())
    a.behavior['social']['distress']=state(a)['reaction']
    a.memories.append({'type':'direct_experience','event_id':cause,'learned_at':sim.time,
                       'domain':domain,'severity':severity})
    sim.record('local_disruption_experienced',{'agent':a.id,'domain':domain,'severity':severity},cause)


def temporal(sim,a,expense,income_harm,cause):
    s=state(a);cfg=sim.behavior_profile['character_dynamics'];day=sim.time//1440
    levels={'living_cost':clamp(max(0.,expense-a.expense)/max(1.,a.expense)),
            'income_security':clamp(income_harm)}
    for key,value in levels.items():
        s['domains'].setdefault(key,{'expected':0.,'fatigue':0.,'level':0.,'updated_day':None})['level']=value
    for key,d in s['domains'].items():
        if d['updated_day']==day:continue
        old=d['expected'];surprise=max(0.,d['level']-old)
        d['fatigue']+=(d['level']-d['fatigue'])/cfg['fatigue_days']
        d['expected']+=(d['level']-old)/cfg['adaptation_days']
        d.update(surprise=surprise,reaction=clamp(surprise+d['fatigue']),updated_day=day)
    reaction=1-math.prod(1-d.get('reaction',0.) for d in s['domains'].values())
    s['financials']={'expense':expense,'income':a.income,'savings':a.savings}
    s['material_stress']=income_harm>0 or expense>a.income
    s['reaction']=clamp(reaction)
    sim.record('temporal_appraisal',{'agent':a.id,'domains':deepcopy(s['domains']),
        'reaction':s['reaction'],'material_stress':s['material_stress']},cause)
    return s['reaction']


def track_trust(a,changes):
    s=state(a)
    for x in changes:
        if a.behavior['known'].get(x['source'],{}).get('pole')!=a.alignment:continue
        key='verified_failures' if x['new']<x['old'] else 'verified_recoveries'
        actual_recovery=a.behavior['harm']<s['last_physical_harm']
        if x['new']!=x['old'] and (key=='verified_failures' or actual_recovery) and x['message_id'] not in s[key]:
            s[key].append(x['message_id'])
    s['last_physical_harm']=a.behavior['harm']


def validate(sim,a,p):
    if p['type']=='self_study':
        if a.initial_group!='observer':return 'self-study policy is observer-specific'
        if state(a)['last_study_day']==sim.time//1440:return 'already studied today'
    else:
        target=p.get('target')
        if a.initial_group!='authority':return 'institutional competition requires authority'
        if not isinstance(target,str) or target==a.id or a.behavior['known'].get(target,{}).get('group')!='authority':
            return 'rival must be locally known authority'
        if target not in sim.authorities:return 'unknown institution'
        cfg=sim.behavior_profile['character_dynamics']
        if sim.time//1440-state(a)['last_competition_day']<cfg['competition_cooldown_days']:return 'competition cooldown'
        if a.savings<cfg['competition_cost']:return 'insufficient institutional resources'
        if sim.authorities[target]['institutional_power']<=0:return 'no rival position to contest'
    return None


def apply(sim,a,p,cause):
    s=state(a);cfg=sim.behavior_profile['character_dynamics']
    if p['type']=='self_study':
        old=s['development'];s['development']+=cfg['study_step']*(1-old);s['last_study_day']=sim.time//1440
        # Only falsifiable, later personal outcomes can verify forecast statements.
        # Other propositions stay unresolved; self-study is not access to truth.
        for e in s['signals'].values():
            if e['topic']!='economic_outlook' or e['claim'] is None or e['message_id'] in s['checked_messages']:continue
            outcomes=[m for m in a.memories if m.get('type')=='direct_experience' and 'expense' in m
                      and e['learned_at']<m['learned_at']<=sim.time]
            if not outcomes or sim.time-e['learned_at']>sim.behavior_profile['dynamics']['forecast_days']*1440:continue
            outcome=outcomes[-1]
            harm=clamp(max(0.,outcome['expense']-a.expense)/max(1.,a.expense)+
                       max(0.,a.behavior['reference_income']-outcome['income'])/max(1.,a.behavior['reference_income']))
            error=clamp(abs(e['claim']/100-harm))
            s['checked_messages'].append(e['message_id'])
            s['source_assessments'][e['source']]={'error':error,'evidence':e['message_id'],
                'development_used':s['development'],'confidence':s['development']*(1-error),
                'outcome_observed_at':outcome['learned_at'],'type':'personal_forecast_check'}
        sim.record('self_development',{'agent':a.id,'old':old,'new':s['development'],
            'checked_sources':deepcopy(s['source_assessments'])},cause)
    else:
        rival=sim.agents[p['target']];cost=cfg['competition_cost']
        amount=min(cfg['competition_transfer'],sim.authorities[rival.id]['institutional_power'])
        a.savings-=cost
        sim.authorities[a.id]['institutional_power']+=amount
        sim.authorities[rival.id]['institutional_power']-=amount
        s['last_competition_day']=sim.time//1440
        # Both participants directly observe the material contest, not private balances.
        for person in (a,rival):
            other=rival if person.id==a.id else a
            state(person)['rival_actions'][other.id]={'event_id':cause,'time':sim.time,
                'own_power':sim.authorities[person.id]['institutional_power'],'transfer':amount,
                'role':'initiator' if person.id==a.id else 'challenged'}
            person.memories.append({'type':'direct_experience','event_id':cause,'learned_at':sim.time,
                'actor':other.id,'institutional_transfer':amount})
        # The observed challenger becomes locally known by the signed contest.
        rival.behavior['known'][a.id]={'pole':a.public_alignment,'group':'authority','trust':0.}
        sim.record('institutional_competition',{'actor':a.id,'target':rival.id,'cost':cost,
            'transfer':amount,'actor_power':sim.authorities[a.id]['institutional_power'],
            'target_power':sim.authorities[rival.id]['institutional_power'],'party_change':False},cause)


def policy(obs):
    """Role-specific action selection. Always return an auditable reason."""
    if 'character' not in obs:return None,None
    s=obs['character'];day=obs['time']//1440;cfg=obs['character_config'];group=obs['group']
    if group=='observer':
        if s['last_study_day']!=day:return {'type':'self_study'},'self_development'
        return {'type':'wait'},'inward_focus_already_studied'
    if group=='authority':
        for rival,x in s['rival_actions'].items():
            if x['role']=='challenged' and obs.get('institutional_position',1.)<1 and day-s['last_competition_day']>=cfg['competition_cooldown_days']:
                reserve=obs['traits']['risk_tolerance']*obs['savings']
                if reserve>=cfg['competition_cost'] and obs['savings']-cfg['competition_cost']>=s['financials'].get('expense',0.):
                    return {'type':'compete_position','target':rival},'defend_observed_institutional_position'
        for gid,g in obs['social']['known_gatherings'].items():
            if g['organizer']==obs['agent_id'] and g['start']<=obs['time']<g['end'] and obs['social']['present_at'] is None:
                return {'type':'attend_gathering','gathering_id':gid,'participation':'support'},'lead_own_registered_event'
        # Heterogeneous aspiration uses existing risk preferences, not statements.
        # Public identity/contact trust ranks locally known institutional rivals;
        # their current power and private resources are not visible to the policy.
        goal=1+cfg['institutional_ambition_scale']*obs['traits']['risk_tolerance']
        affordable=(obs['traits']['risk_tolerance']*obs['savings']>=cfg['competition_cost'] and
                    obs['savings']-cfg['competition_cost']>=s['financials'].get('expense',0.))
        if (obs.get('institutional_position',1.)<goal and affordable and
                day-s['last_competition_day']>=cfg['competition_cooldown_days']):
            rivals=[(source,x) for source,x in obs['behavior']['known'].items()
                    if source!=obs['agent_id'] and x['group']=='authority']
            if rivals:
                rival=min(rivals,key=lambda item:(item[1]['pole']==obs['alignment'],item[1]['trust'],item[0]))[0]
                return {'type':'compete_position','target':rival},'pursue_local_institutional_aspiration'
        return {'type':'wait'},'no_affordable_material_rivalry' if s['rival_actions'] else 'no_affordable_local_opportunity'
    if obs['public_support']>0 and obs['private_loyalty']<.5 and s['verified_failures']:
        return {'type':'withdraw_support'},'withdraw_after_personally_failed_forecast'
    # Restore only after a personally checked recovery, not because of crowd size.
    if obs['public_support']==0 and obs['private_loyalty']>=.5 and s['verified_recoveries'] and obs['alignment'] in ('A','B'):
        return {'type':'declare_support','value':obs['private_loyalty']},'support_recovery_from_personal_evidence'
    from . import collective
    for gid,g in obs['social']['known_gatherings'].items():
        if g['organizer']==obs['agent_id'] and obs['time']<g['start']:
            sent=s['invited'].get(gid,[])
            for target in obs['contacts']:
                if target not in sent:
                    if obs['budgets_used']['communication']>=obs['budget_limits']['communication']:
                        return {'type':'wait'},'communication_budget_exhausted'
                    return {'type':'send','target':target,'text':'Invitation, not a promised crowd','gathering_id':gid},'invite_local_contact'
    proposal=collective.policy(obs)
    if proposal is not None:
        if proposal['type']=='attend_gathering':proposal['participation']='support'
        return proposal,'support_withdrawal' if proposal['type']=='withdraw_support' else 'locally_supported_attendance'
    if group=='discontented' and obs['social']['distress']>0:
        own_future=any(g['organizer']==obs['agent_id'] and obs['time']<g['end'] for g in obs['social']['known_gatherings'].values())
        peers=[e for source,e in s['grievances'].items() if source!=obs['agent_id'] and e['claim']>0 and obs['time']-e['learned_at']<=7*1440]
        readiness=obs['social']['distress']*obs['traits']['risk_tolerance']
        if peers:readiness+=max(e['channel_trust']*(1-obs['traits']['peer_opinion_resistance']) for e in peers)
        if peers and not own_future and day-s['last_gathering_day']>=cfg['gathering_cooldown_days'] and readiness>1-obs['traits']['risk_tolerance']:
            start=(day+1)*1440+60
            return {'type':'create_gathering','place':'local:'+obs['agent_id'],'start':start,'end':start+120,'purpose':'local-material-distress'},'seek_actual_gathering_after_local_grievance'
        if s['last_grievance_day']!=day and obs['contacts']:
            if obs['budgets_used']['communication']>=obs['budget_limits']['communication']:
                return {'type':'wait'},'communication_budget_exhausted'
            return {'type':'send','target':obs['contacts'][0],'topic':'grievance','claim':100*obs['social']['distress'],
                    'text':'Personal distress; not a claim of actual attendance'},'seek_local_support'
        if not peers:return None,'no_read_local_support'
        if readiness<=1-obs['traits']['risk_tolerance']:return None,'risk_exceeds_local_readiness'
        if own_future:return None,'known_future_gathering'
        return None,'organizing_cooldown'
    if obs['social']['distress']==0:return None,'no_current_personal_distress'
    if obs['social']['present_at'] is not None:return None,'already_participating'
    if not obs['social']['known_gatherings']:return None,'no_known_gathering'
    return None,'no_acceptable_invitation_or_readiness'
