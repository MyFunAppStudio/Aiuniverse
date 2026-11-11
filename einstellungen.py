# ============================================
# Einstellungen: dauerhaft gespeichert (JSON)
# Alles was im Dashboard geaendert wird, landet hier.
# ============================================
import json
from pathlib import Path

BASIS = Path(__file__).parent
DATEI = BASIS / "regeln" / "einstellungen.json"
SICHERUNG = BASIS / "regeln" / "einstellungen_backup.json"


def _prompt_a():
    return """DU BIST: Erzaehler fuer diesen Kanal.

=== TITEL (Titel + Thumbnail = 80% des Erfolgs) ===
Denk dir 10 Varianten aus, nimm den STAERKSTEN.
Spannend + klickstark, neugierig machen ohne zu viel zu verraten.
Erste 100 Zeichen zaehlen. Das Skript haelt das Titel-Versprechen.

=== HOOK (die ersten 3 Sekunden entscheiden ALLES) ===
Nutze EINEN dieser 4 Hook-Typen (unter 12 Woerter):
1. OPEN LOOP: "Niemand konnte erklaeren was dann geschah..."
2. CONTRARIAN: "Alles was du ueber diesen Fall weisst ist falsch."
3. CONFESSION: "Die Ermittler gaben zu: so etwas hatten sie nie gesehen."
4. IDENTITY: "Wenn du echte ungeloeste Faelle liebst..."
KEIN "Hallo" oder "In diesem Video" - killt 70% sofort.

=== VIDEO-AUFBAU ===
1. HOOK (0-3 Sek): sofort fesseln, Versprechen machen
2. SETUP (3-15 Sek): Wer, wo, wann - schnell und konkret
3. AUFBAU: Spannung steigern, Details enthuellen
4. MICRO-CLIFFHANGER alle 60-90 Sek:
   "Aber jetzt wird es noch seltsamer..."
5. HOEHEPUNKT: die grosse Wendung
6. AUFLOESUNG: bei ungeloesten Faellen offen lassen
7. CTA + Ausblick auf naechstes Video

=== RETENTION ===
Neues Bild / neuer Reiz alle 3-5 Sekunden.
Kurze Saetze. Sprich wie ein Mensch, nicht wie ein Aufsatz.
Emotionale Stimme, Spannung aufbauen.

=== STRUKTUR-VARIANTE (wechsle jedes Video) ===
A: Chronologisch   B: Ende zuerst   C: Verschiedene Perspektiven

=== THEMEN (rotiere, nie wiederholen) ===
Ungeklaerte Verschwinden, mysterioese Funde, alte Faelle,
seltsame Vorfaelle in der Natur, ungeloeste Raetsel.

=== RECHTLICH SICHER ===
Geschichten als FIKTIV kennzeichnen.
KI-Kennzeichnung setzen. Kein Blut, keine Gewaltdetails.
Keine echten lebenden Personen namentlich.

=== BILDBESCHREIBUNGEN (sehr wichtig fuer den Look) ===
Zeige KONKRETE MOMENTE, keine allgemeinen Motive.
Nenne in JEDER Beschreibung:
1. Kameraeinstellung - wechsle staendig ab:
   extreme close-up / close-up / medium shot / wide shot /
   POV / over-the-shoulder / overhead / low angle / dutch angle
2. Lichtquelle: Taschenlampenkegel, Strassenlaterne, Scheinwerfer
   im Nebel, blaues Polizeilicht, Mondlicht, Neonschild, Kerze
3. Ein erzaehlendes Detail: offene Autotuer, ein Schuh auf der
   Strasse, umgeworfener Stuhl, Polaroid an der Pinnwand,
   roter Faden, Beweistuete, unfertiges Essen, Uhr die stehen blieb

KEINE ganzen Gesichter - nur Silhouetten, Haende, Rueckenansicht,
Umrisse im Gegenlicht.

Schlecht: "dark forest at night"
Gut: "POV shot, flashlight beam cutting through dense fog,
      bare tree trunks blurred at frame edges, wet leaves underfoot"

Schlecht: "old house"
Gut: "wide shot, front door left ajar, warm light spilling onto
      wooden porch, yellowed newspaper still lying on the mat, dusk"

Schlecht: "police investigation"
Gut: "overhead shot of cluttered desk, case file open, three
      polaroids and a red thread, single desk lamp, cold blue window light"

EIGENE THEMEN HIER:"""


