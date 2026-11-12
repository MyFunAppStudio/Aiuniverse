# ============================================
# Medien: Bilder (Flux) + Stimme (ElevenLabs)
# ueber fal.ai - EIN Key fuer alles
# ============================================
import json
import time
import urllib.request
from pathlib import Path
import config
from concurrent.futures import ThreadPoolExecutor
import einstellungen

FAL_BILD = "https://fal.run/fal-ai/flux/schnell"
FAL_STIMME = "https://fal.run/fal-ai/elevenlabs/tts/multilingual-v2"


def _modell_url(pfad):
    """Macht aus 'fal-ai/flux/schnell' eine volle URL."""
    if pfad.startswith("http"):
        return pfad
    return "https://fal.run/" + pfad.strip("/")


def _fal_anfrage(url, daten, schluessel=None):
    """Ruft ein Modell auf. Key kommt aus dem Dashboard."""
    schluessel = schluessel or config.FAL_KEY
    if not schluessel:
        raise RuntimeError("Kein fal.ai-Key im Dashboard eingetragen (Kanal -> APIs)")
    anfrage = urllib.request.Request(
        _modell_url(url),
        data=json.dumps(daten).encode(),
        headers={
            "Authorization": f"Key {schluessel}",
            "Content-Type": "application/json",
        }
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=600) as antwort:
            return json.loads(antwort.read().decode())
    except urllib.error.HTTPError as f:
        leib = f.read().decode()[:400]
        raise RuntimeError(f"API-Fehler {f.code} bei {_modell_url(url)}\n{leib}")


def _lade_datei(url, ziel):
    """Laedt eine Datei herunter."""
    urllib.request.urlretrieve(url, ziel)
    return ziel


def _test_bild(ziel, nummer):
    """Erzeugt ein einfaches Testbild mit ffmpeg."""
    import subprocess
    farben = ["gray", "darkblue", "darkgreen", "maroon", "navy", "black"]
    farbe = farben[nummer % len(farben)]
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", f"color=c={farbe}:s=1280x720:d=1",
        "-frames:v", "1", str(ziel)
    ], check=True)
    return ziel


def _test_ton(ziel, sekunden=10):
    """Erzeugt eine stille Testtonspur."""
    import subprocess
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(sekunden), str(ziel)
    ], check=True)
    return ziel


def erzeuge_bilder(kanal, bild_prompts, ordner):
    """Erzeugt alle Bilder GLEICHZEITIG (viel schneller)."""
    ordner = Path(ordner)
    ordner.mkdir(parents=True, exist_ok=True)

    if config.TESTMODUS:
        pfade = []
        for i in range(len(bild_prompts)):
            ziel = ordner / f"bild_{i:03d}.jpg"
            _test_bild(ziel, i)
            pfade.append(ziel)
        print(f"[Bild] {len(pfade)} Test-Bilder")
        return pfade

    api = einstellungen.aktive_api(kanal, "bilder") or {}
    name = api.get("name", "?")
    url = api.get("url") or FAL_BILD
    schluessel = api.get("key")
    gesamt = len(bild_prompts)
    print(f"[Bild] {gesamt} Bilder gleichzeitig ({name})...")

    stil = (kanal.get("bildstil") or "").strip()

    def eins(paar):
        i, prompt = paar
        if stil:
            prompt = f"{prompt}. Style: {stil}"
        ziel = ordner / f"bild_{i:03d}.jpg"
        try:
            ergebnis = _fal_anfrage(url, {
                "prompt": prompt,
                "image_size": einstellungen.bild_format(kanal),
                "num_images": 1,
            }, schluessel)
            _lade_datei(ergebnis["images"][0]["url"], ziel)
            if not _bild_brauchbar(ziel):
                print(f"[Bild] {i+1}/{gesamt} unbrauchbar - zweiter Versuch")
                ergebnis = _fal_anfrage(url, {
                    "prompt": prompt + ", helles Tageslicht, klar erkennbar",
                    "image_size": einstellungen.bild_format(kanal),
                    "num_images": 1,
                }, schluessel)
                _lade_datei(ergebnis["images"][0]["url"], ziel)
            print(f"[Bild] {i+1}/{gesamt} fertig")
            return ziel
        except Exception as f:
            print(f"[Bild] {i+1}/{gesamt} FEHLER: {str(f)[:120]}")
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        ergebnisse = list(pool.map(eins, enumerate(bild_prompts)))

    pfade = [x for x in ergebnisse if x]
    print(f"[Bild] {len(pfade)}/{gesamt} erfolgreich")
    if not pfade:
        raise RuntimeError("Kein einziges Bild konnte erzeugt werden")
    return pfade

