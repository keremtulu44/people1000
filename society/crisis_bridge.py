"""Tek Gerçeklik Köprüsü: Dinamik kriz dallanması ve senaryo -> motor senkronizasyonu.

Senaryo zincirindeki her gün:
1) Sabit gün numarası yerine biriken örtbas, öfke, içerideki çatlak, boykot ve
   kullanıcı müdahalesine (`custom_event`) göre dinamik olarak dallanır.
2) Arkadaki 100 ajanın gerçek simülasyon motoruna (`Simulation`) doğrulanmış yerel
   olaylar (`price_shock`, `local_disruption`, `pressure`, `revoke_contract`,
   `amplify`, `create_gathering`, `send`) olarak işlenir.
"""
from __future__ import annotations

from copy import deepcopy

from .agenda import ReferenceAdvisor
from .agenda_api import AgendaProvider
from .dynamics import clamp
from .session import Session
from . import collective, psychology


def init_branch_state(sim=None, tier: str = "ordinary") -> dict:
    mem = psychology.institutional_memory_state(sim) if sim is not None else {}
    past = int(mem.get("past_crises", 0))
    scar = float(mem.get("coverup_scar", 0.0))
    # İki ve üzeri geçmiş örtbas krizinden sonra kurumsal çatlak ve halk öfkesi hazır başlar.
    chronic_boost = 1 if (past >= 2 and scar >= 0.28 and tier != "ordinary") else 0
    return {
        "insider_strain": chronic_boost * 2,
        "public_anger_heat": chronic_boost * 2,
        "coverup_heat": 0,
        "reform_credibility": 0,
        "boycott_active": False,
        "branch_path": "rutin" if tier == "ordinary" else "kriz_baslangici",
        "milestones": [],
    }


def is_pure_question(text: str) -> bool:
    """Kullanıcının yeni bir olay başlatmak yerine yalnız mevcut durumu sorduğu sorgular."""
    t = (text or "").strip().lower()
    if not t.endswith("?"):
        return False
    crisis_words = (
        "saldırı", "bomba", "deprem", "yangın", "sel", "çökme", "facia", "patlama",
        "maden", "yolsuzluk", "rüşvet", "ihale", "sansür", "tutuklama", "gözaltı",
        "enflasyon", "zam", "iflas", "grev", "boykot", "sızıntı", "kriz", "atandı",
    )
    if any(w in t for w in crisis_words):
        return False
    return len(t) <= 120


def _apply_custom_intervention(cond: dict, bstate: dict, custom_event: str | None) -> str | None:
    if not custom_event:
        return None
    low = custom_event.lower()
    triggered = None
    # 1. Şeffaf reform / erken fiziksel önlem / üst düzey hesap verme dalı
    if any(w in low for w in (
        "önlem alındı", "şeffaf soruşturma", "bağımsız denetim", "güvenlik sağlandı",
        "istifa etti", "görevden alındı ve denetim", "reform",
    )):
        bstate["reform_credibility"] = min(10, bstate["reform_credibility"] + 7)
        bstate["boycott_active"] = False
        bstate["public_anger_heat"] = max(1, bstate["public_anger_heat"] - 3)
        cond["unaddressed_neglect"] = False
        cond["aftershock_stage"] = "contained"
        cond["coverup_level"] = "none"
        cond["prosecution_fear"] = "low"
        bstate["branch_path"] = "seffaf_onarim"
        triggered = "reform"

    # 2. İçeriden belge / ses kaydı sızıntısı dalı
    if any(w in low for w in ("sızıntı", "sızdı", "belge çıktı", "ses kaydı", "ifşa", "rapor ortaya çıktı")):
        cond["leak_occurred"] = True
        bstate["insider_strain"] = max(bstate["insider_strain"], 5)
        bstate["public_anger_heat"] = min(10, bstate["public_anger_heat"] + 2)
        if "leak" not in bstate["milestones"]:
            bstate["milestones"].append("leak")
        bstate["branch_path"] = "erken_sizinti"
        triggered = triggered or "leak"

    # 3. Sert baskı / sansür / gözaltı dalı
    if any(w in low for w in ("gözaltı", "tutuklama", "soruşturma açıldı", "yayın yasağı", "sansür", "baskın")):
        cond["prosecution_fear"] = "high"
        cond["coverup_level"] = "high"
        cond["detained_individuals"] = max(1, cond.get("detained_individuals", 0) + 1)
        bstate["coverup_heat"] = min(10, bstate["coverup_heat"] + 3)
        bstate["insider_strain"] = min(10, bstate["insider_strain"] + 2)
        if "sanctions" not in bstate["milestones"]:
            bstate["milestones"].append("sanctions")
        bstate["branch_path"] = "sert_baski"
        triggered = triggered or "crackdown"

    # 4. Halk boykotu / grev / iş bırakma dalı
    if any(w in low for w in ("boykot", "grev", "iş bırakma", "kepenk", "meydan")):
        bstate["boycott_active"] = True
        bstate["public_anger_heat"] = max(bstate["public_anger_heat"], 7)
        if "boycott" not in bstate["milestones"]:
            bstate["milestones"].append("boycott")
        bstate["branch_path"] = "toplumsal_boykot"
        triggered = triggered or "boycott"

    # 5. Gözlemci / uzman teknik uyarı raporu dalı
    if any(w in low for w in ("teknik uyarı", "uzman raporu", "bilim kurulu", "denetçi uyarısı", "bağımsız rapor")):
        cond["leak_occurred"] = True
        bstate["observer_warned"] = True
        bstate["insider_strain"] = max(bstate["insider_strain"], 4)
        bstate["public_anger_heat"] = min(10, bstate["public_anger_heat"] + 1)
        bstate["branch_path"] = "epistemik_teknik_uyari"
        triggered = triggered or "observer_warning"

    return triggered