def _prompt_b():
    return """CHARAKTER: Immer derselbe (siehe Referenzbild).
SPRACHE: Freundlich, einfach, wie zu einem Freund.

=== TITEL ===
Denk dir 10 Varianten aus, nimm den staerksten.
Nutzen zeigen: "So sparst du 200 Euro im Jahr" statt "Ueber Sparen".
Erste 100 Zeichen zaehlen.

=== HOOK (erste 3 Sekunden) ===
Nutze EINEN dieser 4 Typen (unter 12 Woerter):
1. CONTRARIAN: "Fast alle machen diesen Geldfehler."
2. IDENTITY: "Wenn du unter 30 bist, hoer genau zu."
3. OPEN LOOP: "Diese eine Zahl aendert alles ueber dein Geld."
4. CONFESSION: "Das haette ich frueher wissen sollen..."
KEIN "Hallo" oder "Heute geht es um".

=== VIDEO-AUFBAU (60-90 Sek) ===
1. HOOK (0-3 Sek): Frage oder Behauptung
2. PROBLEM (3-10 Sek): warum das wichtig ist
3. ERKLAERUNG: EIN Thema, einfach, mit konkretem Beispiel
4. AHA-MOMENT: die Kernaussage auf den Punkt
5. CTA: "Folge fuer mehr" + Nutzen-Versprechen

=== RETENTION ===
Neues Bild / Grafik alle 3-5 Sekunden, Zahlen einblenden.
Kurze Saetze, EIN Gedanke pro Satz.

=== AUSSEHEN / KLEIDUNG je Thema ===
Aktien -> Anzug, Krypto -> Hoodie, Sparen -> Sparschwein,
Kredit -> Banker, Steuern -> Taschenrechner

=== THEMEN (rotiere, nie wiederholen) ===
Zinsen, Zinseszins, ETF, Aktien, Inflation, Kredit, Dispo,
Notgroschen, 50-30-20 Regel, Sparplan, Diversifikation,
Dividenden, Bitcoin, Blockchain, Wallet, aktuelle Finanz-News.

=== WICHTIG ===
Immer Hinweis: keine Finanzberatung, nur Bildung.
KI-Kennzeichnung setzen.

=== BILDBESCHREIBUNGEN (sehr wichtig fuer den Look) ===
Zeige KONKRETE Situationen statt abstrakter Symbole.
Nenne in JEDER Beschreibung:
1. Kameraeinstellung - wechsle ab:
   close-up / medium shot / wide shot / overhead / low angle /
   dynamic angle
2. Was der Zuschauer davon hat - zeige das ERGEBNIS:
   jemand freut sich, Kontostand waechst, entspannte Person,
   Haekchen, Pfeil nach oben
3. Ein klares Finanz-Symbol im Bild: Muenzen, steigender Chart,
   Sparschwein, Geldbeutel, Rechner, Kalender

Schlecht: "money"
Gut: "close-up of hands holding phone showing growing green chart,
      warm sunlight, coffee cup blurred in foreground"

Schlecht: "saving"
Gut: "overhead shot of coins stacking into three neat piles on a
      bright desk, small calendar and pen beside them, cheerful colors"

NEUE THEMEN HIER:"""


def _regeln_a():
    return """HOOK: erste 3 Sek - einer der 4 Typen
KEIN "Hallo" / "In diesem Video" - killt Retention
Neues Bild / Reiz alle 3-5 Sekunden
Stille ueber 0,5 Sek rausschneiden
Micro-Cliffhanger alle 60-90 Sek
Kurze Saetze, gesprochen wie ein Mensch
Untertitel dezent (klein, weiss)
Kapitelmarken fuer YouTube
KI-Kennzeichnung + als FIKTIV kennzeichnen
Follow Mitte + Ende, Ausblick aufs naechste Video
Themen niemals wiederholen
Kein Blut, keine Gewaltdetails"""


