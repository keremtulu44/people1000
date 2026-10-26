"""Audit recorded character-study evidence; never fill history from final values."""
from collections import Counter,defaultdict
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import statistics as st

from .character_study import OUT, GROUPS, source_hashes

NAMES={'power_aligned':'Güç yanlısı','opposition':'Muhalif','authority':'Burjuva/mevkili',
       'wealthy':'Zengin','discontented':'Huzursuz','observer':'Gözlemci'}


def mean(xs):return st.mean(xs) if xs else None


def paired(a,b,field,scale=True):
    aa={x['seed']:x for x in a};bb={x['seed']:x for x in b}
    vals=[(aa[s][field]/aa[s]['population']-bb[s][field]/bb[s]['population'])*100 if scale else aa[s][field]-bb[s][field] for s in sorted(aa.keys()&bb.keys())]
    rng=random.Random(991)
    boots=sorted(st.mean(rng.choices(vals,k=len(vals))) for _ in range(2000)) if vals else []
    return {'n':len(vals),'mean_difference':mean(vals),'min':min(vals,default=None),'max':max(vals,default=None),
            'bootstrap95':[boots[49],boots[1949]] if boots else None,'per_seed':vals}


def table(headers,rows):
    return ['| '+' | '.join(headers)+' |','|'+'|'.join('---' for _ in headers)+'|']+['| '+' | '.join(map(str,r))+' |' for r in rows]


def chart(path,title,series,ylabel):
    colors=['#2563eb','#d97706','#7c3aed','#059669'];w,h=900,340;left,top,pw,ph=65,45,610,240
    ymax=max(v for _,values in series for v in values)*1.08 or 1
    n=max(len(x) for _,x in series)
    bits=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">',
          '<rect width="100%" height="100%" fill="white"/>',f'<text x="65" y="24" font-size="18">{title}</text>']
    for i in range(5):
        y=top+ph-i*ph/4;value=ymax*i/4
        bits += [f'<path d="M{left},{y}h{pw}" stroke="#e5e7eb"/>',f'<text x="5" y="{y+5}" font-size="12">{value:.2f}</text>']
    for j,(label,values) in enumerate(series):
        pts=' '.join(f'{left+i*pw/max(1,n-1):.2f},{top+ph-v/ymax*ph:.2f}' for i,v in enumerate(values))
        bits += [f'<polyline fill="none" stroke="{colors[j]}" stroke-width="2" points="{pts}"/>',f'<text x="690" y="{65+j*25}" fill="{colors[j]}" font-size="13">{label}</text>']
    bits += [f'<text x="65" y="315" font-size="13">Gün 0 → {n-1}; {ylabel}</text>','</svg>']
    path.write_text('\n'.join(bits))


