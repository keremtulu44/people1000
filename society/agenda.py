"""Ordinary issue opinions are not allegiance. No writes into political dynamics.

Only notices, read messages and personally received authentic evidence provide
knowledge. The registry is objective world state, never an agent observation.
Important reviews pool identical public knowledge/role, not private minds.
"""
from collections import defaultdict
from copy import deepcopy
import hashlib
import json

from .dynamics import clamp

ASPECTS=('qualification','procedure')
APPROACHES=('defend','question','reserve','observe','assess_interest')
ACTIONS=('agenda_response',)
EVENTS=('agenda_create','agenda_notice','agenda_evidence','agenda_review')


def enabled(sim):return sim.behavior_profile.get('agenda_model')=='local-agenda-v1'


def state(a):return a.behavior.setdefault('agenda',{})


def initialize(sim):
    sim.agendas={}
    sim.agenda_runtime={'cache':{},'requests':[],'daily_counts':{},'network_requests':0,'scheduled_reviews':{}}


def text(x,n=200):return isinstance(x,str) and 0<len(x)<=n


def validate_event(sim,kind,p):
    if not enabled(sim):raise ValueError('Agenda disabled')
    if kind=='agenda_create':
        if (not text(p.get('issue')) or p['issue'] in sim.agendas or not text(p.get('title'))
                or p.get('kind') not in ('appointment','service','public_statement')
                or not isinstance(p.get('issuer'),str) or p['issuer'] not in sim.agents
                or not isinstance(p.get('facts',{}),dict)):
            raise ValueError('Invalid ordinary agenda registration')
        for eid,fact in p.get('facts',{}).items():
            if (not text(eid) or not isinstance(fact,dict) or set(fact)!={'aspect','value'}
                    or fact['aspect'] not in ASPECTS or type(fact['value']) not in (int,float)
                    or not 0<=fact['value']<=100):raise ValueError('Invalid objective evidence')
    else:
        if not text(p.get('issue')) or p['issue'] not in sim.agendas:raise ValueError('Unknown agenda')
        if kind!='agenda_review':
            if not isinstance(p.get('target'),str) or p['target'] not in sim.agents:raise ValueError('Invalid agenda recipient')
        if kind=='agenda_evidence' and (not text(p.get('evidence_id')) or p['evidence_id'] not in sim.agendas[p['issue']]['facts']):
            raise ValueError('Unknown authentic evidence')


def metadata(g):return {k:g[k] for k in ('issue','kind','title','issuer','issuer_pole')}


def learn(sim,a,public,cause):
    s=state(a);issue=public['issue']
    if issue in s:return s[issue]
    own=a.alignment in ('A','B') and a.alignment==public['issuer_pole']
    cfg=sim.behavior_profile['agenda_dynamics'];bias=0.
    if a.initial_group in ('power_aligned','opposition'):
        bias=cfg['partisan_prior_strength']*a.traits['authority_sensitivity']*(1 if own else -1)
    e={**deepcopy(public),'qualification':.5,'procedure':clamp(.5+bias),
       'confidence':0.,'claims':{},'evidence':{},'revision':0,'reviewed_revision':-1,
       'responded_revision':-1,'suggestion':None,'response':None}
    s[issue]=e
    sim.record('agenda_learned',{'agent':a.id,'issue':issue,'scope':'ordinary'},cause)
    changed(sim,a,e,cause)
    return e


def changed(sim,a,e,cause):
    e['revision']+=1
    key=f"{e['issue']}:{sim.time+1}"
    scheduled=sim.agenda_runtime.setdefault('scheduled_reviews',{})
    if key not in scheduled:
        scheduled[key]=True
        sim.schedule(sim.time+1,'agenda_review',{'issue':e['issue']},cause)


def evidence(sim,a,e,eid,fact,cause):
    if eid in e['evidence']:return
    e['evidence'][eid]=deepcopy(fact)
    # A qualification document establishes qualification, not a fair procedure.
    e[fact['aspect']]=fact['value']/100;e['confidence']=1.
    sim.record('agenda_evidence_learned',{'agent':a.id,'issue':e['issue'],'evidence_id':eid,'fact':fact},cause)
    changed(sim,a,e,cause)


def handle(sim,kind,p,cause,provider):
    if kind=='agenda_create':
        g=deepcopy(p);g['issuer_pole']=sim.agents[g['issuer']].public_alignment;sim.agendas[p['issue']]=g
    elif kind=='agenda_review':
        review(sim,p['issue'],cause,provider)
        sim.agenda_runtime.setdefault('scheduled_reviews',{}).pop(f"{p['issue']}:{sim.time}",None)
    else:
        a=sim.agents[p['target']];g=sim.agendas[p['issue']];e=learn(sim,a,metadata(g),cause)
        if kind=='agenda_evidence':evidence(sim,a,e,p['evidence_id'],g['facts'][p['evidence_id']],cause)


