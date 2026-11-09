"""Themenliste und Themengedaechtnis je Kanal."""
import json, os, time

ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regeln")


def _key(kanal):
    if isinstance(kanal, dict):
        return str(kanal.get("_key") or kanal.get("name") or "a")
    return str(kanal or "a")


def _pfad(kanal):
    return os.path.join(ORDNER, "themen_%s.json" % _key(kanal))


def laden(kanal):
    d = {"offen": [], "erledigt": []}
    p = _pfad(kanal)
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                g = json.load(f)
            if isinstance(g, dict):
                d["offen"] = [str(x).strip() for x in (g.get("offen") or []) if str(x).strip()]
                d["erledigt"] = [x for x in (g.get("erledigt") or []) if isinstance(x, dict)]
        except Exception:
            pass
    return d


def speichern(kanal, d):
    os.makedirs(ORDNER, exist_ok=True)
    with open(_pfad(kanal), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


def naechstes(kanal):
    d = laden(kanal)
    return d["offen"][0] if d["offen"] else None


def erledigt(kanal, thema):
    if not thema:
        return
    t = str(thema).strip()
    d = laden(kanal)
    d["offen"] = [x for x in d["offen"] if x.lower() != t.lower()]
    schon = [(x.get("thema") or "").strip().lower() for x in d["erledigt"]]
    if t.lower() not in schon:
        d["erledigt"].append({"thema": t, "datum": time.strftime("%Y-%m-%d %H:%M")})
    d["erledigt"] = d["erledigt"][-200:]
    speichern(kanal, d)


def hinzufuegen(kanal, thema):
    t = str(thema or "").strip()
    if not t:
        return False
    d = laden(kanal)
    if t.lower() in [x.lower() for x in d["offen"]]:
        return False
    d["offen"].append(t)
    speichern(kanal, d)
    return True


def entfernen(kanal, thema):
    t = str(thema or "").strip().lower()
    d = laden(kanal)
    vorher = len(d["offen"])
    d["offen"] = [x for x in d["offen"] if x.lower() != t]
    speichern(kanal, d)
    return len(d["offen"]) < vorher


def zuruecksetzen(kanal):
    d = laden(kanal)
    d["erledigt"] = []
    speichern(kanal, d)


def hinweis(kanal, anzahl=25):
    d = laden(kanal)
    alt = [(x.get("thema") or "").strip() for x in d["erledigt"][-anzahl:]]
    alt = [x for x in alt if x]
    if not alt:
        return ""
    return ("\nDiese Themen gab es auf diesem Kanal schon. Nimm KEINES davon "
            "und auch nichts, was inhaltlich fast dasselbe ist:\n- "
            + "\n- ".join(alt) + "\n")
