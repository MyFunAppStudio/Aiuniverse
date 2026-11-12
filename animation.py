# -*- coding: utf-8 -*-
"""KI-Animation einzelner Szenen (Kling und Verwandte ueber fal.ai).

Nimmt Adresse, Schluessel und Preis aus der Modellverwaltung des Kanals
(Slot "video"). Der Schluessel wird nur im Kopf der Anfrage benutzt und
nie ausgegeben.
"""
import base64
import json
import mimetypes
import os
import time
import urllib.error
import urllib.request

import schluessel

BASIS = os.path.dirname(os.path.abspath(__file__))
WARTE_MAX = 420.0          # hoechstens 7 Minuten auf einen Clip warten
TAKT = 5.0


def _slot(kanal, slot="video"):
    """Aktiver Eintrag des Slots, oder None."""
    for e in ((kanal or {}).get("apis") or {}).get(slot) or []:
        if isinstance(e, dict) and e.get("aktiv"):
            return e
    for e in ((kanal or {}).get("apis") or {}).get(slot) or []:
        if isinstance(e, dict) and (e.get("url") or "").strip():
            return e
    return None


def bereit(kanal):
    """(ok, Grund) - ob Animation ueberhaupt benutzt werden kann."""
    e = _slot(kanal)
    if not e:
        return False, "Kein Animationsmodell eingetragen"
    if not (e.get("url") or "").strip():
        return False, "Dem Animationsmodell fehlt die Adresse"
    if not schluessel.fuer(kanal, e):
        return False, "Dem Animationsmodell fehlt der Schluessel"
    return True, ""


def preis_je_clip(kanal, sekunden=5.0):
    """Was ein Clip kostet, nach dem in der Modellverwaltung hinterlegten Preis."""
    e = _slot(kanal) or {}
    try:
        je_sek = float(str(e.get("preis")).replace(",", "."))
    except Exception:
        je_sek = 0.07
    return round(max(0.0, je_sek) * max(1.0, sekunden), 4)


def _basis_url(adresse):
    a = (adresse or "").strip()
    if a.startswith("http://") or a.startswith("https://"):
        return a.rstrip("/")
    return "https://queue.fal.run/" + a.strip("/")


def _daten_uri(pfad):
    art = mimetypes.guess_type(str(pfad))[0] or "image/jpeg"
    with open(pfad, "rb") as f:
        return "data:%s;base64,%s" % (art, base64.b64encode(f.read()).decode("ascii"))


def _hole(url, key, koerper=None, zeit=60):
    daten = json.dumps(koerper).encode("utf-8") if koerper is not None else None
    a = urllib.request.Request(url, data=daten)
    a.add_header("Authorization", "Key " + key)
    if daten is not None:
        a.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(a, timeout=zeit) as r:
        roh = r.read()
    try:
        return json.loads(roh.decode("utf-8"))
    except Exception:
        return {}


def _video_url(antwort):
    """Findet die Videoadresse, egal wie das Modell sie nennt."""
    if not isinstance(antwort, dict):
        return None
    v = antwort.get("video")
    if isinstance(v, dict) and v.get("url"):
        return v["url"]
    if isinstance(v, str) and v.startswith("http"):
        return v
    for schl in ("videos", "output", "outputs"):
        x = antwort.get(schl)
        if isinstance(x, list) and x:
            e = x[0]
            if isinstance(e, dict) and e.get("url"):
                return e["url"]
            if isinstance(e, str) and e.startswith("http"):
                return e
    if isinstance(antwort.get("url"), str) and antwort["url"].startswith("http"):
        return antwort["url"]
    return None


def erzeuge(kanal, bild_pfad, prompt, sekunden, ziel, format_seite="9:16"):
    """Macht aus einem Standbild einen bewegten Clip. Pfad oder None."""
    ok, grund = bereit(kanal)
    if not ok:
        print("[Animation] %s" % grund)
        return None
    if not os.path.exists(bild_pfad):
        print("[Animation] Bild fehlt:", bild_pfad)
        return None
    e = _slot(kanal)
    basis = _basis_url(e.get("url"))
    key = schluessel.fuer(kanal, e)
    dauer = "10" if float(sekunden or 5) > 7.5 else "5"
    koerper = {"image_url": _daten_uri(bild_pfad),
               "prompt": (prompt or "sanfte, ruhige Kamerabewegung")[:900],
               "duration": dauer,
               "aspect_ratio": format_seite}
    try:
        start = _hole(basis, key, koerper, zeit=90)
    except urllib.error.HTTPError as f:
        print("[Animation] Abgelehnt (%s). Adresse oder Schluessel pruefen." % f.code)
        return None
    except Exception as f:
        print("[Animation] Keine Verbindung:", f)
        return None

    status_url = start.get("status_url")
    antwort_url = start.get("response_url")
    if not status_url and not antwort_url:
        # Manche Modelle antworten sofort
        url = _video_url(start)
        return _laden(url, ziel) if url else None

    t0 = time.time()
    st = {}
    gemeldet = ""
    while time.time() - t0 < WARTE_MAX:
        time.sleep(TAKT)
        try:
            st = _hole(status_url, key, zeit=40)
        except Exception as f:
            print("[Animation] Abfrage gestoert:", f)
            continue
        lage = (st.get("status") or "").upper()
        if lage != gemeldet:
            gemeldet = lage
            print("[Animation] %s nach %d s" % (lage or "ohne Angabe", int(time.time() - t0)))
        if lage == "COMPLETED":
            break
        if st.get("error"):
            print("[Animation] Fehlgeschlagen:", str(st.get("error"))[:200])
            return None
    else:
        print("[Animation] Zeit abgelaufen nach %d Sekunden" % int(WARTE_MAX))
        return None

    fertig = _ergebnis_holen(basis, key, start, st, status_url, antwort_url)
    if not fertig:
        print("[Animation] Ergebnis war unter keiner Adresse zu holen")
        return None
    url = _video_url(fertig)
    if not url:
        print("[Animation] Antwort enthaelt kein Video")
        return None
    return _laden(url, ziel)


