"""Kanaele anlegen, klonen, loeschen. Ein Kanal = eine Videoart."""
import json, os, shutil
import einstellungen, vorlagen

BASIS = os.path.dirname(os.path.abspath(__file__))
VIDEOS = os.path.join(BASIS, "fertige_videos")


GELOESCHT = os.path.join(BASIS, "regeln", "geloescht.json")


def _daten():
    return einstellungen.laden()


def _weg_liste():
    try:
        with open(GELOESCHT, encoding="utf-8") as f:
            d = json.load(f)
        return [str(x) for x in d] if isinstance(d, list) else []
    except Exception:
        return []


def _weg_merken(key):
    d = _weg_liste()
    if key not in d:
        d.append(key)
    os.makedirs(os.path.dirname(GELOESCHT), exist_ok=True)
    with open(GELOESCHT, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def neuer_key():
    d = _daten()
    n = 1
    while ("k%d" % n) in d:
        n += 1
    return "k%d" % n


def anzahl_videos(key):
    try:
        return len([x for x in os.listdir(VIDEOS) if x.startswith(key + "_")])
    except Exception:
        return 0


def liste():
    d = _daten()
    raus = []
    for k, v in d.items():
        if not isinstance(v, dict) or not (v.get("name") or k in ("a", "b")):
            continue
        raus.append({
            "key": k,
            "name": v.get("name") or k,
            "vorlage": v.get("vorlage") or "erklaer",
            "sprachen": v.get("sprachen") or ["de"],
            "eltern": v.get("geschwister_von") or None,
            "aktiv": bool(v.get("automatik_an", True)),
            "videos": anzahl_videos(k),
        })
    raus.sort(key=lambda x: (x["eltern"] or x["key"], x["eltern"] or ""))
    return raus


def kinder(key):
    return [x["key"] for x in liste() if x["eltern"] == key]


def anlegen(name, vorlage="erklaer", sprache="de"):
    v = vorlagen.holen(vorlage)
    d = _daten()
    key = neuer_key()
    d[key] = {
        "id": key,
        "emoji": "\U0001F3AC",
        "name": str(name or "Neuer Kanal").strip(),
        "vorlage": vorlage,
        "sprachen": [sprache],
        "prompt": v.get("prompt", ""),
        "laenge": v.get("laenge", 20),
        "bilder_pro_minute": v.get("bilder_pro_minute", 24),
        "stimme_an": v.get("stimme_an", True),
        "untertitel_an": v.get("untertitel_an", True),
        "automatik_an": False,
        "format": "9:16",
    }
    einstellungen.speichern(d)
    return key


def klonen(quelle, name):
    d = _daten()
    if quelle not in d:
        return None
    key = neuer_key()
    neu = dict(d[quelle])
    neu.pop("_key", None)
    neu.pop("geschwister_von", None)
    neu["id"] = key
    neu["name"] = str(name or (neu.get("name", "Kopie") + " Kopie")).strip()
    neu["automatik_an"] = False
    d[key] = neu
    einstellungen.speichern(d)
    return key


def geschwister(eltern, name, sprache, stimme=None):
    d = _daten()
    if eltern not in d:
        return None
    key = klonen(eltern, name)
    if not key:
        return None
    d = _daten()
    d[key]["geschwister_von"] = eltern
    d[key]["sprachen"] = [sprache]
    d[key]["automatik_an"] = False
    if stimme:
        d[key]["stimme_id"] = stimme
    einstellungen.speichern(d)
    return key


def loesen(key):
    d = _daten()
    if key in d and d[key].get("geschwister_von"):
        d[key].pop("geschwister_von", None)
        einstellungen.speichern(d)
        return True
    return False


def loeschen(key, mit_videos=False):
    if key in ("a", "b") and len(liste()) <= 1:
        return "letzter Kanal"
    if kinder(key):
        return "hat Geschwisterkanaele"
    d = _daten()
    if key not in d:
        return "unbekannt"
    del d[key]
    einstellungen.speichern(d)
    _weg_merken(key)
    for n in ("themen_%s.json" % key,):
        p = os.path.join(BASIS, "regeln", n)
        if os.path.exists(p):
            os.remove(p)
    if mit_videos:
        try:
            for x in os.listdir(VIDEOS):
                if x.startswith(key + "_"):
                    shutil.rmtree(os.path.join(VIDEOS, x), ignore_errors=True)
        except Exception:
            pass
    return None


# ---------- Nachtrag k2: Kanal ohne Vorlage anlegen ----------
#
# Die Vorlagen sind raus. Sie haben einmalig fuenf Werte in den neuen
# Kanal kopiert, von denen drei inzwischen tot sind (stimme_an,
# automatik, bilder_pro_minute). Uebrig waren Schreibanweisung und
# Laenge - und die Schreibanweisung steht sowieso im Masterprompt des
# Kanals, den man im Dashboard bearbeitet. Ein neuer Kanal faengt
# jetzt leer an. vorlagen.py bleibt liegen, wird nicht mehr gerufen.

_k2_anlegen_alt = anlegen


def anlegen(name, vorlage=None, sprache="de"):
    d = _daten()
    key = neuer_key()
    d[key] = {
        "id": key,
        "emoji": "\U0001F3AC",
        "name": str(name or "Neuer Kanal").strip(),
        "sprachen": [sprache or "de"],
        "prompt": "",
        "laenge": 20,
        "untertitel_an": True,
        "format": "9:16",
    }
    einstellungen.speichern(d)
    return key
