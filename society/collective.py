"""v3.1: private distress, explicit support withdrawal, actual co-presence.

A gathering is a bounded, peaceful public expression, not violence or a party
conversion. Calendar details are authenticated; attendance is NOT promised by an
invitation. Non-attendees cannot see a global headcount or private motivations.
"""
from copy import deepcopy

ACTIONS = ('create_gathering', 'attend_gathering', 'leave_gathering', 'withdraw_support')


def enabled(sim):
    return sim.behavior_profile.get('social_model') == 'collective-v1'


def state(a):
    return a.behavior.setdefault('social', {'distress': 0., 'known_gatherings': {},
        'present_at': None, 'visible_participants': [], 'collective_strength': 0.,
        'collective_active': False})


def details(g):
    return {k: g[k] for k in ('id', 'organizer', 'place', 'start', 'end')} | ({'purpose':g['purpose']} if 'purpose' in g else {})


def observe(sim, a):
    # The agent sees only previously learned invitations and physical observations.
    return deepcopy(state(a))


def validate(sim, a, p):
    kind = p['type']
    if kind == 'create_gathering':
        start, end = p.get('start'), p.get('end')
        if type(start) is not int or type(end) is not int or not sim.time < start < end or end-start > 1440:
            return 'gathering requires future start and duration at most one day'
        if p.get('purpose') is not None and (not isinstance(p['purpose'],str) or not 0<len(p['purpose'])<=200):
            return 'invalid explicit gathering purpose'
        if not isinstance(p.get('place'), str) or not 0 < len(p['place']) <= 200:
            return 'invalid gathering place'
    elif kind in ('attend_gathering', 'leave_gathering'):
        gid = p.get('gathering_id')
        if not isinstance(gid, str) or gid not in state(a)['known_gatherings']:
            return 'gathering not learned'
        g = sim.gatherings.get(gid)
        if g is None:
            return 'unknown gathering'
        if kind == 'attend_gathering':
            from . import characters
            if characters.enabled(sim) and p.get('participation','observe') not in ('observe','support'):
                return 'participation must be observe or support'
            if not g['start'] <= sim.time < g['end']:
                return 'gathering not open'
            if state(a)['present_at'] is not None:
                return 'already attending a gathering'
        elif state(a)['present_at'] != gid:
            return 'not attending this gathering'
    return None


def learn(sim, a, invitation, cause):
    s = state(a)
    gid = invitation['id']
    first = gid not in s['known_gatherings']
    if first:
        s['known_gatherings'][gid] = {**details(invitation), 'endorsements': {}}
    # A peer's earlier invitation must not prevent a later trusted endorsement.
    # Each authenticated source has one latest statement, not extra supporters.
    source = {k: invitation[k] for k in ('source','group','source_pole','channel_trust')}
    source.update(learned_at=sim.time, evidence_id=cause)
    s['known_gatherings'][gid]['endorsements'][source['source']] = source
    sim.record('gathering_learned', {'agent': a.id, 'invitation': invitation}, cause)
    if first and invitation['start'] > sim.time:
        # Local reminder from this read invitation, not a global broadcast.
        sim.schedule(invitation['start'], 'decide', {'target': a.id}, cause)


def invitation(sim, a, gid):
    g = sim.gatherings[gid]
    return {**details(g), 'source': a.id, 'group': a.initial_group,
            'source_pole': a.public_alignment, 'channel_trust': 1.}


def receive(sim, a, m, sender):
    if 'gathering' not in m:
        return
    value = deepcopy(m['gathering'])
    value.update(source=m['original_source'], group=m['source_group'],
                 source_pole=m['source_alignment'], channel_trust=sim.edge(sender,a.id)['trust'])
    learn(sim, a, value, m['id'])


def refresh(sim, g, cause):
    from . import characters
    if characters.enabled(sim):
        return refresh_location(sim,g['place'],cause)
    present = sorted(g['participants'])
    for aid in present:
        a = sim.agents[aid]
        s = state(a)
        was_active = s['collective_active']
        s['visible_participants'] = present.copy()
        s['collective_strength'] = (len(present)-1)/len(present)
        s['collective_active'] = len(present) >= 2
        if was_active != s['collective_active']:
            sim.record('collective_expression_started' if s['collective_active'] else 'collective_expression_ended',
                {'agent': aid, 'gathering_id': g['id'], 'mode': 'peaceful'}, cause)
        sim.record('collective_observation', {'agent': aid, 'gathering_id': g['id'],
            'visible_participants': present, 'collective_strength': s['collective_strength'],
            'collective_active': s['collective_active']}, cause)


