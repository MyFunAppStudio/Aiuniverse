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


def ref_koerper(hintergrund, figuren, prompt, sekunden, seite="9:16",
                dauer_als_text=True):
    """Baut die Anfrage. Getrennt, damit sie sich pruefen laesst."""
    dauer = int(max(3, min(15, round(float(sekunden or 5)))))
    k = {"prompt": (prompt or "")[:2000],
         "duration": str(dauer) if dauer_als_text else dauer,
         "aspect_ratio": seite or "9:16"}
    elemente = []
    for f in figuren or []:
        bilder = [p for p in (f.get("bilder") or []) if os.path.exists(p)]
        if not bilder:
            continue
        e = {"frontal_image_url": _daten_uri(bilder[0])}
        weitere = [_daten_uri(p) for p in bilder[1:4]]
        if weitere:
            e["reference_image_urls"] = weitere
        elemente.append(e)
    if elemente:
        k["elements"] = elemente
    if hintergrund and os.path.exists(hintergrund):
        k["image_urls"] = [_daten_uri(hintergrund)]
    return k


def ref_platz(figuren, hintergrund):
    """Wie viele der vier Plaetze belegt waeren."""
    n = len([f for f in (figuren or [])
             if any(os.path.exists(p) for p in (f.get("bilder") or []))])
    if hintergrund and os.path.exists(hintergrund):
        n += 1
    return n


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

    fertig = _ergebnis_holen(basis, key, start, st, status_url, antwort_url)
    if not fertig:
        sag("Ergebnis war unter keiner Adresse zu holen")
        return None
    url = _video_url(fertig)
    if not url:
        sag("Antwort enthaelt kein Video")
        return None
    sag("Clip wird geladen")
    return _laden(url, ziel)
