"""Read-only audit/report for completed v3.3 research. No behavior tuning.
Run from repository root: python tools/analyze_character_research_v33.py
"""
from collections import Counter,defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import statistics as st
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from society.character_research_v33 import specs
from society.character_research_v32 import identifier,sources

OUT=ROOT/'reports/character-research-v33'
NAMES={'power_aligned':'Güç yanlısı','opposition':'Muhalif','authority':'Yönetici / burjuva','wealthy':'Zengin','discontented':'Tepkisel huzursuz','observer':'Gözlemci'}


def load(path):return json.loads(path.read_text())
def gzload(path):
    with gzip.open(path,'rt') as f:return json.load(f)
def avg(xs):return st.mean(xs) if xs else None

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows])

def dump(name,x):(OUT/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')


def main():
    execution=load(OUT/'execution.json');assert execution['status']=='complete',execution
    protocol=load(OUT/'protocol.json');assert protocol['sources']==sources()
    done=[json.loads(x) for x in (OUT/'completed.jsonl').read_text().splitlines()]
    expected={identifier(j) for j in specs()};assert {x['run']['id'] for x in done}==expected
    assert len(done)==len(expected)==808
    runs=[x['run'] for x in done];groups=[g for x in done for g in x['groups']]
    audits={};last_days={};daily_groups=raw_rows=verified_files=0;errors=[]
    transitions=[];reasons=Counter();api_status=Counter();proof_rows=[]
    for item in done:
        r=item['run'];rid=r['id'];folder=OUT/'evidence'/rid
        for name,meta in item['files'].items():
            p=ROOT/name;assert p.stat().st_size==meta['bytes'],name
            assert hashlib.sha256(p.read_bytes()).hexdigest()==meta['sha256'],name
            verified_files+=1
        count=0;last={}
        with gzip.open(folder/'group-days.jsonl.gz','rt') as f:
            for line in f:
                q=json.loads(line);day=count//6
                assert q['id']==rid and q['day']==day and q['time']==(day+1)*1440-1
                assert sum(q['alignment'].values())==q['n']
                for dist in q['distributions'].values():
                    if dist is not None:assert dist['min']<=dist['mean']+1e-9 and dist['mean']<=dist['max']+1e-9
                last[q['group']]=q;count+=1
        assert count==r['days']*6
        assert sum(q['n'] for q in last.values())==r['population']
        assert sum(q['alignment'].get('A',0) for q in last.values())==r['final_A']
        daily_groups+=count;last_days[rid]=last
        raw=ROOT/item['raw_agent_days']['path']
        if raw.exists():
            assert hashlib.sha256(raw.read_bytes()).hexdigest()==item['raw_agent_days']['sha256']
            with gzip.open(raw,'rb') as f:n=sum(1 for _ in f)
            assert n==item['raw_agent_days']['rows'];raw_rows+=n
        else:errors.append({'id':rid,'raw':'not available; not backfilled'})
        audit=gzload(folder/'audit.json.gz');audits[rid]=audit
        assert r['transitions_accessible'] and r['frozen_traits'] and r['closed_gatherings_clear']
        assert r['solo_expression_errors']==0 and r['support_membership_errors']==0
        if r['model'] in ('v3.2','v3.3'):
            assert r['core_changes']==0
            assert abs(r['initial_institutional_position']-r['final_institutional_position'])<1e-8
        assert r['network_attempts']==0
        reasons.update(audit['daily_reasons']);api_status.update(x['status'] for x in audit.get('agenda_runtime',{}).get('requests',[]))
        for event in audit['events']:
            if event['kind']=='alignment_changed':transitions.append(dict(run=rid,**event))
        if r['section'].startswith('agenda'):
            for target in audit['targets']:
                issue=target['agenda'].get('appointment')
                proof_rows.append({'run':rid,'case':r['case'],'seed':r['seed'],'population':r['population'],'group':target['group'],
                    'qualification':issue['qualification'] if issue else None,'procedure':issue['procedure'] if issue else None,
                    'evidence_count':len(issue['evidence']) if issue else 0,'claim_count':len(issue['claims']) if issue else 0,
                    'read_messages':len(target['read_messages']),'initial_alignment':target['initial']['alignment'],'alignment':target['alignment']})
    assert raw_rows==execution['agent_days'] and not errors,errors
    # Fresh v3.2 matched arms: compare outcomes, not profile hash or wall time.
    matched=[];fields=('ever_changed','switches','withdrawn','attended','expressed','core_changes','losses','negative_savings',
        'read_events','final_A','final_B','final_none','institutional_contests','self_study_actions','initial_world_hash')
    current={(r['case'],r['seed'],r['population'],r['days']):r for r in runs if r['model']=='v3.3' and r['section']=='replication'}
    for r in runs:
        if r['section']!='fresh-v32-control':continue
        other=current[r['case'],r['seed'],r['population'],r['days']]
        different={f:[r[f],other[f]] for f in fields if r[f]!=other[f]}
        matched.append({'v32':r['id'],'v33':other['id'],'differences':different})
    assert len(matched)==32
    # Ordinary agenda: compare full final deep vectors to a same-seed untreated Wait arm.
    controls={(r['seed'],r['population']):r for r in runs if r['case']=='agenda-no-notice'}
    agenda_checks=[]
    for r in runs:
        if not r['section'].startswith('agenda'):continue
        if r['population']==100:
            control=controls[r['seed'],100]
        else:
            control=next(x for x in runs if x['case']=='agenda-notice' and x['population']==1000 and x['seed']==r['seed'])
        a=audits[r['id']]['final_deep_state'];b=audits[control['id']]['final_deep_state']
        changed=[aid for aid in a if a[aid]!=b[aid]]
        agenda_checks.append({'id':r['id'],'control':control['id'],'deep_changed_agents':changed,
            'comparison':'untreated Wait' if r['population']==100 else 'notice vs received-document Wait'})
    assert all(not x['deep_changed_agents'] for x in agenda_checks)
    # Compare explicit historical controls to recorded old summaries (raw old files unavailable).
    historical=[]
    for path in (ROOT/'reports/character-study/completed.jsonl',ROOT/'reports/character-study/followup/completed.jsonl'):
        historical.extend(json.loads(x)['run'] for x in path.read_text().splitlines())
    hidx={(r['case'],r['seed'],r['population'],r['days'],r['model']):r for r in historical}
    legacy_checks=[]
    for r in runs:
        if r['model'] not in ('v2','v3.0'):continue
        h=hidx[r['case'],r['seed'],r['population'],r['days'],r['model']]
        differences={f:[h[f],r[f]] for f in fields if f in h and h[f]!=r[f]}
        legacy_checks.append({'id':r['id'],'differences':differences})
    aggregate=[]
    by=defaultdict(list)
    for r in runs:by[r['case'],r['model'],r['population'],r['days'],r['section']].append(r)
    for key,items in sorted(by.items()):
        aggregate.append(dict(zip(('case','model','population','days','section'),key),seeds=len(items),
            **{field:{'mean':avg([r[field] for r in items]),'min':min(r[field] for r in items),'max':max(r[field] for r in items)} for field in
                ('ever_changed','withdrawn','attended','expressed','losses','institutional_contests','self_study_actions','review_attempts','imposed_rejected')}))
    dump('aggregates.json',aggregate);dump('ordinary-targets.json',proof_rows)
    dump('fresh-v32-comparison.json',matched);dump('ordinary-deep-state-checks.json',agenda_checks);dump('historical-control-checks.json',legacy_checks)
    with gzip.open(OUT/'transitions.json.gz','wt') as f:json.dump(transitions,f,separators=(',',':'))
    validation={'runs':len(runs),'verified_persisted_files':verified_files,'actual_sampled_group_days':daily_groups,
        'verified_raw_agent_days':raw_rows,'causal_transition_records':len(transitions),'sources_unchanged_after_declared_fixture_amendment':True,'source_amendments':protocol.get('source_amendments',[]),
        'fresh_v32_pairs':len(matched),'fresh_v32_outcome_mismatches':sum(bool(x['differences']) for x in matched),
        'ordinary_deep_state_comparisons':len(agenda_checks),'ordinary_deep_state_mismatches':sum(bool(x['deep_changed_agents']) for x in agenda_checks),
        'historical_controls':len(legacy_checks),'historical_control_mismatches':sum(bool(x['differences']) for x in legacy_checks),
        'network_attempts':sum(r['network_attempts'] for r in runs),'review_statuses':dict(api_status),'daily_reference_reasons':dict(reasons),
        'analyzer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    dump('validation.json',validation)
    # Write compact result tables. Interpretive overview is authored after inspecting these.
    lines=['# v3.3 geniş araştırma — ölçüm tabloları','',f"{len(runs)} koşu; {raw_rows:,} gerçek kişi-gün; {daily_groups:,} gerçek grup-gün.",'',
        'Tablolardaki değişim kişi sayısıdır, yüzde değildir. 100 ve 1000 kişilik koşullar ayrı tutulur. Sıfır, gerçek dünya imkânsızlığı anlamına gelmez.','']
    selected=('none','sudden60','severe80','extreme900','ramp60','late_equal_cost60','i80-A-positive','i80-unknown-positive','i80-external-positive','i80-A-known','contract-repeat','crowd-none','crowd-same-place-split','x-local-support-severe','x-local-support-blocked')
    rows=[]
    for q in aggregate:
        if q['case'] in selected and q['model']=='v3.3':
            rows.append([q['case'],q['population'],q['days'],q['seeds'],f"{q['ever_changed']['mean']:.2f} ({q['ever_changed']['min']}–{q['ever_changed']['max']})",f"{q['withdrawn']['mean']:.2f}",f"{q['attended']['mean']:.2f}",f"{q['expressed']['mean']:.2f}"])
    lines.extend(['## Seçilmiş karakter koşulları','',table(['Koşul','N','Gün','Tohum','Taraf değiştiren ort. (aralık)','Destek çeken','Katılan','Kolektif ifade'],rows),'',
        '## Normal gündem / değerlendirme sayısı',''])
    rows=[]
    for q in aggregate:
        if q['section'].startswith('agenda'):
            targets=[x for x in proof_rows if x['case']==q['case'] and x['population']==q['population'] and x['qualification'] is not None]
            rows.append([q['case'],q['population'],q['seeds'],f"{q['review_attempts']['mean']:.2f} ({q['review_attempts']['min']}–{q['review_attempts']['max']})",
                f"{avg([x['qualification'] for x in targets]):.3f}" if targets else 'öğrenilmedi',q['imposed_rejected']['mean']])
    lines.extend([table(['Koşul','N','Tohum','Çevrimdışı inceleme ort. (aralık)','Ölçülen hedef yeterlilik ort.','Reddedilen plan girdisi ort.'],rows),'',
        'Bu çağrılar ücretli LLM istekleri değil; gerçek arayüzden geçen çevrimdışı ReferenceAdvisor değerlendirmeleridir. Gerçek dil modeli kullanımı/token maliyeti ölçülmedi.','',
        '## Altı kesim',''])
    dossiers=[]
    for group,label in NAMES.items():
        rows=[]
        for case in ('none','severe80','i80-A-positive','i80-unknown-positive','contract-repeat','source-aligned','source-opposed','x-local-support-severe'):
            items=[g for g in groups if g['model']=='v3.3' and g['group']==group and g['case']==case and g['population']==100 and g['days']==30]
            if not items:continue
            rows.append([case,len(items),f"{avg([100*g['ever_changed']/g['n'] for g in items]):.2f}%",f"{avg([100*g['withdrawn']/g['n'] for g in items]):.2f}%",f"{avg([100*g['attended']/g['n'] for g in items]):.2f}%",f"{avg([g['probe_view_delta'] for g in items if g['probe_view_delta'] is not None]):.3f}" if case.startswith('source-') and any(g['probe_view_delta'] is not None for g in items) else '—'])
        dossiers.extend([f'## {label}','',table(['Koşul','Tohum','Taraf değiştiren','Destek çeken','Katılan','Hedef genel-konu görüş farkı'],rows),''])
    (OUT/'group-dossiers.md').write_text('\n'.join(['# Altı kesim — v3.3 ölçümleri','','Görüş farkı yalnız kontrollü kaynak deneyindeki hedef kişiyi ölçer; bütün kesimin ortalama kanaati değildir. Nötr 50 ölçüm referansıdır; sıfır, yeni inanç oluştuğunu kanıtlamaz. Diğer koşullarda konu ölçülmediği için — kullanılır. Yüzdeler ilgili başlangıç kesimi içindedir; gerçek toplum oranı değildir.','',*dossiers]))
    lines.extend(['[Kesim tabloları](group-dossiers.md) · [Makine okunur doğrulama](validation.json)','',
        '803 koşudan sonra yalnız 1000 kişilik gündem kurulumuna ilişkin kaynak seçimi düzeltildi. Davranış kodu ve katsayılar değişmedi; hata ve protokol yaması saklandı.'])
    (OUT/'results.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(validation,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
