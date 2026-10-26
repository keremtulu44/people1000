"""Declared supplementary check: execute ordinary advice, not just review it.
Main 808-run study stays frozen. No network and no coefficient modifications.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from society import agenda
from society.character_research_v33 import specs,prepared
from society.engine import Simulation

OUT=ROOT/'reports/character-research-v33'


class AgendaOnly:
    agenda_advisor=agenda.ReferenceAdvisor()
    def decide(self,obs):return agenda.policy(obs) or {'type':'wait'}


def advance(sim,until):
    p=sim.protocol['character_study'];provider=AgendaOnly()
    while p['next_input']<len(p['plan']) and p['plan'][p['next_input']]['at']<=until:
        x=p['plan'][p['next_input']];sim.run(x['at'],provider,max_events=1000000)
        if x['kind']=='action':
            did=sim.propose(x['actor'],deepcopy(x['proposal']));ok=sim.apply(did)
            p['input_outcomes'].append({'time':sim.time,'decision':did,'actor':x['actor'],'type':x['proposal']['type'],'accepted':ok})
        else:sim.schedule(sim.time,x['kind'],x['payload'])
        p['next_input']+=1
    sim.run(until,provider,max_events=1000000)


def deep(sim):
    return {a.id:(a.alignment,a.public_alignment,a.public_support,a.private_loyalty,
        a.behavior['core_orientation'],a.change_evidence,dict(a.behavior['trust'])) for a in sim.agents.values()}


def main():
    selected=('notice','claim-aligned','qualification-only','false-assertion','evidence-transmitted','late-document')
    rows=[]
    for seed in range(4):
        controlspec=next(j for j in specs() if j['section']=='agenda' and j['seed']==seed and j['case']['name']=='agenda-no-notice')
        control=prepared(controlspec)
        advance(control,30*1440-1);expected=deep(control)
        for name in selected:
            j=next(j for j in specs() if j['section']=='agenda' and j['seed']==seed and j['case']['name']=='agenda-'+name)
            sim=prepared(j);advance(sim,30*1440-1)
            responses=[e for e in sim.log if e['kind']=='agenda_response']
            assert responses and deep(sim)==expected
            assert sim.agenda_runtime['network_requests']==0
            rows.append({'case':j['case']['name'],'seed':seed,'responses_applied':len(responses),
                'review_attempts':len(sim.agenda_runtime['requests']),'network_attempts':0,
                'deep_state_matches_untreated':True,'input_refusals':sum(not x['accepted'] for x in sim.protocol['character_study']['input_outcomes']),
                'responses':[{'time':e['time'],**e['payload']} for e in responses]})
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'agenda-execution-followup.json').write_text(json.dumps({'description':'Supplementary execution check declared after main study was frozen: AgendaOnly executes advice; unrelated autonomous actions suppressed. Not LLM validation.',
        'runs':len(rows),'control_worlds':4,'rows':rows},ensure_ascii=False,indent=2)+'\n')
    print('24 active-advice runs + 4 untreated controls; applied decisions preserve deep state')


if __name__=='__main__':main()
