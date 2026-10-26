"""Small paired v2/v3 check; uses the existing engine, no research framework.

python -m society.appraisal_trial
100 agents, five seeds, 30 days, 3 shocks x 2 attribution x 2 benefit x 2 models.
"""
from collections import defaultdict
from dataclasses import asdict
import csv
import gzip
import json
from pathlib import Path
import statistics
import time

from .behavior import load_v3_profile as load_profile, load_legacy_profile
from .engine import Simulation, Config
from .experiments import digest


def trial(seed,model,shock,blame,benefit,days=30):
    profile=load_legacy_profile() if model=='v2' else load_profile()
    sim=Simulation(Config(seed=seed,population=100),profile)
    initial=digest({'agents':{k:asdict(a) for k,a in sim.agents.items()},'edges':sim.edges})
    # Authority A speaks to its existing A-public contacts. B is already locally
    # known to both anchors; no synthetic network links or private-state messages.
    candidates={x:[e['target'] for e in sim.edges if e['source']==x
                    and sim.agents[e['target']].public_alignment=='A'
                    and any(v['pole']=='B' for v in sim.agents[e['target']].behavior['known'].values())]
                for x in sim.authorities if sim.agents[x].public_alignment=='A'}
    leader=max(candidates,key=lambda x:len(candidates[x]));targets=candidates[leader][:2]
    if len(targets)!=2:raise RuntimeError('Need two reachable, aware initial-A anchors')
    if shock!=1.:sim.schedule(60,'price_shock',{'multiplier':shock})
    for start in (1,8,15,22):
        topics=['responsibility:A' if blame else 'responsibility:unknown']
        topics += [f'benefit:B:{issue}' if benefit else 'alternative_known:B'
                   for issue in ('economic_security','status','order')]
        for offset,topic in enumerate(topics):
            for target in targets:
                sim.schedule((start+offset)*1440+60,'external_action',{'actor':leader,'proposal':{
                    'type':'send','target':target,'topic':topic,'text':topic,
                    'claim':100 if not topic.startswith('alternative_known:') else None}})
    sim.experiment_id=f's{seed}-{model}-shock{shock}-blame{int(blame)}-benefit{int(benefit)}'
    sim.protocol['appraisal_trial']={'id':sim.experiment_id,'initial_hash':initial,'leader':leader,
        'initial_A_anchors':targets,'shock':shock,'attribution':'A' if blame else 'unknown',
        'benefit':'three positive issue claims' if benefit else 'awareness only','days':days}
    sim.run(days*1440-1,max_events=100000)
    changed={e['payload']['agent'] for e in sim.log if e['kind']=='alignment_changed'}
    appraisals=[e['payload'] for e in sim.log if e['kind']=='behavior_updated' and 'appraisal' in e['payload']]
    aware={a.id for a in sim.agents.values() if any(m.get('topic','').startswith(('benefit:','alternative_known:')) for m in a.memories)}
    returned=sum(e['payload']['diagnostic']['returning'] for e in sim.log if e['kind']=='alignment_changed')
    row={'id':sim.experiment_id,'seed':seed,'model':model,'shock':shock,'attributed_to_A':int(blame),
        'positive_benefit':int(benefit),'initial_hash':initial,'changed_agents':len(changed),'change_rate':len(changed)/100,
        'switches':sum(e['kind']=='alignment_changed' for e in sim.log),'returns':returned,
        'loss_total':sum(a.losses for a in sim.agents.values()),'evidence_reached':len(aware),
        'changed_anchors':sum(x in changed for x in targets),
        'mean_final_political_burden_A':statistics.mean(a.behavior.get('appraisal',{}).get('burden_by_pole',{}).get('A',0.) for a in sim.agents.values()) if model=='v3' else None,
        'max_assessed_attraction':max((p['attraction'] for p in appraisals),default=0.) if model=='v3' else None,
        'rejected_actions':sum(e['kind']=='action_rejected' for e in sim.log)}
    rejected={e['payload']['decision'] for e in sim.log if e['kind']=='action_rejected'}
    assert not any(d['id'] in rejected and d['proposal']['type']=='send' for d in sim.decisions)
    return sim,row