def _regeln_b():
    return """HOOK: erste 3 Sek - einer der 4 Typen
KEIN "Hallo" / "Heute geht es um"
Neues Bild / Grafik alle 3-5 Sek, Zahlen einblenden
Stille ueber 0,5 Sek rausschneiden
EIN Thema klar erklaeren, mit konkretem Beispiel
Kurze Saetze, EIN Gedanke pro Satz
Aha-Moment klar auf den Punkt
Untertitel gross + dynamisch
Am Ende: Folge fuer mehr + Nutzen
Hinweis: keine Finanzberatung, nur Bildung
Kleidung je Thema anpassen
Themen niemals wiederholen"""


STANDARD = {
    "a": {
        "format": "9:16",
        "name": "True Crime",
        "emoji": "\U0001F47B",
        "farbe": "#00c97a",
        "plattformen": "YouTube + TikTok",
        "auto_an": True,
        "uhrzeit": "03:00",
        "videos_pro_tag": 1,
        "laenge": 120,
        "laenge_einheit": "Sek",
        "laenge_min": 5,
        "laenge_max": 3600,
        "sprachen": ["Englisch"],
        "bilder_pro_minute": 6,
        "schnitte_pro_bild": 2,
        "zoom_effekte": True,
        "mit_avatar": True,
        "bildstil": "cinematic true crime documentary still, 35mm film grain, deep shadows with pools of light, desaturated cold palette with one warm accent, shallow depth of field, volumetric fog, police evidence aesthetic, no faces visible, unsettling and atmospheric, anamorphic lens flare, moody night photography, hyperdetailed, professional cinematography",
        "untertitel_stil": "modern",
        "untertitel_groesse": 46,
        "untertitel_schrift": "DejaVu Sans",
        "untertitel_position": 60,
        "geraeusche_an": False,
        "geraeusche_pegel": 0.12,
        "abo_position": "ende",
        "cta_text_folgen": "",
        "cta_text_like": "",
        "cta_text_abo": "",
        "thumb_groesse": 78,
        "thumb_farbe": "#FFDD00",
        "musik_an": True,
        "musik_pegel": 0.22,
        "lautheit": -14,
        "musik_prompt": "dark cinematic suspense underscore, low drone, slow pulse, tension building, no vocals, no drums, eerie atmosphere",
        "stimme_id": "",
        "stimme_energie": 0.55,
        "prompt": _prompt_a(),
        "regeln": _regeln_a(),
        "titel_auto": True,
        "titel_stil": "Frage",
        "besch_youtube": "[Hook - 2 Zeilen zum Video]\n\nIn diesem Video: [kurze Zusammenfassung]\n\nAI-generated fictional content - inspired by true crime patterns.\n\nAbonniere fuer neue Faelle jede Woche!\n\n#truecrime #mystery #unsolved",
        "besch_tiktok": "[Hook-Frage] #truecrime #mystery #fyp",
        "besch_instagram": "[Hook]\n\nFolge fuer mehr!\n\n#truecrime #mystery #crime #story",
        "hashtags": "#truecrime #mystery #unsolved #fyp",
        "pinned": "Welcher Fall soll als naechstes dran sein?",
        "links": "",
        "cta_mitte": True,
        "cta_like": True,
        "cta_kommentar": False,
        "cta_speichern": False,
        "cta_teilen": False,
        "anim_follow": True,
        "anim_like": True,
        "anim_abo": True,
        "apis": {
            "text":   [{"name":"Anthropic Claude","key":"","url":"https://api.anthropic.com","aktiv":True}],
            "stimme": [{"name":"ElevenLabs (fal.ai)","key":"","url":"fal-ai/elevenlabs/tts/multilingual-v2","aktiv":True},
                       {"name":"ElevenLabs direkt","key":"","url":"https://api.elevenlabs.io","aktiv":False}],
            "video":  [{"name":"Kling (fal.ai)","key":"","url":"fal-ai/kling-video/v2/standard","aktiv":True},
                       {"name":"Veo 3.1 (fal.ai)","key":"","url":"fal-ai/veo3","aktiv":False},
                       {"name":"Kling direkt","key":"","url":"https://api.klingai.com","aktiv":False},
                       {"name":"Grok","key":"","url":"https://api.x.ai","aktiv":False}],
            "bilder": [{"name":"Flux (fal.ai)","key":"","url":"fal-ai/flux/schnell","aktiv":True},
                       {"name":"Flux Pro (fal.ai)","key":"","url":"fal-ai/flux-pro","aktiv":False}],
            "avatar": [{"name":"Hedra","key":"","url":"https://api.hedra.com","aktiv":True},
                       {"name":"HeyGen","key":"","url":"https://api.heygen.com","aktiv":False}],
            "musik":  [{"name":"Stable Audio (fal.ai)","key":"","url":"fal-ai/stable-audio","aktiv":True}],
            "sound":  [{"name":"Freesound","key":"","url":"https://freesound.org/apiv2","aktiv":True}],
        },
        "telegram_token": "",
        "telegram_chat": "",
    },
    "b": {
        "format": "9:16",
        "name": "Fluffy Finanzen",
        "emoji": "\U0001F419",
        "farbe": "#ffaa00",
        "plattformen": "TikTok + YouTube + Instagram",
        "auto_an": True,
        "uhrzeit": "05:00",
        "videos_pro_tag": 1,
        "laenge": 75,
        "laenge_einheit": "Sek",
        "laenge_min": 5,
        "laenge_max": 3600,
        "sprachen": ["Deutsch"],
        "bilder_pro_minute": 10,
        "schnitte_pro_bild": 2,
        "zoom_effekte": True,
        "mit_avatar": False,
        "bildstil": "bright bold 3D illustration, cinematic lighting, vibrant orange and teal palette, soft shadows and rim light, shallow depth of field, dynamic camera angle, finance symbols (coins, rising charts, wallet, piggy bank), happy relatable people, optimistic energetic mood, clean modern look, professional render, eye-catching social media graphic",
        "untertitel_stil": "modern",
        "untertitel_groesse": 46,
        "untertitel_schrift": "DejaVu Sans",
        "untertitel_position": 60,
        "geraeusche_an": False,
        "geraeusche_pegel": 0.12,
        "abo_position": "ende",
        "cta_text_folgen": "",
        "cta_text_like": "",
        "cta_text_abo": "",
        "thumb_groesse": 78,
        "thumb_farbe": "#FFDD00",
        "musik_an": True,
        "musik_pegel": 0.22,
        "lautheit": -14,
        "musik_prompt": "upbeat modern background music, light electronic groove, positive and motivating, no vocals, subtle",
        "stimme_id": "",
        "stimme_energie": 0.85,
        "prompt": _prompt_b(),
        "regeln": _regeln_b(),
        "titel_auto": True,
        "titel_stil": "Nutzen",
        "besch_youtube": "[Hook - 2 Zeilen zum Thema]\n\nHeute erklaert Fluffy: [Thema]\n\nKeine Finanzberatung - nur einfache Bildung.\n\nFolge Fluffy fuer taegliche Finanztipps!\n\n#finanzen #geld #sparen",
        "besch_tiktok": "[Hook-Frage] Fluffy erklaert! #finanzen #geld #fyp",
        "besch_instagram": "[Hook]\n\nFolge Fluffy!\n\n#finanzen #geld #sparen #investieren",
        "hashtags": "#finanzen #geld #sparen #investieren #fyp",
        "pinned": "Welches Finanzthema soll Fluffy als naechstes erklaeren?",
        "links": "",
        "cta_mitte": True,
        "cta_like": True,
        "cta_kommentar": False,
        "cta_speichern": True,
        "cta_teilen": False,
        "anim_follow": True,
        "anim_like": True,
        "anim_abo": True,
        "apis": {
            "text":   [{"name":"Anthropic Claude","key":"","url":"https://api.anthropic.com","aktiv":True}],
            "stimme": [{"name":"ElevenLabs (fal.ai)","key":"","url":"fal-ai/elevenlabs/tts/multilingual-v2","aktiv":True},
                       {"name":"ElevenLabs direkt","key":"","url":"https://api.elevenlabs.io","aktiv":False}],
            "video":  [{"name":"Kling (fal.ai)","key":"","url":"fal-ai/kling-video/v2/standard","aktiv":True},
                       {"name":"Veo 3.1 (fal.ai)","key":"","url":"fal-ai/veo3","aktiv":False},
                       {"name":"Kling direkt","key":"","url":"https://api.klingai.com","aktiv":False},
                       {"name":"Grok","key":"","url":"https://api.x.ai","aktiv":False}],
            "bilder": [{"name":"Flux (fal.ai)","key":"","url":"fal-ai/flux/schnell","aktiv":True},
                       {"name":"Flux Pro (fal.ai)","key":"","url":"fal-ai/flux-pro","aktiv":False}],
            "avatar": [{"name":"Hedra","key":"","url":"https://api.hedra.com","aktiv":True},
                       {"name":"HeyGen","key":"","url":"https://api.heygen.com","aktiv":False}],
            "musik":  [{"name":"Stable Audio (fal.ai)","key":"","url":"fal-ai/stable-audio","aktiv":True}],
            "sound":  [{"name":"Freesound","key":"","url":"https://freesound.org/apiv2","aktiv":True}],
        },
        "telegram_token": "",
        "telegram_chat": "",
    },
}