def next_dynamic_directive(chain: dict, day: int, custom_event: str | None = None, sim=None) -> dict:
    """Durum güdümlü dinamik kriz dallanması (sabit gün şablonu yerine nedensel durum makinesi)."""
    tier = chain["tier"]
    dom = chain.get("domain", "ordinary")
    cond = chain["conditions"]
    bstate = chain.setdefault("branch_state", init_branch_state(sim, tier))
    ms = bstate.setdefault("milestones", [])

    intervention = _apply_custom_intervention(cond, bstate, custom_event)

    # 1. SIRADAN GÜNDEM
    if tier == "ordinary":
        phases = {
            1: "İlk duyulma: Kitleler olayı kendi mizaç, konfor ve tahammül eşiklerine göre değerlendirir.",
            2: "Sözlü iddialar ve sosyal medya tartışması: Taraflı medya kendi kutbunu savunur, muhalifler belge sorar.",
            3: "Kurum içi denge ve belge beklentisi: Tarafsızlar ve yöneticiler çıkar/usul dengesini izler.",
            4: "Belge/uygulama netleşmesi: Liyakat veya içerik netleşse de usul tartışması ayrı kalır.",
        }
        dev = custom_event or phases.get(day, f"{day}. günde tartışma rutin gündem içinde sürer; kalıcı taraf değişimi olmaz.")
        return {
            "day": day, "tier": tier, "domain": dom, "phase": "Sıradan Gündem",
            "branch": bstate["branch_path"], "boycott_active": False,
            "event_of_day": dev,
            "allowed_extremes": "YOK — Sıradan gündemde gözaltı, tutuklama, saldırı, ölüm veya intihar kesinlikle olmaz (0 kişi).",
            "conditions": dict(cond),
        }

    # Şeffaf reform dalına girildiyse kriz tırmanmak yerine kurumsal onarıma evrilir
    if bstate["reform_credibility"] >= 6:
        bstate["branch_path"] = "seffaf_onarim"
        if "reform_stabilized" not in ms:
            ms.append("reform_stabilized")
            dev = custom_event or (
                f"{day}. Gün (Şeffaf Denetim ve Kurumsal Onarım Dalı): Erken alınan somut önlemler ve açık soruşturma "
                f"sayesinde ikincil facia ve günah keçisi tiyatrosu önlenir; muhalifler takibi sürdürürken toplumda tansiyon düşer."
            )
        else:
            dev = custom_event or (
                f"{day}. Gün (Kontrollü Normalleşme): Alınan yapısal önlemlerin uygulanması izlenir; "
                f"yeni mağduriyet doğmadan süreç kurumsal denetim altında kapanır."
            )
        return {
            "day": day, "tier": tier, "domain": dom, "phase": "Şeffaf Denetim ve Kurumsal Onarım",
            "branch": bstate["branch_path"], "boycott_active": False,
            "event_of_day": dev,
            "allowed_extremes": "Erken şeffaf önlem alındığı için gözaltı dalgası, ikincil vaka, ölüm veya intihar yok.",
            "conditions": dict(cond),
        }

    # 2. KURUMSAL VEYA EKONOMİK KRİZ DİNAMİK DALLANMASI
    if tier == "institutional_crisis":
        econ = (dom == "economic_crisis")
        phase_base = "Ekonomik / Geçim Krizi" if econ else "Kurumsal / Siyasi Kriz"
        if "initial_shock" not in ms:
            ms.append("initial_shock")
            cond["coverup_level"] = "moderate"
            bstate["insider_strain"] += 2
            bstate["public_anger_heat"] += 2
            bstate["branch_path"] = "ilk_savunma"
            dev = custom_event or (
                "1. Gün: Ekonomik sarsıntı ve geçim darbesi duyulur; yöneticiler geçici dalgalanma açıklaması yapar, A/B medya kanatları karşıt algı kurar."
                if econ else
                "1. Gün: Kurumsal kriz duyulur; yöneticiler ilk savunma ve kontrol refleksini gösterir, A/B sosyal medya kanatları karşıt algı kurar."
            )
            allow = "YOK — İlk aşamada tutuklama, saldırı, ölüm veya intihar olmaz."
        elif "tightened_control" not in ms and bstate["insider_strain"] < 4 and intervention != "leak":
            ms.append("tightened_control")
            cond["coverup_level"] = "high"
            cond["prosecution_fear"] = "elevated"
            bstate["insider_strain"] += 2
            bstate["public_anger_heat"] += 1
            bstate["branch_path"] = "bilgi_daraltma"
            dev = custom_event or (
                f"{day}. Gün: Resmi veriler ve açıklamalar daraltılır; A yanlısı medya olumlu vitrin kurarken tarafsız ticari kesimde piyasa ve soruşturma tedirginliği başlar."
                if econ else
                f"{day}. Gün: Yöneticiler bilgi akışını daraltır; A yanlısı sosyal medya gündemi değiştirmeye çalışır, tarafsız medyada suçlanma tedirginliği başlar."
            )
            allow = "Henüz gözaltı yok; yalnız soruşturma uyarısı ve otosansür korkusu başlar. Ölüm/intihar yok."
        elif "leak_and_probe" not in ms:
            ms.append("leak_and_probe")
            cond["leak_occurred"] = True
            cond["detained_individuals"] = max(1, cond["detained_individuals"])
            cond["prosecution_fear"] = "high"
            bstate["public_anger_heat"] += 2
            bstate["branch_path"] = "sizinti_ve_sorusturma"
            dev = custom_event or (
                f"{day}. Gün: Gerçek maliyet/kayıp tablosunu gösteren kurum içi bir belge sızar; tabloyu sert imalarla paylaşan 1 sosyal medya/sermaye figürü ifadeye çağrılır."
                if econ else
                f"{day}. Gün: İçeriden bir belge/kayıt sızar; sızıntıyı büyütüp sert imada bulunan 1 sosyal medya/zengin figürü ifadeye çağrılır."
            )
            allow = "En fazla 1-2 tekil medya/zengin figürüne soruşturma/gözaltı; tarafsızlarda yüksek suçlanma korkusu. Saldırı/ölüm/intihar yok."
        elif "probe_aftermath" not in ms and bstate["public_anger_heat"] < 7:
            ms.append("probe_aftermath")
            cond["prosecution_fear"] = "high"
            bstate["public_anger_heat"] += 2
            bstate["branch_path"] = "otosansur_ve_baski"
            dev = custom_event or (
                f"{day}. Gün: Soruşturma baskısı tarafsız medyayı otosansüre iterken sızan belgenin yankısı işyerlerinde ve geçim/adalet tartışmasında büyür."
            )
            allow = "En fazla 1-2 tekil medya/zengin figürüne soruşturma/gözaltı; tarafsızlarda yüksek suçlanma korkusu. Saldırı/ölüm/intihar yok."
        elif "scapegoat" not in ms:
            ms.append("scapegoat")
            cond["scapegoat_isolated"] = True
            bstate["boycott_active"] = econ or bstate["public_anger_heat"] >= 7
            bstate["branch_path"] = "gunah_kecisi_manevrasi"
            dev = custom_event or (
                f"{day}. Gün: Üst yöneticiler kendilerini korumak için alt kademeden bir görevliyi günah keçisi ilan edip görevden alır; hoşnutsuzlarda geçim/adalet öfkesi büyür."
            )
            allow = "Alt kademeden 1 günah keçisi görevden alınır; tarafsız medya otosansürde kalır. Saldırı/ölüm/intihar yok."
        elif "scapegoat_echo" not in ms and day <= 7:
            ms.append("scapegoat_echo")
            bstate["boycott_active"] = False
            bstate["branch_path"] = "alt_kademe_tasfiyesi"
            dev = custom_event or (
                f"{day}. Gün: Görevden alınan alt sorumlu üzerinden dosya daraltılır; sermaye kesimi iş kaybını çalışanlara yansıtırken muhaliflerde bastırılmış tepki sürer."
            )
            allow = "Alt kademeden 1 günah keçisi görevden alınır; tarafsız medya otosansürde kalır. Saldırı/ölüm/intihar yok."
        else:
            bstate["boycott_active"] = False
            bstate["branch_path"] = "sogutma_ve_yorgunluk"
            dev = custom_event or (
                f"{day}. Gün: Yöneticiler kısmi idari düzenlemeyle dosyayı soğutmaya çalışır; çözümsüz kalan hoşnutsuzlarda yorgunluk başlarken gözlemciler tiyatronun tamamlandığını tespit eder."
            )
            allow = "Yeni tutuklama, saldırı, ölüm veya intihar yok."
        return {
            "day": day, "tier": tier, "domain": dom, "phase": phase_base,
            "branch": bstate["branch_path"], "boycott_active": bool(bstate["boycott_active"]),
            "event_of_day": dev, "allowed_extremes": allow, "conditions": dict(cond),
        }

    # 3. AĞIR GÜVENLİK VEYA AFET/İHMAL KRİZİ DİNAMİK DALLANMASI
    is_disaster = (dom == "disaster_neglect")
    has_school = "okul" in (chain.get("initial_event") or "").lower()
    venue = "başka bir okulda/noktada" if has_school else "korumasız başka bir noktada/tesiste"
    venue_plural = "okullarda ve kamusal alanlarda" if has_school else "kritik noktalarda ve tesislerde"
    phase = "Ağır Afet / İhmal Krizi" if is_disaster else "Ağır Güvenlik / Yaşam Krizi"

    if "initial_shock" not in ms:
        ms.append("initial_shock")
        cond["coverup_level"] = "moderate"
        bstate["insider_strain"] += 2
        bstate["public_anger_heat"] += 2
        bstate["branch_path"] = "ilk_sok"
        dev = custom_event or f"1. Gün (İlk Şok): {chain['initial_event']}. İlk müdahale/kınamalar, bilgi kısıtlaması ve sorumluluk tartışması başlar."
        allow = "1. günde kimse gözaltına alınmaz, ikincil vaka veya intihar kesinlikle olmaz."
    elif "media_restriction" not in ms and bstate["insider_strain"] < 4 and intervention not in ("leak", "crackdown", "boycott"):
        ms.append("media_restriction")
        cond["coverup_level"] = "high"
        cond["prosecution_fear"] = "elevated"
        bstate["insider_strain"] += 2
        bstate["public_anger_heat"] += 1
        bstate["branch_path"] = "yayin_kisitlamasi"
        dev = custom_event or (
            f"{day}. Gün (Yayın Kısıtlaması ve Algı Savaşı): Yöneticiler resmi açıklama dışındaki yayınları kısıtlar; "
            f"A yanlısı sosyal medya kendi bölgesini koruyup gündemi yumuşatmaya, B yanlısı sosyal medya ihmali büyütmeye çalışır; tarafsız zenginlerde suçlanma korkusu başlar."
        )
        allow = "Yayın kısıtlaması ve soruşturma uyarısı var; henüz gözaltı, yeni can kaybı veya intihar yok."
    elif "leak" not in ms:
        ms.append("leak")
        cond["leak_occurred"] = True
        cond["aftershock_stage"] = "foiled_attempt"
        bstate["public_anger_heat"] += 2
        bstate["branch_path"] = "ihmal_sizintisi"
        if is_disaster:
            dev = custom_event or (
                f"{day}. Gün (Denetim İhmali Sızıntısı ve Önlenen Tehlike): Örtbas sürerken içeriden daha önce sümenaltı edilmiş "
                f"bir yapı/güvenlik denetim uyarısı sızar; ayrıca hasarlı başka bir noktada çökme/yangın tehlikesi son anda tahliyeyle atlatılır."
            )
            allow = "1 son anda tahliyeyle önlenen ikincil tehlike (can kaybı yok) ve denetim belgesi sızıntısı; intihar yok."
        else:
            dev = custom_event or (
                f"{day}. Gün (İhmal Sızıntısı ve Yakalanan Girişim): Örtbas sürerken içeriden daha önce dikkate alınmamış bir güvenlik uyarısı belgesi sızar; "
                f"ayrıca {venue} güvenlik ihlali/saldırı girişimi son anda fark edilip yakalanır."
            )
            allow = "1 önlenen/yakalanan güvenlik girişimi (can kaybı yok) ve belge sızıntısı; intihar yok."
    elif "sanctions" not in ms:
        ms.append("sanctions")
        cond["detained_individuals"] = max(2, cond["detained_individuals"])
        cond["prosecution_fear"] = "high"
        bstate["public_anger_heat"] += 1
        bstate["branch_path"] = "medya_yaptirimi"
        dev = custom_event or (
            f"{day}. Gün (Sosyal Medyaya Yaptırım ve Korku Dalgası): Sızıntıyı ve ihmal iddiasını paylaşırken sert imalarda bulunan "
            f"2 sosyal medya/zengin figürü (biri B yanlısı, biri tarafsız yorumcu) gözaltına alınır; tarafsız medyada suç işleme korkusu zirveye çıkar."
        )
        allow = "Sınırı aşan 1-2 sosyal medya/zengin aktörüne gözaltı/yargılama; yeni saldırı/yıkım veya intihar yok."
    elif cond["unaddressed_neglect"] and "aftershock" not in ms:
        ms.append("aftershock")
        cond["aftershock_stage"] = "aftershock_occurred"
        bstate["public_anger_heat"] += 3
        bstate["branch_path"] = "artci_kriz"
        if is_disaster:
            dev = custom_event or (
                f"{day}. Gün (Denetim Boşluğundan Doğan İkincil Facia): Kök denetim ve tahliye önlemleri alınmadan yalnız algı ve gözaltıyla yetinildiği için "
                f"denetimsiz başka bir hasarlı yapıda/tesiste ikincil çökme/kaza yaşanır; toplumda büyük öfke patlar."
            )
            allow = "Denetim ihmalinin nedensel sonucu olarak 1 ikincil kaza/yıkım vakası; kitlelerde intihar kesinlikle yok."
        else:
            dev = custom_event or (
                f"{day}. Gün (Güvenlik Boşluğundan Doğan Artçı Olay): Kök güvenlik sorunu çözülmeden yalnız algı ve gözaltıyla yetinildiği için "
                f"{venue} artçı saldırı yaşanır (5 ölü, 3 yaralı); toplumda büyük öfke patlar."
            )
            allow = "Güvenlik ihmalinin nedensel sonucu olarak 1 artçı olay (5 ölü, 3 yaralı); kitlelerde intihar kesinlikle yok."
    elif "boycott" not in ms:
        ms.append("boycott")
        bstate["boycott_active"] = True
        bstate["branch_path"] = "toplumsal_boykot"
        dev = custom_event or (
            f"{day}. Gün (Güvensizlik Boykotu ve Yönetici Paniği): Halk riskli binalara ve işyerlerine girmeyi reddeder, kriz günlük hayatı vurur; sıkışan üst yöneticiler suçu yıkacak bir alt sorumlu aramaya başlar."
            if is_disaster else
            f"{day}. Gün (Günlük Hayat Boykotu ve Yönetici Paniği): Halk güvenlik kaygısıyla günlük akışı ve kurumları boykot eder, kriz piyasayı vurur; sıkışan üst yöneticiler suçu yıkacak bir alt sorumlu aramaya başlar."
        )
        allow = "Günlük hayat boykotu ve kurumsal panik; yeni can kaybı, yeni tutuklama veya intihar yok."
    elif "scapegoat" not in ms:
        ms.append("scapegoat")
        cond["scapegoat_isolated"] = True
        cond["singular_tragedy_occurred"] = True
        bstate["boycott_active"] = True
        bstate["branch_path"] = "gunah_kecisi_cokusu"
        dev = custom_event or (
            f"{day}. Gün (Günah Keçisi İlanı ve Tekil Çöküş): Üst yöneticiler kendilerini kurtarmak için bütün ihmali tekil bir alt kademe sorumlunun üzerine yıkıp tutuklatır; "
            f"tamamen yalnız bırakılan bu tekil sorumlunun (yalnız 1 kişi) nezarette şüpheli ölümü/intihar girişimi gündeme düşer."
        )
        allow = "Yalnızca bütün suçun üzerine yıkıldığı tekil günah keçisi sorumluda (1 kişi, asla halkta veya kitle yüzdesinde değil!) tekil trajik vaka."
    elif cond["unaddressed_neglect"] or "delayed_containment" not in ms:
        ms.append("delayed_containment")
        cond["unaddressed_neglect"] = False
        cond["aftershock_stage"] = "contained"
        bstate["boycott_active"] = False
        bstate["branch_path"] = "gecikmeli_onlem"
        dev = custom_event or (
            f"{day}. Gün (Gecikmeli Sıkı Önlemler ve Otosansür): Tepkileri durdurmak için nihayet {venue_plural} sıkı fiziksel denetim/güvenlik önlemleri başlatılır; "
            f"tarafsız sosyal medya yargılanma korkusuyla tamamen otosansüre çekilir."
        )
        allow = "Fiziksel önlem alındığı için yeni vaka, ölüm veya intihar yok."
    elif "lower_closure" not in ms:
        ms.append("lower_closure")
        bstate["boycott_active"] = False
        bstate["branch_path"] = "alt_kademede_kapatma"
        dev = custom_event or (
            f"{day}. Gün (Dosyanın Alt Kademede Kapatılması): Fiziksel önlemlerle yeni vakalar durur ancak soruşturma alt kademedeki günah keçileriyle sınırlı tutulup üst yöneticilere dokunulmaz; "
            f"A yanlısı medya 'sorun çözüldü' propagandasını başlatır."
        )
        allow = "Yeni vaka, tutuklama, ölüm veya intihar yok."
    else:
        bstate["boycott_active"] = False
        bstate["branch_path"] = "tukenmislik_ve_kalici_guvensizlik"
        dev = custom_event or (
            f"{day}. Gün (Kapanış, Tükenmişlik ve Kalıcı Güvensizlik): Gündem kontrollü biçimde soğutulur; hoşnutsuz kesimde yorgunluk ve derin güvensizlik kalırken, "
            f"gözlemciler 'yine aynı tiyatro oynandı, günah keçileriyle üst kademe korundu' tespitini yapar."
        )
        allow = "Yeni vaka, tutuklama, ölüm veya intihar yok."

    return {
        "day": day, "tier": tier, "domain": dom, "phase": phase,
        "branch": bstate["branch_path"], "boycott_active": bool(bstate["boycott_active"]),
        "event_of_day": dev, "allowed_extremes": allow, "conditions": dict(cond),
    }


