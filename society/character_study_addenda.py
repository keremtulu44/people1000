"""Exploratory directional results and character dossiers from recorded data."""
from collections import defaultdict, Counter
import gzip
import hashlib
import json
from pathlib import Path
import statistics as st
import tempfile
from .engine import Simulation, BaselineProvider

from .character_study import OUT, GROUPS, source_hashes
from .character_study_report import NAMES, table, paired


def read_trace(item):
    folder=Path(next(iter(item['files']))).parent
    with gzip.open(folder/'trace.json.gz','rt') as f:return json.load(f)


def build():
    primary=[json.loads(x) for x in (OUT/'completed.jsonl').read_text().splitlines()]
    follow=[json.loads(x) for x in (OUT/'followup/completed.jsonl').read_text().splitlines()]
    assert len(primary)==508 and len(follow)==104
    p=json.loads((OUT/'followup/protocol.json').read_text());assert p['sources']==source_hashes()
    by_seed={x['run']['seed']:x['run']['initial_world_hash'] for x in primary if x['run']['case']=='none' and x['run']['model']=='v3.1' and x['run']['population']==100}
    rows=0;files=0;bytes_=0
    for item in follow:
        r=item['run'];assert r['initial_world_hash']==by_seed[r['seed']]
        assert r['transitions_accessible'] and r['frozen_traits'] and r['closed_gatherings_clear'] and not r['solo_expression_errors']
        for path,meta in item['files'].items():
            file=Path(path);assert hashlib.sha256(file.read_bytes()).hexdigest()==meta['sha256']
            assert file.stat().st_size==meta['bytes'];files+=1;bytes_+=meta['bytes']
        folder=Path(next(iter(item['files']))).parent;count=0
        with gzip.open(folder/'daily.jsonl.gz','rt') as f:
            for line in f:
                row=json.loads(line);day=count//100
                assert row['day']==day and row['time']==(day+1)*1440-1
                count+=1
        assert count==3000;rows+=count
    data=primary+follow;allruns=[x['run'] for x in data];gg=[g for x in data for g in x['groups']]
    get=lambda name,model='v3.1': [r for r in allruns if r['case']==name and r['model']==model and r['population']==100 and r['days']==30]
    rate=lambda records,field='ever_changed': st.mean(100*r[field]/r['population'] for r in records)
    summary={'total_runs':len(data),'main_runs':508,'exploratory_runs':104,'extra_raw_files_verified':files,
             'extra_raw_bytes':bytes_,'extra_actual_agent_day_rows':rows,'sources_unchanged':True,
             'extra_transition_count':sum(r['switches'] for r in [x['run'] for x in follow])}
    stats=[]
    for name in sorted({x['run']['case'] for x in follow}):
        for model in sorted({x['run']['model'] for x in follow if x['run']['case']==name}):
            rr=get(name,model)
            stats.append({'case':name,'model':model,'seeds':len(rr),'change_percent':rate(rr),'withdraw_percent':rate(rr,'withdrawn'),
                'mean_final_A_percent':st.mean(r['final_A'] for r in rr),'mean_final_B_percent':st.mean(r['final_B'] for r in rr),
                'min_final_A':min(r['final_A'] for r in rr),'max_final_A':max(r['final_A'] for r in rr)})
    summary['aggregates']=stats
    # All paired one/many-author attribution states, not inferred from outcomes.
    repeats={}
    for item in primary:
        r=item['run']
        if r['case'] not in ('repeat-once','repeat-many'):continue
        tr=read_trace(item)
        repeats[r['case'],r['seed']]={a:tr['final_agents'][a]['behavior']['appraisal']['responsibility'] for a in tr['protocol']['targets']}
    summary['same_author_final_attributions_equal_all_8_seeds']=all(repeats['repeat-once',s]==repeats['repeat-many',s] for s in range(8))
    assert summary['same_author_final_attributions_equal_all_8_seeds']
    # Source forecast trust at the controlled target, not population-diluted mean.
    forecast=defaultdict(list)
    support=defaultdict(list)
    base_savings={};wealth=[];candidate_examples=[];sample_none={};withdrawal_policy_queries=[];exposure=Counter();switch_days=defaultdict(list)
    for item in primary:
        r=item['run'];case=r['case']
        if r['model']!='v3.1' or r['population']!=100:continue
        if case=='i80-A-positive' and r['days']==30:
            tr=read_trace(item);folder=Path(next(iter(item['files']))).parent
            with gzip.open(folder/'daily.jsonl.gz','rt') as f:
                initial={x['agent']:x for x in [json.loads(next(f)) for _ in range(100)]}
            got={e['payload']['agent'] for e in tr['log'] if e['kind']=='appraisal_evidence_learned' and e['payload']['topic'].startswith('benefit:B:')}
            changed={e['payload']['agent'] for e in tr['log'] if e['kind']=='alignment_changed'}
            for aid,a in initial.items():
                g=a['group'];exposure[g,'total']+=1
                if a['alignment']=='A':
                    exposure[g,'initial_A']+=1
                    if aid in got:exposure[g,'accepted_alt']+=1
                    if aid in got and aid in changed:exposure[g,'changed_accepted']+=1
            for e in tr['log']:
                if e['kind']=='alignment_changed':switch_days[initial[e['payload']['agent']]['group']].append(e['time']/1440)
        if case in ('forecast-false','forecast-accurate'):
            tr=read_trace(item)
            for aid in tr['protocol']['targets']:
                a=tr['final_agents'][aid]
                sources={m['original_source'] for m in a['memories'] if m.get('topic')=='economic_outlook'}
                assert len(sources)==1
                forecast[case,a['initial_group']].append(a['behavior']['trust'][sources.pop()])
        if r['days']==30 and case in ('i40-A-known','i80-A-known'):
            tr=read_trace(item)
            support[case].extend(e['time']/1440 for e in tr['log'] if e['kind']=='support_withdrawn')
        if r['days']==30 and case=='none':
            tr=read_trace(item);target=next(a for a in tr['final_agents'].values() if a['initial_group']=='wealthy')
            base_savings[r['seed']]=target['savings']
        if r['days']==30 and case=='contract-valid':
            tr=read_trace(item);target=next(a for a in tr['final_agents'].values() if a['initial_group']=='wealthy')
            wealth.append({'seed':r['seed'],'losses_recorded':target['losses'],'final_savings':target['savings'],'income':target['income']})
        if case=='severe80' and r['days']==180:
            for group in ('discontented','observer'):
                g=next(x for x in item['groups'] if x['group']==group)
                sample_none[group,r['seed']]={'loyalty_at_day179':g['mean_loyalty'],'harm_at_day179':g['mean_harm'],'party_none':g['final_none']==g['n']}
        if r['seed']==0 and case=='forecast-false':
            folder=Path(next(iter(item['files']))).parent
            with gzip.open(folder/'state.json.gz','rt') as f:snapshot_text=f.read()
            with tempfile.TemporaryDirectory(dir=OUT) as tmp:
                file=Path(tmp)/'state.json';file.write_text(snapshot_text);saved=Simulation.load(file)
                for aid in saved.protocol['character_study']['targets']:
                    a=saved.agents[aid]
                    if a.private_loyalty < .5:
                        obs=saved.observation(aid)
                        withdrawal_policy_queries.append({'run':r['id'],'agent':aid,'group':a.initial_group,
                            'private_loyalty':a.private_loyalty,'public_support':a.public_support,
                            'responsibility_current':obs['political_responsibility'],
                            'policy_proposal':BaselineProvider().decide(obs)})
        if r['seed']==0 and case=='benefit-aligned':
            folder=Path(next(iter(item['files']))).parent
            with gzip.open(folder/'state.json.gz','rt') as f:snap=json.load(f)
            found=set()
            for e in snap['log']:
                if e['kind']!='behavior_updated':continue
                pp=e['payload'];aid=pp['agent'];g=snap['agents'][aid]['initial_group'];ap=pp.get('appraisal',{})
                if g in ('observer','discontented') and g not in found and ap.get('expected_utility',{}).get('B',0)>0 and ap['attraction']==0:
                    candidate_examples.append({'run':r['id'],'event':e['id'],'agent':aid,'group':g,'time':e['time'],
                        'expected_utility':ap['expected_utility'],'alternative':ap['alternative'],'attraction':ap['attraction'],'evidence_ids':ap['benefit_evidence_ids']})
                    found.add(g)
    for x in wealth:x['matched_savings_gap']=base_savings[x['seed']]-x['final_savings']
    summary['withdrawal_day']={k:{'mean':st.mean(v),'min':min(v),'max':max(v),'events':len(v)} for k,v in support.items()}
    summary['contract_accounting']=wealth
    summary['neutral_loyalty_samples']=[dict(group=g,seed=s,**v) for (g,s),v in sample_none.items()]
    summary['neutral_candidate_counterexamples']=candidate_examples
    summary['saved_state_withdrawal_policy_queries']=withdrawal_policy_queries
    summary['conditional_exposure']={g:{k:exposure[g,k] for k in ('total','initial_A','accepted_alt','changed_accepted')} for g in GROUPS}
    summary['observed_switch_days']={g:{'min':min(v),'max':max(v),'events':len(v)} for g,v in switch_days.items()}
    (OUT/'followup/validation.json').write_text(json.dumps(summary,indent=2))
    lines=['# Ek keşif: yön, eşzamanlı kampanya ve ölçüm sınırları','',
        '**104 ek koşu** ana sonuçlar görüldükten sonra kapsam açığını kapatmak için tanımlandı. Bunlar kör/önkayıtlı doğrulama değildir. Ana 508 koşu ve protokol değiştirilmedi. Toplam **612 koşu** oldu.',
        '', '## B yönüne çevrilen kampanya ve iki kampanya birden',
        'Aynı toplumda B kaynakları mevcut B-ağ temaslarına B sorumluluğu ve olumlu A ifadeleri yolladı. Dual kolunda A ve B kampanyaları birlikte var. Başlangıç fiziksel/kişilik hashleri aynı; farklı köklerin ağ erişimi farklı, dolayısıyla A/B farkı yalnız grup parametresi değildir. Dual kolunun toplam gönderim dozu da iki katıdır.', '']
    lines+=table(['Ek senaryo','Sürüm','Tohum','Geçiş %','Destek çekme %','Son A %','Son B %'],[
        [x['case'],x['model'],x['seeds'],f"{x['change_percent']:.2f}",f"{x['withdraw_percent']:.2f}",f"{x['mean_final_A_percent']:.2f}",f"{x['mean_final_B_percent']:.2f}"] for x in stats])
    lines+=['','B’ye dönük kampanya muhaliflerin gerçekten değişip değişemediğini sınar. A’ya yönelik ana kolun sıfır muhalif geçişini tek başına direnç başarısı saymak doğru değildi. İki tarafın değişmesi de bir eşitlik hedefi demek değildir; son A/B sayıları burada doğrudan ölçülür.',
        'İsimlerde mirror/dual, temel A senaryosunun adını taşır. Gerçek ayna planında B atfı/A faydası vardır; case içindeki eski alanlar temel senaryo metadatasıdır. Etkin müdahaleler plan kayıtlarından yorumlanmalıdır.',
        'Maliyet kontrolü: v2’de aynı dört tohumda ani %60 için geçiş ortalaması %20, kademeli %60 için %0.25; maliyeti kademeli kola eşlenen geç ani kol için yine %0.25 çıktı. Bu küçük örnek ve kodda öğrenen referans bulunmaması nedeniyle sonucu alışma psikolojisinin doğrulanması diye sunamayız.',
        '', '## Düşük nüfus oranı, maruz kalanların dirençli olduğunu kanıtlamaz',
        'Ağır A-atfı/olumlu B kolunda, 8 tohumdaki kişiler birleştirilerek gerçek kabul edilen fayda-tanıklığı olayları ayrıca sayıldı. Bu tedavi sonrası seçilmiş alt gruptur; nedensel etki veya toplumsal olasılık değildir. Başlangıç A olan, gerçekten tanıklığı kabul edenlerde:',
        *table(['Grup','Bütün grupta kişi','Başlangıç A','Olumlu alternatif tanıklığı kabul eden','Bunlardan geçen'],[[NAMES[g],exposure[g,'total'],exposure[g,'initial_A'],exposure[g,'accepted_alt'],exposure[g,'changed_accepted']] for g in GROUPS]),
        'Özellikle mevkililerde bütün grubun geçiş oranı %6.67 görünürken, bu dar maruz kalan alt grupta 12 kişiden 8’i geçti. Güç yanlılarında 52 kişiden 35’i, zenginlerde 7 kişiden 4’ü geçti. Küçük ve seçilmiş paydalarla gerçekçilik/nadirlik hükmü kurulamaz; ancak yalnız genel orana bakmanın kırılganlığı gizlediği açıktır.',
        'Bu koldaki gerçekleşmiş geçişler güç yanlılarında gün 13–28, mevkililerde 13–27, zenginlerde 16–28 aralığında. Anlık/rastgele sıçrama değil, yerel skor birikimi var. Fakat mevkili için kapsamlı makam/servet/kurum transferi sonucu modellenmediğinden değişimin anlamlı kurumsal bedeli ayrıca kanıtlanmış değil.',
        '', '## Tekrarlanan kaynak ve yanlış/doğru tahmin',
        'Tek sefer ve çok tekrarda aynı kaynağın son atıf dağılımı 8 tohumun tamamında aynı çıktı. Daha fazla okuma oldu ama yeni bağımsız tanık yaratılmadı. Bu koruma özel atıf/fayda kayıtlarına aittir; normal konu görüşleri aynı kaynaktan tekrarlarla kademeli değişebilir.',
        'Aynı hedefin ilgili mevkili kaynağa son güveni:']
    lines+=table(['Grup','Yanlış tahmin (0; gözlenen zarar .8)','Uyumlu tahmin (.8)'],[
        [NAMES[g],f"{st.mean(forecast['forecast-false',g]):.3f}",f"{st.mean(forecast['forecast-accurate',g]):.3f}"] for g in GROUPS])
    lines+=['','## Hızlı destek çekme: ideoloji değil, yine de eşik anlamı önemli',
        *[f"- {k}: {v['events']} destek çekme olayı; ortalama gün {v['mean']:.2f}, aralık {v['min']:.2f}–{v['max']:.2f}." for k,v in summary['withdrawal_day'].items()],
        'Bu sayılar ilk ihlalden beri geçen süre değil, simülasyonun başlangıcından olay günüdür. Başlangıç özel sadakati bütün gruplarda .5; ilk günlük güncelleme sonra değişir. Bilinen sorumlulukta sadakatin .5 altına inmesi, referans politikada destek çekmek için yeterli olabilir. Bu nedenle orta/ağır şokta benzer destek çekme oranı “aynı şiddette hissediyorlar” demek değildir. Karaktere özgü başlangıç sadakatinin bulunmaması ayrı bir sınırlamadır.',
        'Ek politika sınırı: yanlış tahmin koşulu Wait kullandığı için otomatik destek çekme ölçülmez. Bunun yanında, kaydedilmiş son durumdaki düşük sadakatli hedeflere referans politikayı yalnız sorguladık (eylem uygulamadık):',
        *['- '+x['agent']+': özel sadakat '+format(x['private_loyalty'],'.3f')+', sorumluluk '+str(x['responsibility_current'])+'; politika '+x['policy_proposal']['type']+' önerdi.' for x in withdrawal_policy_queries],
        'Bu sorgu yeni bir toplum koşusu değildir. Nedensel suçlama 0 olduğunda, güven kaybı/özel sadakat düşüşü tek başına bu politikada destek çekmeye yetmiyor. Dolayısıyla bağımsız yolların hepsinin uygulandığı iddia edilmemeli.',
        '', '## Tarafsızların özel sadakati ve aday yanlılığı',
        '180 günlük şiddetli fakat atıfsız şokta tarafsız grupların özel sadakat alanı:']
    lines+=table(['Grup','Tohum','179. gün özel sadakat','Son zarar','Hâlâ tarafsız mı'],[
        [NAMES[g],s,f"{v['loyalty_at_day179']:.3f}",f"{v['harm_at_day179']:.2f}",v['party_none']] for (g,s),v in sorted(sample_none.items())])
    lines+=['','Kaynak yokluğunda distrust=0 seçilmesi sadakat alanını yukarı sürükleyebiliyor. Tarafsız bir kişinin bu sadakatinin neye yöneldiği açıklanmadıkça sayı psikolojik sonuç diye okunmamalı. Bu kişi partisini veya ideolojisini değiştirdi demek değildir.',
        'B lehine pozitif yerel fayda görüşü olup A tek aday seçildiği için çekiciliğin 0 kaldığı gerçek kayıtlardan örnekler:']
    lines+=table(['Grup / kişi','A faydası','B faydası','Seçilen aday','Çekicilik','Olay'],[
        [f"{NAMES[e['group']]} / {e['agent']}",f"{e['expected_utility']['A']:.3f}",f"{e['expected_utility']['B']:.3f}",e['alternative'],e['attraction'],e['event']] for e in candidate_examples])
    lines+=['','Bu örneklerde gelecekte ne olacağını varsaymadık; o anki appraisal kaydı gösteriliyor. Aday seçimi sorunu, her iki adayı karşılaştıran bir karar olmadığına somut kanıttır.',
        '', '## Gelir kaybının iki farklı ölçümü',
        f"Geçerli tek sözleşme iptalinde kayıtlı losses ortalaması {st.mean(x['losses_recorded'] for x in wealth):.3f}; aynı tohumun müdahalesiz hedefiyle son tasarruf farkı ortalaması {st.mean(x['matched_savings_gap'] for x in wealth):.3f}. Başlangıç günü ve müdahale zamanı aynı. Bunlar aynı ekonomik büyüklük değildir.",
        '', '## Sıfır tepkiyi yanlış yorumlamama',
        'Referans politika kendiliğinden buluşma oluşturmaz, kurumsal baskı/sözleşme stratejisi yürütmez ve çekilmiş desteği geri ilan etmez. Bu eylemler izinli olsa da otomatik politikada seçilmiyor. O yüzden davetsiz aşırı şokta sıfır kolektif eylem, insanların sakin veya karakterin gerçekçi olduğunu kanıtlamaz; organizasyon politikası eksikliğidir.',
        '', '## Ek kayıt doğrulaması',
        f"{files} ek ham dosyanın hashleri ve {rows:,} ek gerçek ajan-gün satırı doğrulandı. Model kaynakları değişmedi. Ana + ek toplam: 612 koşu, 2,232,000 gerçek ajan-gün gözlemi. [Ek protokol](followup/protocol.json), [ek sonuçlar](followup/runs.csv), [ek doğrulama](followup/validation.json)."]
    (OUT/'followup-findings.md').write_text('\n'.join(lines)+'\n')
    # Compact per-character dossier across the full directional coverage.
    dossiers=['# Altı grubun ölçülmüş karakter dosyaları','',
        'Grup içi yüzdeler. Ana A kampanyası ile keşif amaçlı B/dual kampanyalar ayrı satırlardır; ağ erişimi eşitlenmiş sayılmaz. Kaynak testleri tek hedef/8 tohum; bütün grup genellemesi değildir.']
    for group in GROUPS:
        dossiers+=['',f'## {NAMES[group]}', '']
        vals=[]
        for case in ('severe80','i80-A-positive','mirror-i80-A-positive','dual-i80-A-positive','crowd-none','crowd-peer'):
            rows_=[g for g in gg if g['group']==group and g['case']==case and g['model']=='v3.1' and g['population']==100 and g['days']==30]
            vals.append([case,f"{st.mean(100*x['ever_changed']/x['n'] for x in rows_):.2f}",f"{st.mean(100*x['withdrawn']/x['n'] for x in rows_):.2f}",f"{st.mean(100*x['attended']/x['n'] for x in rows_):.2f}",f"{st.mean(x['mean_loyalty'] for x in rows_):.3f}"])
        dossiers+=table(['Koşul','Geçiş %','Destek çekme %','Katılım %','Son özel sadakat'],vals)
        baseline=[g for g in gg if g['case']=='none' and g['group']==group and g['model']=='v3.1' and g['population']==100]
        dossiers += ['',f"Doğal ağda ortalama çıkış derecesi {st.mean(x['mean_out_degree'] for x in baseline):.2f}, giriş derecesi {st.mean(x['mean_in_degree'] for x in baseline):.2f}. Ortak günlük iletişim bütçesi 2; bu derece farkı tek başına özgül hız/frekans rejimi değildir."]
    (OUT/'group-dossiers.md').write_text('\n'.join(dossiers)+'\n')
    report=Path('reports/character-study-report.md')
    text=report.read_text();marker='\n## 14. Keşif amaçlı yön ve anlam kontrolleri\n'
    if marker in text:text=text.split(marker)[0]
    text+=marker+'''Ana çalışmadan sonra A-odaklı kapsam açığı için **104 ek koşu** çalıştırıldı: 64 B-yönü aynalama, 32 eşzamanlı A/B kampanyası ve 8 tarihsel maliyet-eşlenmiş kontrol. Toplam **612 koşu**. Bunlar keşif analizidir; ana 508 koşuluk protokolün önkayıtlı parçası değildir.

[Ek sonuçlar, tarafsız aday karşı örnekleri ve ölçüm sınırları](character-study/followup-findings.md) · [Altı ayrı karakter dosyası](character-study/group-dossiers.md)

Bu ek analiz; kaynak yokken tarafsızların özel sadakat alanının yükselmesi, başlangıç sadakatinin bütün gruplarda .5 olması, destek çekmenin erken eşiği, farklı buluşma kimliklerinin mekân etkisi ve gelir kaybı metriğinin sınırlarını ayrıca görünür kıldı. Hiçbiri araştırma sırasında davranış kodu değiştirilerek giderilmedi.
'''
    report.write_text(text)
    print('Exploratory follow-up verified:',len(follow),'runs; combined',len(data))


if __name__=='__main__':build()
