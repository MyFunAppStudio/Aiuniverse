"""Vorlagen: Bauplaene, aus denen Kanaele entstehen."""
import json, os

ORDNER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "regeln")
DATEI = os.path.join(ORDNER, "vorlagen_eigene.json")

STANDARD = {
    "erklaer": {
        "name": "Erklaervideo",
        "beschreibung": "Eine Figur erklaert ein Thema in kurzen Saetzen. Wiederholbar, laeuft automatisch.",
        "stimme_an": True, "untertitel_an": True, "automatik": True,
        "bilder_pro_minute": 24, "laenge": 20,
        "prompt": "Du erklaerst ein Thema so, dass es jeder sofort versteht. "
                  "Kurze Hauptsaetze, keine Fachbegriffe ohne Erklaerung. "
                  "Beginne mit einer Zahl oder Behauptung, die ueberrascht. "
                  "Schliesse mit einem Satz, der zum Folgen auffordert.",
    },
    "build": {
        "name": "Build-Video",
        "beschreibung": "Etwas entsteht Schritt fuer Schritt. Ohne Stimme, nur Musik und Text.",
        "stimme_an": False, "untertitel_an": True, "automatik": True,
        "bilder_pro_minute": 40, "laenge": 25,
        "prompt": "Zeige, wie etwas Schritt fuer Schritt entsteht. "
                  "Pro Szene nur ein kurzer Hinweis von zwei bis vier Woertern, "
                  "wie eine Beschriftung. Kein Fliesstext, keine Anrede.",
    },
    "maerchen": {
        "name": "Maerchen",
        "beschreibung": "Erzaehlbogen mit Anfang, Wendung und Schluss. Mehrere Figuren moeglich.",
        "stimme_an": True, "untertitel_an": True, "automatik": True,
        "bilder_pro_minute": 14, "laenge": 90,
        "prompt": "Erzaehle eine kleine Geschichte mit Anfang, Wendung und Schluss. "
                  "Ruhiger Ton, bildhafte Sprache. Wenn Figuren sprechen, "
                  "stelle ihren Saetzen den Namen voran, so: NAME: Text.",
    },
    "firma": {
        "name": "Firmenvideo",
        "beschreibung": "Einmaliges Video fuer ein Angebot. Nur von Hand, keine Automatik.",
        "stimme_an": True, "untertitel_an": True, "automatik": False,
        "bilder_pro_minute": 20, "laenge": 30,
        "prompt": "Stelle ein Angebot sachlich und freundlich vor. "
                  "Nutzen vor Eigenschaften. Keine Superlative, keine leeren Versprechen. "
                  "Am Ende ein klarer naechster Schritt.",
    },
    "musik": {
        "name": "Musikvideo",
        "beschreibung": "Bilder zu einem eigenen Lied. Nur von Hand.",
        "stimme_an": False, "untertitel_an": False, "automatik": False,
        "bilder_pro_minute": 30, "laenge": 60,
        "prompt": "Beschreibe Bilder, die zur Stimmung des Liedes passen. "
                  "Kein gesprochener Text, nur Bildbeschreibungen.",
    },
    "slideshow": {
        "name": "Slideshow",
        "beschreibung": "Liste oder Aufzaehlung, ein Punkt pro Bild.",
        "stimme_an": True, "untertitel_an": True, "automatik": True,
        "bilder_pro_minute": 30, "laenge": 25,
        "prompt": "Zaehle Punkte auf, einen pro Szene. "
                  "Jeder Punkt ein kurzer Satz. Der staerkste Punkt kommt zuletzt.",
    },
}


def eigene():
    if not os.path.exists(DATEI):
        return {}
    try:
        with open(DATEI, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def alle():
    d = dict(STANDARD)
    for k, v in eigene().items():
        if isinstance(v, dict):
            d[k] = v
    return d


def holen(kennung):
    return dict(alle().get(kennung) or STANDARD["erklaer"])


def speichern_eigene(kennung, daten):
    k = str(kennung or "").strip().lower()
    if not k or k in STANDARD:
        return False
    d = eigene()
    d[k] = daten
    os.makedirs(ORDNER, exist_ok=True)
    with open(DATEI, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return True


def loeschen_eigene(kennung):
    d = eigene()
    if kennung not in d:
        return False
    del d[kennung]
    with open(DATEI, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return True
