"""Operator-controlled day checkpoints. Reports are not agent observations."""
from collections import Counter
from .engine import BaselineProvider
from . import agenda


class Session:
    def __init__(self,simulation,provider=None):
        self.simulation=simulation;self.provider=provider or BaselineProvider()

    def day(self,checkpoint=None):
        sim=self.simulation
        # At an existing day-end advance to the following day-end.
        end=(sim.time//1440+1)*1440-1
        if end<=sim.time:end+=1440
        try:sim.run(end,self.provider)
        finally:
            if checkpoint is not None:sim.save(checkpoint)
        return self.report()

    def days(self,count,checkpoint=None):
        if type(count) is not int or count<0:raise ValueError('Nonnegative day count required')
        return [self.day(checkpoint) for _ in range(count)]

    def report(self):
        sim=self.simulation
        result={'scope':'operator_only','time':sim.time,'world_metrics':sim.behavior_metrics(),
                'events_today':dict(Counter(e['kind'] for e in sim.log if e['time']//1440==sim.time//1440))}
        if agenda.enabled(sim):
            rt=sim.agenda_runtime
            result['reviews']={'attempts':len(rt['requests']),'network_attempts':rt['network_requests'],
                'statuses':dict(Counter(r['status'] for r in rt['requests']))}
            result['ordinary_opinions']={issue:{'aware':sum(issue in agenda.state(a) for a in sim.agents.values()),
                'responses':dict(Counter(agenda.state(a)[issue]['response']['approach'] for a in sim.agents.values()
                   if issue in agenda.state(a) and agenda.state(a)[issue]['response'] is not None))} for issue in sim.agendas}
        return result
