import einstellungen
import json
from pathlib import Path
import config


def lade_prompt(kanal):
    """Laedt den Master-Prompt aus dem regeln-Ordner."""
    datei = config.ORDNER_REGELN / f"prompt_{kanal['id']}.txt"
    if datei.exists():
        return datei.read_text(encoding="utf-8")
    return f"Du bist Erzaehler fuer den Kanal {kanal['name']}."


def lade_regeln(kanal):
    """Laedt die Regeln aus dem regeln-Ordner."""
    datei = config.ORDNER_REGELN / f"regeln_{kanal['id']}.txt"
    if datei.exists():
        return datei.read_text(encoding="utf-8")
    return ""


def erzeuge_paket(kanal, eigenes_thema=None):
    """Erzeugt das komplette Text-Paket fuer EIN Video."""
    laenge = einstellungen.laenge_in_minuten(kanal)
    anzahl_bilder = max(3, int(laenge * kanal["bilder_pro_minute"]))

    prompt = f"""{lade_prompt(kanal)}

REGELN:
{lade_regeln(kanal)}

AUFGABE:
Erstelle EIN komplettes Video-Paket.
Laenge: ca. {laenge*60:.0f} Sekunden gesprochen
Das SKRIPT hat genau {anzahl_bilder} Szenen. Jede Szene ist EIN gesprochener Satz mit {max(4, int(laenge*60*_p37_wps(kanal)/max(1,anzahl_bilder)))} bis {max(6, int(laenge*60*_p37_wps(kanal)/max(1,anzahl_bilder))+3)} Woertern. Insgesamt rund {int(laenge*60*_p37_wps(kanal))} Woertern. Zaehle die Woerter und halte dich exakt daran. Lieber etwas laenger als kuerzer - zu kurz ist schlimmer!
{P49_THEMA % eigenes_thema if eigenes_thema else "Waehle selbst ein passendes Thema."}
"""
    antwort = kanal.get("_testantwort") or "{}"
    import json
    try:
        return _p40_json(antwort)
    except json.JSONDecodeError:
        return {"_prompt": prompt, "_fehler": "json"}


# ---------- Nachtrag p33: Serien ----------
# Ein Fall wird am Stueck geschrieben und danach getrennt. Die KI kennt beim
# Schreiben das Ende und kann die Nahtstellen dahin legen, wo es wehtut.

_p33_prompt_alt = lade_prompt

SERIE_SATZ = """SERIE: Dieser Fall wird in %d Teile geteilt.
Schreibe alle Teile am Stueck, als eine durchgehende Geschichte.
Setze zwischen zwei Teile eine eigene Szene, deren Text nur ### ist
und die keine Bildbeschreibung hat.
Jeder Teil beginnt mit einem eigenen Haken, nicht mit einer Zusammenfassung
des vorigen. Jeder Teil endet mitten im Geschehen, an einer Stelle, wo gerade
etwas Neues aufgetaucht ist.
Teil 1 muss fuer sich allein verstaendlich sein - er bringt die Reichweite.
Jeder Teil ist mindestens 70 Sekunden gesprochen, also kein Teil darf kurz sein."""


def lade_prompt(kanal):
    """Wie bisher, plus Serienanweisung wenn der Kanal eine Serie baut."""
    text = _p33_prompt_alt(kanal)
    try:
        n = int((kanal or {}).get("serie_teile") or 1)
    except Exception:
        n = 1
    if n > 1 and "SERIE:" not in text:
        text = text + "\n\n" + (SERIE_SATZ % n)
    return text


# ---------- Nachtrag p36: Masterprompt aus dem Dashboard + Serie ----------
# Steht absichtlich als letztes in der Datei. Was hier definiert wird, gilt.

_p36_alt_prompt = lade_prompt
try:
    _p36_alt_regeln = lade_regeln
except NameError:
    _p36_alt_regeln = None

P36_FIGUR = ("Wenn %s etwas sagt, schreibe es in Anfuehrungszeichen mitten in "
             "den Satz. Alles ohne Anfuehrungszeichen spricht der Erzaehler.")