API_SLOTS = [
    ("text","TEXT / Skript","Skripte, Titel, Beschreibungen"),
    ("stimme","STIMME","Erzaehler- oder Charakterstimme"),
    ("video","VIDEO","Charakter animieren, Clips (Kling, Veo, Grok)"),
    ("bilder","BILDER","Hintergrundbilder, Thumbnails, Grafiken"),
    ("avatar","AVATAR","Lippensync - Gesicht zum Sprechen bringen"),
    ("musik", "MUSIK", "Hintergrundmusik erzeugen"),
    ("sound",  "SOUNDEFFEKTE","Wind, Schritte, Atmosphaere"),
]

SCHRIFTEN = ["DejaVu Sans", "DejaVu Sans Condensed", "Liberation Sans",
             "FreeSans", "DejaVu Serif", "Liberation Serif"]

SPRACHEN_LISTE = ["Englisch", "Deutsch", "Spanisch", "Portugiesisch",
                  "Franzoesisch", "Italienisch", "Hindi", "Niederlaendisch"]


def laden():
    """Laedt die Einstellungen, ergaenzt fehlende Werte mit Standard."""
    daten = {}
    if DATEI.exists():
        try:
            daten = json.loads(DATEI.read_text(encoding="utf-8"))
        except Exception:
            daten = {}
    ergebnis = {}
    for kid, standard in STANDARD.items():
        werte = dict(standard)
        werte.update(daten.get(kid, {}))
        werte["id"] = kid
        ergebnis[kid] = werte
    return ergebnis