def main():
    execution=json.loads((OUT/'execution.json').read_text());assert execution['status']=='complete'
    protocol=json.loads((OUT/'protocol.json').read_text());assert protocol['model_sources']==source_hashes()
    done=[json.loads(x) for x in (OUT/'completed.jsonl').read_text().splitlines()]
    runs=[x['run'] for x in done];groups=[g for x in done for g in x['groups']]
    assert len(runs)==execution['expected']
    worlds=defaultdict(set)
    for r in runs:worlds[r['population'],r['seed'],r['family']=='source'].add(r['initial_world_hash'])
    assert all(len(v)==1 for v in worlds.values())
    curves=defaultdict(lambda:defaultdict(lambda:[0.,0.,0.,0]))
    trace_counts=Counter();special={};examples=[];mismatch=[];references=[];snapshot_calls=0;leaks=0
    raw_files=0;daily_rows=0;transition_count=0;total_bytes=0;case_inputs=defaultdict(Counter)
    for item in done:
        r=item['run'];rid=r['id'];first={};last={};count=0
        for path,meta in item['files'].items():
            p=Path(path);assert p.stat().st_size==meta['bytes']
            assert hashlib.sha256(p.read_bytes()).hexdigest()==meta['sha256']
            raw_files+=1;total_bytes+=meta['bytes']
        folder=Path(next(iter(item['files']))).parent
        with gzip.open(folder/'daily.jsonl.gz','rt') as f:
            for line in f:
                row=json.loads(line);expected_day=count//r['population']
                assert row['day']==expected_day and row['time']==(expected_day+1)*1440-1
                if expected_day==0:first[row['agent']]=row
                if expected_day==r['days']-1:last[row['agent']]=row
                count+=1
                if r['model']=='v3.1' and r['population']==100 and r['days']==30:
                    values=curves[r['case']][expected_day]
                    values[0]+=row['harm'];values[1]+=row['burden'];values[2]+=row['distress'];values[3]+=1
        assert count==r['population']*r['days'];daily_rows+=count
        assert sum(x['alignment']=='A' for x in last.values())==r['final_A']
        with gzip.open(folder/'trace.json.gz','rt') as f:trace=json.load(f)
        logs=trace['log'];decisions={d['id']:d for d in trace['decisions']}
        for v in trace['protocol']['input_outcomes']:
            if not v['accepted']:case_inputs[r['case']][v['type']]+=1
        # Reconstruct public announcements from actual day-0 observations and
        # chronological logged actions, never from final affiliations.
        pub={aid:x['public_alignment'] for aid,x in first.items()};private={aid:x['alignment'] for aid,x in first.items()}
        for e in logs:
            p=e['payload'];kind=e['kind']
            if kind=='alignment_changed':
                private[p['agent']]=p['new'];transition_count+=1
                relevant=p['diagnostic'].get('appraisal',{})
                references.append({'run':rid,'event':e['id'],'agent':p['agent'],'time':e['time'],
                                   'has_appraisal':bool(relevant),'code_path':p['diagnostic']['code_path']})
                if len(examples)<30 and r['model']=='v3.1':
                    examples.append({'run':rid,'event_id':e['id'],'agent':p['agent'],'group':p['diagnostic']['initial_group'],
                        'day':e['time']/1440,'old':p['old'],'new':p['new'],'score':p['diagnostic']['decision_score'],
                        'threshold':p['threshold'],'attraction':p['attraction'],
                        'responsibility':relevant.get('responsibility'),'expected_utility':relevant.get('expected_utility'),
                        'evidence_ids':relevant.get('benefit_evidence_ids',[])+relevant.get('responsibility_evidence_ids',[])})
            elif kind=='support_withdrawn':pub[p['agent']]='none'
            elif kind=='action_applied':
                d=decisions[p['decision']];a=p['actor'];proposal=d['proposal']
                if p['type']=='declare_support':pub[a]=private[a]
                elif p['type']=='pressure':pub[proposal['target']]=private[a]
                elif p['type']=='send':
                    found=[m for m in trace['messages'].values() if m['original_source']==a and m['created_at']==e['time'] and int(d['id'][1:])<int(m['id'][1:])<int(e['id'][1:])]
                    assert len(found)==1
                    if r['model']=='v3.1' and found[0]['source_alignment']!=pub[a]:mismatch.append({'run':rid,'message':found[0]['id']})
        if r['family']=='institution':
            target=next(a for a in trace['final_agents'].values() if a['initial_group']=='wealthy')
            initial=first[target['id']]
            special[rid]={'target':target['id'],'income':target['income'],'losses':target['losses'],
                          'initial_savings_observed_day0':initial['savings'],'final_savings':target['savings'],
                          'public_support':target['public_support'],'private_loyalty':target['private_loyalty'],
                          'alignment':target['alignment'],'public_alignment':target['public_alignment']}
        if r['case'] in ('repeat-once','repeat-many'):
            special[rid]={'target_attributions':{aid:a['behavior'].get('appraisal',{}).get('responsibility') for aid,a in trace['final_agents'].items() if aid in trace['protocol']['targets']}}
        if r['case']=='crowd-same-place-split':
            special[rid]={'gatherings':trace['gatherings'],'attended_events':[e for e in logs if e['kind']=='gathering_attended'],
                          'expression_events':[e for e in logs if e['kind']=='collective_expression_started']}
        snap=folder/'state.json.gz'
        if snap.exists():
            with gzip.open(snap,'rt') as f:snapshot=json.load(f)
            for call in snapshot['calls']:
                obs=call['observation'];social=obs.get('social')
                if social is None:continue
                snapshot_calls+=1
                if any('participants' in g for g in social['known_gatherings'].values()):leaks+=1
                if social['present_at'] is None and social['visible_participants']:leaks+=1
        trace_counts[r['family']]+=1
    v31=[r for r in runs if r['model']=='v3.1']
    assert all(r['transitions_accessible'] and r['closed_gatherings_clear'] and r['frozen_traits'] and not r['solo_expression_errors'] for r in runs)
    assert not mismatch and not leaks
    validation={'completed_runs':len(runs),'primary_v31_runs':sum(r['model']=='v3.1' and r['population']==100 and r['days']==30 for r in runs),
        'raw_files_verified':raw_files,'raw_bytes':total_bytes,'actual_agent_day_rows':daily_rows,'world_pair_cohorts':len(worlds),
        'initial_common_worlds_equal':True,'model_sources_unchanged':True,'total_transitions':transition_count,
        'transitions_with_structured_appraisal':sum(x['has_appraisal'] for x in references),
        'transitions_without_structured_appraisal':sum(not x['has_appraisal'] for x in references),
        'transition_accessibility_errors':sum(not r['transitions_accessible'] for r in runs),
        'solo_expression_errors':sum(r['solo_expression_errors'] for r in runs),'unclosed_gatherings':sum(not r['closed_gatherings_clear'] for r in runs),
        'v31_core_changes':sum(r['core_changes'] for r in v31),'v31_public_header_mismatches':mismatch,
        'archived_provider_observations_checked':snapshot_calls,'headcount_leak_observations':leaks,
        'imposed_rejections_by_case':{k:dict(v) for k,v in case_inputs.items()},
        'scope':'Accessible evidence IDs checked for every run at execution; public metadata reconstructed from real day-0 snapshots and chronological logs. Provider views checked only where full seed-0 snapshots exist.'}
    (OUT/'validation.json').write_text(json.dumps(validation,indent=2))
    (OUT/'examples.json').write_text(json.dumps(examples,indent=2))
    (OUT/'special-probes.json').write_text(json.dumps(special,indent=2))
    agg=[]
    for key in sorted({(r['case'],r['model'],r['population'],r['days']) for r in runs}):
        rr=[r for r in runs if (r['case'],r['model'],r['population'],r['days'])==key]
        a={'case':key[0],'model':key[1],'population':key[2],'days':key[3],'n_seeds':len(rr)}
        for field in ('ever_changed','withdrawn','attended','expressed','negative_savings'):
            values=[100*x[field]/x['population'] for x in rr]
            a[field]={'mean_percent':st.mean(values),'min_percent':min(values),'max_percent':max(values)}
        a['mean_losses']=st.mean(r['losses'] for r in rr);a['imposed_rejected']=sum(r['imposed_rejected'] for r in rr)
        agg.append(a)
    (OUT/'aggregates.json').write_text(json.dumps(agg,indent=2))
    def select(case,model='v3.1',n=100,days=30):return [r for r in runs if r['case']==case and r['model']==model and r['population']==n and r['days']==days]
    comparisons={}
    for a,b,field,scale in [('sudden60','ramp60','losses',False),('ramp60','late_equal_cost60','losses',False),
                            ('i80-A-positive','i80-unknown-positive','ever_changed',True),
                            ('i80-A-positive','i80-A-known','ever_changed',True),
                            ('crowd-none','crowd-messages-only','expressed',True),
                            ('crowd-none','crowd-no-shock','attended',True)]:
        comparisons[f'{a} minus {b}: {field}']=paired(select(a),select(b),field,scale)
    for case in ('severe80','i80-A-positive','ramp60'):
        for m in ('v2','v3.0'):
            comparisons[f'{case}: v3.1 minus {m} change_pp']=paired(select(case),select(case,m),'ever_changed')
    (OUT/'paired-comparisons.json').write_text(json.dumps(comparisons,indent=2))
    chosen=('sudden60','ramp60','late_equal_cost60','pulse60')
    for field,index in [('burden',1),('distress',2)]:
        series=[(c,[curves[c][d][index]/curves[c][d][3] for d in range(30)]) for c in chosen]
        chart(OUT/f'{field}.svg',f'Gerçek günlük örnekler: {field}',series,field)
    replay_examples()
    write_report(runs,groups,agg,validation,comparisons,special,protocol)
    if (OUT/'followup/execution.json').exists():
        from .character_study_addenda import build
        build()
    print(json.dumps({k:validation[k] for k in ('completed_runs','raw_files_verified','actual_agent_day_rows','total_transitions','v31_core_changes')},indent=2))