P36_SERIE = """=== SERIE: DIESER FALL WIRD IN %(n)d TEILE GETEILT ===
Das ist die wichtigste Regel dieses Auftrags.

Schreibe alle %(n)d Teile am Stueck als EINE durchgehende Geschichte.

Zwischen zwei Teilen steht eine eigene, zusaetzliche Szene als Trenner:
- ihr gesprochener Text ist genau ### und sonst gar nichts
- ihre Bildbeschreibung ist genau: black screen
Anzahl dieser Trennerszenen: %(t)d. Ohne sie ist der Auftrag nicht
erfuellt. Schreibe sonst nirgends ### hin.

Jeder Teil faengt mit einem eigenen Haken an, nicht mit einer
Zusammenfassung des vorigen, und endet mitten im Geschehen an einer
Stelle, wo gerade etwas Neues aufgetaucht ist.
Teil 1 muss fuer sich allein verstaendlich sein - er bringt die Reichweite.
Jeder Teil ist mindestens 70 Sekunden gesprochen. Kein Teil darf kurz sein."""


def _p36_teile(kanal):
    try:
        n = int((kanal or {}).get("serie_teile") or 1)
    except Exception:
        n = 1
    return n if n > 1 else 1


def lade_prompt(kanal):
    """Dashboard-Feld schlaegt Datei schlaegt Notnagel, dann Figur, dann Serie."""
    k = kanal or {}
    text = (k.get("prompt") or "").strip()
    if not text:
        try:
            text = (_p36_alt_prompt(k) or "").strip()
        except Exception:
            text = ""
    if not text:
        text = "Du bist Erzaehler fuer den Kanal %s." % (k.get("name") or "")

    figur = (k.get("geschichte_figur") or "").strip()
    if figur and "nfuehrungszeichen" not in text and "nf\u00fchrungszeichen" not in text:
        text = text + "\n\n" + (P36_FIGUR % figur)

    n = _p36_teile(k)
    if n > 1 and "SERIE" not in text:
        text = text + "\n\n" + (P36_SERIE % {"n": n, "t": n - 1})
    return text


def lade_regeln(kanal):
    """Regeln: Dashboard-Feld schlaegt Datei."""
    k = kanal or {}
    text = (k.get("regeln") or "").strip()
    if text:
        return text
    if _p36_alt_regeln is None:
        return ""
    try:
        return _p36_alt_regeln(k) or ""
    except Exception:
        return ""


# ---------- Nachtrag p37: Woerter je Sekunde ----------
# 1,8 war geraten. An einem fertigen Video gemessen: 2,65 Woerter je Sekunde
# Video. 2,5 als Vorgabe laesst etwas Luft nach oben, damit ein Teil eher
# zu lang als zu kurz wird. Im Kanal unter woerter_pro_sekunde aenderbar.

P37_STANDARD = 2.5


def _p37_wps(kanal):
    try:
        wert = float((kanal or {}).get("woerter_pro_sekunde") or P37_STANDARD)
    except Exception:
        wert = P37_STANDARD
    if wert < 1.2 or wert > 4.0:
        wert = P37_STANDARD
    return wert


# ---------- Nachtrag p40: JSON mit Anfuehrungszeichen retten ----------
# Ein gerades " mitten in einem Text beendet dort den JSON-Wert. Wir gehen
# Zeichen fuer Zeichen durch und ersetzen nur die Anfuehrungszeichen, auf
# die KEIN Komma, Doppelpunkt oder Klammerende folgt - das sind die, die
# im Text stehen und nicht zum JSON gehoeren.

import json as _p40_json_modul

_P40_STRUKTUR = ":,}]"


def _p40_flicken(text):
    raus = []
    im_string = False
    auf = True
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if not im_string:
            raus.append(c)
            if c == chr(34):
                im_string = True
            i += 1
            continue
        if c == chr(92):
            raus.append(text[i:i + 2])
            i += 2
            continue
        if c == chr(34):
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j >= n or text[j] in _P40_STRUKTUR:
                raus.append(c)
                im_string = False
            else:
                raus.append("\u00bb" if auf else "\u00ab")
                auf = not auf
            i += 1
            continue
        raus.append(c)
        i += 1
    return "".join(raus)


def _p40_json(antwort):
    """Erst normal einlesen, bei Bruch einmal flicken und nochmal."""
    try:
        return _p40_json_modul.loads(antwort)
    except Exception:
        pass
    geflickt = _p40_flicken(antwort)
    try:
        d = _p40_json_modul.loads(geflickt)
        print("[Text] Anfuehrungszeichen im JSON geflickt")
        return d
    except Exception:
        raise _p40_json_modul.JSONDecodeError(
            "JSON auch nach dem Flicken unlesbar", antwort, 0)