def _ergebnis_holen(basis, key, start, letzter_stand, status_url, antwort_url):
    """Das fertige Ergebnis abholen. Kling gibt nicht immer dieselbe Adresse zurueck,
    darum werden der Reihe nach alle plausiblen probiert."""
    rid = (start or {}).get("request_id") or (letzter_stand or {}).get("request_id") or ""
    kandidaten = []

    def dazu(u, woher):
        if u and isinstance(u, str) and u.startswith("http") and u not in [k[0] for k in kandidaten]:
            kandidaten.append((u, woher))

    dazu((letzter_stand or {}).get("response_url"), "aus der Statusantwort")
    dazu(antwort_url, "aus der Startantwort")
    if status_url and status_url.endswith("/status"):
        dazu(status_url[:-len("/status")], "Status ohne /status")
    if rid:
        dazu(basis.rstrip("/") + "/requests/" + rid, "aus Adresse und Nummer")
        teile = basis.rstrip("/").split("/")
        if len(teile) >= 5:
            # fal legt das Ergebnis oft unter der Grundadresse des Modells ab
            grund = "/".join(teile[:5])
            dazu(grund + "/requests/" + rid, "Grundadresse des Modells")

    if not kandidaten:
        print("[Animation] Keine Ergebnisadresse bekommen")
        return None
    for u, woher in kandidaten:
        try:
            antwort = _hole(u, key, zeit=90)
        except Exception as f:
            print("[Animation] %s: %s" % (woher, str(f)[:70]))
            continue
        if _video_url(antwort):
            if woher != "aus der Startantwort":
                print("[Animation] Ergebnis geholt (%s)" % woher)
            return antwort
        print("[Animation] %s: kein Video in der Antwort" % woher)
    return None


def _laden(url, ziel):
    try:
        with urllib.request.urlopen(url, timeout=180) as r, open(ziel, "wb") as f:
            while True:
                stueck = r.read(262144)
                if not stueck:
                    break
                f.write(stueck)
    except Exception as f:
        print("[Animation] Herunterladen ging nicht:", f)
        return None
    if not os.path.exists(ziel) or os.path.getsize(ziel) < 2048:
        print("[Animation] Datei zu klein, verworfen")
        try:
            os.remove(ziel)
        except Exception:
            pass
        return None
    return str(ziel)


REDE = '"\u201e\u201c\u201d\u00bb\u00ab'


def _redet(szene):
    """Redet die Figur in dieser Szene? Erkannt an einem Paar Anfuehrungszeichen."""
    t = szene.get("text") or ""
    return sum(1 for z in t if z in REDE) >= 2


def _verteilt(liste, wieviel):
    """wieviel Stueck gleichmaessig aus liste herausgreifen."""
    if wieviel <= 0 or not liste:
        return set()
    if wieviel >= len(liste):
        return set(liste)
    schritt = len(liste) / float(wieviel)
    return set(liste[int(i * schritt)] for i in range(wieviel))


def avatar_bereit(kanal):
    """(ok, Grund) - ob der Avatar benutzt werden kann.

    Der Avatar bekommt Bild und Tonspur und gibt einen Clip zurueck, in dem
    die Figur den Text spricht. Eigener Slot "avatar" in der Modellverwaltung,
    damit die normale Animation davon unberuehrt bleibt.
    """
    e = _slot(kanal, "avatar")
    if not e:
        return False, "Kein Avatar-Modell eingetragen"
    if not (e.get("url") or "").strip():
        return False, "Dem Avatar-Modell fehlt die Adresse"
    if not schluessel.fuer(kanal, e):
        return False, "Dem Avatar-Modell fehlt der Schluessel"
    return True, ""


def preis_je_avatar(kanal, sekunden=5.0):
    """Was ein Sprechclip kostet, nach dem hinterlegten Preis je Sekunde."""
    e = _slot(kanal, "avatar") or {}
    try:
        je_sek = float(str(e.get("preis")).replace(",", "."))
    except Exception:
        je_sek = 0.0562
    return round(max(0.0, je_sek) * max(0.5, sekunden), 4)