def replay_examples():
    import tempfile
    from .character_study import catalog,run_case,RAW
    results=[]
    for name in ('source-aligned','i80-A-positive','crowd-same-place-split','contract-repeat'):
        case=next(c for c in catalog() if c['name']==name)
        old=RAW/f'{name}-n100-s0-v3.1-d30'
        with tempfile.TemporaryDirectory(dir=RAW) as tmp:
            run_case(case,raw_root=Path(tmp))
            new=Path(tmp)/old.name
            hashes={}
            for file in ('daily.jsonl.gz','trace.json.gz','state.json.gz'):
                with gzip.open(old/file,'rb') as f:a=f.read()
                with gzip.open(new/file,'rb') as f:b=f.read()
                assert a==b, f'Exact replay failed: {name}/{file}'
                hashes[file]=hashlib.sha256(a).hexdigest()
            results.append({'case':name,'exact_uncompressed_daily_trace_and_state':True,'sha256':hashes})
    (OUT/'replays.json').write_text(json.dumps(results,indent=2))
    return results


def write_report(runs,groups,agg,validation,comparisons,special,protocol):
    def rr(name,model='v3.1',n=100,d=30):return [r for r in runs if r['case']==name and r['model']==model and r['population']==n and r['days']==d]
    def pct(name,field='ever_changed',model='v3.1',n=100,d=30):return st.mean(100*r[field]/r['population'] for r in rr(name,model,n,d))
    primary=[r for r in runs if r['model']=='v3.1' and r['population']==100 and r['days']==30]
    def gr(case,group):return [g for g in groups if g['case']==case and g['group']==group and g['model']=='v3.1' and g['population']==100 and g['days']==30]
    probe_rows=[]
    for case in ('source-aligned','source-opposed','source-ordinary','source-same_group','source-wealthy','peer-authority-text'):
        probe_rows.append([case]+[f"{st.mean(g['probe_view_delta'] for g in gr(case,group)):.3f}" for group in GROUPS])
    extra_path=OUT/'followup/execution.json'
    extra_runs=json.loads(extra_path.read_text())['runs'] if extra_path.exists() else 0
    lines=['# v3.1 karakter araştırması — ayrıntılı rapor','',
        '## Yönetici özeti',
        f"**{len(runs)} ana + {extra_runs} keşif amaçlı ek = {len(runs)+extra_runs} koşu; {len(protocol['cases'])} ana senaryo. Davranış kodu ve katsayıları değiştirilmedi.** Karakter tarifi ölçüt olarak korundu, sonuçlar o tarife uysun diye model düzeltilmedi.",
        'Bu çalışma kod içi doğrulama ve kontrollü simülasyon araştırmasıdır. Gerçek insan psikolojisinin, ideolojilerin veya toplumların bilimsel doğrulaması değildir.',
        f"Ana kol: 55 senaryo × 8 tohum × 100 kişi × 30 gün = {len(primary)} koşu. Ek olarak 48 tarihsel v2/v3.0 karşılaştırması, 8 adet 1000 kişilik ölçek kontrolü ve 12 adet 180 günlük uzun ufuk koşusu yapıldı.",
        'Başlıca sonuç: kaynak kapıları, ayrı destek çekme ve katılım ayrımı çalışıyor; fakat iletişim karakterleri ve ideolojinin içeriği eksik. Kitle mekanizması gerçek mekândan çok buluşma kaydını sayıyor. Düşük geçiş oranını tek başına başarı saymak yanlış.',
        '', '## 1. Araştırma sınırı ve kaynaklar',
        '[Kullanıcının altı karakter sözleşmesi](../docs/six-character-contract.md), motor, dynamics, appraisal, collective ve üç dondurulmuş profil okundu. Altı oran ve kişiler arasındaki heterojen örneklenmiş özellikler korundu. [Dondurulmuş protokol](character-study/protocol.json) kaynak SHA256 değerlerini, bütün koşuları ve müdahale sınırlarını içerir.',
        'Yeni mekanizma, API, panel veya genel amaçlı araştırma platformu kurulmadı; sabit deney betiği ve kayıt analizörü eklendi. %20–30 veya başka bir sonuca göre katsayı ayarlanmadı.',
        '', '## 2. Deney düzeni ve karıştırılmaması gerekenler',
        '- Ana senaryolar: ekonomik doz/zamanlama; atıf × fayda; kaynak rolü/çelişkili açıklamalar; gerçek/olmayan katılım; yönetici–zengin bağımlılığı.',
        '- Kaynak mikro-deneylerinde bütün kollara aynı kontrollü bağlantılar ve kamuya açık başlangıç kaynak bilgisi verildi (güven .8, gecikme 10 dakika); kişilik ve ekonomik değerler değiştirilmedi. Her grupta tek bir hedef var. Bu ağ, doğal ağla sonuç oranı karşılaştırması değildir.',
        '- Kaynak mikro-deneylerinde Wait politikası, okumayı ve günlük dinamikleri bırakıp otomatik eylemi durdurur. Zorunlu yalnız/iki kişi/ayrılma kalabalık kontrolleri de Wait kullanır. Diğer ana kollar özerk referans politikayı kullanır. Zorlanan katılım karakterin bunu kendisinin seçeceğini kanıtlamaz.',
        '- Aynı tohumlarda ortak fiziksel/kişilik başlangıç hashleri eşit. Yeni/eski zihinsel durum şemalarının aynı olduğu iddia edilmedi. Mesajın olumlu olması doğrulanmış ekonomik fayda gerçekleştiği anlamına gelmez.',
        '- Ani %60 ve kademeli toplam %60 aynı son fiyata gider ama toplam ödenen maliyetleri eşit değildir. late_equal_cost60 kolu, kademeli kolun 30 günlük maliyetini de eşler. Bu müdahale eşlemesidir, davranış katsayısı ayarı değildir.',
        '- Yüzdeler tohum başına kişi oranlarının ortalamasıdır. Aralıklar tohum min–maks; paired-comparisons dosyasındaki bootstrap yalnız tohum belirsizliğidir, toplumsal olasılık değildir. 1000 kişilik iki tohum keşifseldir.',
        '', '## 3. Bütün ana senaryoların sonuçları',
        'Geçiş = dönem içinde en az bir kez siyasi kutup değiştirme. Destek çekme ayrı; katılım ayrı; temel yönelim ayrı. Gösterilenler nüfus yüzdesidir.']
    selected=[a for a in agg if a['model']=='v3.1' and a['population']==100 and a['days']==30]
    lines+=table(['Senaryo','Geçiş ort. % [min–maks]','Destek çekme %','Katılım %','Ortak ifade %','Reddedilen müdahale'],[
        [a['case'],f"{a['ever_changed']['mean_percent']:.2f} [{a['ever_changed']['min_percent']:.0f}–{a['ever_changed']['max_percent']:.0f}]",
         f"{a['withdrawn']['mean_percent']:.2f}",f"{a['attended']['mean_percent']:.2f}",f"{a['expressed']['mean_percent']:.2f}",a['imposed_rejected']] for a in selected])
    lines+=['','Reddedilen müdahaleler gizlenmedi: yanlış yöneticiye sözleşme iptali gibi bilinçli geçersiz girişler ile bütçeden reddedilen gerçek çağrılar [doğrulama dosyasında](character-study/validation.json) eylem türüne göre ayrıdır. Planlanmış gönderimi gerçekleşmiş iletişim saymadık.',
        '', '## 4. Ani / kademeli şok: neyi gösteriyor?',
        f"Ani %60 kolunda ortalama siyasi geçiş %{pct('sudden60'):.2f}; kademeli kolda %{pct('ramp60'):.2f}. İkisinde de atıf veya alternatif tanıklığı otomatik verilmedi. Sıfır siyasi geçiş, kişilerin rahatsız olmadığı anlamına gelmez.",
        'Gerçek günlük zarar/yük/rahatsızlık kayıtları:',
        '![Günlük yük](character-study/burden.svg)',
        '![Günlük rahatsızlık](character-study/distress.svg)',
        'Zarar başlangıç giderine göre ölçülüyor; referans gider/beklenti öğrenilerek yenilenmiyor. Rahatsızlık, birikmiş yükün 1’de kırpılmış hali. Bu nedenle farklı ekonomik yollar aynı doygun rahatsızlık değerine ulaşabilir. **Bu, alışma psikolojisinin uygulandığı anlamına gelmez.**',
        'Maliyet-eşlenmiş kol da birikim/unutma ve olay zamanlaması farklarını içerir. Bu farkları otomatik “alışma etkisi” diye adlandırmak yanlış olur.',
        '', '## 5. Kaynak ve karakter kapıları',
        'Aşağıdaki hücreler her grubun tek hedefindeki normal konu görüşünün 50’den değişimi: 8 tohum ortalaması, 0–100 görüş puanı. Bunlar bütün grubun ortalama fikir değişimi değildir.']
    lines+=table(['Kaynak']+[NAMES[g] for g in GROUPS],probe_rows)
    lines+=['',
        'İlk iki kesimde akran/diğer halk grubunun doğrudan fikir etkisinin sıfır olması ve mevkili kaynağın farklı etkisi birlikte ölçüldü. Mevkili orijinal kaynağın aracıyla yayılması temel motor testleriyle korunuyor. Metne “mevkiliyim” yazmak rol değiştirmiyor; kimlik motor tarafından doğrulanıyor. Gerçek dünyadaki sahte kimlik problemi burada modellenmiyor.',
        'Gözlemcinin mevkili konu etkisi, yüksek temel yönelim direncine rağmen mevcut. Bu “bağımsız analiz yapan gözlemci” sözleşmesinin tamamının uygulanmadığına somut karşı örnek. Gözlemcilerin hiç kalabalığa katılmaması ise referans politikada açık dışlama; ölçülmüş psikolojik direnç değil.',
        '', '## 6. Atıf ile alternatif faydası',
        f"Ağır şok + A atfı + olumlu B tanıklığı: ortalama %{pct('i80-A-positive'):.2f} siyasi geçiş. Aynı tanıklık, belirsiz atıfla %{pct('i80-unknown-positive'):.2f}; A atfı fakat yalnız bilinirlikle %{pct('i80-A-known'):.2f}.",
        'Mevcut-kutup atfı başlangıçta A’yı destekleyen iki ağ çapasına yönelik A atfıdır; bütün nüfusun gizli bağlılığına göre kişiselleştirilmiş suçlama yok. Yayılım sonrasında her okuyucu kendi eriştiği bilgiyle değerlendiriliyor.',
        'Yöneticiye atıf ile A’ya atıf semantik olarak aynı değildir: kişinin bilinen kamu kutbu değişirse yöneticiyi kutba bağlama da değişebilir. Bu farkı tek bir katsayının etkisi diye yorumlamıyoruz.',
        '', '## 7. Altı grup ayrı ayrı',
        'Ağır şok + A atfı + olumlu alternatif kolu; grup içi yüzdeler:']
    lines+=table(['Grup','Geçiş %','Destek çekme %','Temel yönelim değişim sayısı','Son özel sadakat'],[
        [NAMES[g],f"{st.mean(100*x['ever_changed']/x['n'] for x in gr('i80-A-positive',g)):.2f}",
         f"{st.mean(100*x['withdrawn']/x['n'] for x in gr('i80-A-positive',g)):.2f}",
         sum(x['core_changes'] for x in gr('i80-A-positive',g)),f"{st.mean(x['mean_loyalty'] for x in gr('i80-A-positive',g)):.3f}"] for g in GROUPS])
    lines+=['',
        '- **Güç yanlısı:** mevkili kapısı korunuyor; hız/sıklık ve değişen mevki/para gücünü takip eden strateji yok. Gizli güç tersine döndüğünde tepki vermemek doğru bilgi sınırıdır; mevkileri izleme özelliğinin doğrulandığı anlamına gelmez.',
        '- **Muhalif:** kaynak simetrisi var; dinamik zıtlık ilişkisi yok. B başlangıcı, karşı grubun bütün davranışlarına muhalefet eden bir karar politikası değildir.',
        '- **Burjuva:** yetki ve çıkış maliyetleri mevcut. Bir geçiş deterministik ve yerel gerekçeli olabilir ama bu, kapsamlı makam/kurum/ittifak çıkar hesabı yaptığı anlamına gelmez. Halkçı alt tip ve bastırılma yok.',
        '- **Zengin:** yönetici bağımlılığı gerçek eylemle sınandı. Rekabet ve işveren–halk gelir akışı yok; employer alanı ekonomik etkiyi kendi başına oluşturmaz.',
        '- **Huzursuz:** özerk katılım ve kısa süreli kolektif ifade var; her isyan/koalisyon veya yavaş-hızlı iletişim rejimi yok. Tarafsız başlangıç ile ilk partiye geçiş genel kuralları hâlâ ayrı inceleme gerektiriyor.',
        '- **Gözlemci:** az çıkış bağlantısı var, gelen erişim aynı ölçüde kısıtlı değil. Temel yönelim v3.1’de bütün gruplarda donuk; gözlemciye özgü muhakeme kanıtı olarak kullanılamaz.',
        '', '## 8. Kitle davranışında mantıklı ve sorunlu sonuçlar',
        f"Yalnız davet/katılım engeli kolunda ortak ifade %{pct('crowd-messages-only','expressed'):.2f}; zorunlu tek katılımcıda %{pct('crowd-solo','expressed'):.2f}; iki gerçek katılımcıda %{pct('crowd-two','expressed'):.2f}.",
        f"Aynı yer ve saatte iki ayrı buluşma kaydına bölünmüş iki gerçek katılımcıda ifade %{pct('crowd-same-place-split','expressed'):.2f}. Bu kayıt-id bağımlılığı, gerçek fiziksel birlikte bulunma modelinin sınırını gösteriyor: aynı meydan/aynı zaman tek başına kayıtları birleştirmiyor.",
        f"Şoksuz özerk çağrı kolunda katılım %{pct('crowd-no-shock','attended'):.2f}; şoklu çağrıda %{pct('crowd-none','attended'):.2f}. Mevkili açıklaması ekonomik öfke olmadan da katılım doğurabilir. Bu otomatik mantıksızlık değildir; fakat katılımın hangi amaçla yapıldığı çok zayıf modelleniyor.",
        'Ayrılan ve biten buluşmalarda ortak güç sıfırlanıyor; bütün kapalı buluşmalar temizlendi. Ancak güç endeksi psikolojik geri besleme veya kuruma etki hesabı değil, kişi sayısından türetilen bir çıktı. “Kitle psikolojisi bütünüyle uygulandı” denemez.',
        '', '## 9. Ekonomik ve kurumsal kontroller',
        'Yanlış yönetici iptali reddedildi; doğru yönetici gelir azaltabildi. Baskı, kamu desteği ile özel sadakatin farklı kalabildiğini gösterir. Bu, bütün halka baskı modeli değil; başlangıçta yöneticiye bağımlı zengin kapsamıdır.',
        'Önemli ölçüm sınırı: losses, gelir iptalinin bir seferlik gelir farkını kaydeder; sonraki her gün vazgeçilen geliri losses’a tekrar eklemez. Bu yüzden sözleşme senaryosunda losses toplamını bütün ekonomik maliyet diye okumamak gerekir. Gerçek birikimli sonuç için eşleştirilmiş tasarruf farkına da bakılmalı. [Hedef gelir/tasarruf kayıtları](character-study/special-probes.json) saklandı.',
        f"Aşırı %900 fiyat artışı kolunda ortalama %{pct('extreme900','negative_savings'):.2f} kişi negatif tasarrufa indi. Negatif tasarruf iflas, işsizlik veya erişim kaybı üretmiyor. Bu kol sınır testi, gerçekçi kriz tahmini değildir.",
        '', '## 10. Uzun ufuk ve ölçek',
        '180 gün koşuları üç tohumla, son müdahale bittikten sonra eski tanıklığın etkisini de izler. Sıfır geçişi sonsuz imkânsızlığın deneysel kanıtı saymadık; tarafsızlık aday seçiminde A yanlılığı ve eşik kapıları koddan ayrıca görülebilir. Olumlu fayda tanıklığının son kullanma tarihi yok; güven güncellenmezse eski ifade uzun süre kararda kalabilir.',
        '1000 kişilik dört senaryo yalnız iki tohumla çalıştırıldı. Kitleye verilen başlangıç çağrısı yine iki temasla sınırlı: bu kişi-başı eşit iletişim dozu değildir; oran farkını yalnız nüfus etkisi diye açıklayamayız.']
    extra=[a for a in agg if a['model']=='v3.1' and (a['population']==1000 or a['days']==180)]
    lines+=table(['Senaryo','N','Gün','Tohum','Geçiş %','Destek çekme %','Katılım %'],[
        [a['case'],a['population'],a['days'],a['n_seeds'],f"{a['ever_changed']['mean_percent']:.2f}",f"{a['withdrawn']['mean_percent']:.2f}",f"{a['attended']['mean_percent']:.2f}"] for a in extra])
    lines+=['','## 11. Eski sürümlerle eşleştirilmiş karşılaştırma',
        'Aynı fiziksel/kişilik başlangıcı ve senaryo. Tarihsel profiller açıkça yüklendi; v2/v3.0 sessizce v3.1’e yükseltilmedi. Sonuçlar değişen mekanizmaların toplam etkisidir; tek parametreye nedensel pay biçmiyoruz.']
    lines+=table(['Senaryo','v2 geçiş %','v3.0 geçiş %','v3.1 geçiş % (aynı 4 tohum)'],[
        [c,f"{pct(c,model='v2'):.2f}",f"{pct(c,model='v3.0'):.2f}",f"{st.mean(100*r['ever_changed']/r['population'] for r in rr(c) if r['seed']<4):.2f}"] for c in ('none','sudden60','severe80','ramp60','i80-A-positive','i80-unknown-known')])
    lines+=['','## 12. Kanıt bütünlüğü ve açıklanabilirlik',
        f"{validation['raw_files_verified']} ham dosyanın boyutu ve SHA256 değeri, {validation['actual_agent_day_rows']:,} gerçek ajan-gün gözlemi, {validation['total_transitions']} siyasi geçiş kaydı denetlendi. Geçmiş durumlar finalden doldurulmadı.",
        f"{validation['transitions_with_structured_appraisal']} geçişte yapılandırılmış appraisal var; {validation['transitions_without_structured_appraisal']} eski geçişte bu şema yok. Mevcut tanıklık referansları ilgili kişinin o anda öğrenmiş olduğu mesaj/deneyimlerle eşleşti; olmayan tarihsel referanslar üretilmedi. v3.1 kamu başlığı uyumsuzluğu {len(validation['v31_public_header_mismatches'])}; tek kişide kolektif ifade hatası {validation['solo_expression_errors']}. Bu, kararın insan psikolojisine uygunluğunu değil kayıt içi erişilebilirliğini doğrular.",
        f"Tam seed-0 snapshotlarından {validation['archived_provider_observations_checked']} sağlayıcı gözlemi ayrıca kontrol edildi; katılmayanın kalabalık sayısını gördüğü gözlem bulunmadı. Diğer tohumlarda bütün sağlayıcı çağrılarının saklandığı iddia edilmiyor; günlük durumlar, mesajlar, kararlar ve olay izleri saklandı.",
        'Dört farklı aileden seed-0 koşusu ayrıca tam tekrarlandı: günlük kayıt, olay izi ve tam snapshot sıkıştırılmamış içerikleri arşivle birebir eşit. Bunlar dört yeni bağımsız örnek değil, tekrar üretim kontrolüdür. [Tekrar hashleri](character-study/replays.json).',
        'Yeni ölçüm/plan testleriyle toplam 107 test çalıştırıldı: [tam çıktı](character-study-tests.txt). Yeşil test paketi, karakter kabul tablosunun hepsinin başarılı olduğu anlamına gelmez. [11×6 güncel matris](character-study/feature-matrix.md), [kabul sonuçları](character-study/acceptance.md) ve [yöntem](../docs/character-study-method.md) ayrıca okunmalıdır.',
        'Somut geçiş örnekleri, skor/eşik ve erişilmiş kanıt kimlikleri: [examples.json](character-study/examples.json). Bütün grup sonuçları: [groups.csv](character-study/groups.csv); koşular: [runs.csv](character-study/runs.csv).',
        '', '## 13. Karar: ne korunuyor, neyi çözülmüş sayamayız?',
        '**Korunan/örneklerde doğrulanan:** oranlar ve kimlikler; ilk iki grubun kaynak kapıları; ekonomik zarar–atıf–fayda ayrımı; destek çekmenin ayrı olması; yönetici→zengin yetki yönü; davet ile katılımın ayrılması; yalnız kişinin kolektif güç kazanmaması.',
        '**Tarifle çelişen veya dar temsiller:** gözlemcinin sıradan mevkili etkilenmesi; bütün büyük gruplarda ortak iletişim bütçesi/gecikme rejimi; gerçek mekân yerine buluşma-id’sine bağlı güç; tarafsızlarda tek A aday seçimi; desteği geri kazanmanın referans politikada ayrı bir yolu olmaması.',
        '**Henüz uygulanmamış/kanıtsız:** alışma, ideolojinin içeriksel değişimi, stratejik senaryo yönetimi, halkçı azınlık, zengin rekabeti/işveren gelir ilişkisi, kapsamlı isyan dinamikleri ve geçişlerin gerçekçi zaman/oran ölçeği.',
        '**Önerilen sıra:** önce çıktı anlamlarını ve kabul sözleşmelerini sabitlemek; sonra mekân/id ve tarafsız aday sorunlarını ayrı küçük düzeltmelerle ele almak; alışma ve ideoloji içeriğini ayrıca tanımlamak. Mevcut araştırma sırasında bunlar düzeltilmedi. Araştırma, “oranı düşürme” değil karakter ihlallerini görünür kılma amacı taşıdı.',
        '', '## Tekrar üretim', '```bash','python -m unittest discover -s tests -v','python -m society.character_study','python -m society.character_study_followup','python -m society.character_study_report','```',
        '[Dondurulmuş kaynak arşivi](character-study/frozen-source.zip) · [Son kontroller](character-study/final-checks.json).',
        'Model kaynakları ve protokol değişirse mevcut araştırma dizinine karışık sonuç yazılmaz; sabit betik protokol uyuşmazlığında durur. Aynı protokolde tamamlanan koşular atlanarak devam edilir. Ham günlük veriler/snapshotlar runs/character-study altında Git dışında tutulur.']
    Path('reports/character-study-report.md').write_text('\n'.join(lines)+'\n')
    acceptance=[
        ('Başlangıç oranları/kimlik','korunuyor','508 koşuda sabit grup ve trait denetimi; grup oranları üretim/testte doğrulandı'),
        ('İlk iki grup: akranla normal konu değişimi','korunuyor','aynı ağdaki kaynak mikro-deneyi; akran delta=0'),
        ('İlk iki grup: kendi/karşı mevkili ayrımı','korunuyor','normal konu mikro-deneyi + kaynak kapısı kodu; bütün ideoloji içeriği değil'),
        ('Gözlemci: bağımsız muhakeme','kısmen korunuyor','temel yönelim donuk, normal mevkili konu etkisi var; özel analitik politika yok'),
        ('Hızlı/yavaş/patlamalı iletişim','uygulanmamış','ortak bütçeler/gecikme aralıkları; bazı grup dereceleri farklı ama hız rejimi yok'),
        ('Ekonomik öfke tek başına ideoloji değiştirmesin','korunuyor','v3.1 core değişimi 0; bu aşamada açıkça dondurulmuş, ideoloji modeli değil'),
        ('İdeoloji gerekçeyle değişebilsin','uygulanmamış','kullanıcının seçtiği ilk aşamada içerik tasarımı ertelendi'),
        ('Destek çekme / parti değişimi ayrı','kısmen korunuyor','bağımsız eylem var; politika nedensel atıf şartı koyuyor, geri kazanım yolu eksik'),
        ('Sorumluluk ve alternatif bilinirliği ayrımı','korunuyor','faktöriyel ana koşular ve mevcut testler; kaynak anlatısı doğru sayılmadı'),
        ('Yönetici→zengin bağımlılığı','korunuyor','doğru/yanlış yönetici karşılaştırması; ters yetki verilmedi'),
        ('Burjuva stratejisi ve halkçı istisna','uygulanmamış','yerel sayısal neden var, kapsamlı çıkar/kurum stratejisi yok'),
        ('Zengin rekabeti / işçi gelir bağı','uygulanmamış','employer kaydı davranış veya gelir akışı değildir'),
        ('Davet gerçek katılım sayılamaz','korunuyor','mesaj-only ve yalnız kontrolleri, gerçek katılım olayları'),
        ('Aynı fiziksel yer/zaman kolektif güç','bozulmuş','iki buluşma kaydı aynı yerde/zamanda ayrı sayılıyor; somut sınır karşı örneği'),
        ('Kitle ayrılınca güç söner','korunuyor','ayrılma/bitiş ve bütün kapanmış buluşmalar kontrol edildi'),
        ('Huzursuz: kapsamlı destekli isyan','kısmen korunuyor','katılım/ortak ifade var; koalisyon ve kurumsal sonuçlar yok'),
        ('Alışma / beklenti referansı','uygulanmamış','eşit son fiyat ve eşit toplam maliyet kolları var; öğrenen referans gider yok'),
        ('Tarafsızların her iki alternatifi seçebilmesi','bozulmuş','none için A seçiliyor; B kanıtı karşılaştırmalı seçilmiyor'),
        ('Oranların gerçek toplumla doğruluğu','kanıt yok','bu simülasyon içi çalışma, ampirik kalibrasyon değil')]
    (OUT/'acceptance.md').write_text('# Karakter kabul sonuçları\n\n'+ '\n'.join(table(['Sözleşme','Durum','Kanıt / sınır'],acceptance))+'\n\nTam 11×6 tarif matrisi: [tarihsel ayrıntı](../six-character-audit-details.md). Bu tablo v3.1 araştırmasının güncel, kapsamı açık kabul sonuçlarıdır.\n')


if __name__=='__main__':main()