# ---------- Nachtrag p42: Rettung mit Spur ----------

import os as _p42_os

_P42_SPUR = _p42_os.path.join(
    _p42_os.path.dirname(_p42_os.path.abspath(__file__)), "letzte_antwort.txt")
_P42_SCHWAENZE = ("", "]}", "}]}", "\"}]}", "]", "}", "}}")


def _p42_merken(antwort, grund):
    try:
        with open(_P42_SPUR, "w", encoding="utf-8") as f:
            f.write("GRUND: %s\n" % grund)
            f.write("ZEICHEN: %d\n" % len(antwort or ""))
            f.write("ENDET AUF: %r\n" % (antwort or "")[-40:])
            f.write("-" * 60 + "\n")
            f.write(antwort or "")
        print("[Text] Rohantwort liegt in %s" % _P42_SPUR)
    except Exception:
        pass


def _p42_abschneiden(text):
    """Bei abgeschnittener Antwort bis zur letzten ganzen Szene zurueck."""
    stellen = [i for i, c in enumerate(text) if c == "}"]
    for i in reversed(stellen[-60:]):
        stueck = text[:i + 1]
        for schwanz in _P42_SCHWAENZE:
            try:
                d = _p40_json_modul.loads(stueck + schwanz)
            except Exception:
                continue
            if isinstance(d, dict) and d.get("szenen"):
                return d
    return None


def _p40_json(antwort):
    """Normal lesen, sonst Anfuehrungszeichen flicken, sonst abschneiden."""
    erster = None
    try:
        return _p40_json_modul.loads(antwort)
    except Exception as e:
        erster = e

    try:
        d = _p40_json_modul.loads(_p40_flicken(antwort))
        print("[Text] Anfuehrungszeichen im JSON geflickt")
        return d
    except Exception:
        pass

    d = _p42_abschneiden(antwort)
    if d is not None:
        print("[Text] Antwort war abgeschnitten - %d ganze Szenen gerettet"
              % len(d.get("szenen") or []))
        _p42_merken(antwort, "abgeschnitten, %d Szenen gerettet" % len(d.get("szenen") or []))
        return d

    d = _p42_abschneiden(_p40_flicken(antwort))
    if d is not None:
        print("[Text] geflickt und abgeschnitten - %d ganze Szenen gerettet"
              % len(d.get("szenen") or []))
        _p42_merken(antwort, "geflickt und abgeschnitten")
        return d

    _p42_merken(antwort, "unlesbar: %s" % erster)
    raise _p40_json_modul.JSONDecodeError(
        "unlesbar (%s) - Rohantwort liegt in %s" % (erster, _P42_SPUR), antwort or "", 0)


# ---------- Nachtrag p49: das Thema durchsetzen ----------
# Eine Zeile reicht nicht, wenn drumherum 6000 Zeichen stehen. Der Absatz
# steht an derselben Stelle wie vorher, nimmt sich aber mehr Platz und sagt
# klar, dass das Thema die Geschichte bestimmt - nicht nur anregt.

P49_THEMA = """=== DAS THEMA DIESES VIDEOS ===
%s

Die Geschichte handelt von genau diesem Thema. Ort, Titel und Geschehen
muessen dazu passen. Steht im Thema ein Ort - ein Moor, ein See, ein
Bahnhof -, dann spielt die Geschichte dort und nicht woanders.
Weiche nicht auf ein anderes Thema aus, auch nicht auf ein aehnliches.
Faellt dir zu dem Thema wenig ein, erfinde mehr Einzelheiten dazu -
aber bleib dabei."""


# ---------- Nachtrag p80: zwei Regeln in den Masterprompt ----------

P80_WOERTER = """WOERTER:
Benutze keine Woerter mit mehr als 14 Buchstaben. Lange zusammengesetzte
Woerter schreibst du auseinander: statt "Haftpflichtversicherungsbeitrag"
schreibst du "Beitrag fuer die Haftpflicht", statt "Lebenshaltungskosten"
schreibst du "was das Leben kostet". Das gilt fuer jeden gesprochenen Satz.
Kurze Woerter versteht man beim Hoeren besser und sie passen in den
Untertitel, ohne dass er getrennt werden muss."""