def erzeuge_avatar(kanal, bild_pfad, ton_pfad, ziel, prompt=""):
    """Bild + Tonspur -> Clip, in dem die Figur spricht. Pfad oder None."""
    ok, grund = avatar_bereit(kanal)
    if not ok:
        print("[Avatar] %s" % grund)
        return None
    for x in (bild_pfad, ton_pfad):
        if not x or not os.path.exists(x):
            print("[Avatar] Datei fehlt:", x)
            return None
    e = _slot(kanal, "avatar")
    basis = _basis_url(e.get("url"))
    key = schluessel.fuer(kanal, e)
    koerper = {"image_url": _daten_uri(bild_pfad),
               "audio_url": _daten_uri(ton_pfad)}
    if prompt:
        koerper["prompt"] = prompt[:900]
    try:
        start = _hole(basis, key, koerper, zeit=120)
    except urllib.error.HTTPError as f:
        print("[Avatar] Abgelehnt (%s). Adresse oder Schluessel pruefen." % f.code)
        return None
    except Exception as f:
        print("[Avatar] Keine Verbindung:", f)
        return None

    status_url = start.get("status_url")
    antwort_url = start.get("response_url")
    if not status_url and not antwort_url:
        url = _video_url(start)
        return _laden(url, ziel) if url else None

    t0 = time.time()
    st, gemeldet = {}, ""
    while time.time() - t0 < WARTE_MAX:
        time.sleep(TAKT)
        try:
            st = _hole(status_url, key, zeit=40)
        except Exception as f:
            print("[Avatar] Abfrage gestoert:", f)
            continue
        lage = (st.get("status") or "").upper()
        if lage != gemeldet:
            gemeldet = lage
            print("[Avatar] %s nach %d s" % (lage or "ohne Angabe", int(time.time() - t0)))
        if lage == "COMPLETED":
            break
        if st.get("error"):
            print("[Avatar] Fehlgeschlagen:", str(st.get("error"))[:200])
            return None
    else:
        print("[Avatar] Zeit abgelaufen nach %d Sekunden" % int(WARTE_MAX))
        return None

    fertig = _ergebnis_holen(basis, key, start, st, status_url, antwort_url)
    if not fertig:
        print("[Avatar] Ergebnis war unter keiner Adresse zu holen")
        return None
    url = _video_url(fertig)
    if not url:
        print("[Avatar] Antwort enthaelt kein Video")
        return None
    return _laden(url, ziel)


def auswahl(plan, anteil):
    """Welche Szenen animiert werden.

    Zuerst die Szenen, in denen die Figur redet (Anfuehrungszeichen im Text) -
    da fuehlt sich ein Standbild am falschesten an. Bleibt noch Platz, wird der
    Rest gleichmaessig verteilt wie bisher.

    plan: Liste der Szenen. anteil: 0 bis 100.
    Gibt die Menge der Nummern zurueck, die animiert werden sollen.
    """
    bilder = [i for i, s in enumerate(plan) if s.get("typ") != "clip"]
    try:
        a = max(0, min(100, int(anteil)))
    except Exception:
        a = 0
    if not bilder or a <= 0:
        return set()
    n = max(1, int(round(len(bilder) * a / 100.0)))
    n = min(n, len(bilder))
    if n >= len(bilder):
        return set(bilder)

    redner = [i for i in bilder if _redet(plan[i])]
    nimm = _verteilt(redner, min(n, len(redner)))
    if len(nimm) < n:
        rest = [i for i in bilder if i not in nimm]
        nimm |= _verteilt(rest, n - len(nimm))
    if redner:
        print("[Animation] %d von %d Bildern, Sprechszenen zuerst (%d mit Rede)"
              % (len(nimm), len(bilder), len(redner)))
    return nimm


# ---------- Nachtrag r4: Referenzmodus ----------

R4_SLOT = "ref"
R4_STILL = ("The people stay in the foreground and hold their position while "
            "they explain; they do not walk around. One single camera move "
            "for the whole shot. No text, no letters, no logos, no watermark.")


def ref_slot(kanal):
    return _slot(kanal, R4_SLOT)


def ref_bereit(kanal):
    """(ok, Grund) - ob Clips mit Referenzbildern erzeugt werden koennen."""
    e = ref_slot(kanal)
    if not e:
        return False, ("Kein Referenzmodell eingetragen. Unter KI & Technik bei "
                       "Referenzclip auf '+ Eigenes Modell': Adresse "
                       "fal-ai/kling-video/o3/standard/reference-to-video")
    if not (e.get("url") or "").strip():
        return False, "Dem Referenzmodell fehlt die Adresse"
    if not schluessel.fuer(kanal, e):
        return False, "Dem Referenzmodell fehlt der Schluessel"
    return True, ""


def ref_preis(kanal, sekunden=5.0):
    e = ref_slot(kanal) or {}
    try:
        je_sek = float(str(e.get("preis")).replace(",", "."))
    except Exception:
        je_sek = 0.112
    return round(max(0.0, je_sek) * max(1.0, float(sekunden)), 4)


R4_PLAETZE = 4      # so viele Referenzen nimmt das Modell insgesamt an


def ref_verteilen(figuren, hintergrund):
    """Teilt die vier Referenzplaetze auf Hintergrund und Figuren auf.

    Jede Figur bekommt ihr Frontalbild, und was danach uebrig ist, wird
    reihum als zusaetzliches Referenzbild verteilt. Steht eine Figur allein
    in der Szene, bekommt sie also drei Bilder von sich und bleibt sich
    deutlich aehnlicher, als wenn zwei Figuren sich die Plaetze teilen.

    Gibt (Liste von Bildlisten je Figur, Hintergrund oder None) zurueck.
    """
    dabei = []
    for f in figuren or []:
        bilder = [p for p in (f.get("bilder") or []) if os.path.exists(p)]
        if bilder:
            dabei.append(bilder)
    hg = hintergrund if (hintergrund and os.path.exists(hintergrund)) else None

    frei = R4_PLAETZE - (1 if hg else 0)
    if not dabei:
        return [], hg
    # Wenn nicht einmal fuer je ein Frontalbild Platz ist, fallen die
    # hintersten Figuren weg - lieber weniger Figuren als eine Absage.
    dabei = dabei[:max(1, frei)]
    genommen = [b[:1] for b in dabei]
    uebrig = frei - len(genommen)
    i = 0
    while uebrig > 0:
        gewachsen = False
        for nr in range(len(dabei)):
            if uebrig <= 0:
                break
            if len(genommen[nr]) < len(dabei[nr]):
                genommen[nr].append(dabei[nr][len(genommen[nr])])
                uebrig -= 1
                gewachsen = True
        if not gewachsen:
            break           # keine weiteren Bilder vorhanden
        i += 1
        if i > R4_PLAETZE:
            break
    return genommen, hg


