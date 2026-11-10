# ============================================
# Musik + Sounddesign
# Erzeugt oder waehlt Hintergrundmusik und mischt
# sie professionell unter die Stimme (mit Ducking).
# ============================================
import json
import random
import subprocess
import urllib.request
from pathlib import Path
import config

try:
    import einstellungen
except Exception:
    einstellungen = None

FAL_MUSIK = "fal-ai/stable-audio"


def _laenge(pfad):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(pfad)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def eigene_musik(kanal):
    """Sucht eine Musikdatei im Ordner musik/<kanal>/ ."""
    ordner = config.BASIS / "musik" / kanal["id"]
    if not ordner.exists():
        return None
    treffer = [f for f in sorted(ordner.iterdir())
               if f.is_file() and f.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")]
    return random.choice(treffer) if treffer else None


def erzeuge_musik(kanal, sekunden, ziel):
    """Erzeugt Musik per KI (fal.ai). Gibt None zurueck wenn nicht moeglich."""
    if einstellungen is None:
        return None
    api = einstellungen.aktive_api(kanal, "musik") or {}
    schluessel = api.get("key")
    if not schluessel:
        return None

    beschreibung = (kanal.get("musik_prompt") or "").strip()
    if not beschreibung:
        beschreibung = "calm cinematic background music, subtle, no vocals"

    url = api.get("url") or FAL_MUSIK
    voll = url if url.startswith("http") else "https://fal.run/" + url.strip("/")
    daten = json.dumps({
        "prompt": beschreibung,
        "seconds_total": int(min(120, max(10, sekunden + 5))),
    }).encode()
    anfrage = urllib.request.Request(voll, data=daten, headers={
        "Authorization": f"Key {schluessel}",
        "Content-Type": "application/json",
    })
    try:
        print(f"[Musik] erzeuge ({api.get('name','?')}): {beschreibung[:50]}...")
        with urllib.request.urlopen(anfrage, timeout=600) as antwort:
            e = json.loads(antwort.read().decode())
        adresse = (e.get("audio_file") or e.get("audio") or {}).get("url") or e.get("url")
        if not adresse:
            print("[Musik] keine Datei in der Antwort")
            return None
        ziel = Path(ziel)
        urllib.request.urlretrieve(adresse, ziel)
        print(f"[Musik] fertig ({_laenge(ziel):.1f}s)")
        return ziel
    except Exception as f:
        print(f"[Musik] nicht erzeugt: {str(f)[:140]}")
        return None


def hole_musik(kanal, sekunden, ordner):
    """Eigene Datei bevorzugt, sonst KI. None wenn Musik aus."""
    if not kanal.get("musik_an", True):
        return None
    eigen = eigene_musik(kanal)
    if eigen:
        print(f"[Musik] eigene Datei: {eigen.name}")
        return eigen
    return erzeuge_musik(kanal, sekunden, Path(ordner) / "musik.mp3")


def eigene_geraeusche(kanal):
    """Sucht eine Geraeusch-Datei im Ordner geraeusche/<kanal>/ ."""
    ordner = config.BASIS / "geraeusche" / kanal["id"]
    if not ordner.exists():
        return None
    zustand = {}
    z = ordner / "_aktiv.json"
    if z.exists():
        try:
            zustand = json.loads(z.read_text())
        except Exception:
            zustand = {}
    treffer = [f for f in sorted(ordner.iterdir())
               if f.is_file() and f.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg")
               and zustand.get(f.name, True)]
    return random.choice(treffer) if treffer else None


def hole_ambience(kanal):
    """Atmosphaere-Geraeusch, falls eingeschaltet."""
    if not kanal.get("geraeusche_an", False):
        return None
    g = eigene_geraeusche(kanal)
    if g:
        print(f"[Ton] Atmosphaere: {g.name}")
    return g


def mische(kanal, stimme, musik, ziel, dauer=None, ambience=None):
    """Mischt Stimme + Musik: Ducking, Fades, Normalisierung."""
    stimme, ziel = Path(stimme), Path(ziel)
    dauer = dauer or _laenge(stimme)
    pegel = float(kanal.get("musik_pegel", 0.22))
    ziel_lufs = float(kanal.get("lautheit", -14))

    if not musik or not Path(musik).exists() or pegel <= 0:
        # nur Stimme, aber sauber normalisiert
        befehl = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(stimme),
                  "-af", f"loudnorm=I={ziel_lufs}:TP=-1.5:LRA=11,alimiter=limit=0.97",
                  "-t", f"{dauer:.3f}", "-c:a", "aac", "-b:a", "192k", str(ziel)]
        subprocess.run(befehl, check=True, capture_output=True)
        print("[Ton] nur Stimme, normalisiert")
        return ziel

    ausblenden = max(0.5, min(3.0, dauer * 0.12))
    kette = (
        f"[0:a]asplit=2[st][trig];"
        f"[1:a]aloop=loop=-1:size=2e9,atrim=duration={dauer:.3f},"
        f"volume={pegel},afade=t=in:st=0:d=1.5,"
        f"afade=t=out:st={max(0, dauer - ausblenden):.3f}:d={ausblenden:.3f}[mus];"
        f"[mus][trig]sidechaincompress=threshold=0.03:ratio=10:attack=5:release=350[duck];"
        f"[st][duck]amix=inputs=2:duration=first:normalize=0[roh];"
        f"[roh]loudnorm=I={ziel_lufs}:TP=-1.5:LRA=11,alimiter=limit=0.97[out]"
    )
    eingaben = ["-i", str(stimme), "-i", str(musik)]
    if ambience and Path(ambience).exists():
        amb_pegel = float(kanal.get("geraeusche_pegel", 0.12))
        eingaben += ["-i", str(ambience)]
        kette = kette.replace("[roh];",
            f"[stimmemusik];[2:a]aloop=loop=-1:size=2e9,"
            f"atrim=duration={dauer:.3f},volume={amb_pegel},"
            f"afade=t=in:st=0:d=2,afade=t=out:st={max(0,dauer-2):.3f}:d=2[amb];"
            f"[stimmemusik][amb]amix=inputs=2:duration=first:normalize=0[roh];")
        print(f"[Ton] + Atmosphaere ({int(amb_pegel*100)}%)")

    befehl = ["ffmpeg", "-y", "-loglevel", "error"] + eingaben + [
              "-filter_complex", kette, "-map", "[out]",
              "-t", f"{dauer:.3f}", "-c:a", "aac", "-b:a", "192k", str(ziel)]
    e = subprocess.run(befehl, capture_output=True, text=True)
    if e.returncode != 0:
        print("[Ton] Mischen fehlgeschlagen:", e.stderr[-300:])
        return stimme
    print(f"[Ton] Stimme + Musik gemischt (Musik {int(pegel*100)}%, Ducking an)")
    return ziel


if __name__ == "__main__":
    print("=" * 46)
    print("MUSIK-MODUL")
    print("=" * 46)
    for k in config.KANAELE:
        an = k.get("musik_an", True)
        print(f"{k['emoji']} {k['name']}: Musik {'AN' if an else 'AUS'}, "
              f"Pegel {int(float(k.get('musik_pegel',0.22))*100)}%")
        e = eigene_musik(k)
        wo = e.name if e else "keine in musik/" + k["id"] + "/"
        print(f"   eigene Dateien: {wo}")
    print("=" * 46)