P80_EINTEILIG = """ENDE:
Diese Geschichte ist mit diesem einen Video zu Ende. Erzaehle sie fertig.
Kuendige keinen naechsten Teil an, schreibe kein "Fortsetzung folgt", kein
"mehr dazu im naechsten Video" und kein offenes Ende. Die letzte Szene
loest auf, worum es ging."""

_p80_prompt_alt = lade_prompt


def lade_prompt(kanal):
    """Wie bisher, dazu die Wortregel - und bei einem Teil die Endregel."""
    text = _p80_prompt_alt(kanal)
    # Auf den genauen Satz pruefen, nicht auf ein Allerweltswort -
    # "Buchstaben" kann in jedem Prompt stehen.
    if "mehr als 14 Buchstaben" not in text:
        text = text + "\n\n" + P80_WOERTER
    try:
        teile = _p36_teile(kanal)
    except Exception:
        teile = 1
    # Bei einem Teil kommt die Endregel immer. Steht im Prompt noch ein
    # Serienrest von frueher, soll sie ihn gerade ueberstimmen - sie steht
    # hinten und gilt damit zuletzt.
    if teile <= 1 and "Kuendige keinen naechsten Teil" not in text:
        text = text + "\n\n" + P80_EINTEILIG
    return text


# ---------- Nachtrag p82: Regieanweisung in den Masterprompt ----------

P82_REGIE = """REGIEANWEISUNG
Hinter jeden gesprochenen Satz setzt du eine Anweisung in eckige Klammern.
Sie wird nicht gesprochen und steht in keinem Untertitel. Sie sagt dem
Modell, das die Szene bewegt, was sich im Bild ruehren soll.

In die Klammern kommt nur, was ein Bild-zu-Video-Modell sauber kann:
Kamera - langsam heranfahren, langsam zurueck, sanft zur Seite ziehen.
Umgebung - Nebel, Rauch, Staub im Licht, Regen, Schnee, Blaetter, Funken.
Licht - flackern, langsam heller werden, Schatten wandert, ein Blitz.
Stoff und Haare - ein Vorhang bewegt sich, ein Mantel weht, Haare im Wind.
Wasser - Wellen, Tropfen, eine Spiegelung zittert.

In die Klammern kommt nie: Personen, die gehen, greifen, sich umdrehen,
die Haende bewegen, den Kopf drehen oder reden. Keine Gesichtsausdruecke.
Menschen im Bild bleiben ruhig - bewegt wird alles um sie herum. Steht
eine Figur im Bild, wird sie in der Klammer nicht erwaehnt.

Eine Klammer je Szene, hoechstens zwoelf Woerter.
Beispiel: Er hatte den Brief nie geoeffnet. [Kamera faehrt langsam heran,
Staub schwebt im Lichtstrahl]"""

_p82_prompt_alt = lade_prompt


def lade_prompt(kanal):
    """Wie bisher, dazu der Regieblock."""
    text = _p82_prompt_alt(kanal)
    if "REGIEANWEISUNG" not in text:
        text = text + "\n\n" + P82_REGIE
    return text


# ---------- Nachtrag p85: Beweisbilder statt Stimmungsbilder ----------