def speichern(neue_daten):
    """Speichert und legt vorher eine Sicherung an."""
    DATEI.parent.mkdir(parents=True, exist_ok=True)
    if DATEI.exists():
        try:
            SICHERUNG.write_text(DATEI.read_text(encoding="utf-8"), encoding="utf-8")
        except Exception:
            pass
    DATEI.write_text(json.dumps(neue_daten, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


def zuruecksetzen(kanal_id):
    """Setzt EINEN Kanal auf die Standardwerte zurueck."""
    alle = laden()
    alle[kanal_id] = dict(STANDARD[kanal_id])
    alle[kanal_id]["id"] = kanal_id
    speichern(alle)
    return alle


def aktive_api(kanal, slot):
    for e in kanal.get("apis", {}).get(slot, []):
        if e.get("aktiv"):
            return e
    return None



# Preise in Euro. Bei Bedarf hier anpassen.
# bild = pro Bild, stimme = pro Minute, text = pro Video, musik = pro Stueck
PREISE = {
    "bilder": {
        "flux/schnell":     0.003,
        "flux/dev":         0.025,
        "flux-pro/v1.1":    0.045,
        "flux-pro":         0.055,
        "recraft-v3":       0.045,
        "nano-banana":      0.035,
        "_standard":        0.04,
    },
    "stimme": {
        "elevenlabs":       0.18,
        "playht":           0.12,
        "_standard":        0.18,
    },
    "text": {
        "anthropic":        0.05,
        "_standard":        0.05,
    },
    "musik": {
        "stable-audio":     0.05,
        "_standard":        0.05,
    },
    "video": {
        "kling":            0.030,
        "veo":              0.180,
        "_standard":        0.050,
    },
}


def preis_fuer(kanal, slot):
    """Preis pro Einheit fuer die aktive AI dieses Slots."""
    tab = PREISE.get(slot, {})
    api = aktive_api(kanal, slot)
    if not api:
        return 0.0
    kennung = (api.get("url", "") + " " + api.get("name", "")).lower()
    for muster, wert in tab.items():
        if muster != "_standard" and muster in kennung:
            return wert
    return tab.get("_standard", 0.0)


def laenge_in_minuten(k):
    if k.get("laenge_einheit") == "Sek":
        return k.get("laenge", 60) / 60.0
    return float(k.get("laenge", 5))


def anzahl_bilder(k):
    minuten = laenge_in_minuten(k)
    return max(3, int(round(minuten * k.get("bilder_pro_minute", 6))))


if __name__ == "__main__":
    alle = laden()
    print("=" * 45)
    print("EINSTELLUNGEN")
    print("=" * 45)
    for kid, k in alle.items():
        print(f"{k['emoji']} {k['name']}")
        print(f"   Uhrzeit:  {k['uhrzeit']}  ({k['videos_pro_tag']}x taeglich)")
        print(f"   Laenge:   {k['laenge']} {k['laenge_einheit']}")
        print(f"   Sprachen: {', '.join(k['sprachen'])}")
        print(f"   Bilder:   {anzahl_bilder(k)} Stueck ({k['bilder_pro_minute']}/Min)")
        print(f"   Auto:     {'AN' if k['auto_an'] else 'AUS'}")
    print("=" * 45)


# ===== Bildformat (Patch Hochformat) =====
FORMATE = {
    "9:16": (1080, 1920, "portrait_16_9"),
    "16:9": (1920, 1080, "landscape_16_9"),
    "1:1": (1080, 1080, "square_hd"),
    "4:5": (1080, 1350, "portrait_4_3"),
}


def format_name(kanal):
    f = "9:16"
    try:
        if isinstance(kanal, dict):
            f = kanal.get("format") or "9:16"
        else:
            f = ((laden().get(kanal) or {}).get("format") or "9:16")
    except Exception:
        pass
    return f if f in FORMATE else "9:16"


def format_masse(kanal):
    b, h, _ = FORMATE[format_name(kanal)]
    return b, h


def bild_format(kanal):
    return FORMATE[format_name(kanal)][2]


# ===== Kanalschluessel im Einstellungs-Paket (Patch T1) =====
_laden_alt = laden
_speichern_alt = speichern


def laden():
    d = _laden_alt()
    try:
        for k, v in d.items():
            if isinstance(v, dict):
                v["_key"] = k
    except Exception:
        pass
    return d


def speichern(neue_daten):
    try:
        sauber = {}
        for k, v in (neue_daten or {}).items():
            if isinstance(v, dict):
                v = dict((kk, vv) for kk, vv in v.items() if kk != "_key")
            sauber[k] = v
    except Exception:
        sauber = neue_daten
    return _speichern_alt(sauber)


# ===== Geloeschte Kanaele bleiben geloescht (Patch T2) =====
_laden_t2 = laden


def laden():
    d = _laden_t2()
    try:
        import json as _j, os as _o
        p = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)),
                         "regeln", "geloescht.json")
        if _o.path.exists(p):
            with open(p, encoding="utf-8") as f:
                weg = _j.load(f)
            for k in (weg or []):
                d.pop(k, None)
    except Exception:
        pass
    return d


