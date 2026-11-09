import json, os
from pathlib import Path

ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regeln")
DATEI = Path(ORDNER) / "einstellungen.json"

STANDARD = {"a": {"name": "True Crime", "laenge": 20},
            "b": {"name": "Fluffy Finanzen", "laenge": 20}}


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


def speichern(neue):
    os.makedirs(ORDNER, exist_ok=True)
    sauber = {}
    for k, v in (neue or {}).items():
        if isinstance(v, dict):
            v = dict((kk, vv) for kk, vv in v.items() if kk != "_key")
        sauber[k] = v
    json.dump(sauber, open(DATEI, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


_laden_alt = laden


def laden():
    d = _laden_alt()
    try:
        for k, v in d.items():
            if isinstance(v, dict):
                v["_key"] = k
    except Exception:
        pass
    return d


_laden_t2 = laden


def laden():
    d = _laden_t2()
    try:
        import json as _j, os as _o
        p = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "regeln", "geloescht.json")
        if _o.path.exists(p):
            with open(p, encoding="utf-8") as f:
                weg = _j.load(f)
            for k in (weg or []):
                d.pop(k, None)
    except Exception:
        pass
    return d


API_SLOTS = [("text", "Text-KI"), ("bilder", "Bild-KI"), ("stimme", "Stimme"),
             ("video", "Animation"), ("musik", "Musik"), ("sound", "Geraeusche"),
             ("avatar", "Avatar")]


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


def laenge_in_minuten(kanal):
    try:
        return float((kanal or {}).get("laenge") or 20) / 60.0
    except Exception:
        return 20 / 60.0


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
