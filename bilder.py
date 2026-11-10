# -*- coding: utf-8 -*-
"""Bilder je Szene erzeugen - mit oder ohne feste Figur.

Adresse, Schluessel und Preis kommen aus der Modellverwaltung (Slot "bilder").
Wird ein Referenzbild uebergeben, versucht das Modul, dieselbe Figur in jede
Szene zu setzen. Welches Feld das Modell dafuer braucht, erkennt es an der
Adresse; passt es nicht, faellt es auf ein Bild ohne Figur zurueck.
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
WARTE_MAX = 150.0        # normales Bildmodell
WARTE_VORLAGE = 420.0    # Modelle mit Vorlage stehen oft lange in der Warteschlange
TAKT = 3.0
VORLAGE_MAX = 1024       # laengste Kante eines Vorlagenbildes
VORLAGE_GUETE = 88       # JPEG-Guete
VORLAGE_RUHIG = 400000   # kleiner als das bleibt, wie es ist

# Welches Feld das Modell fuer das Referenzbild benutzt
REFERENZ_FELD = [("instant-character", "image_url"),
                 ("ideogram", "reference_image_urls"),
                 ("character", "image_url"),
                 ("kontext", "image_url"),
                 ("redux", "image_url")]


def _nimmt_vorlage(url):
    """Ob die Adresse zu einem Modell gehoert, das ein Vorlagenbild annimmt."""
    u = (url or "").lower()
    for merkmal, _feld in REFERENZ_FELD:
        if merkmal in u:
            return True
    return False


def _slot(kanal, slot="bilder", braucht_vorlage=None):
    """Der passende Eintrag.

    braucht_vorlage=True  -> ein Modell, das eine Vorlage annimmt
    braucht_vorlage=False -> ein normales Modell ohne Vorlage
    None                  -> wie frueher: einfach das aktive
    Gibt es keins der gewuenschten Sorte, wird das aktive genommen.
    """
    liste = [e for e in (((kanal or {}).get("apis") or {}).get(slot) or [])
             if isinstance(e, dict) and (e.get("url") or "").strip()]
    if not liste:
        return None
    if braucht_vorlage is not None:
        passend = [e for e in liste
                   if _nimmt_vorlage(e.get("url")) == bool(braucht_vorlage)]
        if passend:
            liste = passend
    for e in liste:
        if e.get("aktiv"):
            return e
    return liste[0]


def bereit(kanal):
    e = _slot(kanal)
    if not e:
        return False, "Kein Bildmodell eingetragen"
    if not (e.get("url") or "").strip():
        return False, "Dem Bildmodell fehlt die Adresse"
    if not schluessel.fuer(kanal, e):
        return False, "Dem Bildmodell fehlt der Schluessel"
    return True, ""


def kann_figur(kanal):
    """Ob ueberhaupt ein Bildmodell eingetragen ist, das eine Vorlage annimmt."""
    e = _slot(kanal, braucht_vorlage=True) or {}
    u = (e.get("url") or "").lower()
    for merkmal, feld in REFERENZ_FELD:
        if merkmal in u:
            return True, feld
    return False, ""


def preis_je_bild(kanal):
    e = _slot(kanal) or {}
    try:
        return round(float(str(e.get("preis")).replace(",", ".")), 4)
    except Exception:
        return 0.05


def _basis_url(adresse):
    a = (adresse or "").strip()
    if a.startswith("http://") or a.startswith("https://"):
        return a.rstrip("/")
    return "https://queue.fal.run/" + a.strip("/")


def _klein(pfad):
    """Macht aus einem grossen Vorlagenbild ein kleines JPEG.

    Ein 3-MB-Bild wird als Anfrage 4 MB gross und muss bei jedem einzelnen
    Bild neu hochgeladen werden. Die Modelle rechnen ohnehin kleiner.
    """
    try:
        from PIL import Image
    except Exception:
        return pfad
    try:
        vorher = os.path.getsize(pfad)
        if vorher < VORLAGE_RUHIG:
            return pfad
        b = Image.open(pfad)
        b.load()
        if max(b.size) <= VORLAGE_MAX and vorher < VORLAGE_RUHIG:
            return pfad
        b = b.convert("RGB")
        art = getattr(getattr(Image, "Resampling", Image), "LANCZOS", 1)
        b.thumbnail((VORLAGE_MAX, VORLAGE_MAX), art)
        ziel = os.path.join(BASIS, "vorlage_klein.jpg")
        b.save(ziel, "JPEG", quality=VORLAGE_GUETE, optimize=True)
        nachher = os.path.getsize(ziel)
        print("[Bild] Vorlage verkleinert: %.2f MB -> %.2f MB (%dx%d)"
              % (vorher / 1048576.0, nachher / 1048576.0, b.size[0], b.size[1]))
        return ziel
    except Exception as f:
        print("[Bild] Vorlage blieb gross:", f)
        return pfad


def _daten_uri(pfad):
    art = mimetypes.guess_type(str(pfad))[0] or "image/png"
    with open(pfad, "rb") as f:
        return "data:%s;base64,%s" % (art, base64.b64encode(f.read()).decode("ascii"))


def _ruf(url, key, koerper=None, zeit=60):
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


def _bild_url(antwort):
    if not isinstance(antwort, dict):
        return None
    for schl in ("images", "image"):
        x = antwort.get(schl)
        if isinstance(x, dict) and x.get("url"):
            return x["url"]
        if isinstance(x, list) and x:
            e = x[0]
            if isinstance(e, dict) and e.get("url"):
                return e["url"]
            if isinstance(e, str) and e.startswith("http"):
                return e
    if isinstance(antwort.get("url"), str) and antwort["url"].startswith("http"):
        return antwort["url"]
    return None


def _masse(seite):
    """Breite und Hoehe fuer das gewuenschte Seitenverhaeltnis."""
    return {"9:16": (1080, 1920), "16:9": (1920, 1080),
            "1:1": (1024, 1024), "4:5": (1080, 1350)}.get(seite, (1080, 1920))


P59_STICHWORT = {"9:16": "portrait_16_9", "4:5": "portrait_4_3",
                 "1:1": "square_hd", "16:9": "landscape_16_9"}
P59_VERHAELTNIS = {"9:16": "9:16", "4:5": "3:4", "1:1": "1:1", "16:9": "16:9"}


def _p59_stichwort(seite):
    return P59_STICHWORT.get(seite, "portrait_16_9")


def _p59_verhaeltnis(seite):
    return P59_VERHAELTNIS.get(seite, "9:16")


def _koerper_varianten(prompt, seite, referenz_feld, referenz_uri, modell=""):
    """Mehrere Spielarten des Anfragekoerpers, die beste fuer das Modell zuerst."""
    b, h = _masse(seite)
    grund = {"prompt": prompt}
    if referenz_feld and referenz_uri:
        if referenz_feld == "reference_image_urls":
            grund[referenz_feld] = [referenz_uri]
        else:
            grund[referenz_feld] = referenz_uri

    def mit(**zusatz):
        d = dict(grund)
        d.update(zusatz)
        return d

    wort = mit(image_size=_p59_stichwort(seite))
    verh = mit(aspect_ratio=_p59_verhaeltnis(seite))
    masse = mit(image_size={"width": b, "height": h})
    nackt = dict(grund)

    url = (modell or "").lower()
    if "ultra" in url:
        return [verh, wort, masse, nackt]
    if "flux" in url:
        return [wort, masse, verh, nackt]
    return [wort, verh, masse, nackt]


def erzeuge(kanal, prompt, ziel, referenz=None, seite="9:16"):
    """Erzeugt ein Bild. Gibt den Pfad zurueck oder None."""
    ok, grund = bereit(kanal)
    if not ok:
        print("[Bild] %s" % grund)
        return None
    will_vorlage = bool(referenz and os.path.exists(referenz))
    e = _slot(kanal, braucht_vorlage=will_vorlage) or _slot(kanal)
    basis = _basis_url(e.get("url"))
    key = schluessel.fuer(kanal, e)
    print("[Bild] Modell: %s" % (e.get("name") or e.get("url")))

    feld = ""
    uri = None
    if will_vorlage:
        geht = _nimmt_vorlage(e.get("url"))
        if geht:
            feld = ""
            for merkmal, f in REFERENZ_FELD:
                if merkmal in (e.get("url") or "").lower():
                    feld = f
                    break
            try:
                uri = _daten_uri(_klein(referenz))
            except Exception as f:
                print("[Bild] Referenzbild nicht lesbar:", f)
                feld, uri = "", None
        else:
            print("[Bild] Kein Modell fuer Vorlagen eingetragen - Bild entsteht ohne Figur. "
                  "Unter KI und Technik beim Slot Bild z.B. fal-ai/instant-character eintragen.")

    letzter = ""
    for nr, koerper in enumerate(
            _koerper_varianten(prompt, seite, feld, uri, e.get("url") or ""), 1):
        try:
            start = _ruf(basis, key, koerper, zeit=90)
        except urllib.error.HTTPError as f:
            letzter = "HTTP %s" % f.code
            if f.code in (400, 422) and nr < 4:
                continue                      # Feld passt nicht, sparsamer versuchen
            print("[Bild] Abgelehnt (%s). Adresse oder Schluessel pruefen." % f.code)
            return None
        except Exception as f:
            print("[Bild] Keine Verbindung:", f)
            return None
        pfad = _abwarten(start, basis, key, ziel,
                         WARTE_VORLAGE if uri else WARTE_MAX)
        if pfad:
            return pfad
        if pfad is False:
            return None          # klarer Fehlschlag, sparsamer wird es nicht besser
        letzter = "ohne Ergebnis"
    print("[Bild] Kein Bild bekommen (%s)" % letzter)
    return None


def _abwarten(start, basis, key, ziel, grenze=None):
    grenze = float(grenze or WARTE_MAX)
    url = _bild_url(start)
    if url:
        return _laden(url, ziel)
    status_url = start.get("status_url")
    antwort_url = start.get("response_url")
    if not status_url:
        return None
    t0 = time.time()
    daneben = 0
    letzte = ""
    gemeldet = ""
    while time.time() - t0 < grenze:
        time.sleep(TAKT)
        try:
            st = _ruf(status_url, key, zeit=40)
            daneben = 0
        except urllib.error.HTTPError as f:
            letzte = "HTTP %s" % f.code
            try:
                letzte += " " + f.read().decode("utf-8", "ignore")[:200]
            except Exception:
                pass
            daneben += 1
            if daneben >= 3:
                print("[Bild] Nachfrage schlaegt fehl: %s" % letzte)
                return False
            continue
        except Exception as f:
            letzte = str(f)[:160]
            daneben += 1
            if daneben >= 3:
                print("[Bild] Keine Verbindung: %s" % letzte)
                return False
            continue
        zustand = (st.get("status") or "").upper()
        if zustand != gemeldet:
            gemeldet = zustand
            print("[Bild] %s nach %d s" % (zustand or "ohne Angabe", int(time.time() - t0)))
        if zustand == "COMPLETED":
            break
        if zustand in ("FAILED", "ERROR", "CANCELLED"):
            print("[Bild] Modell meldet %s: %s"
                  % (zustand, str(st.get("error") or st.get("detail") or st)[:200]))
            return False
        if st.get("error"):
            print("[Bild] Fehlgeschlagen: %s" % str(st.get("error"))[:180])
            return False
    else:
        print("[Bild] Zeit abgelaufen nach %d Sekunden (%s)"
              % (int(grenze), letzte or "Modell hat nie fertig gemeldet"))
        return False
    try:
        fertig = _ruf(antwort_url or status_url.replace("/status", ""), key, zeit=90)
    except Exception as f:
        print("[Bild] Ergebnis nicht lesbar:", f)
        return None
    url = _bild_url(fertig)
    return _laden(url, ziel) if url else None


def _laden(url, ziel):
    try:
        with urllib.request.urlopen(url, timeout=120) as r, open(ziel, "wb") as f:
            while True:
                stueck = r.read(262144)
                if not stueck:
                    break
                f.write(stueck)
    except Exception as f:
        print("[Bild] Herunterladen ging nicht:", f)
        return None
    if not os.path.exists(ziel) or os.path.getsize(ziel) < 1024:
        try:
            os.remove(ziel)
        except Exception:
            pass
        return None
    return str(ziel)


def figur_referenz(kanal, name):
    """Bild der Figur, das als Vorlage dient. Erste Pose, die ein Bild ist."""
    if not (name or "").strip():
        return None
    try:
        import figuren
        f = figuren.holen(kanal, name)
        if not f:
            return None
        for p in f.get("posen") or []:
            if figuren.pose_art(p["datei"]) == "bild":
                pfad = figuren.datei_pfad(kanal, p["datei"])
                if os.path.exists(pfad):
                    return pfad
    except Exception as e:
        print("[Bild] Figur nicht lesbar:", e)
    return None


# ---------- Nachtrag p45: kein schwarzes Bild durchlassen ----------

import re as _p45_re
import subprocess as _p45_sub

_p45_erzeuge_alt = erzeuge

P45_HELL = ", soft natural light on the main subject, clearly visible, not a black frame"
P45_VERSUCHE = 2


def _p45_werte(pfad):
    """Mittlere, kleinste und groesste Helligkeit eines Bildes."""
    try:
        r = _p45_sub.run(["ffmpeg", "-v", "error", "-i", str(pfad),
                          "-vf", "signalstats,metadata=print:file=-",
                          "-f", "null", "-"],
                         capture_output=True, text=True, timeout=40)
        text = (r.stdout or "") + (r.stderr or "")
        zahl = lambda name: float(_p45_re.search(name + r"=([\d.]+)", text).group(1))
        return zahl("YAVG"), zahl("YMIN"), zahl("YMAX")
    except Exception:
        return None


def _p45_tauglich(pfad):
    """False, wenn das Bild flaechig gleich hell ist - also kein Bild.

    Ein dunkles Bild ist in Ordnung, solange irgendwo Licht ist. Erst wenn
    hell und dunkel kaum auseinanderliegen, ist nichts drauf.
    """
    try:
        if not os.path.exists(pfad) or os.path.getsize(pfad) < 2048:
            return False
    except Exception:
        return True
    werte = _p45_werte(pfad)
    if not werte:
        return True
    schnitt, klein, gross = werte
    if gross - klein < 24:
        return False
    if gross < 32:
        return False
    return True


def erzeuge(kanal, prompt, ziel, referenz=None, seite="9:16"):
    """Wie bisher, aber ein leeres Bild wird noch einmal gemalt."""
    letzte = None
    text = prompt
    for versuch in range(P45_VERSUCHE + 1):
        letzte = _p45_erzeuge_alt(kanal, text, ziel, referenz, seite)
        try:
            if not letzte or not os.path.exists(ziel):
                return letzte      # gar nicht erst gemalt - wiederholen hilft nicht
            if _p45_tauglich(ziel):
                if versuch:
                    print("[Bild] Versuch %d hat geklappt" % (versuch + 1))
                return letzte
        except Exception:
            return letzte
        if versuch < P45_VERSUCHE:
            print("[Bild] leeres Bild zurueckbekommen - male es neu (%d von %d)"
                  % (versuch + 1, P45_VERSUCHE))
            if P45_HELL not in text:
                text = text + P45_HELL
    print("[Bild] ACHTUNG: Bild bleibt leer, Szene wird so gebaut")
    return letzte