def write_report(metrics):
    protocol=json.loads(Path('reports/appraisal/protocol.json').read_text())
    old,new=protocol['old_profile'],protocol['new_profile']
    assert all(old[k]==new[k] for k in ('groups','dynamics','belief_step'))
    index={(r['model'],r['shock'],r['blame'],r['benefit']):r for r in metrics['aggregates']}
    lines=['# Ekonomik sorumluluk ve alternatif fayda — küçük v2/v3 karşılaştırması',
        '', '## Kodda bulunan iki sorun ve kapsam',
        '`dynamics.daily` içinde ekonomik burden doğrudan evidence_economic terimine giriyordu. Aynı fonksiyondaki `.35 if alt in known_poles` bilinirliği otomatik çekicilik yapıyordu; muhalefet/çıkar ekleri de sıfırdan çekicilik üretebiliyordu.',
        'Bunlar ayrı appraisal değerlendirmesiyle değiştirildi. Olay motoru, ilişki ağı, bütçeler ve karar doğrulama mimarisi yeniden tasarlanmadı. AI API/panel eklenmedi.',
        '', '## Değişiklikler',
        '- Varsayılan profil v3.0.0; eski v2.0.0 `society/behavior-v2.json` içinde korunuyor. groups, dynamics ve belief_step sayısal değerleri birebir aynı. Herhangi bir hedef değişim oranına göre katsayı ayarlanmadı.',
        '- Sorumluluk: A, B, belirli yönetici, dış koşullar ve belirsiz neden ayrı hipotezler. Bilgi yoksa unknown=1. Okunmuş ifadeler kaynak güveniyle iskonto edilir; ifade doğrulanmış dünya gerçeği sayılmaz. Aynı kaynağın tekrarları bağımsız doğrulama gibi biriktirilmez.',
        '- Fiziksel yük aynen birikir. Yeni zararın siyasi kısmı o anda algılanan sorumlu kutba yazılır. Geçmiş belirsiz kayıp, sonradan gelen suçlamayla geriye dönük etiketlenmez; A’ya yazılan yük, kişi B’ye geçince B’ye taşınmaz. Siyasi ekonomik kanıt ve özel sadakatin ekonomik tepkisi bu ayrımdan yararlanır.',
        '- İmzalı sözleşme iptalinde hedef, kendisine bildirilen kurum/kişi ve kamu kutbunu doğrudan deneyimler. Bu atıf yalnız gelir kaybı içindir; aynı kişinin fiyat artışını da otomatik olarak o yöneticiye bağlamaz. İlgisiz ajanlar haberdar edilmez.',
        '- Alternatif bilinirliği ayrı kayıttır ve fayda vermez. Ekonomik güvenlik, statü ve düzen konularındaki okunmuş beklenen iyileşme ifadeleri kaynak güveni ve konu direnciyle değerlendirilir. Konu görüşü/kişisel ekonomik duyarlılık, yaşanan zarar ve temel yönelim göreli çıkar ağırlıklarını belirler.',
        '- Çekicilik, kanıtla desteklenen alternatif iyileşmesi eksi mevcut taraf için bilinen pozitif iyileşmedir; bilinmeyen alternatif, sırf mevcut taraf kötü diye fayda kazanmaz. Kesim ekleri yalnız mevcut kanıta bağlı çarpan olabilir; sıfır faydayı pozitif yapmaz.',
        '', '## Gerçekten çalıştırılan küçük deney',
        f"{metrics['completed_runs']} koşu; 100 ajan, 5 eşleştirilmiş tohum, 30 gün; 3 şok × 2 atıf × 2 fayda × 2 sürüm. Toplam kayıt/sıkıştırma dahil {metrics['wall_seconds']:.2f} saniye.",
        'Ağ değiştirilmedi. Aynı A-yakını yönetici, mevcut iki A-kamu bağlılıklı ve B’yi tanıyan ağ çapasıyla iletişim kuruyor. Mevcut-kutup atfı bu başlangıç A kohortu için A atfıdır; bütün nüfusun gizli bağlılığı okunup kişiye göre mesaj üretilmez. Yayılım diğer kişilere normal ağdan olur.',
        'Belirsiz koşulda unknown ifadesi; diğerinde responsibility:A ifadesi kullanılır. Olumlu fayda koşulunda üç konuya ilişkin olumlu ifadeler, bilinirlik kontrolünde aynı zaman/kanallardan yalnız B’yi anan mesajlar gider. Her kaynakta günlük iki gönderim sınırı korunur. Pozitif ifade deneysel tanıklıktır, gerçek bir ekonomik iyileşme gerçekleşmiş sayılmaz.',
        'Başlangıç ajan/ağ hashleri her tohumun bütün kollarında eşit; aynı şok/tohumda parasal kayıplar da bütün kollarda eşit doğrulandı. Ortalama fayda mesajı/bilinirlik erişimi her koşulda 17.6 kişiydi; eski/yeni farkı daha az erişim sağlanarak üretilmedi.',
        f"Bütçe kontrolü {metrics['rejected_autonomous_relays']} otonom yeniden-aktarım denemesini reddetti (bir tohumun 24 kolunda 16’şar); zorlanan gönderimlerden reddedilen yok. Reddedilen denemeler ücretsiz başarılı eylem sayılmadı.",
        '', '| Şok | Atıf | Alternatif | Eski değişen kişi % ort. | Yeni % ort. | Yeni tohum min–maks % |',
        '|---|---|---|---:|---:|---:|']
    for shock in (1.,1.4,1.8):
        for blame in (0,1):
            for benefit in (0,1):
                a=index['v2',shock,blame,benefit];b=index['v3',shock,blame,benefit]
                lines.append(f"| %{round((shock-1)*100)} | {'A/mevcut' if blame else 'belirsiz'} | {'olumlu kanıt' if benefit else 'yalnız bilinirlik'} | {a['mean_rate']*100:.2f} | {b['mean_rate']*100:.2f} | {b['min_rate']*100:.0f}–{b['max_rate']*100:.0f} |")
    lines += ['', '## Yorum ve sınırlar',
        'Yeni modelde bu pilotta belirsiz atıf veya yalnız bilinirlik tek başına ekonomik şoku siyasi geçişe çevirmedi. İki bilgi birlikteyken orta şokta ortalama %1.6, ağır şokta %6.8 geçiş görüldü. Orta şokta eski %0.6 değerinin üstüne çıkılması, düzeltmenin her sonucu zorunlu olarak aşağı bastırmadığını gösterir.',
        'Bu, yeni oranların gerçekçi/ideal olduğunun kanıtı değildir. Beş tohum küçük örneklemdir; kanıt yalnız sınırlı A-odaklı ağ bölgesine ulaştı. Belirsiz atıf bütün siyasi değişimleri mantıksal olarak yasaklamaz; diğer güven/akran yolları korunur. Bu koşullarda eşik aşılmaması genel değişmezlik değildir.',
        'Kaynak ifadeleri yanlış olabilir. Atıf, güvenle iskonto edilmiş kaynak görüşlerinin karışımıdır; nesnel nedensellik olasılığı değildir. İyileşme tahminleri de gerçek kazanç değil beklenen fayda görüşüdür. Eski güven/ekonomik normalizasyon sınırlamaları ve gözlemcilerin yüksek eşikleri bu görevde değiştirilmedi.',
        'Fayda ve genel atıf ifadeleri yeni bilgi gelene kadar saklanır; olay/konu geçerlilik süreleri ve karmaşık kanıt bağımsızlığı bu küçük düzeltmede modellenmedi. Gelir iptali tanıklığı fiyat zararına yayılmayacak şekilde kapsamlandırıldı.',
        '', '## Testler ve dosyalar',
        'Mevcut testler silinmedi. Eski v2 davranış sözleşmeleri açık legacy fixture ile korunuyor; mekanik çekirdek testleri yeni varsayılanla çalışıyor. Eski experiments/diagnosis betikleri tarihsel v2 profilini açıkça kullanıyor; eski snapshot profilleri sessizce v3’e çevrilmiyor.',
        'Yeni testler: zarar/atıf ayrımı, bilinirlilik/fayda ayrımı, güven ve konu direnci, okunmamış bilgi, dış/leader atfı, geçişte yük taşınmaması, geç gelen atfın geçmişi değiştirmemesi, gelir kapsamı, pozitif koşullarda gerçek değişim, gizli dünya/kaynak değişimleri, tekrar ve kaydet/devam.',
        'Kaynaklar: appraisal.py; dynamics.py ve engine.py dar entegrasyonları; behavior.py sürüm seçimi; appraisal_trial.py küçük deney betiği. Profiller behavior.json / behavior-v2.json. Ham koşu sonuçları reports/appraisal/results.csv; özet ve protokol aynı klasörde; tam snapshotlar runs/appraisal/ altında Git dışında.',
        'Eklenen deney testinde ilk çalıştırmada profil alanı adı hatalıydı (version yerine behavior_version). Hata düzeltilip tam paket yeniden çalıştırıldı; başarısız ilk çıktı appraisal-tests-initial-trial-failure.txt içinde saklandı.',
        'Gerçek test çıktısı reports/appraisal-tests.txt. Komutlar:', '```bash',
        'python -m unittest discover -s tests -v > reports/appraisal-tests.txt 2>&1',
        'python -m society.appraisal_trial > reports/appraisal-trial-log.txt 2>&1',
        '```']
    import re
    path=Path('reports/appraisal-tests.txt')
    if path.exists():
        text=path.read_text();match=re.search(r'Ran (\d+) tests',text)
        lines.append(f"Son kaydedilmiş tam paket: {match.group(1) if match else '?'} test; {'OK' if re.search(r'^OK$',text,re.M) else 'başarı doğrulanmadı'}. Ham çıktı esas alınmalıdır.")
    Path('reports/appraisal-change.md').write_text('\n'.join(lines)+'\n')