P85_BILD = """BILD UND BEWEGUNG
Hinter jeden gesprochenen Satz setzt du eine Bildbeschreibung in eckige
Klammern, mit BILD davor. Sie wird nicht gesprochen und steht in keinem
Untertitel. Sie ist das, was gemalt wird - also muss sie ein Bild sein und
nicht der Satz noch einmal.

Beispiel: Drei Euro am Tag sind tausend im Jahr.
[BILD: tausend Ein-Euro-Muenzen flach ausgebreitet auf schwarzem Tisch,
von oben, randlos bis zum Bildrand]

SO BAUST DU EIN BILD
Ein Gegenstand, nah dran. Keine Szene mit mehreren Dingen darin.
Die Menge macht die Aussage: nicht eine Muenze, sondern tausend. Nicht
ein Becher, sondern dreihundertfuenfundsechzig. Nicht ein Blatt, sondern
ein kniehoher Stapel.
Nenne Material und Licht: Blech, Papier, nasser Asphalt, Sonne von der
Seite, Neonlicht von oben, eine Lampe im Dunkeln.
Nenne den Blickwinkel: von oben, dicht ueber dem Tisch, aus der Hocke,
von unten.
Acht bis zwanzig Woerter. Jede Szene ein anderer Gegenstand.

WAS NIE INS BILD KOMMT
Keine Schrift, keine Buchstaben, keine Zahlen, keine Logos, keine
Preisschilder, keine Zeitungen, keine Bildschirme mit Text. Daraus werden
unleserliche Zeichen.
Keine Sinnbilder: kein Muenzstapel, kein Sparschwein, keine Kurve, die
nach oben zeigt, kein Eurozeichen, keine Gluehbirne, keine Waage, keine
Hand, die Geldscheine faechert. Das sieht nach Baukasten aus und wird
weggescrollt.
Nichts Abstraktes: Freiheit, Druck, Sicherheit, Zukunft kann man nicht
malen. Nenne den Gegenstand, an dem man es sieht.
Menschen nur, wenn der Satz von einem Menschen handelt - dann ein
Koerperteil nah dran, kein Gesicht, keine ganze Person.

ZWOELF GEGENSTAENDE ALS RICHTUNG
eine offene leere Geldboerse auf einem Beifahrersitz
ein kniehoher Stapel Kontoauszuege, danebengekippt
Pappbecher in Reihen auf dem Boden einer leeren Wohnung
ein Einkaufswagen mit einem einzigen Artikel darin
eine Stechuhr-Karte, durchgestempelt bis nach unten
ein Kassenzettel, zerknuellt auf nassem Asphalt
ein Schluesselbund an einem Nagel in einer kahlen Wand
ein Umzugskarton, halb gepackt, im Flur
zwei Paar Schuhe nebeneinander, eines neu, eines durchgelaufen
Finger auf einer einzigen Zeile im Kleingedruckten
ein Kuehlschrank von innen, fast leer, Licht an
ein Briefkasten, ueberquellend, von unten gesehen

BEWEGUNG
Nur wenn sich im Video etwas ruehren soll, setzt du eine zweite Klammer
mit BEWEGUNG davor. Laesst du sie weg, bleibt das Bild stehen - bei
solchen Bildern ist das meist das Bessere.
In die Bewegungsklammer kommt nur, was ein Bild-zu-Video-Modell sauber
kann: Kamera langsam heran oder zurueck, Staub im Licht, Rauch, Regen,
Licht das flackert, ein Vorhang der sich bewegt, Wasser das zittert.
Nie Personen, die gehen, greifen, sich umdrehen oder reden - daraus wird
Matsch. Hoechstens zwoelf Woerter.

Beispiel mit beidem: Er hatte den Brief nie geoeffnet.
[BILD: ein ungeoeffneter Brief auf einem Holzboden, Staub, Licht von
schraeg oben] [BEWEGUNG: Kamera faehrt langsam heran, Staub schwebt]"""

_p85_prompt_alt = lade_prompt


def lade_prompt(kanal):
    """Wie bisher - der Regieblock aus p82 weicht dem neuen Bildblock.

    Der alte Block verlangte einen Kamerabefehl in denselben Klammern, in
    denen jetzt die Bildbeschreibung steht. Zwei Anweisungen fuer eine
    Klammer waeren ein Widerspruch, darum wird der alte herausgenommen.
    """
    text = _p85_prompt_alt(kanal)
    alt = globals().get("P82_REGIE") or ""
    if alt and alt in text:
        text = text.replace("\n\n" + alt, "")
        text = text.replace(alt, "")
    if "BILD UND BEWEGUNG" not in text:
        text = text.rstrip() + "\n\n" + P85_BILD
    return text


# ---------- Nachtrag p87: vollstaendiger Prompt steht fuer sich ----------

P87_MARKE = "=== AIU PROFI-FORMAT"

_p87_alt = lade_prompt


def lade_prompt(kanal):
    """Traegt der Prompt die Marke, wird nichts mehr angehaengt."""
    k = kanal or {}
    eigen = k.get("prompt") or ""
    if P87_MARKE not in eigen:
        return _p87_alt(k)

    text = eigen.rstrip()

    # Figur und Serie haengen am Kanal, nicht am Format - die bleiben.
    figur = (k.get("geschichte_figur") or "").strip()
    if figur and "nfuehrungszeichen" not in text and "nführungszeichen" not in text:
        try:
            text = text + "\n\n" + (P36_FIGUR % figur)
        except Exception:
            pass
    try:
        n = _p36_teile(k)
    except Exception:
        n = 1
    if n > 1 and "SERIE" not in text:
        try:
            text = text + "\n\n" + (P36_SERIE % {"n": n, "t": n - 1})
        except Exception:
            pass
    return text