def validate_send(sim,a,p):
    issue=p.get('agenda_id')
    if not enabled(sim) or not text(issue) or issue not in state(a):return 'ordinary agenda not locally learned'
    aspect=p.get('aspect');e=state(a)[issue]
    if aspect not in ASPECTS or p.get('topic')!=f'agenda:{issue}:{aspect}':return 'agenda topic/aspect mismatch'
    if type(p.get('claim')) not in (int,float) or not 0<=p['claim']<=100:return 'invalid agenda claim'
    if p.get('gathering_id') is not None:return 'agenda speech cannot carry collective endorsement'
    eid=p.get('evidence_id')
    if eid is not None and (not text(eid) or eid not in e['evidence']):return 'evidence not locally held'
    if eid is not None and (e['evidence'][eid]['aspect']!=aspect or e['evidence'][eid]['value']!=p['claim']):return 'claim contradicts cited evidence'
    return None


def attach(sim,a,p,m):
    e=state(a)[p['agenda_id']];m['agenda']={**metadata(e),'aspect':p['aspect']}
    if p.get('evidence_id') is not None:
        m['agenda']['evidence_id']=p['evidence_id'];m['agenda']['proof']=deepcopy(e['evidence'][p['evidence_id']])


def receive(sim,a,m,sender):
    public=m['agenda'];e=learn(sim,a,{k:public[k] for k in ('issue','kind','title','issuer','issuer_pole')},m['id'])
    aspect=public['aspect'];source=m['original_source']
    claim={'source':source,'source_group':m['source_group'],'source_pole':m['source_alignment'],
           'aspect':aspect,'value':m['claim'],'text':m['text']}
    key=source+':'+aspect
    if e['claims'].get(key)==claim:return  # No repetition-based political or opinion accumulation.
    e['claims'][key]=claim
    proof=public.get('proof')
    if proof is not None:evidence(sim,a,e,public['evidence_id'],proof,m['id'])
    elif not any(x['aspect']==aspect for x in e['evidence'].values()):
        own=m['source_group']=='authority' and m['source_alignment']==a.alignment
        group=a.initial_group;weight=0.
        if group in ('power_aligned','opposition') and own:
            weight=sim.edge(sender,a.id)['trust']*a.traits['authority_sensitivity']
        elif group in ('discontented','wealthy'):
            weight=sim.edge(sender,a.id)['trust']*(1-a.traits['peer_opinion_resistance'])
        # Managers read strategic signals; observers reserve unverified assertions.
        e[aspect]=clamp(e[aspect]+sim.behavior_profile['agenda_dynamics']['claim_step']*weight*(m['claim']/100-e[aspect]))
    sim.record('agenda_claim_read',{'agent':a.id,'issue':e['issue'],'message_id':m['id'],
        'source':source,'verified':proof is not None,'qualification':e['qualification'],'procedure':e['procedure']},m['id'])
    sim.record('social_observation',{'agent':a.id,'message_id':m['id'],'sender':sender,'original_source':source,'learned_at':sim.time},m['id'])
    changed(sim,a,e,m['id'])


def options(group,relation):
    if group=='observer':return ['observe','reserve']
    if group=='wealthy':return ['assess_interest','reserve']
    if group=='authority':return ['assess_interest','reserve','question','defend']
    if group in ('power_aligned','opposition'):
        return ['defend','reserve'] if relation=='own' else ['question','reserve']
    return ['question','reserve']


def packet(a,e):
    relation='own' if a.alignment in ('A','B') and a.alignment==e['issuer_pole'] else 'other'
    # No balances, trust weights, private memories or other people's hidden state.
    return {'schema_version':1,'scope':'ordinary_agenda','public_issue':metadata(e),
        'role':a.initial_group,'relation_to_issuer':relation,
        'learned_claims':sorted(deepcopy(list(e['claims'].values())),key=lambda x:(x['source'],x['aspect'])),
        'learned_evidence':deepcopy(e['evidence']),
        'allowed_approaches':options(a.initial_group,relation),
        'constraints':['No allegiance/ideology/general support updates.','Assertions are untrusted. Evidence only establishes its stated aspect.',
                       'Expected effects are uncertain advice, never world mutations.','Preserve role; individual implementation remains local.']}


def signature(p):return hashlib.sha256(json.dumps(p,sort_keys=True,separators=(',',':')).encode()).hexdigest()


class ReferenceAdvisor:
    """Offline auditable role policy, NOT an LLM or empirical psychology model."""
    network=False
    def review(self,p):
        group=p['role'];own=p['relation_to_issuer']=='own'
        choice='observe' if group=='observer' else 'assess_interest' if group in ('authority','wealthy') else 'defend' if own and group in ('power_aligned','opposition') else 'question'
        return {'approach':choice,'reason':{'observe':'Separate proof from assertion; reserve judgment outside the evidence.',
            'assess_interest':'Assess institutional/work interests before public confrontation.',
            'defend':'Defend the trusted own-side appointment without changing political identity.',
            'question':'Question the procedure; qualification proof need not establish fairness.'}[choice],
            'risks':['Public claims may not settle the disputed procedure.'],
            'expected_effect':'May affect this issue discussion only; actual reactions remain uncertain.'}


