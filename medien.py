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