def refresh_location(sim, place, cause):
    """Physical visibility crosses calendar IDs; endorsement does not.

    Separate registrations only share strength if an explicit identical purpose
    was declared. Missing purposes never imply a shared cause. No party updates.
    """
    groups=[g for g in sim.gatherings.values() if g['place']==place and
            g['start']<=sim.time<g['end'] and g['participants']]
    visible=sorted({aid for g in groups for aid in g['participants']})
    for g in groups:
        supporters=sorted({aid for other in groups if other['id']==g['id'] or
                           (g.get('purpose') is not None and other.get('purpose')==g['purpose'])
                           for aid in other.get('supporters',[])})
        for aid in g['participants']:
            s=state(sim.agents[aid]);was_active=s['collective_active']
            s.update(visible_participants=visible.copy(),supporting_participants=supporters.copy(),
                     visible_gatherings=[details(other) for other in groups],
                     collective_strength=(len(supporters)-1)/len(supporters) if aid in supporters else 0.,
                     collective_active=aid in supporters and len(supporters)>=2)
            if was_active!=s['collective_active']:
                sim.record('collective_expression_started' if s['collective_active'] else 'collective_expression_ended',
                           {'agent':aid,'gathering_id':g['id'],'mode':'peaceful'},cause)
            sim.record('collective_observation',{'agent':aid,'gathering_id':g['id'],
                       'visible_participants':visible,'supporting_participants':supporters,
                       'collective_strength':s['collective_strength'],'collective_active':s['collective_active']},cause)


def clear(sim, a, gid, cause):
    s = state(a)
    if s['collective_active']:
        sim.record('collective_expression_ended', {'agent': a.id, 'gathering_id': gid, 'mode': 'peaceful'}, cause)
    if 'supporting_participants' in s:s.update(supporting_participants=[],visible_gatherings=[])
    s.update(present_at=None, visible_participants=[], collective_strength=0., collective_active=False)
    sim.record('gathering_departed', {'agent': a.id, 'gathering_id': gid}, cause)


def apply(sim, a, p, cause):
    kind = p['type']
    if kind == 'withdraw_support':
        before = {'public_alignment': a.public_alignment, 'public_support': a.public_support}
        a.public_alignment, a.public_support = 'none', 0.
        sim.record('support_withdrawn', {'agent': a.id, 'before': before,
            'alignment_unchanged': a.alignment, 'private_loyalty': a.private_loyalty,
            'core_orientation': a.behavior['core_orientation']}, cause)
    elif kind == 'create_gathering':
        gid = sim._id('G')
        g = {'id': gid, 'organizer': a.id, 'place': p['place'], 'start': p['start'],
             'end': p['end'], 'participants': []}
        from . import characters
        if characters.enabled(sim):g.update(purpose=p.get('purpose'),supporters=[])
        sim.gatherings[gid] = g
        learn(sim, a, invitation(sim,a,gid), cause)
        sim.schedule(g['end'], 'gathering_close', {'gathering_id': gid}, cause)
        sim.record('gathering_created', details(g), cause)
    elif kind == 'attend_gathering':
        g = sim.gatherings[p['gathering_id']]
        g['participants'].append(a.id)
        from . import characters
        if characters.enabled(sim) and p.get('participation','observe')=='support':g['supporters'].append(a.id)
        state(a)['present_at'] = g['id']
        sim.record('gathering_attended', {'agent': a.id, 'gathering_id': g['id']}, cause)
        refresh(sim,g,cause)
    elif kind == 'leave_gathering':
        g = sim.gatherings[p['gathering_id']]
        g['participants'].remove(a.id)
        if a.id in g.get('supporters',[]):g['supporters'].remove(a.id)
        clear(sim,a,g['id'],cause)
        refresh(sim,g,cause)


def close(sim, gid, cause):
    g = sim.gatherings[gid]
    for aid in g['participants']:
        clear(sim,sim.agents[aid],gid,cause)
    g['participants'] = []
    if 'supporters' in g:g['supporters']=[]
    from . import characters
    if characters.enabled(sim):refresh_location(sim,g['place'],cause)


def policy(obs):
    """Small explicit reference policy, not a calibrated social psychology model.

    Organizing is an intervention in this stage. Attendance is autonomous, based
    only on received invitations, private distress/risk and trusted public sources.
    """
    s = obs.get('social')
    if s is None:
        return None
    current = obs['alignment']
    if (obs['public_support'] > 0 and obs['private_loyalty'] < .5 and
            obs['behavior'].get('appraisal',{}).get('responsibility',{}) and
            obs.get('political_responsibility',0.) > 0):
        return {'type':'withdraw_support'}
    if s['present_at'] is not None or obs['group'] == 'observer':
        return None
    for gid, g in s['known_gatherings'].items():
        if not g['start'] <= obs['time'] < g['end']:
            continue
        # Managers/wealthy are not assigned a random crowd-following impulse.
        if obs['group'] in ('authority','wealthy') and obs['behavior'].get('dependency_loss',0.) <= 0 and g['organizer'] != obs['agent_id']:
            continue
        for source in g['endorsements'].values():
            if obs['group'] in ('power_aligned','opposition'):
                if source['group'] != 'authority' or source['source_pole'] != current:
                    continue
            t = obs['traits']
            if source['group'] == 'authority':
                trust = obs['behavior']['trust'].get(source['source'],source['channel_trust'])
                credibility = trust*t['authority_sensitivity']
            else:
                credibility = source['channel_trust']*(1-t['peer_opinion_resistance'])
            readiness = s['distress']*t['risk_tolerance']+credibility
            if readiness > 1-t['risk_tolerance']:
                return {'type':'attend_gathering','gathering_id':gid}
    return None
