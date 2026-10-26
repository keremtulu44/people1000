"""Analyze recorded diagnostics, never substitute final states for past states."""
import csv
from collections import defaultdict,Counter
import gzip
import json
from pathlib import Path
import statistics
import re

from .diagnosis import OUT, ROOT, summary, write_csv
from .experiments import digest
from .behavior import load_legacy_profile as load_profile


def number(v):
    if v=='':return None
    try:return float(v)
    except (ValueError,TypeError):return v


def build():
    rows=[];runs=[]
    for label in ('n100','n1000','n100-probe'):
        rows += [{k:number(v) for k,v in r.items()} for r in csv.DictReader((OUT/f'groups-{label}.csv').open())]
        runs += [{k:number(v) for k,v in r.items()} for r in csv.DictReader((OUT/f'runs-{label}.csv').open())]
    groups=defaultdict(list);conditions=defaultdict(list);by_run=defaultdict(list)
    for r in rows:
        key=(int(r['population']),r['shock'],int(r['announcement']),r['ablation'],int(r['peer_probe']),r['group'])
        groups[key].append(r);by_run[r['run_id']].append(r)
    metric_names=('change_rate','first_change_mean_days','return_rate_among_changed','topic_change_rate','mean_strength_gap',
        'mean_alignment_distance','core_changed_agents','loss_mean','loss_min','loss_max','evidence_economic','evidence_distrust','evidence_peer',
        'evidence_relief','evidence_unattributed','switches_without_authority_message','switches_without_any_message')
    group_summary=[];stats={}
    for key,subset in sorted(groups.items()):
        stats[str(key)]={k:summary([r[k] for r in subset if r[k] is not None]) for k in metric_names}
        group_summary.append(dict(zip(('population','shock','announcement','ablation','peer_probe','group'),key))|
            {'seed_count':len(subset),'switches_mean':statistics.mean(r['switches'] for r in subset),'changed_agents_mean':statistics.mean(r['changed_agents'] for r in subset),
             'changed_agents_min':min(r['changed_agents'] for r in subset),'changed_agents_max':max(r['changed_agents'] for r in subset),
             **{k+'_mean':stats[str(key)][k]['mean'] for k in metric_names},
             'change_rate_ci95':json.dumps(stats[str(key)]['change_rate']['ci95']),
             'unchanged_censored_mean':statistics.mean(r['unchanged_censored'] for r in subset)})
    totals=[]
    for r in runs:
        subset=by_run[r['run_id']]
        totals.append({**r,'rate':r['changed_agents']/r['population'],
            'returns':sum(g['returned_agents'] for g in subset),
            'core_changed_agents':sum(g['core_changed_agents'] for g in subset)})
        conditions[(int(r['population']),r['shock'],int(r['announcement']),r['ablation'],int(r['peer_probe']))].append(totals[-1])
    condition_summary=[]
    for key,subset in sorted(conditions.items()):
        st=summary([r['rate'] for r in subset])
        condition_summary.append(dict(zip(('population','shock','announcement','ablation','peer_probe'),key))|
            {'seeds':len(subset),'rate_mean':st['mean'],'rate_median':st['median'],'rate_min':st['min'],'rate_max':st['max'],
             'rate_sd':st['sd'],'rate_ci95':json.dumps(st['ci95']),
             'switches_mean':statistics.mean(r['switches'] for r in subset),'returns_mean':statistics.mean(r['returns'] for r in subset)})
    indexed={(int(r['population']),int(r['seed']),r['shock'],int(r['announcement']),r['ablation'],int(r['peer_probe'])):r for r in totals}
    paired=[]
    for key,subset in sorted(conditions.items()):
        pop,shock,ann,abl,probe=key
        if abl=='none':continue
        differences=[]
        for r in subset:
            control=indexed[(pop,int(r['seed']),shock,ann,'none',probe)]
            differences.append(r['rate']-control['rate'])
        paired.append({'population':pop,'shock':shock,'announcement':ann,'ablation':abl,'peer_probe':probe,
            **summary(differences),'positive':sum(x>0 for x in differences),'zero':sum(x==0 for x in differences),'negative':sum(x<0 for x in differences)})
    announcement_effects=[]
    for pop in (100,1000):
        seeds=sorted({int(r['seed']) for r in totals if r['population']==pop and not r['peer_probe']})
        for shock in ('none','mild','moderate','severe'):
            values=[indexed[(pop,seed,shock,1,'none',0)]['rate']-indexed[(pop,seed,shock,0,'none',0)]['rate'] for seed in seeds]
            announcement_effects.append({'population':pop,'shock':shock,**summary(values),
                'positive':sum(x>0 for x in values),'zero':sum(x==0 for x in values),'negative':sum(x<0 for x in values)})
    # Every NEW transition has the contemporaneous snapshot. Attribute numerical
    # components at the actual threshold; do not claim these are independent causes.
    arithmetic=defaultdict(Counter);transition_count=0;examples=[];profile_hashes=set()
    for r in runs:
        if r['peer_probe']:continue
        key=f"n{int(r['population'])}:{r['shock']}:ann{int(r['announcement'])}:{r['ablation']}"
        with gzip.open(r['transition_file'],'rt') as f:
            for line in f:
                e=json.loads(line);p=e['payload'];d=p['diagnostic'];transition_count+=1
                c=arithmetic[key];c['transitions']+=1
                c['without_messages']+=not d['messages_learned']
                c['without_authority_message']+=not any(m.get('source_group')=='authority' for m in d['messages_learned'])
                c['returning']+=d['returning'];c['pressure_nonzero']+=d['before']['pressure']!=0
                c['attraction_equals_035']+=abs(d['attraction']-.35)<1e-10
                c['private_loyalty_over_half']+=d['before']['private_loyalty']>.5
                c['known_alt_without_measured_advantage']+=d['attraction']>=.35 and not any(m.get('topic')=='public_support' for m in d['messages_learned'])
                assert abs(sum(d['accumulated_components'].values())-p['accumulated_evidence'])<1e-8
                assert all(m['learned_at']<=e['time'] for m in d['messages_learned'])
                for term in ('economic','distrust','peer'):
                    c['instant_necessary_'+term]+=(d['decision_score']-d['accumulated_components'][term]*d['attraction']<=p['threshold'])
                if len(examples)<4 and r['ablation']=='none' and r['shock']=='severe':examples.append(e)
    write_csv(OUT/'condition-summary.csv',condition_summary);write_csv(OUT/'group-summary.csv',group_summary)
    write_csv(OUT/'paired-ablation-effects.csv',[{k:(json.dumps(v) if isinstance(v,list) else v) for k,v in r.items()} for r in paired])
    write_csv(OUT/'paired-announcement-effects.csv',[{k:(json.dumps(v) if isinstance(v,list) else v) for k,v in r.items()} for r in announcement_effects])
    # Pairing/hash and earlier experiment reproduction checks across available seeds.
    hash_groups=defaultdict(set)
    for r in runs:hash_groups[(r['population'],r['seed'])].add(r['initial_hash'])
    assert all(len(v)==1 for v in hash_groups.values())
    old={(int(r['population']),int(r['seed']),r['arm']):int(r['alignment_changes']) for r in csv.DictReader(open('reports/behavior-experiment-results.csv'))}
    matches=[]
    for r in totals:
        if r['shock']=='severe' and r['ablation']=='none' and not r['peer_probe']:
            arm='B' if r['announcement'] else 'A'
            expected=old[(int(r['population']),int(r['seed']),arm)]
            matches.append({'run':r['run_id'],'prior_switches':expected,'new_switches':int(r['switches']),'equal':expected==r['switches']})
    protocol_checks=[]
    for label in ('n100','n1000','n100-probe'):
        protocol=json.loads((OUT/f'protocol-{label}.json').read_text())
        profile_hashes.add(protocol['profile_hash'])
        protocol_checks.append(json.loads((OUT/f'execution-{label}.json').read_text()))
    assert len(profile_hashes)==1 and digest(load_profile()) in profile_hashes
    data={'completed_runs':len(runs),'new_transitions_examined_excluding_probe':transition_count,
        'legacy':json.loads((OUT/'legacy-audit.json').read_text())['counts'],
        'group_statistics':stats,'paired_ablations':paired,'paired_announcements':announcement_effects,
        'threshold_arithmetic':{k:dict(v) for k,v in arithmetic.items()},'examples':examples,
        'initial_world_hashes_equal':True,'prior_baseline_reproduction':matches,'profile_checks':protocol_checks,
        'confidence_interval_note':'Normal approximation across seed means; n=5 exploratory only; no multiple-testing correction.'}
    boundary_path=ROOT/'n100-s0-mild-ann1-none'/'state.json.gz'
    with gzip.open(boundary_path,'rt') as f:
        boundary=json.load(f)
    boundary_updates=[e for e in boundary['log'] if e['kind']=='trust_updated']
    data['numerical_boundary_case']={'run_id':boundary['experiment_id'],
        'errors':sorted({e['payload']['error'] for e in boundary_updates}),
        'negative_updates':sum(e['payload']['new']<e['payload']['old'] for e in boundary_updates),
        'rule':'error > .1 uses binary float, no tolerance; deliberately not fixed during frozen experiment'}
    (OUT/'metrics.json').write_text(json.dumps(data,indent=2))
    build_markdown(data,condition_summary,group_summary)
    print(f'Analyzed {len(runs)} new runs; {transition_count} non-probe transitions; {len(matches)} prior-baseline comparisons.')