def erzeuge_stimme(kanal, text, ziel, stimme_id=None):
    """Erzeugt die Sprachaufnahme."""
    ziel = Path(ziel)
    ziel.parent.mkdir(parents=True, exist_ok=True)

    if config.TESTMODUS:
        sekunden = max(5, len(text) // 15)
        _test_ton(ziel, sekunden)
        print(f"[Stimme] Test-Ton erzeugt ({sekunden}s)")
        return ziel

    api = einstellungen.aktive_api(kanal, "stimme") or {}
    print(f"[Stimme] {kanal['name']} ({api.get('name','?')}): erzeuge Audio...")
    daten = {"text": text}
    stimme_id = stimme_id or kanal.get("stimme_id") or ""
    if stimme_id:
        daten["voice"] = stimme_id
    energie = float(kanal.get("stimme_energie", 0.6))
    # hohe Energie = lebendiger, niedrige = ruhiger/gleichmaessiger
    daten["stability"] = max(0.0, min(1.0, 1.0 - energie))
    daten["similarity_boost"] = 0.75
    daten["style"] = max(0.0, min(1.0, energie))
    ergebnis = _fal_anfrage(api.get("url") or FAL_STIMME, daten, api.get("key"))
    _lade_datei(ergebnis["audio"]["url"], ziel)
    return ziel


if __name__ == "__main__":
    print("=" * 45)
    print("MEDIEN TEST")
    print("=" * 45)
    test_ordner = config.ORDNER_VIDEOS / "_test"
    bilder = erzeuge_bilder(config.KANAL_A, ["Test 1", "Test 2", "Test 3"], test_ordner)
    print(f"\n{len(bilder)} Bilder erzeugt:")
    for b in bilder:
        print(f"  {b.name} ({b.stat().st_size // 1024} KB)")
    ton = erzeuge_stimme(config.KANAL_A, "Ein kurzer Test." * 5, test_ordner / "ton.mp3")
    print(f"\nTon: {ton.name} ({ton.stat().st_size // 1024} KB)")
    print("=" * 45)


def _bild_brauchbar(ziel):
    import os as _o, re as _r, subprocess as _s
    try:
        if not _o.path.exists(str(ziel)) or _o.path.getsize(str(ziel)) < 20000:
            return False
        r = _s.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(ziel), "-vf",
                    "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                    "-f", "null", "-"], capture_output=True, text=True, timeout=60)
        m = _r.search(r"YAVG=([0-9.]+)", r.stderr or "")
        return (float(m.group(1)) if m else 128.0) >= 22.0
    except Exception:
        return True


# ---------- Nachtrag r8: Wortzeiten statt Schaetzung ----------
#
# Bisher hat der Untertitel geraten, wann welches Wort gesprochen wird -
# nach Buchstabenzahl. Das geht bei zwei, drei Woertern gerade so, aber
# Pausen an Kommas zaehlt es nicht mit, und ein langes deutsches Wort wird
# nicht proportional laenger gesprochen.
#
# fal liefert auf Wunsch Zeitstempel je Wort mit. Das kostet nichts extra,
# es ist ein Feld mehr in der Anfrage. Die Zeiten landen als Beidatei neben
# der Tonspur, damit sich an erzeuge_stimme() nichts aendert und nichts
# kaputtgehen kann: sind Zeiten da, werden sie benutzt; kommen keine,
# bleibt es bei der Schaetzung wie bisher.

import json as _r8_json

_r8_stimme_alt = erzeuge_stimme


def worte_datei(ton):
    """Wo die Wortzeiten zu einer Tonspur liegen."""
    return Path(str(ton) + ".worte.json")


def _r8_zeiten_auslesen(roh):
    """Macht aus fals Antwort eine Liste [(wort, start, ende), ...].

    fal hat die Form schon zweimal geaendert, darum werden mehrere
    Schreibweisen angenommen statt einer einzigen erwartet.
    """
    if not roh:
        return []
    if isinstance(roh, dict):
        for schl in ("words", "word_timestamps", "timestamps", "alignment",
                     "characters"):
            if schl in roh:
                return _r8_zeiten_auslesen(roh[schl])
        return []
    if not isinstance(roh, list):
        return []
    raus = []
    for e in roh:
        if not isinstance(e, dict):
            continue
        wort = e.get("word") or e.get("text") or e.get("character") or ""
        # Vorsicht: das erste Wort faengt bei 0.0 an, und 0.0 gilt in Python
        # als leer. Mit "or" verkettet faellt es durch und das erste Wort
        # fehlt. Darum ausdruecklich auf None pruefen.
        anf = end = None
        for schl in ("start", "start_time", "start_time_seconds", "start_s"):
            if e.get(schl) is not None:
                anf = e[schl]
                break
        for schl in ("end", "end_time", "end_time_seconds", "end_s"):
            if e.get(schl) is not None:
                end = e[schl]
                break
        if anf is None or end is None:
            continue
        try:
            anf, end = float(anf), float(end)
        except Exception:
            continue
        if not str(wort).strip():
            continue        # Leerzeichen zwischen den Woertern
        raus.append((str(wort), anf, end))
    return raus


def erzeuge_stimme(kanal, text, ziel, stimme_id=None):
    """Wie bisher, aber mit Zeitstempeln je Wort, wenn der Anbieter sie gibt."""
    ziel = Path(ziel)
    if config.TESTMODUS:
        return _r8_stimme_alt(kanal, text, ziel, stimme_id)

    api = einstellungen.aktive_api(kanal, "stimme") or {}
    print("[Stimme] %s (%s): erzeuge Audio..." % (kanal["name"], api.get("name", "?")))
    daten = {"text": text, "timestamps": True}
    sid = stimme_id or kanal.get("stimme_id") or ""
    if sid:
        daten["voice"] = sid
    energie = float(kanal.get("stimme_energie", 0.6))
    daten["stability"] = max(0.0, min(1.0, 1.0 - energie))
    daten["similarity_boost"] = 0.75
    daten["style"] = max(0.0, min(1.0, energie))

    try:
        ergebnis = _fal_anfrage(api.get("url") or FAL_STIMME, daten, api.get("key"))
    except Exception as e:
        # Mag der Anbieter das Feld nicht, dann eben ohne - lieber eine
        # geschaetzte Zeit als gar keine Stimme.
        print("[Stimme] Zeitstempel abgelehnt (%s), versuche es ohne"
              % str(e)[:90])
        return _r8_stimme_alt(kanal, text, ziel, stimme_id)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    _lade_datei(ergebnis["audio"]["url"], ziel)

    zeiten = []
    for schl in ("timestamps", "word_timestamps", "alignment", "words"):
        if schl in (ergebnis or {}):
            zeiten = _r8_zeiten_auslesen(ergebnis[schl])
            if zeiten:
                break
    bei = worte_datei(ziel)
    if zeiten:
        try:
            with open(bei, "w", encoding="utf-8") as f:
                _r8_json.dump([{"w": w, "a": a, "e": e} for w, a, e in zeiten],
                              f, ensure_ascii=False)
            print("[Stimme] %d Wortzeiten gemessen" % len(zeiten))
        except Exception as e:
            print("[Stimme] Wortzeiten nicht ablegbar: %s" % str(e)[:90])
    else:
        try:
            if bei.exists():
                bei.unlink()       # alte Zeiten einer frueheren Fassung weg
        except Exception:
            pass
        print("[Stimme] keine Wortzeiten geliefert - Untertitel werden geschaetzt")
    return ziel


def worte_lesen(ton):
    """Die Wortzeiten zu einer Tonspur, oder eine leere Liste."""
    try:
        with open(worte_datei(ton), encoding="utf-8") as f:
            d = _r8_json.load(f)
        return [(x["w"], float(x["a"]), float(x["e"])) for x in d
                if str(x.get("w") or "").strip()]
    except Exception:
        return []


# ---------- Nachtrag r20: aufschreiben, was fal wirklich schickt ----------
#
# Im Log stand nur "keine Wortzeiten geliefert". Ob das Feld fehlt, leer
# ist oder nur anders heisst, war daran nicht zu erkennen - und ohne das
# laesst sich der Leser nicht anpassen.
#
# Jetzt steht bei einem Fehlschlag kurz dabei, welche Felder die Antwort
# hatte und wie der erste Eintrag aussieht. Der Text selbst kommt nicht
# ins Log, nur die Form.

def _r20_form(ergebnis):
    try:
        if not isinstance(ergebnis, dict):
            return "Antwort ist kein Objekt (%s)" % type(ergebnis).__name__
        felder = sorted(ergebnis.keys())
        zusatz = ""
        for schl in ("timestamps", "word_timestamps", "alignment", "words"):
            w = ergebnis.get(schl)
            if w is None:
                continue
            if isinstance(w, list):
                zusatz = " | %s: Liste mit %d" % (schl, len(w))
                if w and isinstance(w[0], dict):
                    zusatz += ", erster hat %s" % sorted(w[0].keys())
                elif w:
                    zusatz += ", erster ist %s" % type(w[0]).__name__
            elif isinstance(w, dict):
                zusatz = " | %s: Objekt mit %s" % (schl, sorted(w.keys()))
            else:
                zusatz = " | %s: %s" % (schl, type(w).__name__)
            break
        return "Felder: %s%s" % (felder, zusatz)
    except Exception as e:
        return "Form nicht lesbar: %s" % str(e)[:60]


_r20_erzeuge_alt = erzeuge_stimme


def erzeuge_stimme(kanal, text, ziel, stimme_id=None):
    global _R20_LETZTE
    pfad = _r20_erzeuge_alt(kanal, text, ziel, stimme_id)
    try:
        if pfad and not worte_datei(pfad).exists() and _R20_LETZTE:
            print("[Stimme] Antwort ohne Wortzeiten - %s" % _R20_LETZTE)
            _R20_LETZTE = ""
    except Exception:
        pass
    return pfad


_R20_LETZTE = ""
_r20_anfrage_alt = _fal_anfrage


def _fal_anfrage(url, daten, key=None, *a, **k):
    global _R20_LETZTE
    ergebnis = _r20_anfrage_alt(url, daten, key, *a, **k)
    try:
        if isinstance(daten, dict) and daten.get("timestamps"):
            _R20_LETZTE = _r20_form(ergebnis)
    except Exception:
        pass
    return ergebnis
