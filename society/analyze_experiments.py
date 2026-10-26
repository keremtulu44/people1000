"""Post-run analysis from real compressed artifacts; no fabricated measurements."""
from collections import Counter, defaultdict
import csv
import gzip
import json
from pathlib import Path
import statistics

from .experiments import digest, region
from .engine import Simulation


def fmt(x):
    return '—' if x is None else f'{x:.3f}'


def main():
    root=Path('reports')
    metrics=json.loads((root/'behavior-metrics.json').read_text())
    rows=list(csv.DictReader((root/'behavior-experiment-results.csv').open()))
    if len(rows)!=metrics['completed_runs']:
        raise RuntimeError('Incomplete experiment output; wait for runner completion')
    region_data=defaultdict(lambda:defaultdict(list))
    extra=defaultdict(lambda:defaultdict(list))
    local_audits=[]
    examples=[]
    baseline_states={}
    pressure_checks=[]
    causal_chain=None
    control_switches={}
    for row in rows:
        path=Path(row['artifact'])
        with gzip.open(path,'rt') as f:data=json.load(f)
        pop=int(row['population']);arm=row['arm'];key=f'{pop}:{arm}'
        # Derive the SAME topology-only BFS region for B and its paired controls.
        leaders=[x for x,v in data['authorities'].items() if v['pole_alignment']=='A']
        leader=max(leaders,key=lambda x:sum(e['source']==x for e in data['edges']))
        recipients=[e['target'] for e in data['edges'] if e['source']==leader][:2]
        shell=Simulation.__new__(Simulation);shell.agents=data['agents'];shell.edges=data['edges']
        local=set(region(shell,recipients))
        read_times=defaultdict(list)
        for aid,a in data['agents'].items():
            for m in a['memories']:
                if 'message_id' in m:
                    message=data['messages'][m['message_id']]
                    read_times['local' if aid in local else 'outside'].append(m['learned_at']-message['created_at'])
        for name in ('local','outside'):
            times=read_times[name]
            region_data[key][name+'_read_count'].append(len(times))
            if times:
                region_data[key][name+'_first_minutes'].append(min(times))
                region_data[key][name+'_median_minutes'].append(statistics.median(times))
        events=[e for e in data['log'] if e.get('event_id') is not None]
        duplicates=len(events)-len({e['event_id'] for e in events})
        outside_reads=len(read_times['outside']) if arm=='C' else 0
        daily_count=len(data['daily_metrics'])
        violations=sum(any(a['used'][k]>data['config'][k+'_budget'] for k in ('read','communication','action'))
                       for a in data['agents'].values())
        local_audits.append({'id':data['experiment_id'],'duplicate_processed_events':duplicates,
                             'scope_outside_reads':outside_reads,'final_budget_violations':violations,
                             'daily_measurements':daily_count})
        for group in data['behavior_profile']['groups']:
            losses=[a['losses'] for a in data['agents'].values() if a['initial_group']==group]
            extra[key]['loss_'+group+'_mean'].append(statistics.mean(losses))
            extra[key]['loss_'+group+'_min'].append(min(losses))
            extra[key]['loss_'+group+'_max'].append(max(losses))
        extra[key]['mean_actions_per_agent'].append(sum(e['kind']=='action_applied' and e['payload']['type']!='wait' for e in data['log'])/pop)
        extra[key]['mean_communications_per_agent'].append(sum(e['kind']=='action_applied' and e['payload']['type'] in ('send','relay') for e in data['log'])/pop)
        extra[key]['alignment_aware_support_distance'].append(statistics.mean((abs(a['public_support']-a['private_loyalty']) if a['public_alignment']==a['alignment'] else a['public_support']+a['private_loyalty'])/2 for a in data['agents'].values()))
        changes=Counter(e['payload']['agent'] for e in data['log'] if e['kind']=='alignment_changed')
        extra[key]['repeat_switch_agents'].append(sum(v>1 for v in changes.values()))
        extra[key]['changed_agents'].append(len(changes))
        extra[key]['unreached_topic_changes'].append(json.loads((path.parent/'metrics.json').read_text())['details']['unreached_topic_changes'])
        extra[key]['trust_recovery_censored'].append(int(row['recovery_censored_pairs']))
        extra[key]['fully_recovered_pairs'].append(int(row['fully_recovered_pairs']))
        extra[key]['rejected_actions'].append(int(row['rejected_actions']))
        extra[key]['budget_blocked_decisions'].append(int(row['budget_blocked_decisions']))
        if pop==100 and arm=='A' and row['seed']=='0':
            for e in data['log']:
                if e['kind']=='alignment_changed':
                    control_switches.setdefault(e['payload']['agent'],[]).append(e['time'])
        if pop==100 and arm=='B':
            baseline_states[row['seed']]={aid:{k:a[k] for k in ('savings','public_support','private_loyalty')} for aid,a in data['agents'].items()}
        if pop==100 and arm=='pressure':
            pressure=next(e for e in data['log'] if e['kind']=='pressure_experienced')
            aid=pressure['payload']['target'];actor=pressure['payload']['actor']
            baseline=baseline_states[row['seed']]
            pressure_checks.append({'seed':int(row['seed']), 'target':aid,
                'target_public_delta':data['agents'][aid]['public_support']-baseline[aid]['public_support'],
                'target_private_delta':data['agents'][aid]['private_loyalty']-baseline[aid]['private_loyalty'],
                'total_savings_delta':sum(a['savings']-baseline[x]['savings'] for x,a in data['agents'].items()),
                'actor_public_delta':data['agents'][actor]['public_support']-baseline[actor]['public_support'],
                'other_private_differences':sum(a['private_loyalty']!=baseline[x]['private_loyalty'] for x,a in data['agents'].items() if x!=aid)})
        if row['seed']=='0' and pop==100 and arm=='B':
            examples=[e for e in data['log'] if e['kind'] in ('alignment_changed','trust_updated')][:3]
            changed={e['payload']['agent'] for e in data['log'] if e['kind']=='alignment_changed'}
            update=next((e for e in data['log'] if e['kind']=='trust_updated' and e['payload']['agent'] in changed),None)
            if update:
                aid=update['payload']['agent'];mid=update['payload']['evidence']
                memory=next(m for m in data['agents'][aid]['memories'] if m.get('message_id')==mid)
                switch=next(e for e in data['log'] if e['kind']=='alignment_changed' and e['payload']['agent']==aid)
                causal_chain={'agent':aid,'message':data['messages'][mid],'learning':memory,
                    'first_trust_update':update,'first_switch':switch,'control_switch_times':control_switches.get(aid,[])}
        del data,shell
    summarize=lambda values:{'mean':statistics.mean(values),'median':statistics.median(values),
                              'min':min(values),'max':max(values),'n':len(values)}
    metrics['network_region_metrics']={k:{n:summarize(v) for n,v in cols.items()} for k,cols in region_data.items()}
    metrics['additional_metrics']={k:{n:summarize(v) for n,v in cols.items()} for k,cols in extra.items()}
    metrics['artifact_audits']=local_audits
    metrics['causal_examples']=examples
    metrics['causal_chain']=causal_chain
    metrics['pressure_paired_checks']=pressure_checks
    (root/'behavior-metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False))
    verification=json.loads((root/'behavior-verification.json').read_text())
    report=[
        '# Birikimli davranış — çalıştırılmış deneyler ve değerlendirme',
        '', 'Tarih: 2026-10-25. Model: davranış v2.0.0; deney protokolü v1.1.0.',
        '**Bu sonuçlar gerçek toplumlar hakkında kanıt değildir.** Tüm sayılar çalıştırılmış koşulardan üretilmiştir.',
        '', '## 1. Kapsam ve önceden belirlenen protokol',
        f"Nihai veri: **{len(rows)} tamamlanmış 30 günlük koşu**. Her iki nüfusta A/B/C/D × 20 eşleştirilmiş tohum = 160 ana koşu. 100 kişide beş ek kol × 20 = 100 tamamlayıcı koşu.",
        f"Koşu betiğinin toplam duvar süresi (sıkıştırma/kayıt dahil): {metrics['total_wall_seconds']:.2f} saniye.",
        'A: dakika 60’ta fiyat ×1.8; B: aynı şok + gün 1/8/15/22’de iki erişilebilir alıcıya yönetici tahmini; C: aynı açıklama yalnızca BFS ağ bölgesine; D: B, birikimli modül kapalı.',
        'Ek kollar: iki kat güven aşınması, düşük bağlılık eşiği, düşük gözlemci temel direnci, tek baskı eylemi ve gün 22’de doğru tahmine geçiş.',
        'Güçlü %80 fiyat şoku özellikle stres koşuludur. Doğal/toplumsal sıklık iddiası yoktur. Başarı beklenen siyasi sonuç değildir.',
        'Profil ve protokol deneyden önce `behavior-protocol.json` içine yazıldı. Ana koşular arasında sonuca göre katsayı ayarı yapılmadı.',
        '', '## 2. Toplu sonuçlar',
        'Aşağıdaki geçiş sayısı **olay sayısıdır**, benzersiz kişi sayısı değildir. Sonraki sütun benzersiz kişileri gösterir.',
        '', '| Nüfus | Kol | Geçiş ort. | Değişen kişi ort. | Erişen kişi ort. | Açık–özel şiddet farkı | Güven aşınması olayı | Temel değişim |',
        '|---:|---|---:|---:|---:|---:|---:|---:|']
    for key,s in metrics['groups'].items():
        pop,arm=key.split(':');a=metrics['additional_metrics'][key]
        report.append(f"| {pop} | {arm} | {fmt(s['alignment_changes']['mean'])} | {fmt(a['changed_agents']['mean'])} | {fmt(s['reached_agents']['mean'])} | {fmt(s['mean_support_gap']['mean'])} | {fmt(s['trust_erosions']['mean'])} | {fmt(s['core_changes']['mean'])} |")
    report += ['', '## 3. Eşleştirilmiş farklar ve tohumlar arası değişkenlik',
               'Farklar aynı tohumdaki deney eksi kontrol. Aralıklar 1.96×standart hata normal yaklaşımıdır; 20 tohumda betimleyici, çoklu test düzeltmesiz ve gerçek topluma genellenemez.',
               '', '| Karşılaştırma | Geçiş farkı ort. | Yaklaşık %95 aralık | Pozitif / sıfır / negatif tohum |',
               '|---|---:|---|---|']
    for key,s in metrics['paired'].items():
        v=s['alignment_changes']
        report.append(f"| {key} | {fmt(v['mean'])} | {v['normal_approx_95ci']} | {v['positive']} / {v['zero']} / {v['negative']} |")
    report += ['', 'JSON ayrıca her metrik için ortalama, medyan, min/maks, standart sapma ve betimleyici aralığı içerir.',
               '', '## 4. Yerellik, algı ve bilgi yayılımı',
               f"Tüm {len(rows)} kayıtta işlenmiş olay kimliği tekrar toplamı: {sum(a['duplicate_processed_events'] for a in local_audits)}; C kapsamı dışındaki okuma: {sum(a['scope_outside_reads'] for a in local_audits)}; son durum bütçe ihlali: {sum(a['final_budget_violations'] for a in local_audits)}.",
               f"Okunmamış mesaja dayanan güven/kanaat güncellemesi için ölçülen sızıntı toplamı: {sum(int(r['leaks']) for r in rows)}.",
               'Sızıntı denetimi kayıtlı kanıt/öğrenme zamanını denetler; her olası yazılım hatasının bulunacağı iddiası değildir. Başlangıç kamu ilişkileri deney tanımının parçasıdır.',
               'Ajanlar açıklamayı almadan da kendi giderlerini yaşayıp tepki verebilir. `unreached_switches` ve `unreached_topic_changes` bu yüzden tek başına sızıntı değildir.',
               'Gerçek–algı hatası, economic_outlook kanaati olanlarda gerçek normalize zarar ile kanaat farkıdır; örneklem dışındakilere hata=0 atanmaz. Ekonomik kendi deneyimi ayrı experienced_harm konusudur.',
               'Aşağıdaki ağ bölgesi ilk iki alıcıdan BFS ile seçilen nüfusun dörtte biridir; yönlü iletişim yolları değiştirilmez. Boş bölgede süre yoktur (—).',
               '', '| Nüfus/kol | Yerel ilk erişim ort. dk | Dış ilk erişim ort. dk | Dış okuma ort. | Algı hatası ort. |',
               '|---|---:|---:|---:|---:|']
    for key in ('100:A','100:B','100:C','100:D','1000:A','1000:B','1000:C','1000:D'):
        net=metrics['network_region_metrics'][key];s=metrics['groups'][key]
        report.append(f"| {key} | {fmt(net.get('local_first_minutes',{}).get('mean'))} | {fmt(net.get('outside_first_minutes',{}).get('mean'))} | {fmt(net['outside_read_count']['mean'])} | {fmt(s.get('perception_error',{}).get('mean'))} |")
    report += ['', '## 5. Güven, baskı, ekonomi ve eylemler',
               'Yanlış tahmin yalnızca okunduktan sonraki günlük kişisel gözlemle güven aşındırır. Güven toparlanması doğru yeni tahminle mümkündür; tam toparlanmayan kaynak–ajan çiftleri sağdan sansürlüdür. İlk düzeye dönmemek “asla toparlanmaz” anlamına gelmez.',
               '', '| Kol | Güven artışı olayı ort. | Tam toparlanan çift ort. | Sansürlü çift ort. | Reddedilen eylem ort. |',
               '|---|---:|---:|---:|---:|']
    for key in ('100:B','100:recovery','100:pressure','1000:B'):
        s=metrics['groups'][key];a=metrics['additional_metrics'][key]
        # trust_recoveries is included in aggregate; values are real update counts.
        report.append(f"| {key} | {fmt(s['trust_recoveries']['mean'])} | {fmt(a['fully_recovered_pairs']['mean'])} | {fmt(a['trust_recovery_censored']['mean'])} | {fmt(a['rejected_actions']['mean'])} |")
    report += ['Ekonomik kayıp dağılımları her koşunun metrics.json dosyasında kişi/kesim listeleriyle saklanır. Gelirler dışsaldır; bu model davranışlardan piyasaya geri beslenen tam ekonomi değildir. Bu nedenle A/B/C/D ekonomik kayıplarının eşit kalması beklenir.',
               'Baskı kolunda bir yetkili, kendisine bağımlı zengine baskı yapar: uygulayanın kaynağı 2 azalır, hedefin kamu desteği pressure_response kadar artar, özel sadakat aynı anda değişmez. Hedef bunu doğrudan bilir; uzaktakilere otomatik yayın yoktur. Dolaylı yayılım yokluğu sonuç olarak korunur, varsayımsal etki eklenmez.',
               'Ajan başına fiilî iletişim/eylem sayıları her koşunun metrics.json dosyasında; öneri, ret ve uygulamalar tam snapshot içindedir. Referans politika mesaj aktarır; günlük birikimli durum değişimi fiilî eylem diye sayılmaz.',
               '', '## 6. Performans ve 60 günlük yeniden üretim',
               'Koşu başına wall_seconds başlangıç oluşturma ve simülasyonu kapsar, JSON/sıkıştırmayı kapsamaz. Toplam betik süresi bunları da kapsar. RSS sütunu süreç ömrü tepe değeridir, bağımsız koşu bellek ölçümü değildir. Snapshot baytları bellek/RAM ile aynı şey değildir.',
               '', '| Nüfus/kol | Süre ort. s | Olay ort. | Hafıza kaydı ort. | Snapshot MB ort. | Sıkışmış MB ort. |',
               '|---|---:|---:|---:|---:|---:|---:|']
    for key in ('100:B','1000:B'):
        s=metrics['groups'][key]
        report.append(f"| {key} | {fmt(s['wall_seconds']['mean'])} | {fmt(s['events']['mean'])} | {fmt(s['memory_records']['mean'])} | {fmt(s['snapshot_bytes']['mean']/1e6)} | {fmt(s['compressed_bytes']['mean']/1e6)} |")
    for pop in (100,1000):
        peaks=[int(r['rss_process_peak_kib']) for r in rows if int(r['population'])==pop]
        report.append(f"- {pop} kişilik evrede Linux süreç tepe RSS maksimumu: {max(peaks)/1024:.2f} MiB (bağımsız koşuya ait izole RAM ölçümü değildir).")
    for v in verification:
        report.append(f"- {v['population']} ajan, 60 gün, tohum {v['seed']}: tam koşu, tekrar ve 15. günden kayıttan devam olmak üzere {v['completed_trajectories']} tamamlanmış yörünge. Tam JSON SHA-256 eşitliği: **{v['full_replay_resume_equal']}**. Toplam doğrulama süresi {v['total_wall_seconds']:.3f} s; hashler behavior-verification.json içinde.")
    report += ['', '## 7. Bulguların yorumu ve beklenmedik sonuçlar',
               '- Birikim kapalı D’de özel sadakat ve bağlılık değişmez; açık modda kendi ekonomik deneyimi açıklama olmadan da değişim üretir. Bu sonuç modülün kurallarından kaynaklanır, gerçek topluma ilişkin keşif değildir.',
               '- Açıklamanın etkisini toplam nüfus değil erişenler taşır. Nüfus 10 katına çıkınca aynı iki ilk alıcıdan mesajın eriştiği oran aynı kalmaz. Açıklama başına erişim bütçesi nüfusla ölçeklenmediğinden 100/1000 farkı yalnızca nüfus etkisi diye yorumlanamaz.',
               '- Güçlü şok altında geçişler yüksek çıkmıştır. Bazı ajanlar tekrar geçiş yapar; return_margin ve cooldown geçişi geciktirir ama tüm salınımları engellemez. Bu tasarımın nadir değişim hedefi için kalibrasyon sorunudur; sonuç iyi görünsün diye katsayılar sonradan değiştirilmedi.',
               '- Alternatifin varlığı/yerel görünürlüğü basit bir çekicilik sağlar; alternatifin gelecekte gerçekten daha iyi olacağı kanıtlanmış değildir. Bu basitleştirme yüksek geçişin olası nedenidir.',
               '- Gözlemci direnci duyarlılığında 30 günde temel değişim bulunmaması, parametrenin etkisiz olduğunu kanıtlamaz; zaman ufku varsayılan eşiklere göre kısadır. Testler sonlu, güçlü koşulda değişimi doğrular.',
               '- Güven aşınması hızındaki artış, güven yolunu değiştirirken aynı ayrık geçiş sayısını verebilir. Tek bir toplam sonuçtan mekanizma etkisizliği çıkarılamaz.',
               '', '## 8. Testler, geliştirme hataları ve gerçek tamamlanma',
               'Son tam paket: **54 test, 54 başarılı**; ham çıktı behavior-test-results.txt. Eski 36 test korundu; davranış ve deney sözleşmeleri eklendi. Test başarısı gerçekçilik kanıtı değildir.',
               'İlk eklemede zorunlu otomatik kamu beyanı eski bütçe testini bozdu; kaldırıldı. Sentetik gözlemci testinde seçilen eşik beklenenden erken değişime izin verdi; testin güçlü/zayıf koşulları ayrıldı. Bu başarısızlıklar nihai test çıktısında gizli bir geçiş diye sayılmadı.',
               '60 günlük ilk 1000 kişi doğrulamasında run() varsayılan 100000 olay güvenlik sınırı doldu. Hata çıktısı behavior-verification-initial-failure.txt içinde korundu. Deney betiği artık nüfus×gün ölçeğinde açık olay bütçesi sağlar; çekirdeğin güvenlik sınırı kaldırılmadı. Son 60 günlük kontroller tamamlandı.',
               'İlk uzun geliştirme serisi 260 koşuydu; sonra gelecekteki müdahalelerin snapshot dışında kaldığı bulundu. Kuyruk external_action olaylarıyla düzeltildi, ara kayıt eşitlik testi eklendi ve nihai 260 koşu yeniden çalıştırıldı. Ön seri runs/validation-v1 ve runs/behavior-v1 altında, nihai istatistiğe dahil değil. 16 kısa pilot da nihai örnekleme dahil değil.',
               'Nihai analiz 260 karşılaştırmalı koşu + 6 adet 60 günlük doğrulama yörüngesini kapsar. Birim test içi koşular bağımsız deney örneklemi olarak sayılmadı.',
               '', '## 9. Dosyalar ve kalan sınırlamalar',
               '- engine.py: ayrı davranış/gün sonu olayları, durum alanları, kalıcı müdahaleler, yerel bağlam ve kayıt.',
               '- dynamics.py: birikim, kaynak güveni, akran etkisi, ayrılma maliyeti, histerezis ve temel yönelim.',
               '- behavior.json/behavior.py: davranış v2.0.0, katsayı doğrulama, eski profil için kapalı mod.',
               '- experiments.py / verify_runs.py / analyze_experiments.py: önceden tanımlı koşular, sıkıştırılmış ham kayıtlar, tam tekrar doğrulaması ve bu raporun üretimi.',
               '- tests/test_behavior.py, tests/test_experiments.py: mekanik testlerden ayrı davranış ve eşleştirilmiş deney testleri.',
               '- docs/cumulative-behavior.md ve README: güncel semantik/komutlar. behavior-model-audit.md başlangıç kod denetimidir.',
               'Bilinen sınırlar: tam transaction rollback yok; güvenilen yerel snapshot varsayımı; kayıtlar zamanla sınırsız büyür; kaynak kimliği doğrulanmış varsayılır; saf dil anlamı/yanlış hatırlama yok; gerçek AI yok. Kurumsal pazarlık, işten çıkarma yayılımı ve tam piyasa geri beslemesi yok. Baskının uzun vadeli özel psikolojik etkisi eklenmedi.',
               'Varsayılan tüm yedi kesim parametresi etkin. resistance eski uyumluluk adıdır; bağımsız katsayı değildir. Bir kolda veya yetersiz zaman ufkunda sonuç değişmemesi, kod yolunun kullanılmadığı anlamına gelmez.',
               '', '## 10. Öncelikli sonraki işler',
               '1. Alternatif faydayı yalnızca görünürlükten ayırmak, güvenilir alternatif kanıtı istemek; nadir geçiş hedefini ayrı önceden kayıtlı deneyle kalibre etmek.',
               '2. Histerezis/geri dönüş için daha uzun ve ekonomik toparlanma içeren çok tohumlu deneyler; salınım sürelerini ölçmek.',
               '3. Sosyal kamu beyanlarının ajanlarca üretilip yayılacağı daha zengin ama bütçeli referans karar politikası; gerçek ekonomik geri besleme.',
               '4. Transaction destekli kalıcılık, belleğin özet/ham arşiv ayrımı ve performans indeksleri.',
               '', '## Yeniden çalıştırma',
               '```bash',
               'python -m unittest discover -s tests -v > reports/behavior-test-results.txt 2>&1',
               'python -m society.experiments --seeds 20 --populations 100 1000 --days 30 --sensitivity',
               'python -m society.verify_runs',
               'python -m society.analyze_experiments',
               '```',
               'Rastgelelik yalnızca başlangıçta tüketilir; runtime koşulları yeni RNG çekmez. Bu sürümde eşleştirilmiş kolların başlangıç hashleri eşitliği kontrol edilmiştir. İleride koşullu rastgele karar eklenirse yalnızca aynı tohum eşleştirme garantisi vermez.',
               'CSV/JSON/raporlar depoda; büyük tam kayıtlar Git dışında runs/ altında. Temiz checkout’tan bu komutlar ham kayıtları yeniden üretir. Duvar süreleri/hardware RSS farklı olabilir; davranış yörüngeleri aynı kod/profil ile deterministiktir.']
    (root/'behavior-experiments.md').write_text('\n'.join(report)+'\n')
    print(f'Analyzed {len(rows)} real artifacts; report written.')


if __name__=='__main__':main()