# ---------- Nachtrag p32: auch neu angelegte Kanaele laden ----------
# Die bisherige Kette laeuft ueber STANDARD, eine fest im Code stehende Liste.
# Was zusaetzlich in der Datei steht - ein angelegter oder geklonter Kanal -
# wurde nie angeschaut und war damit unsichtbar. Hier kommt es dazu.

_p32_laden_alt = laden


def _p32_geloescht():
    import json as _j, os as _o
    try:
        p = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)),
                         "regeln", "geloescht.json")
        if _o.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return list(_j.load(f) or [])
    except Exception:
        pass
    return []


def laden():
    """Alle Kanaele: die fest eingetragenen und die selbst angelegten."""
    import json as _j
    d = _p32_laden_alt()
    try:
        roh = _j.loads(DATEI.read_text(encoding="utf-8")) if DATEI.exists() else {}
    except Exception:
        roh = {}
    for kid, werte in (roh or {}).items():
        if kid in d or not isinstance(werte, dict):
            continue
        w = dict(werte)
        w["id"] = kid
        w["_key"] = kid
        d[kid] = w
    for k in _p32_geloescht():
        d.pop(k, None)
    return d


# ---------- Nachtrag p54: kein Kanal darf beim Speichern verlorengehen ----------

import json as _p54_json
import os as _p54_os