def sync_day_to_engine(sim, chain: dict, directive: dict) -> dict:
    """Senaryo gününü 100 ajanın gerçek simülasyon motoruna uygular (ücretli API çağrısı yapmaz)."""
    tier = directive["tier"]
    dom = directive.get("domain", "ordinary")
    cond = directive["conditions"]
    boycott = bool(directive.get("boycott_active"))
    now = sim.time
    next_day_start = (now // 1440 + 1) * 1440 if now % 1440 else now

    leaders_a = [a for a in sim.agents.values() if a.initial_group == "authority" and a.alignment == "A"]
    leaders_b = [a for a in sim.agents.values() if a.initial_group == "authority" and a.alignment == "B"]
    wealthy_a = [a for a in sim.agents.values() if a.initial_group == "wealthy" and a.behavior.get("subwing") == "pro_A"]
    wealthy_b = [a for a in sim.agents.values() if a.initial_group == "wealthy" and a.behavior.get("subwing") == "pro_B"]
    wealthy_n = [a for a in sim.agents.values() if a.initial_group == "wealthy" and a.behavior.get("subwing") == "neutral_commercial"]
    discontented = [a for a in sim.agents.values() if a.initial_group == "discontented"]
    opposition = [a for a in sim.agents.values() if a.initial_group == "opposition"]

    log_start = len(sim.log)
    t_ev = sim.time + 5

    # Boykot sinyali (ertesi daily adımında zengin işveren -> çalışan gelir zincirini etkiler)
    if boycott:
        sim.protocol["active_boycott"] = 0.28 if tier == "severe_security_crisis" else 0.18

    if tier != "ordinary":
        # 1. Ekonomik şok veya yerel hizmet/güvenlik kesintisi
        if dom == "economic_crisis":
            if cond["unaddressed_neglect"] and sim.price < 2.2:
                mult = 1.16 if directive["day"] == 1 else 1.08
                sim.schedule(t_ev, "price_shock", {"multiplier": mult})
            elif not cond["unaddressed_neglect"] and sim.price > 1.05:
                sim.schedule(t_ev, "price_shock", {"multiplier": 0.94})
        else:
            dis_domain = "infrastructure" if dom == "disaster_neglect" else (
                "public_safety" if dom == "armed_violence" else "governance")
            sev = (0.78 if cond.get("aftershock_stage") == "aftershock_occurred"
                   else 0.52 if cond["unaddressed_neglect"] else 0.14)
            # Nüfusun etkilenen kesimine gerçek yerel aksama uygula
            targets = (discontented + opposition[:12] + wealthy_n[:2])[:26]
            for idx, ag in enumerate(targets):
                if idx % 2 == directive["day"] % 2 or sev >= 0.70:
                    sim.schedule(t_ev + idx, "local_disruption",
                                 {"target": ag.id, "domain": dis_domain, "severity": sev})
            if boycott and sim.price < 1.65:
                sim.schedule(t_ev + 1, "price_shock", {"multiplier": 1.06})

        # 2. A otoritesinin resmi "her şey kontrol altında" tahmini -> sonradan güven aşınması üretir
        if leaders_a and cond["coverup_level"] in ("moderate", "high"):
            root_a = leaders_a[0]
            out_targets = [e["target"] for e in sim.edges if e["source"] == root_a.id][:4]
            for j, tid in enumerate(out_targets[:2]):
                sim.schedule(t_ev + 10 + j, "external_action", {
                    "actor": root_a.id,
                    "proposal": {
                        "type": "send", "target": tid, "topic": "economic_outlook",
                        "claim": 10,  # düşük zarar tahmini (iyimser örtbas) -> gerçek zararla çelişir!
                        "text": "Resmi açıklama: durum tamamen kontrol altındadır.",
                    },
                })

        # 3. Sosyal medya alt kanatlarının geniş yayın (`amplify`) hamlesi
        if wealthy_a:
            # İyimser 'ekonomi/düzen sağlam' yayını takipçilerde doğrulanabilir beklenti kaydı oluşturur.
            spin_topic = "economic_outlook" if cond["coverup_level"] in ("moderate", "high") else "media:spin_A"
            spin_claim = 8 if spin_topic == "economic_outlook" else 82
            sim.schedule(t_ev + 20, "external_action", {
                "actor": wealthy_a[0].id,
                "proposal": {
                    "type": "amplify", "topic": spin_topic, "claim": spin_claim,
                    "text": "Yönetim gerekli adımları atıyor; istikrar ve refah korunuyor.",
                },
            })
        if wealthy_b:
            sim.schedule(t_ev + 22, "external_action", {
                "actor": wealthy_b[0].id,
                "proposal": {
                    "type": "amplify", "topic": "grievance", "claim": 85,
                    "text": "Ciddi ihmal ve denetimsizlik var; sorumlular hesap vermeli.",
                },
            })
        if wealthy_n:
            # Korku yükseldiyse tarafsız medya otosansür engeline (`self_censored_under_fear`) takılır!
            sim.schedule(t_ev + 24, "external_action", {
                "actor": wealthy_n[0].id,
                "proposal": {
                    "type": "amplify", "topic": "media:commercial", "claim": 55,
                    "text": "Piyasa ve günlük akış üzerindeki belirsizlik izleniyor.",
                },
            })

        # 4. İçeriden belge sızıntısı (`conscience_insider` yönetici -> ağ)
        if cond.get("leak_occurred"):
            insiders = [a for a in sim.agents.values()
                        if a.initial_group == "authority" and a.behavior.get("psychology", {}).get("conscience_insider")]
            leaker = insiders[0] if insiders else (leaders_b[0] if leaders_b else None)
            if leaker:
                leak_targets = [e["target"] for e in sim.edges if e["source"] == leaker.id][:2]
                for k, tid in enumerate(leak_targets):
                    sim.schedule(t_ev + 30 + k, "external_action", {
                        "actor": leaker.id,
                        "proposal": {
                            "type": "send", "target": tid, "topic": "grievance", "claim": 92,
                            "text": "İçeriden sızan denetim uyarısı: risk önceden bildirilmişti.",
                        },
                    })

        # 5. Soruşturma sopası ve sözleşme iptali (`authority` -> bağımlı `wealthy`)
        if cond.get("prosecution_fear") in ("elevated", "high"):
            sanctioned = []
            for cand in [*wealthy_n, *wealthy_b]:
                dep_id = cand.authority_dependency
                if dep_id and dep_id in sim.agents and sim.agents[dep_id].savings >= 4:
                    sanctioned.append((dep_id, cand.id))
            # Baskı uyarısı
            for idx, (dep_id, wid) in enumerate(sanctioned[:3]):
                sim.schedule(t_ev + 40 + idx, "external_action", {
                    "actor": dep_id,
                    "proposal": {"type": "pressure", "target": wid},
                })
            # Gözaltı/ağır yaptırım gününde sözleşme/gelir darbesi (`revoke_contract` -> işveren -> çalışan!)
            det_count = int(cond.get("detained_individuals", 0))
            if det_count > 0 and directive.get("branch") in ("medya_yaptirimi", "sizinti_ve_sorusturma", "sert_baski"):
                for idx, (dep_id, wid) in enumerate(sanctioned[:min(2, det_count)]):
                    sim.schedule(t_ev + 45 + idx, "external_action", {
                        "actor": dep_id,
                        "proposal": {"type": "revoke_contract", "target": wid},
                    })

        # 6. Toplumsal boykot / barışçıl meydan buluşması (`collective`)
        if boycott and collective.enabled(sim) and discontented:
            organizer = discontented[0]
            g_start = sim.time + 60
            g_end = min(next_day_start + 1380, g_start + 900)
            if g_end > g_start + 30:
                sim.schedule(t_ev + 50, "external_action", {
                    "actor": organizer.id,
                    "proposal": {
                        "type": "create_gathering",
                        "place": "kent_meydani",
                        "start": g_start,
                        "end": g_end,
                        "purpose": "Güvenlik ve adalet boykotu",
                    },
                })

    # Tam 1 simülasyon günü ilerlet (yalnız yerel ReferenceAdvisor ile; 0 ağ/ücretli çağrı!)
    session = Session(sim, AgendaProvider(ReferenceAdvisor()))
    session.day()

    new_logs = sim.log[log_start:]
    amplified = sum(1 for e in new_logs if e["kind"] == "media_amplified")
    censored_blocks = sum(
        1 for e in new_logs
        if e["kind"] == "action_rejected" and e["payload"].get("reason") == "self_censored_under_fear"
    )
    observer_warnings = sum(
        1 for e in new_logs
        if e["kind"] == "message_sent" and e["payload"].get("topic") == "technical_warning"
    )
    pressured = sum(1 for e in new_logs if e["kind"] == "pressure_experienced")
    cut_workers = sum(
        1 for a in sim.agents.values()
        if a.initial_group not in ("wealthy", "authority")
        and a.behavior.get("economic_chain", {}).get("employer_cut", 0.0) > 0
    )
    disengaged_citizens = sum(
        1 for a in sim.agents.values()
        if a.behavior.get("psychology", {}).get("disengaged")
    )
    bm = sim.behavior_metrics()

    # Senaryo sinyalleri ile canlı motor durumunun birleşik psikolojik anlık görüntüsü
    chain["synced_day"] = directive["day"]
    live_psych = psychology.group_summary(sim, None)
    # Ayrıca senaryonun o günkü korku/örtbas bağlamını alt kanat ifadeleriyle harmanla
    temp_chain = {
        "tier": tier, "domain": dom, "day": directive["day"], "synced_day": directive["day"] - 1,
        "conditions": deepcopy(cond),
        "history": [{"day": directive["day"], "conditions": deepcopy(cond)}],
    }
    contextual_psych = psychology.group_summary(sim, temp_chain, upto_day=directive["day"])

    effects = {
        "sim_day": sim.time // 1440 + (1 if sim.time > 0 else 0),
        "price": round(sim.price, 3),
        "mean_trust": round(bm["mean_trust"] * 100, 1) if bm["mean_trust"] is not None else None,
        "alignment_changes": bm["alignment_changes"],
        "media_broadcasts": amplified,
        "self_censored_blocks": censored_blocks,
        "observer_warnings": observer_warnings,
        "disengaged_citizens": disengaged_citizens,
        "pressured_actors": pressured,
        "employer_cut_workers": cut_workers,
        "boycott_active": boycott,
        "branch": directive.get("branch", ""),
    }
    return {
        "engine_effects": effects,
        "psychology_snapshot": contextual_psych or live_psych,
    }