def ref_koerper(hintergrund, figuren, prompt, sekunden, seite="9:16",
                dauer_als_text=True):
    """Baut die Anfrage. Getrennt, damit sie sich pruefen laesst."""
    dauer = int(max(3, min(15, round(float(sekunden or 5)))))
    k = {"prompt": (prompt or "")[:2000],
         "duration": str(dauer) if dauer_als_text else dauer,
         "aspect_ratio": seite or "9:16"}
    verteilt, hg = ref_verteilen(figuren, hintergrund)
    elemente = []
    for bilder in verteilt:
        e = {"frontal_image_url": _daten_uri(bilder[0])}
        weitere = [_daten_uri(p) for p in bilder[1:]]
        if weitere:
            e["reference_image_urls"] = weitere
        elemente.append(e)
    if elemente:
        k["elements"] = elemente
    if hg:
        k["image_urls"] = [_daten_uri(hg)]
    return k


def ref_platz(figuren, hintergrund):
    """Wie viele der vier Plaetze wirklich belegt werden."""
    verteilt, hg = ref_verteilen(figuren, hintergrund)
    return sum(len(b) for b in verteilt) + (1 if hg else 0)


def erzeuge_referenz(kanal, hintergrund, figuren, prompt, sekunden, ziel,
                     format_seite="9:16", melden=None):
    """Mehrere Referenzbilder hinein, ein Clip heraus. Pfad oder None.

    figuren ist eine Liste aus {"name": ..., "bilder": [Pfade]}.
    melden(text) wird unterwegs aufgerufen, damit das Dashboard etwas
    anzeigen kann.
    """
    def sag(t):
        print("[Referenz] %s" % t)
        if melden:
            try:
                melden(t)
            except Exception:
                pass

    ok, grund = ref_bereit(kanal)
    if not ok:
        sag(grund)
        return None
    platz = ref_platz(figuren, hintergrund)
    if platz == 0:
        sag("Weder Figuren noch Hintergrund - nichts zu schicken")
        return None
    if platz > 4:
        sag("Zu viele Referenzen (%d). Das Modell nimmt hoechstens vier: "
            "zwei Figuren und einen Hintergrund." % platz)
        return None

    e = ref_slot(kanal)
    basis = _basis_url(e.get("url"))
    key = schluessel.fuer(kanal, e)
    seite = format_seite or "9:16"

    start, letzter_fehler = None, ""
    for als_text in (True, False):
        koerper = ref_koerper(hintergrund, figuren, prompt, sekunden, seite,
                              dauer_als_text=als_text)
        try:
            start = _hole(basis, key, koerper, zeit=180)
            break
        except urllib.error.HTTPError as f:
            roh = ""
            try:
                roh = f.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            letzter_fehler = "%s %s" % (f.code, roh)
            if f.code == 422 and als_text:
                # Manche Modelle wollen die Dauer als Zahl statt als Text
                sag("Dauer als Text abgelehnt, versuche es als Zahl")
                continue
            sag("Abgelehnt (%s). %s" % (f.code, roh[:200]))
            return None
        except Exception as f:
            sag("Keine Verbindung: %s" % f)
            return None
    if start is None:
        sag("Abgelehnt: %s" % letzter_fehler[:200])
        return None

    status_url = start.get("status_url")
    antwort_url = start.get("response_url")
    if not status_url and not antwort_url:
        url = _video_url(start)
        if not url:
            sag("Antwort enthaelt weder Status noch Video")
            return None
        return _laden(url, ziel)

    t0 = time.time()
    st, gemeldet = {}, ""
    while time.time() - t0 < WARTE_MAX:
        time.sleep(TAKT)
        try:
            st = _hole(status_url, key, zeit=40)
        except Exception as f:
            print("[Referenz] Abfrage gestoert:", f)
            continue
        lage = (st.get("status") or "").upper()
        if lage != gemeldet:
            gemeldet = lage
            sag("%s nach %d s" % (lage or "ohne Angabe", int(time.time() - t0)))
        if lage == "COMPLETED":
            break
        if st.get("error"):
            sag("Fehlgeschlagen: %s" % str(st.get("error"))[:200])
            return None
    else:
        sag("Zeit abgelaufen nach %d Sekunden" % int(WARTE_MAX))
        return None

    globals()["LETZTE_BEANSTANDUNG"] = ""
    fertig = _ergebnis_holen(basis, key, start, st, status_url, antwort_url)
    if not fertig:
        b = globals().get("LETZTE_BEANSTANDUNG") or ""
        sag(("fal.ai lehnt die Anfrage ab - " + b) if b
            else "Ergebnis war unter keiner Adresse zu holen")
        return None
    url = _video_url(fertig)
    if not url:
        sag("Antwort enthaelt kein Video")
        return None
    sag("Clip wird geladen")
    return _laden(url, ziel)