_p54_speichern_alt = speichern


def _p54_pfad(name):
    return _p54_os.path.join(
        _p54_os.path.dirname(_p54_os.path.abspath(__file__)), "regeln", name)


def _p54_auf_platte():
    try:
        with open(_p54_pfad("einstellungen.json"), encoding="utf-8") as f:
            d = _p54_json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _p54_geloescht():
    try:
        with open(_p54_pfad("geloescht.json"), encoding="utf-8") as f:
            return set(_p54_json.load(f) or [])
    except Exception:
        return set()


def speichern(neue):
    """Wie bisher, aber nichts geht dabei verloren."""
    neu = dict(neue or {})
    alt = _p54_auf_platte()
    weg = _p54_geloescht()
    zurueck, ergaenzt = [], []
    for k, v in alt.items():
        if not isinstance(v, dict) or k in weg:
            continue
        if k not in neu:
            neu[k] = v
            zurueck.append(k)
            continue
        if not isinstance(neu[k], dict):
            continue
        fehlen = [f for f in v if f not in neu[k]]
        if fehlen and len(neu[k]) < len(v) * 0.6:
            for f in fehlen:
                neu[k][f] = v[f]
            ergaenzt.append("%s (%d Felder)" % (k, len(fehlen)))
    if zurueck:
        print("[Einstellungen] ACHTUNG: Kanal %s waere verschwunden - zurueckgeholt"
              % ", ".join(zurueck))
    if ergaenzt:
        print("[Einstellungen] ACHTUNG: Felder waeren verlorengegangen - zurueckgeholt: %s"
              % ", ".join(ergaenzt))
    return _p54_speichern_alt(neu)


# ---------- Nachtrag r5: Slot fuer das Referenzmodell ----------
# Das Referenzmodell bekommt mehrere Bilder auf einmal (zwei Figuren und
# einen Hintergrund) und macht daraus einen Clip. Das alte Animationsmodell
# im Slot "video" bleibt daneben bestehen.

if not any((x[0] if isinstance(x, (list, tuple)) else x) == "ref"
           for x in API_SLOTS):
    _r5_neu = []
    for _x in API_SLOTS:
        _r5_neu.append(_x)
        if (_x[0] if isinstance(_x, (list, tuple)) else _x) == "video":
            _r5_neu.append(("ref", "Referenzclip"))
    API_SLOTS = _r5_neu


# ---------- Nachtrag e3: alte Figur aus den Kanaelen nehmen ----------
#
# "Figur" war die alte, aufgeklebte Figur. Die Auswahl ist aus dem
# Dashboard raus, in den Kanaldateien steht der Name aber noch drin -
# und acht Stellen im Code lesen ihn weiter und holen sich eine
# Referenz aus dem alten Figurenordner. Was die Figur frueher konnte,
# machen jetzt die Avatare. Deshalb wird das Feld beim Laden
# weggeraeumt und verschwindet beim naechsten Speichern von selbst.

_e3_laden_alt = laden


def laden():
    d = _e3_laden_alt()
    try:
        for v in d.values():
            if isinstance(v, dict):
                v.pop("geschichte_figur", None)
    except Exception:
        pass
    return d
