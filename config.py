# ============================================
# AIUNIVERSE - Zentrale Einstellungen
# Liest die Dashboard-Einstellungen aus einstellungen.json
# ============================================
from pathlib import Path
import einstellungen

BASIS = Path(__file__).parent
ORDNER_BILDER = BASIS / "bilder"
ORDNER_REGELN = BASIS / "regeln"
ORDNER_VIDEOS = BASIS / "fertige_videos"
ORDNER_LOGS = BASIS / "logs"


def lade_env():
    keys = {}
    datei = BASIS / ".env"
    if datei.exists():
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            zeile = zeile.strip()
            if zeile and not zeile.startswith("#") and "=" in zeile:
                name, wert = zeile.split("=", 1)
                keys[name.strip()] = wert.strip()
    return keys


ENV = lade_env()
TESTMODUS = ENV.get("TESTMODUS", "true").lower() == "true"
ANTHROPIC_KEY = ENV.get("ANTHROPIC_KEY", "")
FAL_KEY = ENV.get("FAL_KEY", "")
HEDRA_KEY = ENV.get("HEDRA_KEY", "")
FREESOUND_KEY = ENV.get("FREESOUND_KEY", "")

# Kanaele aus dem Dashboard laden
_alle = einstellungen.laden()
KANAL_A = _alle["a"]
KANAL_B = _alle["b"]
KANAELE = [KANAL_A, KANAL_B]

CHECK_INTERVALL_MIN = 10
MAX_VERSUCHE = 18


def neu_laden():
    """Laedt die Einstellungen frisch (nach Dashboard-Aenderung)."""
    global KANAL_A, KANAL_B, KANAELE, ENV, TESTMODUS
    global ANTHROPIC_KEY, FAL_KEY, HEDRA_KEY, FREESOUND_KEY
    ENV = lade_env()
    TESTMODUS = ENV.get("TESTMODUS", "true").lower() == "true"
    ANTHROPIC_KEY = ENV.get("ANTHROPIC_KEY", "")
    FAL_KEY = ENV.get("FAL_KEY", "")
    HEDRA_KEY = ENV.get("HEDRA_KEY", "")
    FREESOUND_KEY = ENV.get("FREESOUND_KEY", "")
    alle = einstellungen.laden()
    KANAL_A = alle["a"]
    KANAL_B = alle["b"]
    KANAELE = [KANAL_A, KANAL_B]
    return KANAELE


def aktive_bilder(kanal):
    """Gibt nur die AKTIVEN Bilder dieses Kanals zurueck (fuer Rotation)."""
    import json
    ordner = ORDNER_BILDER / kanal["id"]
    if not ordner.exists():
        return []
    zustand = {}
    z = ordner / "_aktiv.json"
    if z.exists():
        try:
            zustand = json.loads(z.read_text())
        except Exception:
            pass
    treffer = []
    for f in sorted(ordner.iterdir()):
        if f.name.startswith("_") or not f.is_file():
            continue
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        if zustand.get(f.name, True):
            treffer.append(f)
    return treffer


if __name__ == "__main__":
    print("=" * 48)
    print("AIUNIVERSE Konfiguration")
    print("=" * 48)
    print(f"Testmodus: {TESTMODUS}")
    for k in KANAELE:
        print(f"\n{k['emoji']} {k['name']}")
        print(f"   {k['plattformen']}")
        print(f"   Laenge:   {k['laenge']} {k['laenge_einheit']}")
        print(f"   Uhrzeit:  {k['uhrzeit']} ({k['videos_pro_tag']}x taeglich)")
        print(f"   Sprachen: {', '.join(k['sprachen'])}")
        print(f"   Bilder:   {einstellungen.anzahl_bilder(k)} Stueck")
        print(f"   Auto:     {'AN' if k['auto_an'] else 'AUS'}")
        print(f"   Eigene Bilder aktiv: {len(aktive_bilder(k))}")
    print("\n" + "-" * 48)
    for name in ["ANTHROPIC_KEY", "FAL_KEY", "HEDRA_KEY"]:
        print(f"  {name}: {'JA' if ENV.get(name) else 'noch leer'}")
    print("=" * 48)