# ---------- Nachtrag a2: sagen, was fal.ai beanstandet ----------
#
# Beim Abholen des Ergebnisses kam "HTTP Error 422: Unprocessable
# Entity" - und mehr nicht. Der Rumpf der Antwort enthaelt aber genau,
# welches Feld fal.ai nicht passt. Der wurde weggeworfen, weil nur
# str(f)[:70] gedruckt wurde. Status COMPLETED und trotzdem 422 heisst
# bei fal: der Auftrag lief durch, das Ergebnis ist aber eine
# Beanstandung unserer Anfrage.

def _a2_fehlertext(f):
    try:
        roh = f.read().decode("utf-8", "replace")
    except Exception:
        roh = ""
    roh = " ".join((roh or "").split())
    code = getattr(f, "code", "")
    return ("HTTP %s: %s" % (code, roh[:300])) if roh else ("HTTP %s" % code)


_a2_ergebnis_alt = _ergebnis_holen


def _ergebnis_holen(basis, key, start, letzter_stand, status_url, antwort_url):
    rid = (start or {}).get("request_id") or (letzter_stand or {}).get("request_id") or ""
    kandidaten = []

    def dazu(u, woher):
        if u and isinstance(u, str) and u.startswith("http") \
                and u not in [k[0] for k in kandidaten]:
            kandidaten.append((u, woher))

    dazu((letzter_stand or {}).get("response_url"), "aus der Statusantwort")
    dazu(antwort_url, "aus der Startantwort")
    if status_url and status_url.endswith("/status"):
        dazu(status_url[:-len("/status")], "Status ohne /status")
    if rid:
        teile = basis.rstrip("/").split("/")
        if len(teile) >= 5:
            dazu("/".join(teile[:5]) + "/requests/" + rid, "Grundadresse des Modells")
        dazu(basis.rstrip("/") + "/requests/" + rid, "aus Adresse und Nummer")

    if not kandidaten:
        print("[Animation] Keine Ergebnisadresse bekommen")
        return None

    beanstandung = ""
    for u, woher in kandidaten:
        try:
            antwort = _hole(u, key, zeit=90)
        except urllib.error.HTTPError as f:
            text = _a2_fehlertext(f)
            print("[Animation] %s: %s" % (woher, text))
            if getattr(f, "code", 0) == 422 and not beanstandung:
                beanstandung = text
            continue
        except Exception as f:
            print("[Animation] %s: %s" % (woher, str(f)[:70]))
            continue
        if _video_url(antwort):
            print("[Animation] Ergebnis geholt (%s)" % woher)
            return antwort
        print("[Animation] %s: kein Video in der Antwort" % woher)
    if beanstandung:
        print("[Animation] fal.ai beanstandet die Anfrage: %s" % beanstandung)
        globals()["LETZTE_BEANSTANDUNG"] = beanstandung
    return None


LETZTE_BEANSTANDUNG = ""


# ---------- Nachtrag a3: jede Figur braucht beides ----------
#
# fal.ai antwortet mit 422 und sagt es woertlich:
#   loc: body.elements[1]
#   "Either frontal_image_url and reference_image_urls or video_url
#    must be provided."
#
# Das Modell will je Figur BEIDES - ein Frontalbild UND mindestens ein
# Referenzbild. ref_koerper hat reference_image_urls aber nur
# geschrieben, wenn noch ein zweites Bild uebrig war. Bei zwei Figuren
# und hoechstens vier Plaetzen bekommt die zweite genau ein Bild - und
# ihr Element ging ohne Referenzliste raus. Darum ist jeder Clip mit
# zwei Avataren gescheitert, einer mit einem allein waere
# durchgelaufen.
#
# Jetzt gilt: ist kein weiteres Bild da, wird das Frontalbild selbst
# als Referenz mitgeschickt. Doppelt kodiert wird es nicht.

def ref_koerper(hintergrund, figuren, prompt, sekunden, seite="9:16",
                dauer_als_text=True):
    dauer = int(max(3, min(15, round(float(sekunden or 5)))))
    k = {"prompt": (prompt or "")[:2000],
         "duration": str(dauer) if dauer_als_text else dauer,
         "aspect_ratio": seite or "9:16"}
    verteilt, hg = ref_verteilen(figuren, hintergrund)
    elemente = []
    for bilder in verteilt:
        if not bilder:
            continue
        frontal = _daten_uri(bilder[0])
        weitere = [_daten_uri(p) for p in bilder[1:]]
        elemente.append({
            "frontal_image_url": frontal,
            # Kling verlangt eine nicht leere Liste. Ohne zweites Bild
            # steht dort dasselbe noch einmal.
            "reference_image_urls": weitere or [frontal],
        })
    if elemente:
        k["elements"] = elemente
    if hg:
        k["image_urls"] = [_daten_uri(hg)]
    return k


# ---------- Nachtrag m5: gestikulieren statt stillstehen ----------
#
# R4_STILL war gegen Matsch geschrieben: "hold their position", "they do
# not walk around". Das hat zu viel verboten - die Figuren standen da wie
# hingestellt, und im Hintergrund ruehrte sich nichts.
#
# Nicht gehen bleibt richtig, davon wird ein Koerper unfoermig. Gesten,
# Kopfdrehen und auf die Szene zeigen kann das Modell sauber, und der
# Hintergrund soll ohnehin die ganze Zeit leben.