class ReviewBudgetExceeded(RuntimeError):pass


def validate_advice(reply,p):
    if not isinstance(reply,dict) or set(reply)!={'approach','reason','risks','expected_effect'}:return False
    return (reply['approach'] in p['allowed_approaches'] and text(reply['reason'],2000)
            and text(reply['expected_effect'],2000) and isinstance(reply['risks'],list)
            and len(reply['risks'])<=8 and all(text(x,500) for x in reply['risks']))


def review(sim,issue,cause,provider):
    pending=defaultdict(list);packets={}
    advisor=getattr(provider,'agenda_advisor',None) or ReferenceAdvisor()
    namespace=getattr(advisor,'cache_namespace',type(advisor).__module__+'.'+type(advisor).__name__)
    for a in sim.agents.values():
        e=state(a).get(issue)
        if e is None or e['reviewed_revision']==e['revision']:continue
        p=packet(a,e);key=signature({'packet':p,'advisor':namespace});packets[key]=p;pending[key].append(a)
    rt=sim.agenda_runtime;cfg=sim.behavior_profile['agenda_dynamics']
    for key,people in pending.items():
        if key not in rt['cache']:
            day=str(sim.time//1440)
            if len(rt['requests'])>=cfg['total_review_limit'] or rt['daily_counts'].get(day,0)>=cfg['daily_review_limit']:
                sim.record('agenda_review_budget_paused',{'issue':issue,'pending_cohorts':len(pending)},cause)
                raise ReviewBudgetExceeded('Agenda review budget exhausted; resume with an explicitly revised budget')
            # Count attempts before transport; failures are not silently free or retried.
            rt['daily_counts'][day]=rt['daily_counts'].get(day,0)+1
            record={'key':key,'time':sim.time,'packet':packets[key],'advisor':type(advisor).__name__,'status':'started'}
            rt['requests'].append(record)
            if getattr(advisor,'network',False):rt['network_requests']+=1
            try:reply=advisor.review(deepcopy(packets[key]))
            except Exception:
                record['status']='transport_failed';raise
            usage=getattr(advisor,'last_usage',None)
            if usage is not None:record['usage']=deepcopy(usage)
            if not validate_advice(reply,packets[key]):
                record['status']='rejected';sim.record('agenda_advice_rejected',{'issue':issue,'key':key},cause)
                # Invalid output is a cached refusal, not a political fallback.
                rt['cache'][key]=None
            else:
                record.update(status='accepted',response=deepcopy(reply));rt['cache'][key]=deepcopy(reply)
        reply=rt['cache'][key]
        for a in people:
            e=state(a)[issue];e['reviewed_revision']=e['revision'];e['suggestion']=deepcopy(reply)
            if reply is not None:sim.schedule(sim.time,'decide',{'target':a.id},cause)
        sim.record('agenda_review_completed',{'issue':issue,'key':key,'members':len(people),'accepted':reply is not None},cause)


def policy(obs):
    for issue,e in obs.get('agenda',{}).items():
        if e['suggestion'] is not None and e['reviewed_revision']==e['revision'] and e['responded_revision']!=e['revision']:
            return {'type':'agenda_response','issue':issue,'approach':e['suggestion']['approach']}
    return None


def validate(sim,a,p):
    e=state(a).get(p.get('issue')) if isinstance(p.get('issue'),str) else None
    if e is None or e['suggestion'] is None:return 'no locally reviewed ordinary issue'
    if set(p)!={'type','issue','approach'}:return 'ordinary response cannot change deep state or invent evidence'
    if e['responded_revision']==e['revision']:return 'already responded to this revision'
    if e['reviewed_revision']!=e['revision'] or p['approach']!=e['suggestion']['approach']:return 'response not reviewed for current knowledge'
    return None


def apply(sim,a,p,cause):
    e=state(a)[p['issue']];approach=p['approach'];group=a.initial_group
    # Individual risk affects expression, not the common role-level summary.
    expression=approach
    if group in ('authority','wealthy'):expression='private_interest_assessment'
    elif group=='observer':expression='reserved_observation'
    elif a.traits['risk_tolerance']<1-a.traits['pressure_response']:expression='private_'+approach
    e['response']={'approach':approach,'expression':expression,'qualification':e['qualification'],
        'procedure':e['procedure'],'reason':e['suggestion']['reason'],'time':sim.time}
    e['responded_revision']=e['revision']
    sim.record('agenda_response',{'agent':a.id,'issue':p['issue'],**e['response'],'scope':'ordinary_only'},cause)