def build_markdown(data,conditions,groups):
    legacy=json.loads((OUT/'legacy-audit.json').read_text())
    get=lambda pop,shock,ann,abl='none',probe=0:next(r for r in conditions if (r['population'],r['shock'],r['announcement'],r['ablation'],r['peer_probe'])==(pop,shock,ann,abl,probe))
    f=lambda x:'—' if x is None else f'{x:.4f}'
    lines=['# Bağlılık değişim nedenleri — teşhis ve kalibrasyon kanıtı',
        '', '## Kapsam ve değiştirilmeyenler',
        '**Davranış profili v2.0.0 ve katsayıları değiştirilmedi. Kalibrasyon yapılmadı.** Yapısal karar denklemleri normal kolda aynıdır; yalnızca açıklanabilirlik alanları ve isimlendirilmiş ablation anahtarları eklendi.',
        f"{legacy['runs_inspected']} eski koşu ve {legacy['counts']['transitions']} eski geçiş incelendi. {data['completed_runs']} yeni 30 günlük koşu tamamlandı: 100 kişide 20 tohum × 4 şok × 2 açıklama × 4 mekanizma = 640; 1000 kişide 5 tohum aynı matris = 160; 100 kişide 20 tohum × akran açık/kapalı pozitif kontrol = 40. Toplam 840.",
        '100 kişilik ana sonuçlar 20 tohumla; 1000 kişilik sonuçlar 5 tohumla keşifsel ölçek doğrulamasıdır, aynı kesinlikte değildir. Tam matris ve geçiş kayıtlarının maliyetini sınırlamak için bu ayrım protokole baştan yazıldı.',
        'Şoklar: yok, %10 hafif, %40 orta, %80 şiddetli. Fiyat olayı dakika 60. Açıklama kollarında gün 1/8/15/22, aynı yönetici ve aynı ilk iki alıcı, beklenen zarar iddiası 0. Müdahalesiz kolda yönetici açıklaması eklenmez. Aynı tohum/başlangıç, aynı politika ve parametreler korunur.',
        '', '## 1. Eski kayıtlar neyi gerçekten gösteriyor?',
        f"Eski {legacy['counts']['transitions']} geçişin {legacy['counts']['without_authority_message']} tanesinde öğrenilmiş yönetici açıklaması yoktu. Bu, yüksek geçişi açıklama veya güven aşınmasının tek başına açıklayamayacağını gösterir; ekonomik etki ile başlangıç güveni ayrıca sınandı.",
        'Eski kayıtta geçişin eski/yeni kutbu, eşik, çekicilik, çıkış bedeli, yük, güvensizlik ve birikmiş kanıt var. Aynı handler’ın behavior_updated kaydındaki loyalty_before tarihsel özel sadakati açıkça kaydeder; bu alan kullanılabilir, gelecekteki gözlem değildir.',
        'Ancak geçiş öncesi tam konu durumu, açık destek/kutup anlık görüntüsü, tam başlangıç güven haritası, maruz kalma özeti ve kanıt bileşenleri yoktur. Bunlar son durumdan doldurulmadı; eski çıkarımda null/eksik olarak işaretlendi. Önceki bir core değişimi varsa yalnızca o kayıt raporlandı; siyasi geçiş temel yönelim değişimi sayılmadı.',
        'Her eski geçiş runs/diagnosis/legacy-transitions.jsonl.gz içinde; örnek ve kapsam reports/diagnosis/legacy-audit.json içinde. Yeni koşular eksik alanları karar anında kaydeder.',
        '', '## 2. Normal mekanizma altında şok şiddeti',
        'Oran = en az bir kere siyasi bağlılık değiştiren kişi / nüfus. Tekrar geçişler bu orana iki kere eklenmez.',
        '', '| Nüfus | Şok | Açıklama | Tohum | Değişen oran ort. | Medyan | Min–maks | Yaklaşık %95 aralık |',
        '|---:|---|---|---:|---:|---:|---|---|']
    for pop in (100,1000):
        for shock in ('none','mild','moderate','severe'):
            for ann in (0,1):
                r=get(pop,shock,ann)
                lines.append(f"| {pop} | {shock} | {ann} | {r['seeds']} | {f(r['rate_mean'])} | {f(r['rate_median'])} | {f(r['rate_min'])}–{f(r['rate_max'])} | {r['rate_ci95']} |")
    lines += ['', 'Aralıklar tohum değişkenliğinin normal yaklaşımıdır; gerçek toplum belirsizliği değildir. Özellikle 5 tohumda zayıf betimleyici aralıklardır. İlk geçiş süreleri yalnızca değişen kişilerde hesaplanır; değişmeyenler sansürlüdür ve group-summary.csv içinde ayrıca sayılır.',
        '', '## 3. Kontrollü ablation sonuçları',
        '- economic_evidence: yalnızca birikimli siyasi kanıta giren ekonomik terim sıfırdır. Gider, kayıp, burden, konu görüşü, özel sadakat ve temel yönelim kanıtı korunur. Bu nedenle “ekonomi tamamen yok” deneyi değildir.',
        '- trust_erosion: yalnızca negatif güven güncellemesi sıfırlanır; başlangıç güvensizliği ve güven toparlanması korunur. Başlangıç güveninin etkisini izole etmez.',
        '- peer: akran sinyali birikimi, akran çekiciliği/kanıtı ve akran konu iknası kapalıdır; mesajın ulaşması, kaynak tanınması ve otorite tahminleri korunur.',
        'Katsayılar sabittir. Sonraki siyasi bağlılık, aynı-kutup güven havuzu, mesajın yayımlandığı kutup ve başka kararlar değişebileceğinden ablation farkı doğrudan + dolaylı toplam etkidir. Bağımsız toplanabilir nedensel pay değildir.',
        '', '| Nüfus | Şok | Açıklama | Kapalı mekanizma | Eşleştirilmiş oran farkı ort. | Yaklaşık %95 | Negatif / sıfır / pozitif tohum |',
        '|---:|---|---:|---|---:|---|---|']
    for r in data['paired_ablations']:
        if r['peer_probe'] or r['shock'] not in ('moderate','severe'):continue
        lines.append(f"| {r['population']} | {r['shock']} | {r['announcement']} | {r['ablation']} | {f(r['mean'])} | {r['ci95']} | {r['negative']} / {r['zero']} / {r['positive']} |")
    lines += ['', 'Tüm şoklar ve açıklama farkları paired-*.csv / metrics.json içinde. Akran ana matrisi yalnızca ekonomik otorite açıklamaları içerir; public_support akran girdisi yoktur. Dolayısıyla buradaki sıfır fark, genel olarak akran mekanizmasının etkisiz olduğunu kanıtlamaz. Ayrı pozitif kontrolde aynı kamu destek mesajları her iki kola eklenir.',
        '', '| Akran pozitif kontrolü, 100 kişi | Oran ort. | Geçiş olayı ort. |', '|---|---:|---:|']
    for abl in ('none','peer'):
        r=get(100,'severe',1,abl,1);lines.append(f"| {abl} | {f(r['rate_mean'])} | {f(r['switches_mean'])} |")
    lines += ['', '## 4. Kesim bazlı teşhis (%80 şok, normal mekanizma)',
        'Aşağıdaki oranlar siyasi bağlılıktır; temel yönelim için ayrı sütun vardır. Gözlemcilerin konu görüşü değişebilirken siyasi bağlılığı/temel yönelimi değişmemiş olabilir.',
        '', '| Nüfus | Açıklama | Kesim | Değişen kişi ort. | Oran | İlk geçiş gün ort.¹ | Dönüş oranı² | Konu değişim oranı | Şiddet farkı | Temel değişen kişi |',
        '|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|']
    for r in groups:
        if r['shock']=='severe' and r['ablation']=='none' and not r['peer_probe']:
            lines.append(f"| {r['population']} | {r['announcement']} | {r['group']} | {f(r['changed_agents_mean'])} | {f(r['change_rate_mean'])} | {f(r['first_change_mean_days_mean'])} | {f(r['return_rate_among_changed_mean'])} | {f(r['topic_change_rate_mean'])} | {f(r['mean_strength_gap_mean'])} | {f(r['core_changed_agents_mean'])} |")
    lines += ['', '¹ Yalnızca değişen ajanlar; süre özeti, değişen ajanların tohum içi ortalamalarının tohumlar arası ortalamasıdır. Değişmeyen tohumlara süre=0 atanmaz. Sağ sansür nedeniyle tüm topluma ait beklenen süre değildir. ² En az bir önceki kutbuna dönen / en az bir geçiş yapan; ilk kimliğe dönmekle her önceki kutba dönüş aynı olmayabilir. Ham kesim/tohum tabloları ayrıca saklanır.',
        'Kayıp min/ortalama/maks ve açık–özel kutup farkını hesaba katan normalize mesafe group-summary.csv içindedir. Bu deneyde temel gider aynı olduğundan ek gider kaybı aynı şok altında kesimler arasında eşittir; tepki katsayıları ve gelir/birikim tamponları farklıdır.',
        '', '## 5. Kod yolundan ölçülebilir açıklama',
        '`engine._handle(behavior) → dynamics.daily → eligible` geçiş yoludur. Aşağıdakiler kayıt ve kodla doğrudan sınanabilir:',
        '1. Ekonomik etki iki kademeli birikir: burden = .90×burden + harm×duyarlılık; kanıt = .96×eski_kanıt + .08×burden + .12×güvensizlik×otorite_duyarlılığı + .05×akran − rahatlama. Süren şok iki kalıcı durum üzerinden aynı eşiklere iter.',
        '2. Alternatif kutbun yerel olarak bilinmesi tek başına .35 çekicilik sağlar. Alternatifin ekonomik olarak daha iyi olduğuna dair ayrı kanıt zorunlu değildir. Çekicilik hem kapı (≥.3) hem kanıt çarpanıdır.',
        '3. Özel sadakat azalır ama eligible koşulunda doğrudan kullanılmaz. Bu nedenle özel sadakat düşüşü siyasi geçişi tek başına açıklayan bir kapı değildir. Kamu desteği ve baskı da bu eşikte doğrudan yoktur.',
        '4. Mevcut başlangıç güveni 1’den düşükse hiç açıklama öğrenmeyenlerde de distrust terimi oluşur. Trust-erosion ablation bu başlangıç kanalını kapatmaz.',
        '5. Geçişte siyasi kanıt sıfırlanır fakat ekonomik burden sıfırlanmaz. Aynı zarar yeni kutupta da sürüyorsa kanıt yeniden hızla birikir; +.30 dönüş marjı ve 5 gün bekleme dönüşü yavaşlatır ama engellemez.',
        '6. Hoşnutsuzlarda .35×.5=.175, gözlemcilerde .35×.3=.105 çekicilik, akran girdisi olmadan .3 kapısını geçemez. Sıfır siyasi değişim yalnızca yüksek dirençten kaynaklanmaz; yapısal kapı da vardır.',
        '7. Yönetici allies sayımı kodda aynı kutuptaki bütün known kaynaklarını sayar; yalnızca kurumsal ittifakları saymaz. Bu bir semantik basitleştirmedir; bu görevde değiştirilmedi.',
        '', 'Her geçişteki katkı defteri ekonomik/güvensizlik/akran/rahatlama bileşenlerini ayrı tutar; negatif toplamın sıfıra kırpılması ve geçiş sonrası sıfırlama da izlenir. Defter karara girdi olmaz. Toplamı kaydedilmiş kanıta eşittir (kayan nokta toleransı).',
        'metrics.json threshold_arithmetic, o anda bir bileşen çıkarılsaydı eşik aşılır mıydı sorusunu yanıtlar. Bu yalnızca yerel aritmetik duyarlılıktır; bütün geçmişin değiştiği ablation yerine geçmez.',
        '', '## 6. Eksik veri ve açıklanabilirlik sınırları',
        'Yeni diagnostic kaydı geçişten önceki özel sadakat, günlük güncelleme öncesi ve karar anındaki konu görüşleri, kamu kutbu/desteği, temel yönelim, yerel ekonomik maruziyet, okunmuş mesajların teslim/öğrenme zamanları, kaynak güvenleri, o günün güven değişimleri, akran durumu, baskı, alternatif, maliyet, eşik ve dönüş koşullarını içerir.',
        'Önceki güven değişimlerinin tam olay akışı yalnızca tam snapshot saklanan tohum 0 koşullarında bulunur; diğerlerinde geçiş anı anlık görüntüsü, o günkü değişimler, mesaj geçmişi ve nihai ajan kayıtları saklanır. Geçiş öncesinin kaydedilmemiş başka iç durumları sonradan üretilmez. Tüm koşular betikle yeniden üretilebilir.',
        'İlk geçişte last_switch_day=-1000 başlangıç sentinelidir; elapsed_days değeri gerçek bin günlük maruziyet olarak yorumlanmaz. Gerçek maruziyet diagnostic_exposure alanlarında ayrı tutulur.',
        '', '## 7. Kanıtın sınırı ve kalibrasyon önerileri',
        'Ablation ve doz–yanıt sonuçları birikimli ekonomik siyasi kanıt yolunu sınar; .08 katsayısının tek başına yanlış olduğunu kanıtlamaz. Kalıcılık, zarar normalizasyonu, alternatif görünürlüğü ve eşik birlikte belirleyicidir. Başlangıç güvensizliğini güven aşınmasıyla karıştırmayın.',
        'Öneri 1: İlk sonraki kontrollü deneyde yalnızca alternatifin “bilinmesi” ile “beklenen faydasının üstün olması” koşulunu ayırın; mevcut .35 değerini keyfî azaltmayın. Gerekçe: kodda karşılaştırmalı üstünlük şartı yok ve mesaj almayan geçişler yaygın.',
        'Öneri 2: Ekonomik yükün hangi kutba atfedildiğini ve geçiş sonrası nasıl taşındığını ayrı hipotezlerle sınayın. Gerekçe: eski yük yeni kutupta da kanıt üretir; dönüş marjını rastgele artırmak nedeni gizleyebilir.',
        'Öneri 3: Başlangıç güven priörünü ve sonradan güven aşınmasını ayrı kollarla sınayın; mevcut erosion ablation başlangıç kanalını ayırmaz.',
        'Öneri 4: Akran girdisi olan/olmayan deneyleri ayırın. Boş girdi altındaki null etkiyi akran direnci katsayısına bağlamayın.',
        'Öneri 5: Hoşnutsuz/gözlemci kapılarının bilinçli varsayım mı yoksa istenmeyen kilit mi olduğunu netleştirin. Siyasi değişim yokluğunu temel yönelim değişmezliği diye sunmayın.',
        'Bu görevde hiçbir eski/yeni kalibre profil üretilmedi: **parametre değişikliği yok**. Eski profil hashleri ve koşu protokolleri karşılaştırıldı. Öneriler gelecek deneyler içindir.',
        '', '## 8. Dosyalar, testler ve tekrar üretim',
        'Kod: dynamics.py (salt teşhis defteri/anlık görüntü + ablation kapıları), engine.py (doğrulanan/saklanan ablation seçeneği), diagnosis.py (eski kayıt çıkarımı ve eşleştirilmiş koşular), diagnosis_report.py (analiz). behavior.json değişmedi.',
        'Testler: tests/test_diagnosis.py; tam paket ve gerçek sonuç reports/diagnosis-tests.txt. Eski ham artifact mevcutsa ayrıca önceki davranışla tüm ajan durumları ve geçiş zamanları karşılaştırılır; yoksa bu tek test açıkça skip olur.',
        f"Yeni normal %80 kolları önceki A/B ile {len(data['prior_baseline_reproduction'])} tohum/koşulda karşılaştırıldı; eşit sayımlar: {sum(r['equal'] for r in data['prior_baseline_reproduction'])}. Sayım eşitliği tek başına tam yörünge eşitliği değildir; bunun için ayrı regresyon testi vardır.",
        'Komutlar:', '```bash',
        'python -m society.diagnosis --legacy',
        'python -m society.diagnosis --seeds 20 --population 100',
        'python -m society.diagnosis --seeds 5 --population 1000',
        'python -m society.diagnosis --seeds 20 --population 100 --peer-probe',
        'python -m society.diagnosis --report',
        'python -m unittest discover -s tests -v > reports/diagnosis-tests.txt 2>&1',
        '```',
        'Küçük tablolar reports/diagnosis/; her yeni geçişin ayrıntıları ve son ajanlar runs/diagnosis/<run-id>/ altında sıkıştırılmıştır. Tohum 0 tam snapshotları da saklanır. Büyük veriler Git dışında; protokol ve kodla yeniden üretilebilir.',
        'RNG yalnızca başlangıçta tüketilir. Bütün eşleştirilmiş kolların ilk ajan/ağ hashleri aynı doğrulandı. Ablation sonrası akış farklılaşması hata değil müdahalenin dolaylı etkisi olabilir. Ölçümler model içi kanıttır, gerçek toplum yasası değildir.']
    group_insertion=lines.index('## 5. Kod yolundan ölçülebilir açıklama')
    cause_lines=['### Kesime göre geçişteki sayısal kanıt (100 ajan, açıklamalı %80 şok)',
        'Aşağıdaki bileşim, geçiş anındaki pozitif ekonomik/güvensizlik/akran defteridir; rahatlama ayrı negatif terimdir. Bu oranlar bağımsız nedensel paylar değildir.',
        '| Kesim | Geçiş başına ekonomik birikim | Geçiş başına güvensizlik birikimi | Geçiş başına akran birikimi | Kodla birlikte yorum |',
        '|---|---:|---:|---:|---|']
    descriptions={'power_aligned':'Ekonomik birikim + aynı-kutup güveni; düzen maliyeti daha yüksek.',
        'opposition':'Ekonomik birikim + kendi otoritesine güvensizlik; güvensizlik alternatif çekiciliğine de eklenir.',
        'authority':'Ekonomik birikim + güven; konum/yerel çevre maliyeti geçişi geciktirir.',
        'wealthy':'Ekonomik birikim + güven; kurumsal bağımlılık ek çıkış bedeli getirir.',
        'discontented':'Bu kolda siyasi geçiş yok; akran girdisi olmadan çekicilik kapısı kilitli.',
        'observer':'Bu kolda siyasi geçiş ve temel değişim yok; iki değişim türü ayrı eşiklere tabidir.'}
    for r in groups:
        if r['population']==100 and r['shock']=='severe' and r['announcement']==1 and r['ablation']=='none' and not r['peer_probe']:
            n=r['switches_mean']
            values=[f(r[k]/n) if n else '—' for k in ('evidence_economic_mean','evidence_distrust_mean','evidence_peer_mean')]
            cause_lines.append(f"| {r['group']} | {' | '.join(values)} | {descriptions[r['group']]} |")
    cause_lines += ['Aynı büyüklük ve aynı eşik dağılımı varsayılmadığından kesim farkları yalnızca kanıt miktarıyla açıklanmaz. Tohum değişkenliği, dönüşler ve özel/kamu farkları diğer tablolarda ayrıdır.', '']
    lines[group_insertion:group_insertion]=cause_lines
    insertion=lines.index('## 6. Eksik veri ve açıklanabilirlik sınırları')
    arithmetic_lines=['### Geçiş anındaki aritmetik duyarlılık',
        'Aşağıdaki yerel test, geçmişi sabit tutup yalnızca o anki birikmiş bileşeni çıkarır. Birden fazla bileşen aynı eşikte gerekli görünebilir; yüzdeler toplanamaz ve “nedensel pay” değildir.',
        '| Nüfus | Açıklama | Geçiş | Mesajsız geçiş | Ekonomik bileşen çıkarılınca eşik geçilemeyen | Güvensizlik bileşeni çıkarılınca |',
        '|---:|---:|---:|---:|---:|---:|']
    for pop in (100,1000):
        for ann in (0,1):
            a=data['threshold_arithmetic'].get(f'n{pop}:severe:ann{ann}:none',{})
            arithmetic_lines.append(f"| {pop} | {ann} | {a.get('transitions',0)} | {a.get('without_messages',0)} | {a.get('instant_necessary_economic',0)} | {a.get('instant_necessary_distrust',0)} |")
    arithmetic_lines += ['Bunların ana karşılaştırması tam-yörünge ablation tablosudur. Eşik anında küçük bir terim bile sonucu çevirebilir; bu durum onu en büyük üretici mekanizma yapmaz.', '']
    lines[insertion:insertion]=arithmetic_lines
    lines += ['', '### Yorum sınırı ve sonraki deney önceliği',
        '“Nadir” için önceden belirlenmiş şok/ufuk/kesim bazlı sayısal kabul aralığı yoktu. Bu yüzden yüksek %80 şok oranı tek başına bir katsayının yanlış olduğunu kanıtlamaz. Hafif/orta/şiddetli doz farkı ve kontrollü kanal kapatmaları birlikte değerlendirilmelidir.',
        'Ekonomik zarar normalizasyonu gider artışını esas alır; fiyat şokunda varlıklı ajan net gelirini korusa da gider artışı aynı harm değerini verir. Servet tamponu bu normalizasyonda yoktur. Kesimlere eşit zarar verilmesi kod gerçeğidir; bunun fazla değişimin nedeni olup olmadığını ayrı kırılganlık deneyi olmadan kesinleştirmiyoruz.',
        'Yeni ana matriste baskı uygulanmadı; sıfır baskı kaydı baskının genel etkisizliğini göstermez. Akran pozitif kontrolü girdi yolunu sınar, tüm sosyal ağ davranışlarının doğrulanması değildir.']
    boundary=data['numerical_boundary_case']
    lines += ['', '### İlave sayısal sınır bulgusu (bu görevde değiştirilmedi)',
        f"100 kişi/tohum 0/%10 şok/açıklamalı koşuda hata değerleri {boundary['errors']}; negatif güven güncellemesi {boundary['negative_updates']}. Matematiksel .1 sınırı ikili kayan noktada .10000000000000009 olarak oluşuyor; error > .1 dalı aşınmayı seçiyor. Bu hassasiyet yüksek %80 şok oranının açıklaması değildir, ama hafif şok güven analizinde önemlidir. Tolerans veya sayısal temsil politikası ayrı regresyonla kararlaştırılmalı; mevcut dondurulmuş koşulara geriye dönük düzeltme uygulanmadı."]
    test_text=Path('reports/diagnosis-tests.txt').read_text()
    match=re.search(r'Ran (\d+) tests',test_text)
    lines += ['',f"Son tam test paketi: {match.group(1) if match else 'bilinmiyor'} test; ham durum: {'OK' if re.search(r'^OK$',test_text,re.M) else 'başarılı olduğu doğrulanmadı'}. Sonuç dosyası değiştirilmeden saklanmıştır."]
    Path('reports/alignment-cause-audit.md').write_text('\n'.join(lines)+'\n')