M5_LEBEN = ("They stay on the spot and do not walk around, but they move "
            "naturally while they talk: hand gestures, turning the head, "
            "and pointing towards what is happening behind them. "
            "The background stays alive for the whole shot: smoke drifts, "
            "crowds and troops keep moving, flags, grass and cloth move in "
            "the wind. One single camera move for the whole shot. "
            "No text, no letters, no logos, no watermark.")

R4_STILL = M5_LEBEN


# ---------- Nachtrag m7: MiniMax H3 als zweites Referenzmodell ----------
#
# Kling nimmt hoechstens vier Referenzen und bewegt die Figuren nur
# sparsam. MiniMax H3 nimmt neun Bilder und ist fuer Bewegung gemacht.
# Der Koerper sieht ganz anders aus: eine flache Liste statt der
# elements-Struktur, und die Bilder werden im Prompt ueber ihre
# Reihenfolge angesprochen ("Image 1 is ...").
#
# Welches Modell gilt, entscheidet die eingetragene Adresse. Steht dort
# minimax oder h3, wird der H3-Koerper gebaut, sonst wie bisher Kling.
# Umschalten geht damit allein ueber die Adresse im Dashboard, ohne
# dass hier etwas geaendert werden muss.

M7_MAX = 9
M7_STUFEN = [6, 10]      # welche Laengen H3 annimmt
M7_AUFLOESUNG = "768P"   # fal will das P gross: 480P, 768P, 2K, 4K


def m7_ist_h3(url):
    u = (url or "").lower()
    return ("minimax" in u or "/h3" in u or "h3-max" in u
            or "seedance" in u)


def m7_koerper(hintergrund, figuren, prompt, sekunden, seite="9:16"):
    """Flache Bildliste. Reihenfolge: erst der Hintergrund, dann die Figuren."""
    bilder = []
    if hintergrund and os.path.exists(hintergrund):
        bilder.append(_daten_uri(hintergrund))
    for f in figuren or []:
        for p in (f.get("bilder") or []):
            if p and os.path.exists(p):
                bilder.append(_daten_uri(p))
    return {"prompt": (prompt or "")[:2000],
            "reference_image_urls": bilder[:M7_MAX],
            "duration": m7_dauer(sekunden),
            "resolution": M7_AUFLOESUNG,
            "aspect_ratio": seite or "9:16"}


def m7_dauer(sekunden):
    """Die naechste Stufe, die mindestens so lang ist wie gebraucht.

    Ohne Angabe nimmt H3 seine eigene Laenge - zuletzt 5,2 Sekunden fuer
    eine Szene, die 8 braucht. Der fehlende Rest wird beim Zusammenbauen
    mit einem eingefrorenen Bild aufgefuellt, und genau das sieht man.
    Lieber zu lang: ueberschuessiges wird abgeschnitten.
    """
    try:
        n = float(sekunden or 6)
    except Exception:
        n = 6.0
    for stufe in M7_STUFEN:
        if stufe >= n - 0.2:
            return stufe
    return M7_STUFEN[-1]


def m7_vorspann(hintergrund, figuren):
    """Sagt dem Modell, welches Bild welches ist - H3 zaehlt sie durch."""
    teile, nr = [], 1
    if hintergrund and os.path.exists(hintergrund):
        teile.append("Image 1 is the background scene.")
        nr = 2
    for f in figuren or []:
        n = len([p for p in (f.get("bilder") or []) if p and os.path.exists(p)])
        if not n:
            continue
        if n == 1:
            teile.append("Image %d is %s." % (nr, f.get("name") or "a person"))
        else:
            teile.append("Images %d to %d are %s, the same person from "
                         "different sides." % (nr, nr + n - 1,
                                               f.get("name") or "a person"))
        nr += n
    return " ".join(teile)


_m7_erzeuge_alt = erzeuge_referenz


def erzeuge_referenz(kanal, hintergrund, figuren, prompt, sekunden, ziel,
                     format_seite="9:16", melden=None):
    """Bei H3 nur Koerper und Vorspann austauschen - Warten, Abholen und
    Herunterladen bleiben, wie sie sind.

    Getauscht wird ueber die Modulnamen, die die alte Funktion benutzt.
    Zwei Clips gleichzeitig wuerden sich dabei in die Quere kommen; das
    Dashboard laesst ohnehin nur einen auf einmal laufen.
    """
    e = ref_slot(kanal) or {}
    if not m7_ist_h3(e.get("url")):
        return _m7_erzeuge_alt(kanal, hintergrund, figuren, prompt, sekunden,
                               ziel, format_seite, melden)

    # Der Kling-Vorspann (@Element1 ...) passt nicht: H3 spricht die Bilder
    # ueber ihre Nummer an. Alles ab dem ersten Satz danach bleibt stehen.
    rest = prompt or ""
    for marke in ("There is exactly", "There are exactly"):
        if marke in rest:
            rest = rest[rest.index(marke):]
            break
    neu_prompt = (m7_vorspann(hintergrund, figuren) + " " + rest).strip()

    # Einmal je Modell nachfragen, was es annimmt - danach gemerkt.
    try:
        werte = m9_werte(kanal)
        laengen = m9_zahlen(werte)
        if laengen:
            globals()["M7_STUFEN"] = laengen
        globals()["M7_AUFLOESUNG"] = m9_passend(werte, "resolution",
                                                M7_AUFLOESUNG, "768P")
    except Exception as f:
        print("[Modell] Werte nicht abfragbar:", str(f)[:120])

    alt_koerper = globals().get("ref_koerper")
    alt_platz = globals().get("ref_platz")
    globals()["ref_koerper"] = (
        lambda hg, fg, pr, sek, seite="9:16", dauer_als_text=True:
        m7_koerper(hg, fg, pr, sek, seite))
    # Die Vierer-Grenze ist eine Kling-Grenze. H3 nimmt neun Bilder.
    globals()["ref_platz"] = lambda fg, hg: 1
    try:
        return _m7_erzeuge_alt(kanal, hintergrund, figuren, neu_prompt,
                               sekunden, ziel, format_seite, melden)
    finally:
        globals()["ref_koerper"] = alt_koerper
        globals()["ref_platz"] = alt_platz