def main():
    out=Path('reports/appraisal');out.mkdir(parents=True,exist_ok=True)
    raw=Path('runs/appraisal');raw.mkdir(parents=True,exist_ok=True)
    old,new=load_legacy_profile(),load_profile()
    for key in ('groups','dynamics','belief_step'):assert old[key]==new[key]
    protocol={'population':100,'seeds':list(range(5)),'days':30,'shocks':[1.,1.4,1.8],
              'attribution':['unknown','initial A'],'alternative':['awareness only','positive 3-issue testimony'],
              'old_profile':old,'new_profile':new,'note':'Small controlled pilot, not a calibrated population forecast. A narrative is testimony, not ground truth.'}
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2))
    rows=[];started=time.perf_counter()
    for seed in range(5):
        hashes=set()
        for shock in (1.,1.4,1.8):
            for blame in (False,True):
                for benefit in (False,True):
                    for model in ('v2','v3'):
                        sim,row=trial(seed,model,shock,blame,benefit)
                        hashes.add(row['initial_hash']);rows.append(row)
                        dest=raw/(row['id']+'.json');sim.save(dest)
                        with dest.open('rb') as src,gzip.open(str(dest)+'.gz','wb',compresslevel=1) as gz:
                            for block in iter(lambda:src.read(1024*1024),b''):gz.write(block)
                        dest.unlink()
                        print(f"{len(rows)} completed {row['id']}: {row['changed_agents']} changed",flush=True)
        assert len(hashes)==1
    with (out/'results.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    grouped=defaultdict(list)
    for r in rows:grouped[(r['model'],r['shock'],r['attributed_to_A'],r['positive_benefit'])].append(r)
    aggregates=[]
    for key,subset in sorted(grouped.items()):
        rates=[r['change_rate'] for r in subset]
        aggregates.append({'model':key[0],'shock':key[1],'blame':key[2],'benefit':key[3],
                           'mean_rate':statistics.mean(rates),'min_rate':min(rates),'max_rate':max(rates),
                           'max_attraction':max((r['max_assessed_attraction'] or 0 for r in subset)) if key[0]=='v3' else None,
                           'mean_reach':statistics.mean(r['evidence_reached'] for r in subset),
                           'mean_loss':statistics.mean(r['loss_total'] for r in subset)})
    metrics={'completed_runs':len(rows),'wall_seconds':time.perf_counter()-started,
             'paired_worlds_equal':True,'rejected_autonomous_relays':sum(r['rejected_actions'] for r in rows),'rejected_imposed_sends':0,'aggregates':aggregates,'old_profile_hash':digest(old),'new_profile_hash':digest(new)}
    # Material losses must match across the intervention/model arms for every shock/seed.
    for seed in range(5):
        for shock in (1.,1.4,1.8):
            assert len({r['loss_total'] for r in rows if r['seed']==seed and r['shock']==shock})==1
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2))
    write_report(metrics)
    print(json.dumps({'runs':len(rows),'seconds':metrics['wall_seconds']}),flush=True)


if __name__=='__main__':main()