# ---------- Nachtrag m9: das Modell selbst fragen ----------
#
# Welche Laengen ein Modell annimmt, stand hier als feste Liste - erst
# geraten, dann von Hand nachgetragen. Beim naechsten Modell faengt das
# von vorne an, und bis es auffaellt, sind Clips zu kurz und Szenen
# enden mit einem eingefrorenen Bild.
#
# fal sagt es aber von sich aus: schickt man unsinnige Werte, nennt die
# Antwort alle erlaubten. Das wird einmal je Modelladresse gemacht und
# gemerkt. Die Anfrage wird abgelehnt, kostet nichts und erzeugt kein
# Video.
#
# Gemerkt werden auch Aufloesung und Seitenverhaeltnis - der Fehler mit
# "768p" statt "768P" waere damit nie entstanden.

import re as _m9_re

M9_DATEI = os.path.join(BASIS, "regeln", "modell_werte.json")
M9_PROBE = {"prompt": "test", "reference_image_urls": [],
            "duration": "xxx", "resolution": "xxx", "aspect_ratio": "xxx"}


def m9_laden():
    try:
        with open(M9_DATEI, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def m9_speichern(d):
    try:
        os.makedirs(os.path.dirname(M9_DATEI), exist_ok=True)
        with open(M9_DATEI, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("[Modell] Werte nicht zu merken:", e)


def m9_auswerten(roh):
    """Aus "Input should be '6' or '10'" die Werte ziehen."""
    raus = {}
    try:
        d = json.loads(roh)
    except Exception:
        return raus
    for p in (d.get("detail") or []):
        pfad = p.get("loc") or []
        feld = str(pfad[-1]) if pfad else ""
        werte = _m9_re.findall(r"'([^']+)'", str(p.get("msg") or ""))
        if feld and werte:
            raus[feld] = werte
    return raus


def m9_fragen(kanal, e=None):
    """Einmal nachfragen, was dieses Modell annimmt."""
    e = e or ref_slot(kanal) or {}
    url = (e.get("url") or "").strip()
    if not url:
        return {}
    key = schluessel.fuer(kanal, e)
    if not key:
        return {}
    try:
        antwort = _hole(m9_direkt(_basis_url(url)), key, M9_PROBE, zeit=45)
        # Manche Modelle pruefen erst beim Rechnen und stellen die Anfrage
        # trotzdem in die Warteschlange. Die wird sofort zurueckgezogen,
        # sonst laeuft ein Auftrag mit Unsinn durch und kostet Geld.
        m9_abbrechen(antwort, key)
        return {}
    except urllib.error.HTTPError as f:
        try:
            roh = f.read().decode("utf-8", "replace")
        except Exception:
            return {}
    except Exception as f:
        print("[Modell] Nicht erreichbar:", f)
        return {}
    werte = m9_auswerten(roh)
    if werte:
        print("[Modell] %s nimmt an: %s"
              % (url.rsplit("/", 2)[-2:] and url, werte))
    return werte


def m9_abbrechen(antwort, key):
    """Zieht eine versehentlich eingereihte Anfrage zurueck.

    fal will dafuer PUT. Mit POST kam nur "405 Method Not Allowed".
    """
    ziel = (antwort or {}).get("cancel_url") if isinstance(antwort, dict) else ""
    if not ziel:
        return False
    a = urllib.request.Request(ziel, data=b"", method="PUT")
    a.add_header("Authorization", "Key " + key)
    try:
        with urllib.request.urlopen(a, timeout=30):
            pass
        print("[Modell] Probeanfrage zurueckgezogen")
        return True
    except Exception as e:
        print("[Modell] Probeanfrage NICHT zurueckgezogen:", str(e)[:120])
        return False


def m9_direkt(url):
    """Die Adresse ohne Warteschlange.

    queue.fal.run nimmt alles an und prueft erst beim Rechnen - zum
    Fragen taugt das nicht. fal.run antwortet sofort.
    """
    u = (url or "").strip()
    return u.replace("queue.fal.run", "fal.run", 1)


def m9_werte(kanal, neu=False):
    """Die erlaubten Werte dieses Modells. Fragt beim ersten Mal nach."""
    e = ref_slot(kanal) or {}
    url = (e.get("url") or "").strip().lower()
    if not url:
        return {}
    alle = m9_laden()
    if neu or url not in alle:
        alle[url] = m9_fragen(kanal, e)
        m9_speichern(alle)
    return alle.get(url) or {}


def m9_zahlen(werte, feld="duration"):
    raus = []
    for x in (werte.get(feld) or []):
        t = str(x).strip()
        if t.isdigit():
            raus.append(int(t))
    return sorted(set(raus))


def m9_passend(werte, feld, wunsch, ersatz):
    """Der Wunschwert, wenn das Modell ihn kennt - sonst ein erlaubter."""
    erlaubt = werte.get(feld) or []
    if not erlaubt:
        return wunsch
    for x in erlaubt:
        if str(x).strip().lower() == str(wunsch).strip().lower():
            return x
    for x in erlaubt:
        if str(x).strip().lower() == str(ersatz).strip().lower():
            return x
    return erlaubt[0]


# ---------- Nachtrag m14: zwei Sprechende in einem Bild ----------
#
# reference-to-video bekommt die Tonspur nie zu sehen und kann die
# Lippen darum nicht treffen. MultiTalk bekommt ein Bild und ZWEI
# Tonspuren und synchronisiert beide Muender. Die Zuordnung geht nach
# links und rechts im Bild - erste Tonspur links, zweite rechts.
#
# Eigener Slot "multi", damit Referenzclip und Avatar unberuehrt bleiben.

M14_SLOT = "multi"


def multi_bereit(kanal):
    e = _slot(kanal, M14_SLOT)
    if not e:
        return False, ("Kein Modell fuer zwei Sprechende eingetragen. Unter "
                       "KI & Technik bei „Zwei Sprechende“ auf "
                       "„+ Eigenes Modell“: Adresse "
                       "fal-ai/ai-avatar/multi")
    if not (e.get("url") or "").strip():
        return False, "Dem Modell fuer zwei Sprechende fehlt die Adresse"
    if not schluessel.fuer(kanal, e):
        return False, "Dem Modell fuer zwei Sprechende fehlt der Schluessel"
    return True, ""


def erzeuge_multi(kanal, bild_pfad, ton_links, ton_rechts, ziel, prompt="",
                  melden=None):
    """Bild + zwei Tonspuren -> Clip, in dem beide lippensynchron reden."""
    def sag(t):
        print("[Multi] %s" % t)
        if melden:
            try:
                melden(t)
            except Exception:
                pass

    ok, grund = multi_bereit(kanal)
    if not ok:
        sag(grund)
        return None
    for x in (bild_pfad, ton_links):
        if not x or not os.path.exists(x):
            sag("Datei fehlt: %s" % x)
            return None
    e = _slot(kanal, M14_SLOT)
    basis = _basis_url(e.get("url"))
    key = schluessel.fuer(kanal, e)
    koerper = {"image_url": _daten_uri(bild_pfad),
               "first_audio_url": _daten_uri(ton_links)}
    if ton_rechts and os.path.exists(ton_rechts):
        koerper["second_audio_url"] = _daten_uri(ton_rechts)
    if prompt:
        koerper["prompt"] = prompt[:900]
    sag("schicke Bild und %d Tonspuren"
        % (2 if koerper.get("second_audio_url") else 1))
    try:
        start = _hole(basis, key, koerper, zeit=180)
    except urllib.error.HTTPError as f:
        roh = ""
        try:
            roh = f.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        sag("Abgelehnt (%s). %s" % (f.code, roh))
        return None
    except Exception as f:
        sag("Keine Verbindung: %s" % f)
        return None
    return _m14_warten(basis, key, start, ziel, sag)


# Zwei Muender synchronisieren dauert laenger als ein Clip aus Bildern.
# Mit den sieben Minuten der Referenzclips kam "Zeit abgelaufen", obwohl
# das Modell noch gerechnet hat. Der Auftrag lief dabei weiter und wurde
# nur nicht mehr abgeholt.
M14_WARTE = 1200.0         # zwanzig Minuten


def _m14_warten(basis, key, start, ziel, sag):
    status_url = start.get("status_url")
    antwort_url = start.get("response_url")
    if not status_url and not antwort_url:
        url = _video_url(start)
        return _laden(url, ziel) if url else None
    t0, st, gemeldet, gesagt = time.time(), {}, "", 0
    while time.time() - t0 < M14_WARTE:
        time.sleep(TAKT)
        try:
            st = _hole(status_url, key, zeit=40)
        except Exception:
            continue
        lage = (st.get("status") or "").upper()
        lief = int(time.time() - t0)
        # Alle halbe Minute ein Lebenszeichen, sonst sieht es tot aus
        if lage != gemeldet or lief - gesagt >= 30:
            gemeldet, gesagt = lage, lief
            sag("%s - %d:%02d" % (lage or "laeuft", lief // 60, lief % 60))
        if lage == "COMPLETED":
            break
        if st.get("error"):
            sag("Fehlgeschlagen: %s" % str(st.get("error"))[:200])
            return None
    else:
        sag("Nach %d Minuten noch nicht fertig - abgebrochen. Das Modell "
            "rechnet bei fal weiter, der Clip wird nur nicht mehr abgeholt."
            % int(M14_WARTE / 60))
        return None
    fertig = _ergebnis_holen(basis, key, start, st, status_url, antwort_url)
    url = _video_url(fertig) if fertig else None
    if not url:
        b = globals().get("LETZTE_BEANSTANDUNG") or ""
        sag(("fal.ai lehnt die Anfrage ab - " + b) if b
            else "Kein Video in der Antwort")
        return None
    return _laden(url, ziel)
