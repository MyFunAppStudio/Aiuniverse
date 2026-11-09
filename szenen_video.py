# -*- coding: utf-8 -*-
"""Baut ein Video aus eigenen Szenen: Bilder, Clips, Texte, Stimme, Musik."""
import json, os, re, subprocess
from pathlib import Path

import szenen

BASIS = os.path.dirname(os.path.abspath(__file__))


def _lauf(befehl):
    return subprocess.run(befehl, capture_output=True, text=True)


def _dauer(pfad):
    r = _lauf(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(pfad)])
    try:
        return max(0.0, float((r.stdout or "0").strip()))
    except Exception:
        return 0.0


def _hat_ton(pfad):
    r = _lauf(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
               "stream=index", "-of", "csv=p=0", str(pfad)])
    return bool((r.stdout or "").strip())


def _masse(kanal):
    import video_bauen as vb
    try:
        vb._setze_format(kanal)
    except Exception:
        pass
    return int(getattr(vb, "BREITE", 1080)), int(getattr(vb, "HOEHE", 1920)), int(getattr(vb, "FPS", 30))


# ---------- Bewegung ----------
# (Zoomhub, Schwenk seitlich, Schwenk hoch/runter)
# Die Schwenkwerte sind die Auslenkung um die Bildmitte, nicht von Rand zu Rand.
STAERKE = {"sanft":  (0.08, 0.25, 0.15),
           "mittel": (0.13, 0.35, 0.22),
           "stark":  (0.20, 0.45, 0.30)}


def _zoompan(bewegung, nr, dauer, b, h, fps, staerke="sanft"):
    rahmen = max(2, int(round(dauer * fps)))
    gb, gh = int(b * 1.25) // 2 * 2, int(h * 1.25) // 2 * 2
    vor = "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (gb, gh, gb, gh)
    if bewegung == "auto":
        bewegung = ["rein", "links", "raus", "rechts", "hoch", "runter"][nr % 6]
    if bewegung == "aus":
        return "%s,scale=%d:%d,setsar=1,fps=%d" % (vor, b, h, fps)
    # weicher Verlauf: langsam anfahren, langsam abbremsen (statt gleichmaessig)
    hub, weit_x, weit_y = STAERKE.get(staerke or "sanft", STAERKE["sanft"])
    lauf = "(on/%d)" % rahmen
    e = "(%s*%s*(3-2*%s))" % (lauf, lauf, lauf)
    # Pendel: laeuft von -1 ueber 0 nach +1, also um die Mitte herum
    pendel = "(2*%s-1)" % e
    mitte_x = "iw/2-(iw/zoom/2)"
    mitte_y = "ih/2-(ih/zoom/2)"
    rand_x = "(iw-iw/zoom)"
    rand_y = "(ih-ih/zoom)"
    if bewegung == "rein":
        zo, x, y = "1.01+%.3f*%s" % (hub, e), mitte_x, mitte_y
    elif bewegung == "raus":
        zo, x, y = "%.3f-%.3f*%s" % (1.01 + hub, hub, e), mitte_x, mitte_y
    else:
        # Schwenk mit leichter Zoomfahrt. Die Mitte bleibt die Mitte, damit
        # bei einer stehenden Figur der Kopf nicht aus dem Bild wandert.
        zo = "1.03+%.3f*%s" % (hub * 0.45, e)
        if bewegung == "links":
            x, y = "%s*(0.5-%.3f*%s)" % (rand_x, weit_x, pendel), mitte_y
        elif bewegung == "rechts":
            x, y = "%s*(0.5+%.3f*%s)" % (rand_x, weit_x, pendel), mitte_y
        elif bewegung == "hoch":
            x, y = mitte_x, "%s*(0.5-%.3f*%s)" % (rand_y, weit_y, pendel)
        else:
            x, y = mitte_x, "%s*(0.5+%.3f*%s)" % (rand_y, weit_y, pendel)
    return ("%s,zoompan=z='%s':x='%s':y='%s':d=%d:s=%dx%d:fps=%d,setsar=1"
            % (vor, zo, x, y, rahmen, b, h, fps))


def _ganz(bewegung, nr, dauer, b, h, fps):
    """Bild ganz zeigen, Rand mit weichgezeichneter Vergroesserung fuellen."""
    rahmen = max(2, int(round(dauer * fps)))
    gb, gh = int(b * 1.25) // 2 * 2, int(h * 1.25) // 2 * 2
    if bewegung == "auto":
        bewegung = ["rein", "raus"][nr % 2]
    grund = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
             "gblur=sigma=26,eq=brightness=-0.12" % (gb, gh, gb, gh))
    if bewegung == "aus":
        hg = grund + ",scale=%d:%d,setsar=1" % (b, h)
    else:
        z = ("max(1.10-0.00035*on,1.0001)" if bewegung == "raus"
             else "min(1.0001+0.00035*on,1.10)")
        hg = grund + (",zoompan=z='%s':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
                      ":d=%d:s=%dx%d:fps=%d,setsar=1" % (z, rahmen, b, h, fps))
    return ("[0:v]split=2[hg][vg];[hg]%s[a];"
            "[vg]scale=%d:%d:force_original_aspect_ratio=decrease,setsar=1[c];"
            "[a][c]overlay=(W-w)/2:(H-h)/2,fps=%d,format=yuv420p[v]" % (hg, b, h, fps))


def _figur_bewegung_filter(hoehe, b, h):
    """Atmen und Wippen fuer ein Standbild, rein per Rechnung, ohne Kosten."""
    atem = max(2, int(hoehe * 0.018))
    dx = max(2, int(b * 0.006))
    dy = max(2, int(h * 0.005))
    skala = ("[1:v]scale=w=-1:h='%d+%d*sin(2*PI*t/2.9)':eval=frame,format=rgba[fig];"
             % (hoehe, atem))
    return skala, "+%d*sin(2*PI*t/3.7)" % dx, "+%d*sin(2*PI*t/2.9)" % dy


def _figur_filter(platz, groesse, b, h, rein, raus, wie="statisch"):
    """Haengt die freigestellte Figur ins Bild. wie: statisch, bewegt, animiert."""
    rand = int(b * 0.045)
    unten = int(h * 0.20)
    hoehe = max(40, int(h * max(10, min(100, groesse)) / 100.0))
    x = {"links_unten": str(rand), "mitte_unten": "(W-w)/2", "rechts_unten": "W-w-%d" % rand,
         "links_oben": str(rand), "rechts_oben": "W-w-%d" % rand,
         "mitte": "(W-w)/2"}.get(platz, "W-w-%d" % rand)
    y = {"links_unten": "H-h-%d" % unten, "mitte_unten": "H-h-%d" % unten,
         "rechts_unten": "H-h-%d" % unten, "links_oben": str(rand),
         "rechts_oben": str(rand), "mitte": "(H-h)/2"}.get(platz, "H-h-%d" % unten)
    skala = ("[1:v]scale=-2:%d:force_original_aspect_ratio=decrease,format=rgba[fig];"
             % hoehe)
    if wie == "bewegt":
        skala, zx, zy = _figur_bewegung_filter(hoehe, b, h)
        x, y = x + zx, y + zy
    return skala + "%s[fig]overlay=%s:%s:format=auto%s" % (rein, x, y, raus)


def _figur_eingang(figur):
    """Wie die Figurdatei als zweiter Eingang geladen wird."""
    if (figur or {}).get("art") == "clip":
        return ["-stream_loop", "-1", "-i", str(figur["pfad"])]
    return ["-loop", "1", "-i", str(figur["pfad"])]


def _p44_masse_der_quelle(pfad):
    """Breite und Hoehe einer Bild- oder Videodatei, sonst None."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                            "-show_entries", "stream=width,height",
                            "-of", "csv=p=0:s=x", str(pfad)],
                           capture_output=True, text=True, timeout=20)
        teile = (r.stdout or "").strip().splitlines()[0].split("x")
        b, h = int(teile[0]), int(teile[1])
        return (b, h) if b > 0 and h > 0 else None
    except Exception:
        return None


def _p44_passen(quelle, b, h, wunsch="auto"):
    """fuellen, wenn die Quelle aufs Format passt - sonst ganz zeigen.

    Ein bisschen Toleranz ist drin: bis sechs Prozent Abweichung faellt beim
    Fuellen nichts Wichtiges weg, und ein randloses Bild sieht besser aus.
    Alles darueber wird ganz gezeigt, damit kein Kopf mehr abgeschnitten wird.
    """
    if wunsch in ("ganz", "fuellen"):
        return wunsch
    masse = _p44_masse_der_quelle(quelle)
    if not masse:
        return "fuellen"
    soll = float(b) / float(h)
    ist = float(masse[0]) / float(masse[1])
    weit = abs(ist - soll) / soll
    return "fuellen" if weit <= 0.06 else "ganz"


def _p44_ganz_clip(b, h, fps, dauer):
    """Wie _ganz, aber fuer einen Clip: Hintergrund ist der Clip selbst."""
    return ("[0:v]split=2[hg][vg];"
            "[hg]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
            "gblur=sigma=26,eq=brightness=-0.12,setsar=1[a];"
            "[vg]scale=%d:%d:force_original_aspect_ratio=decrease,setsar=1[c];"
            "[a][c]overlay=(W-w)/2:(H-h)/2,fps=%d,"
            "tpad=stop_mode=clone:stop_duration=%.3f[v]"
            % (b, h, b, h, b, h, fps, dauer))


def _stueck_bild(quelle, ziel, bewegung, nr, dauer, b, h, fps, passen="auto", figur=None,
                 staerke="sanft"):
    vorn = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(quelle)]
    passen = _p44_passen(quelle, b, h, passen)
    if passen == "ganz":
        grund = _ganz(bewegung, nr, dauer, b, h, fps)
    else:
        grund = "[0:v]" + _zoompan(bewegung, nr, dauer, b, h, fps, staerke) + "[v]"
    if figur and os.path.exists(figur.get("pfad") or ""):
        vorn += _figur_eingang(figur)
        stelle = grund.rfind("[v]")
        grund = (grund[:stelle] + "[v0];"
                 + _figur_filter(figur.get("platz"), figur.get("groesse", 55), b, h, "[v0]", "[v]",
                                 figur.get("wie", "statisch")))
    return _lauf(vorn + ["-filter_complex", grund, "-map", "[v]", "-t", "%.3f" % dauer,
                         "-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264",
                         "-preset", "veryfast", "-crf", "22", "-an", str(ziel)]).returncode == 0


def _stueck_clip(quelle, ziel, dauer, b, h, fps, figur=None, passen="auto"):
    if _p44_passen(quelle, b, h, passen) == "ganz":
        grund = _p44_ganz_clip(b, h, fps, dauer)
    else:
        grund = ("[0:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,"
                 "setsar=1,fps=%d,tpad=stop_mode=clone:stop_duration=%.3f[v]"
                 % (b, h, b, h, fps, dauer))
    vorn = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(quelle)]
    if figur and os.path.exists(figur.get("pfad") or ""):
        vorn += _figur_eingang(figur)
        grund = (grund[:grund.rfind("[v]")] + "[v0];"
                 + _figur_filter(figur.get("platz"), figur.get("groesse", 55), b, h, "[v0]", "[v]",
                                 figur.get("wie", "statisch")))
    r = _lauf(vorn + ["-filter_complex", grund, "-map", "[v]", "-t", "%.3f" % dauer,
                      "-r", str(fps), "-pix_fmt", "yuv420p", "-c:v", "libx264",
                      "-preset", "veryfast", "-crf", "22", "-an", str(ziel)])
    return r.returncode == 0


ANFUEHRUNG = '"\u201e\u201c\u201d\u00bb\u00ab'


def _ohne_anfuehrung(text):
    """Nimmt die Anfuehrungszeichen raus.

    Sie sind eine Anweisung an den Code, keine Schrift fuer den Zuschauer:
    sie sagen, wer spricht. Im Bild stehen sie nur im Weg.
    """
    roh = "".join(" " if z in ANFUEHRUNG else z for z in (text or ""))
    return " ".join(roh.split())


# ---------- Untertitel ----------
def _ass(plan, ziel, b, h, kanal=None):
    import video_bauen as vb
    k = kanal or {}
    gewaehlt = (k.get("untertitel_schrift") or "auto")
    schrift = vb._tt_schrift() if gewaehlt in ("", "auto") else gewaehlt
    try:
        groesse = max(20.0, min(120.0, float(k.get("untertitel_groesse") or 48)))
    except Exception:
        groesse = 48.0
    try:
        woerter = int(k.get("untertitel_woerter") or 3)
    except Exception:
        woerter = 3
    woerter = max(1, min(6, woerter))
    caps = k.get("untertitel_caps") is not False
    fs = max(24, int(h * 0.046 * groesse / 48.0))
    rand = max(3, int(fs * 0.11))
    schatten = max(2, int(fs * 0.07))
    ml = int(b * 0.085)
    mv = int(h * 0.17)
    zeilen = [vb._tt_ass_kopf(fs, rand, schatten, ml, mv, schrift)]
    for s in plan:
        if not s["untertitel"] or not (s["text"] or "").strip():
            continue
        stuecke = vb._tt_stuecke(_ohne_anfuehrung(s["text"]),
                                 max_w=woerter, max_z=max(10, woerter * 6))
        if not stuecke:
            continue
        zeichen = [max(1, len(" ".join(x))) for x in stuecke]
        summe = float(sum(zeichen))
        t = s["start"]
        for st, z in zip(stuecke, zeichen):
            d = max(0.45, s["dauer"] * z / summe)
            text = " ".join(st).replace("{", "(").replace("}", ")")
            if caps:
                text = text.upper()
            zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,{\\fad(90,90)}%s\n"
                          % (vb._tt_zeit(t), vb._tt_zeit(min(t + d, s["start"] + s["dauer"])), text))
            t += d
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("".join(zeilen))
    return ziel


# ---------- Musik ----------
MINDESTLUECKE = 2.5


def _stufen(plan, leise, laut, anheben=True):
    """Lautstaerke je Szene: eigener Wert, sonst automatisch."""
    lang = [False] * len(plan)
    i = 0
    while i < len(plan):
        if plan[i]["stimme"]:
            i += 1
            continue
        j = i
        while j < len(plan) and not plan[j]["stimme"]:
            j += 1
        laenge = sum(plan[x]["dauer"] for x in range(i, j))
        if laenge >= MINDESTLUECKE:
            for x in range(i, j):
                lang[x] = True
        i = j
    raus = []
    for nr, s in enumerate(plan):
        eigen = s.get("musik", "auto")
        if eigen not in (None, "", "auto"):
            try:
                raus.append(max(0.0, min(1.5, float(eigen) / 100.0)))
                continue
            except Exception:
                pass
        if not s["stimme"] and anheben and lang[nr]:
            raus.append(laut)
        else:
            raus.append(leise)
    return raus


def _musik_ausdruck(plan, leise, laut, anheben=True, rampe=0.45):
    """Stufenkurve mit weichen Uebergaengen als ffmpeg-Ausdruck."""
    stufen = _stufen(plan, leise, laut, anheben)
    if not stufen:
        return "%.3f" % leise
    teile = ["%.4f" % stufen[0]]
    for i in range(1, len(stufen)):
        unterschied = stufen[i] - stufen[i - 1]
        if abs(unterschied) < 0.005:
            continue
        ab = max(0.0, plan[i]["start"] - rampe / 2.0)
        teile.append("(%.4f)*max(0,min(1,(t-%.3f)/%.2f))" % (unterschied, ab, rampe))
    return "+".join(teile)


def _stille(ziel, dauer):
    return _lauf(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                  "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                  "-t", "%.3f" % dauer, "-c:a", "pcm_s16le", str(ziel)]).returncode == 0


def _auf_mass(quelle, ziel, dauer):
    return _lauf(["ffmpeg", "-y", "-loglevel", "error", "-i", str(quelle),
                  "-af", "aresample=48000,apad", "-ac", "2", "-t", "%.3f" % dauer,
                  "-c:a", "pcm_s16le", str(ziel)]).returncode == 0


def _liste(dateien, ziel):
    with open(ziel, "w", encoding="utf-8") as f:
        for d in dateien:
            f.write("file '%s'\n" % str(d).replace("'", "'\\''"))
    return ziel


def _zusammen(dateien, liste_pfad, ziel, kopie=True):
    _liste(dateien, liste_pfad)
    befehl = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
              "-i", str(liste_pfad)]
    befehl += (["-c", "copy"] if kopie else [])
    befehl += [str(ziel)]
    return _lauf(befehl).returncode == 0


def _figur_fuer(kanal, s):
    """Welche Figur in welcher Pose kommt in diese Szene."""
    name = (s.get("figur") or "").strip()
    if not name:
        return None
    wie = (s.get("figur_bewegung") or "").strip().lower()
    try:
        import figuren
        if not wie:
            f = figuren.holen(kanal, name) or {}
            wie = (f.get("bewegung") or "bewegt").strip().lower()
        info = figuren.pose_info(kanal, name, s.get("pose"), wie)
    except Exception as e:
        print("[Szenen] Figur nicht nutzbar:", e)
        return None
    if not info or not info.get("pfad") or not os.path.exists(info["pfad"]):
        return None
    if wie not in ("statisch", "bewegt", "animiert"):
        wie = "bewegt"
    if wie == "animiert" and info.get("art") != "clip":
        wie = "bewegt"          # keine Schleife da, dann wenigstens beleben
    if wie != "animiert" and info.get("art") == "clip":
        wie = "animiert"        # eine Schleife laeuft immer als Schleife
    return {"pfad": info["pfad"], "art": info.get("art", "bild"), "wie": wie,
            "platz": s.get("platz", "rechts_unten"),
            "groesse": s.get("figur_groesse", 55)}


ZITAT = '"\u201e\u201c\u201d\u00bb\u00ab\u2019\u2018'


def _nach_anfuehrung(text):
    """Zerlegt einen Satz in Stuecke: (gehoert_der_figur, text).

    Jedes Anfuehrungszeichen schaltet um. Was dazwischen steht, spricht die
    Figur, der Rest der Erzaehler.
    """
    stuecke, puffer, drin = [], "", False
    for z in (text or ""):
        if z in ZITAT:
            if puffer.strip():
                stuecke.append((drin, puffer.strip()))
            puffer, drin = "", not drin
        else:
            puffer += z
    if puffer.strip():
        stuecke.append((drin, puffer.strip()))
    return [(a, b) for a, b in stuecke if b]


def _ton_kleben(teile, ziel):
    """Haengt mehrere Tonstuecke zu einem zusammen."""
    teile = [x for x in teile if x and os.path.exists(x) and os.path.getsize(x) > 400]
    if not teile:
        return None
    if len(teile) == 1:
        return teile[0]
    liste = str(ziel) + ".txt"
    with open(liste, "w", encoding="utf-8") as f:
        for x in teile:
            f.write("file '%s'\n" % str(x).replace("'", "'\\''"))
    r = _lauf(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
               "-i", liste, "-c:a", "libmp3lame", "-q:a", "4", str(ziel)])
    try:
        os.remove(liste)
    except Exception:
        pass
    return str(ziel) if r.returncode == 0 and os.path.exists(ziel) else None


def _stimme_fuer(kanal, figur):
    """Sucht die Stimme einer Figur in der Stimmenliste des Kanals."""
    name = (figur or "").strip().lower()
    if not name:
        return None
    try:
        import figuren
        f = figuren.holen(kanal, name)
        if f and (f.get("stimme") or "").strip():
            return f["stimme"].strip()
    except Exception:
        pass
    for e in (kanal.get("stimmen") or []):
        if isinstance(e, dict) and (e.get("name") or "").strip().lower() == name:
            return (e.get("id") or "").strip() or None
    return None


TEMPO = [["ruhig", "ruhig, lange Bilder", 0.0],
         ["normal", "normal", 6.5],
         ["schnell", "schnell, wie Erklaervideos", 3.2],
         ["sehr_schnell", "sehr schnell, wie Fakten-Clips", 2.3]]
TEMPO_GRENZE = {a[0]: a[2] for a in TEMPO}


def _tempo_grenze(kanal):
    """Hoechste Dauer einer Einstellung in Sekunden. 0 heisst: nicht teilen."""
    w = (kanal.get("tempo") or "normal").strip().lower()
    return TEMPO_GRENZE.get(w, 6.5)


def _schnitte(dauer, hoechst):
    """Teilt eine lange Szene in mehrere Einstellungen gleicher Laenge."""
    if hoechst <= 0.1 or dauer <= hoechst * 1.35:
        return [dauer]
    n = int(dauer / hoechst)
    if dauer - n * hoechst > 1e-6:
        n += 1
    n = max(2, min(12, n))
    s = dauer / float(n)
    return [s] * n


def _knackspur(kanal, arbeit, gesamt, schnitte):
    """Tonspur mit einem Geraeusch je Schnitt. None heisst: keine."""
    art = (kanal.get("schnitt_ton") or "whoosh").strip().lower()
    if art in ("", "aus") or not schnitte or gesamt <= 0.2:
        return None
    try:
        import geraeusche
        return geraeusche.spur(str(arbeit / "schnitte.wav"), gesamt, schnitte, art, 0.9)
    except Exception as e:
        print("[Szenen] Schnittgeraeusche aus:", e)
        return None


NACHLAUF = 0.9      # Sekunden, die nach dem letzten Wort noch stehenbleiben


REGIE = re.compile(r"\[([^\[\]]{1,400})\]", re.S)


def _regie_trennen(text):
    """Trennt die Regieanweisung vom gesprochenen Text.

    Alles in eckigen Klammern ist Regie: es wird nicht gesprochen, steht in
    keinem Untertitel und geht nur an das Modell, das die Szene bewegt.
    Gibt (gesprochener Text, Regieanweisung) zurueck.
    """
    ganz = text or ""
    anweisung = " | ".join(" ".join(x.split()) for x in REGIE.findall(ganz)
                           if x and x.strip())
    rest = " ".join(REGIE.sub(" ", ganz).split())
    return rest, anweisung


def plan_bauen(kanal, ordner):
    """Pro Szene: Stimme erzeugen, Dauer messen, Startzeit festlegen."""
    import medien
    daten = szenen.fuer_anzeige(kanal)
    plan, zeit = [], 0.0
    for nr, s in enumerate(daten["szenen"]):
        quelle = szenen.datei_pfad(kanal, s["datei"])
        # Nachtrag r7: ein im Dashboard abgenommener Clip schlaegt das
        # Standbild. Er ist schon bezahlt, darum wird er in _ki_animieren
        # auch nicht noch einmal durch die Animation geschickt - das
        # uebernimmt dort die Abfrage auf typ == "clip".
        if s.get("clip"):
            _r7_pfad = szenen.datei_pfad(kanal, s["clip"])
            if os.path.exists(_r7_pfad):
                quelle = _r7_pfad
                s["typ"] = "clip"
                s["bewegung"] = "aus"
                print("[Szenen] Szene %d nimmt den abgenommenen Clip %s"
                      % (nr + 1, s["clip"]))
        if not os.path.exists(quelle):
            print("[Szenen] uebersprungen, Datei fehlt: %s" % s["datei"])
            continue
        text, regie = _regie_trennen(s["text"])
        ton, dauer, teile_info = None, 0.0, []
        if s["gesprochen"] and text:
            ton = os.path.join(ordner, "sz_%02d.mp3" % (nr + 1))
            k2 = dict(kanal)
            if s.get("stimmung") and s["stimmung"] in szenen.ENERGIE:
                k2["stimme_energie"] = szenen.ENERGIE[s["stimmung"]]
            figur_name = (s.get("figur") or "").strip() or (kanal.get("geschichte_figur") or "").strip()
            eigene = _stimme_fuer(kanal, figur_name)

            def _sprich(wort, stimme, wohin):
                try:
                    medien.erzeuge_stimme(k2, wort, wohin, stimme_id=stimme)
                except TypeError:
                    medien.erzeuge_stimme(k2, wort, wohin)
                return wohin if os.path.exists(wohin) else None

            stuecke = _nach_anfuehrung(text)
            # Auch ohne eigene Figurenstimme wird getrennt gesprochen: der
            # Avatar braucht das Stueck der Figur als eigene Datei.
            geteilt = len(stuecke) > 1 and any(a for a, _b in stuecke)
            if geteilt:
                gemacht = []
                for j, (ist_figur, wort) in enumerate(stuecke):
                    teil = os.path.join(ordner, "sz_%02d_%d.mp3" % (nr + 1, j))
                    fertig_teil = _sprich(wort, eigene if ist_figur else None, teil)
                    gemacht.append(fertig_teil)
                    if fertig_teil:
                        teile_info.append((bool(ist_figur), fertig_teil,
                                           _dauer(fertig_teil)))
                if None in gemacht:
                    teile_info = []
                zusammen = _ton_kleben(gemacht, ton)
                if zusammen:
                    ton = zusammen
                    print("[Stimme] Szene %d: %d Stuecke, davon %d von der Figur"
                          % (nr + 1, len(stuecke), sum(1 for a, _b in stuecke if a)))
                else:
                    teile_info = []
                    _sprich(text, eigene, ton)
            else:
                _sprich(text, eigene, ton)
            dauer = _dauer(ton)
            if dauer <= 0.05:
                print("[Szenen] Stimme fehlgeschlagen bei Szene %d" % (nr + 1))
                ton, dauer, teile_info = None, 0.0, []
        if dauer <= 0.05:
            ton = None
            if s["typ"] == "clip":
                dauer = _dauer(quelle) or float(s["sekunden"] or s["vorschlag"])
            else:
                dauer = float(s["sekunden"] or s["vorschlag"] or 3.0)
        dauer = max(0.8, min(120.0, dauer))
        plan.append({"nr": nr, "quelle": quelle, "typ": s["typ"], "text": text,
                     "stuecke": teile_info, "regie": regie,
                     "untertitel": bool(s["untertitel"]), "stimme": ton is not None,
                     "ton": ton, "bewegung": s.get("bewegung", "auto"), "musik": s.get("musik", "auto"),
                     "passen": s.get("passen") or "auto",
                     "stimmung": s.get("stimmung", ""), "figur": s.get("figur", ""),
                     "pose": s.get("pose", ""), "platz": s.get("platz", "rechts_unten"),
                     "figur_groesse": s.get("figur_groesse", 55),
                     "start": zeit, "dauer": dauer})
        zeit += dauer

    # Der letzte Satz soll noch stehenbleiben, bevor das Bild weg ist.
    if plan:
        try:
            zu = float(kanal.get("nachlauf", NACHLAUF))
        except Exception:
            zu = NACHLAUF
        zu = max(0.0, min(5.0, zu))
        if zu > 0.01:
            plan[-1]["dauer"] = plan[-1]["dauer"] + zu
            print("[Szenen] %.1f s Nachlauf am Schluss" % zu)
    return plan, daten


BEWEGUNG_GRUND = ("die Figur bewegt sich lebendig: Gewicht verlagert sich, Haare und Kleidung schwingen mit, kleine Gesten mit den Haenden, Kopf dreht sich leicht, Blick zur Kamera, Kamera bleibt ruhig")


def _bewegungs_text(kanal, szene):
    """Was Kling in dieser Szene bewegen soll.

    Ohne Satz wird es bei jeder Szene dieselbe Bewegung - deshalb geht der
    Satz der Szene mit, damit Szene 4 anders aussieht als Szene 1.
    """
    regie = (szene.get("regie") or "").strip()
    if regie:
        # Ausdrueckliche Regieanweisung schlaegt alles andere
        return regie[:900]
    eigen = (kanal.get("kling_prompt") or "").strip()
    grund = eigen or BEWEGUNG_GRUND
    satz = (szene.get("text") or "").strip()
    if satz:
        return ("%s. In dieser Szene: %s" % (grund, satz))[:900]
    return grund[:900]


def _avatar_szene(kanal, s, i, arbeit, grund_text=""):
    """Baut eine Szene, in der die Figur redet.

    Jedes Tonstueck wird ein eigenes Videostueck: das der Figur kommt vom
    Avatar (Mund passt zum Text), das des Erzaehlers bleibt ein Standbild mit
    Kamerafahrt. Danach hintereinandergehaengt. So liegt der bewegte Mund
    genau auf den Woertern der Figur und nicht auf denen des Erzaehlers.
    """
    import animation
    stuecke = list(s.get("stuecke") or [])
    if not stuecke or not any(a for a, _p, _d in stuecke):
        return None, 0.0
    b, h, fps = _masse(kanal)
    # Rundungsreste beim Zusammenkleben landen im letzten Stueck
    summe = sum(max(0.2, d) for _a, _p, d in stuecke)
    rest = float(s.get("dauer") or summe) - summe
    teile, bezahlt = [], 0.0
    for j, (ist_figur, ton, d) in enumerate(stuecke):
        d = max(0.2, float(d or 0))
        if j == len(stuecke) - 1 and rest > 0:
            d += rest
        ziel = arbeit / ("av_%02d_%d.mp4" % (i, j))
        if ist_figur:
            roh = arbeit / ("avroh_%02d_%d.mp4" % (i, j))
            pfad = animation.erzeuge_avatar(kanal, s["quelle"], ton, str(roh),
                                            grund_text)
            if not pfad:
                return None, 0.0
            bezahlt += animation.preis_je_avatar(kanal, d)
            if not _stueck_clip(pfad, ziel, d, b, h, fps):
                return None, 0.0
        else:
            if not _stueck_bild(s["quelle"], ziel, s.get("bewegung") or "auto",
                                i * 10 + j, d, b, h, fps, s.get("passen") or "auto",
                                None, kanal.get("bewegung_staerke") or "sanft"):
                return None, 0.0
        teile.append(ziel)
    ganz = arbeit / ("avganz_%02d.mp4" % i)
    if not _zusammen(teile, arbeit / ("av%02d.txt" % i), ganz):
        return None, 0.0
    return str(ganz), bezahlt


def _ki_animieren(kanal, plan, arbeit):
    """Macht aus ausgewaehlten Standbildern bewegte Clips. Kostet Geld."""
    try:
        import animation
    except Exception as e:
        print("[Szenen] Animation nicht nutzbar:", e)
        return plan
    manuell = set(i for i, s in enumerate(plan) if s.get("ki_animation"))
    avatar_ok, avatar_grund = animation.avatar_bereit(kanal)
    anteil = kanal.get("kling_anteil", 0)

    def _redet_hier(s):
        return (s.get("typ") != "clip"
                and any(a for a, _p, _d in (s.get("stuecke") or [])))

    redner = set(i for i, s in enumerate(plan) if _redet_hier(s))

    # Sprechszenen gehen immer an den Avatar - wer redet, soll auch zu sehen
    # sein. Der Prozentsatz ist nur noch fuer die Szenen da, in denen niemand
    # redet, also fuer die reine Bewegung im Bild.
    if avatar_ok and redner:
        uebrig = [i for i, s in enumerate(plan)
                  if i not in redner and s.get("typ") != "clip"]
        teilplan = [plan[i] for i in uebrig]
        auto = set(uebrig[j] for j in animation.auswahl(teilplan, anteil))
        wunsch = sorted(manuell | redner | auto)
    else:
        auto = animation.auswahl(plan, anteil)
        wunsch = sorted(manuell | auto)
    if not wunsch:
        return plan

    ok, grund = animation.bereit(kanal)
    if not ok and not avatar_ok:
        print("[Szenen] Animation uebersprungen: %s" % grund)
        return plan
    if not ok:
        # Nur der Avatar ist eingerichtet: dann eben nur die Sprechszenen
        print("[Szenen] Nur Sprechszenen bewegt, denn: %s" % grund)
        wunsch = [i for i in wunsch if i in redner]
        if not wunsch:
            return plan
    seite = kanal.get("format") or "9:16"
    gesagt = False
    gemacht, geredet, kosten = 0, 0, 0.0
    for i in wunsch:
        s = plan[i]
        if s.get("typ") == "clip":
            continue
        hinweis = _bewegungs_text(kanal, s)
        redet = any(a for a, _p, _d in (s.get("stuecke") or []))
        if redet:
            if avatar_ok:
                pfad, bezahlt = _avatar_szene(kanal, s, i, arbeit, hinweis)
                if pfad:
                    s["quelle"] = pfad
                    s["typ"] = "clip"
                    s["bewegung"] = "aus"
                    geredet += 1
                    kosten += bezahlt
                    continue
                print("[Szenen] Szene %d: Avatar ging nicht, nehme die Animation"
                      % (i + 1))
            elif not gesagt:
                gesagt = True
                print("[Szenen] Figur redet, aber %s" % avatar_grund)
        if not ok:
            print("[Szenen] Szene %d bleibt ein Standbild" % (i + 1))
            continue
        ziel = arbeit / ("ki_%02d.mp4" % i)
        pfad = animation.erzeuge(kanal, s["quelle"], hinweis, s["dauer"],
                                 str(ziel), seite)
        if pfad:
            s["quelle"] = pfad
            s["typ"] = "clip"
            s["bewegung"] = "aus"
            gemacht += 1
            kosten += animation.preis_je_clip(kanal, 5)
        else:
            print("[Szenen] Szene %d bleibt ein Standbild" % (i + 1))
    if geredet:
        print("[Szenen] %d Sprechszene(n) mit Avatar, Mund passt zum Text" % geredet)
    if gemacht:
        print("[Szenen] %d Szene(n) per KI animiert" % gemacht)
    if kosten:
        print("[Szenen] Bewegte Szenen zusammen etwa %.2f USD" % kosten)
    return plan


def _p52_farbe(wert, ersatz="#FFD400"):
    """#RRGGBB in das Format, das Untertitel brauchen: &H00BBGGRR."""
    s = str(wert or "").strip().lstrip("#")
    if len(s) != 6:
        s = str(ersatz).lstrip("#")
    try:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except Exception:
        return "&H0000D4FF"
    return "&H00%02X%02X%02X" % (b, g, r)


def _p52_zeit(s):
    m, s = divmod(max(0.0, float(s)), 60)
    st, m = divmod(int(m), 60)
    return "%d:%02d:%05.2f" % (st, m, s)


def _p52_abspann_bauen(kanal, b, h, fps, dauer, ziel, arbeit):
    """Dunkler Grund, zwei Zeilen Text. Reines ffmpeg, kostet nichts."""
    import video_bauen as vb
    gewaehlt = (kanal.get("untertitel_schrift") or "auto")
    try:
        schrift = vb._tt_schrift() if gewaehlt in ("", "auto") else gewaehlt
    except Exception:
        schrift = "DejaVu Sans"
    z1 = (kanal.get("abspann_zeile1") or "TEIL 2 FOLGT").strip()
    z2 = (kanal.get("abspann_zeile2") or "FOLGEN · LIKEN · KOMMENTIEREN").strip()
    vorn = _p52_farbe(kanal.get("untertitel_farbe_aktiv"))
    gross = max(30, int(h * 0.055))
    klein = max(18, int(h * 0.026))
    kopf = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "PlayResX: %d\n"
        "PlayResY: %d\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: AB,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,2,0,1,0,0,5,70,70,0,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n" % (b, h, schrift, gross))
    text = "{\\fad(500,500)}%s\\N\\N{\\fs%d\\c%s}%s" % (z1, klein, vorn, z2)
    zeile = ("Dialogue: 0,%s,%s,AB,,0,0,0,,%s\n"
             % (_p52_zeit(0.3), _p52_zeit(max(0.6, dauer - 0.2)), text))
    pfad = Path(arbeit) / "abspann.ass"
    pfad.write_text(kopf + zeile, encoding="utf-8")
    grund = "color=c=0x101014:s=%dx%d:d=%.3f:r=%d" % (b, h, dauer, fps)
    gefiltert = "ass='%s'" % str(pfad).replace("\\", "/").replace(":", "\\:")
    r = _lauf(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", grund,
               "-vf", gefiltert, "-t", "%.3f" % dauer, "-r", str(fps),
               "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "22", "-an", str(ziel)])
    return r.returncode == 0 and os.path.exists(str(ziel))


def _p52_abspann(kanal, arbeit, b, h, fps):
    """Gibt (Pfad, Dauer) des Abspanns zurueck, oder (None, 0) wenn keiner."""
    if kanal.get("abspann_an") is False:
        return None, 0.0
    try:
        dauer = max(2.0, min(15.0, float(kanal.get("abspann_sekunden") or 6)))
    except Exception:
        dauer = 6.0
    ziel = Path(arbeit) / "abspann.mp4"
    eigen = (kanal.get("abspann_datei") or "").strip()
    if eigen and os.path.exists(eigen):
        if eigen.lower().endswith((".mp4", ".mov", ".webm", ".mkv")):
            ok = _stueck_clip(eigen, ziel, dauer, b, h, fps)
        else:
            ok = _stueck_bild(eigen, ziel, "aus", 0, dauer, b, h, fps, "auto")
        if ok and ziel.exists():
            print("[Szenen] Abspann aus eigener Datei, %.1f s" % dauer)
            return str(ziel), dauer
        print("[Szenen] eigene Abspanndatei ging nicht, nehme den gebauten")
    try:
        if _p52_abspann_bauen(kanal, b, h, fps, dauer, ziel, arbeit):
            print("[Szenen] Abspann gebaut, %.1f s" % dauer)
            return str(ziel), dauer
    except Exception as e:
        print("[Szenen] Abspann ging nicht: %s" % str(e)[:120])
    return None, 0.0


def baue(kanal, ziel_pfad, ordner=None):
    """Baut das Video aus den eigenen Szenen. Gibt den Pfad zurueck oder None."""
    import musik
    ordner = Path(ordner or os.path.dirname(str(ziel_pfad)))
    ordner.mkdir(parents=True, exist_ok=True)
    arbeit = ordner / "szenen_teile"
    arbeit.mkdir(exist_ok=True)
    b, h, fps = _masse(kanal)

    plan, daten = plan_bauen(kanal, str(arbeit))
    if not plan:
        print("[Szenen] Keine brauchbaren Szenen")
        return None
    gesamt = sum(s["dauer"] for s in plan)
    print("[Szenen] %d Szenen, zusammen %.1f Sekunden" % (len(plan), gesamt))
    plan = _ki_animieren(kanal, plan, arbeit)

    # 1. Videostuecke. Lange Bilder werden in mehrere Einstellungen geteilt,
    #    damit das Schnitttempo stimmt.
    grenze = _tempo_grenze(kanal)
    teile, schnittzeiten, uhr, sn = [], [], 0.0, 0
    ruhig = kanal.get("bewegung_an") is False
    if ruhig:
        print("[Szenen] Bewegung im Bild ist aus, Standbilder stehen still")
    for i, s in enumerate(plan):
        fig = _figur_fuer(kanal, s)
        bew = "aus" if ruhig else (s.get("bewegung") or "auto")
        if s["typ"] == "clip" or bew != "auto":
            stuecke = [s["dauer"]]
        else:
            stuecke = _schnitte(s["dauer"], grenze)
        for j, d in enumerate(stuecke):
            ziel = arbeit / ("v%02d_%02d.mp4" % (i, j))
            ok = (_stueck_clip(s["quelle"], ziel, d, b, h, fps, fig) if s["typ"] == "clip"
                  else _stueck_bild(s["quelle"], ziel, bew, sn, d, b, h, fps,
                                    s.get("passen") or "auto", fig,
                                    kanal.get("bewegung_staerke") or "sanft"))
            if not ok or not ziel.exists():
                print("[Szenen] Stueck %d fehlgeschlagen" % (i + 1))
                return None
            teile.append(ziel)
            if uhr > 0.05:
                schnittzeiten.append(uhr)
            uhr += d
            sn += 1
    if len(teile) > len(plan):
        print("[Szenen] %d Einstellungen aus %d Szenen (Tempo: %s)"
              % (len(teile), len(plan), (kanal.get("tempo") or "normal")))
    abspann, ab_dauer = _p52_abspann(kanal, arbeit, b, h, fps)
    if abspann:
        teile.append(Path(abspann))
    stumm = arbeit / "ohne_ton.mp4"
    if not _zusammen(teile, arbeit / "v.txt", stumm):
        print("[Szenen] Zusammenhaengen fehlgeschlagen")
        return None

    # 2. Sprachspur
    toene = []
    for i, s in enumerate(plan):
        w = arbeit / ("a%02d.wav" % i)
        quelle = s["ton"]
        if not quelle and s["typ"] == "clip" and _hat_ton(s["quelle"]):
            quelle = s["quelle"]
        if quelle:
            _auf_mass(quelle, w, s["dauer"])
        if not w.exists() or _dauer(w) <= 0:
            _stille(w, s["dauer"])
        toene.append(w)
    if abspann:
        w = arbeit / "a_abspann.wav"
        _stille(w, ab_dauer)
        toene.append(w)
        gesamt += ab_dauer
    stimme = arbeit / "stimme.wav"
    if not _zusammen(toene, arbeit / "a.txt", stimme):
        print("[Szenen] Tonspur fehlgeschlagen")
        return None
    return _fertig(kanal, plan, daten, stumm, stimme, arbeit, ziel_pfad, gesamt, b, h, musik, schnittzeiten)


def _musikdatei(kanal, daten, gesamt, arbeit, musik):
    """Eigenes Lied aus den Szenen, sonst der normale Weg."""
    eigen = daten.get("musik")
    if eigen:
        p = szenen.datei_pfad(kanal, eigen)
        if os.path.exists(p):
            return p
    try:
        return musik.hole_musik(kanal, gesamt, str(arbeit))
    except Exception as e:
        print("[Szenen] Keine Musik:", e)
        return None


def _lautheit(pfad):
    """Gemessene Lautheit in LUFS, oder None."""
    r = _lauf(["ffmpeg", "-hide_banner", "-nostats", "-i", str(pfad),
               "-af", "ebur128=framelog=quiet", "-f", "null", "-"])
    treffer = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", r.stderr or "")
    try:
        return float(treffer[-1]) if treffer else None
    except Exception:
        return None


def _einblendung_filter(kanal, gesamt, b, h, quelle):
    """Baut den Filter fuer die Folgen/Like/Abo-Grafik. (Filter, Eingaenge)."""
    if not (kanal.get("cta_anfang") or kanal.get("cta_mitte") or kanal.get("cta_ende")):
        return None, []
    try:
        import einblendung
    except Exception as e:
        print("[Szenen] Einblendung nicht nutzbar:", e)
        return None, []

    def zahl(name, standard, kleinst, groesst):
        try:
            return max(kleinst, min(groesst, float(kanal.get(name, standard))))
        except Exception:
            return standard

    hoehe = max(30, int(h * zahl("eb_groesse", 7.0, 3.0, 20.0) / 100.0))
    text = kanal.get("eb_text")
    if text is None:
        text = "FOLGEN"
    pfad = einblendung.datei(kanal.get("eb_art") or "folgen", text, hoehe,
                             kanal.get("eb_farbe") or "")
    if not pfad:
        return None, []
    fenster = einblendung.zeiten(kanal, gesamt, zahl("eb_dauer", 2.6, 0.8, 8.0))
    if not fenster:
        return None, []
    platz = kanal.get("eb_platz") or "links_unten"
    rand = int(b * 0.05)
    unten = int(h * 0.30)
    oben = int(h * 0.11)
    links = platz.startswith("links")
    mitte = platz.startswith("mitte")
    hoch = platz.endswith("_oben")
    y0 = str(oben) if hoch else "H-h-%d" % unten
    teile = ["[2:v]format=rgba,split=%d%s" % (len(fenster),
             "".join("[e%d]" % i for i in range(len(fenster))))]
    rein = quelle
    for i, (a, e) in enumerate(fenster):
        pp = (r"min(min(1\,max(0\,(t-%.3f)/0.30))\,min(1\,max(0\,(%.3f-t)/0.30)))"
              % (a, e))
        if mitte:
            x = "(W-w)/2"
            y = "%s+h*(1-%s)" % (y0, pp)
        elif links:
            x = "%d-w*(1-%s)" % (rand, pp)
            y = y0
        else:
            x = "W-w-%d+w*(1-%s)" % (rand, pp)
            y = y0
        raus = "[vout]" if i == len(fenster) - 1 else "[eo%d]" % i
        teile.append("%s[e%d]overlay=x='%s':y='%s':format=auto:"
                     r"enable='between(t\,%.3f\,%.3f)'%s"
                     % (rein, i, x, y, a, e, raus))
        rein = raus
    print("[Szenen] Einblendung %dx eingeblendet" % len(fenster))
    return ";".join(teile), ["-i", str(pfad)]


def _fertig(kanal, plan, daten, stumm, stimme, arbeit, ziel_pfad, gesamt, b, h, musik, schnitte=None):
    ziel_pfad = Path(ziel_pfad)
    ziel_pfad.parent.mkdir(parents=True, exist_ok=True)

    def zahl(name, standard, kleinst, groesst):
        try:
            return max(kleinst, min(groesst, float(kanal.get(name, standard))))
        except Exception:
            return standard

    leise = zahl("musik_leise", 12.0, 0.0, 150.0) / 100.0
    laut = zahl("musik_laut", 75.0, 0.0, 150.0) / 100.0
    ziel_lufs = zahl("lautheit", -14.0, -30.0, -6.0)
    ein = zahl("musik_ein", 1.0, 0.0, 10.0)
    aus = zahl("musik_aus", 1.5, 0.0, 10.0)
    ein = min(ein, max(0.0, gesamt / 3.0))
    aus = min(aus, max(0.0, gesamt / 3.0))
    anheben = kanal.get("musik_anheben", True) is not False

    lied = _musikdatei(kanal, daten, gesamt, arbeit, musik)
    knack = _knackspur(kanal, arbeit, gesamt, schnitte)
    knack_pegel = zahl("schnitt_laut", 35.0, 0.0, 150.0) / 100.0

    # 1. Ton mischen: Stimme, Musik mit Lautstaerkekurve, Schnittgeraeusche
    ton = arbeit / "ton.wav"
    befehl = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(stimme)]
    stufen, quellen, nr = [], ["[0:a]"], 1
    if lied:
        befehl += ["-stream_loop", "-1", "-i", str(lied)]
        blenden = ""
        if ein > 0.05:
            blenden += ",afade=t=in:st=0:d=%.2f" % ein
        if aus > 0.05:
            blenden += ",afade=t=out:st=%.3f:d=%.2f" % (max(0.0, gesamt - aus), aus)
        stufen.append("[%d:a]atrim=0:%.3f,asetpts=N/SR/TB,volume='%s':eval=frame%s[mus]"
                      % (nr, gesamt, _musik_ausdruck(plan, leise, laut, anheben), blenden))
        quellen.append("[mus]")
        nr += 1
    if knack and knack_pegel > 0.01:
        befehl += ["-i", str(knack)]
        stufen.append("[%d:a]volume=%.3f[knk]" % (nr, knack_pegel))
        quellen.append("[knk]")
        nr += 1
    if len(quellen) < 2:
        graph = "[0:a]anull[o]"
    else:
        graph = (";".join(stufen) + ";" + "".join(quellen)
                 + "amix=inputs=%d:duration=first:dropout_transition=0:normalize=0[o]"
                 % len(quellen))
    befehl += ["-filter_complex", graph, "-map", "[o]", "-ac", "2", "-ar", "48000",
               "-c:a", "pcm_s16le", "-t", "%.3f" % gesamt, str(ton)]
    r = _lauf(befehl)
    if r.returncode or not ton.exists():
        print("[Szenen] Tonmischung:", (r.stderr or "")[-300:])
        return None

    # 2. Lautheit messen und mit festem Faktor angleichen
    ist = _lautheit(ton)
    gewinn = 0.0
    if ist is not None and ist > -70:
        gewinn = max(-20.0, min(20.0, ziel_lufs - ist))
        print("[Szenen] Lautheit %.1f LUFS, angeglichen um %+.1f dB" % (ist, gewinn))

    # 3. Video, Ton und Untertitel zusammenfuehren
    ass = _ass(plan, str(arbeit / "ut.ass"), b, h, kanal)
    hat_ut = any(s["untertitel"] and s["text"] for s in plan)
    filter_teile = ["[1:a]volume=%.2fdB,alimiter=limit=0.97[ton]" % gewinn]
    v = "[0:v]"
    _lk = _p56_look(kanal)
    if _lk:
        filter_teile.append("%s%s[lk]" % (v, _lk))
        v = "[lk]"
        print("[Szenen] Look: %s" % (kanal.get("look_stil") or "kalt"))
    if hat_ut:
        filter_teile.append("%sass='%s'" % (v, str(ass).replace("\\", "/").replace(":", "\\:")) + "[vid]")
        v = "[vid]"
    eb_filter, eb_ein = _einblendung_filter(kanal, gesamt, b, h, v)
    if eb_filter:
        filter_teile.append(eb_filter)
        v = "[vout]"
    befehl = (["ffmpeg", "-y", "-loglevel", "error", "-i", str(stumm), "-i", str(ton)]
              + eb_ein
              + ["-filter_complex", ";".join(filter_teile), "-map", v, "-map", "[ton]",
              "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
              "-t", "%.3f" % gesamt, str(ziel_pfad)])
    r = _lauf(befehl)
    if r.returncode or not ziel_pfad.exists():
        print("[Szenen] ffmpeg:", (r.stderr or "")[-400:])
        return None
    print("[Szenen] fertig: %s (%.1f s)" % (ziel_pfad.name, _dauer(ziel_pfad)))
    try:
        import shutil
        shutil.rmtree(str(arbeit), ignore_errors=True)
    except Exception:
        pass
    return str(ziel_pfad)


# ---------- Nachtrag p55: Untertitel-Stile ----------

P55_STILE = ("klassisch", "kino", "fett")

_p55_ass_alt = _ass


def _p55_kopf(b, h, schrift, fs, vorn, aussen, fett, spacing,
              rand, schatten, ml, mv):
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "PlayResX: %d\n"
        "PlayResY: %d\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: TT,%s,%d,%s,&H00FFFFFF,%s,&H96000000,"
        "%d,0,0,0,100,100,%d,0,1,%d,%d,2,%d,%d,%d,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
        % (b, h, schrift, fs, vorn, aussen, fett, spacing,
           rand, schatten, ml, ml, mv))


def _ass(plan, ziel, b, h, kanal=None):
    """Wie bisher, aber mit waehlbarem Stil."""
    k = kanal or {}
    stil = str(k.get("untertitel_stil") or "klassisch").strip().lower()
    if stil not in P55_STILE or stil == "klassisch":
        return _p55_ass_alt(plan, ziel, b, h, kanal)

    import video_bauen as vb
    gewaehlt = (k.get("untertitel_schrift") or "auto")
    try:
        schrift = vb._tt_schrift() if gewaehlt in ("", "auto") else gewaehlt
    except Exception:
        schrift = "DejaVu Sans"
    try:
        groesse = max(20.0, min(120.0, float(k.get("untertitel_groesse") or 48)))
    except Exception:
        groesse = 48.0
    try:
        woerter = int(k.get("untertitel_woerter") or 3)
    except Exception:
        woerter = 3
    woerter = max(1, min(6, woerter))
    caps = k.get("untertitel_caps") is not False

    if stil == "kino":
        fs = max(18, int(h * 0.032 * groesse / 48.0))
        spacing = max(3, int(fs * 0.24))
        vorn, aussen = "&H28FFFFFF", "&HB4000000"
        fett = 0
        rand, schatten = max(2, int(fs * 0.10)), 0
        mv = int(h * 0.47)
        blende = "\\fad(260,260)"
        caps = True
    else:
        fs = max(28, int(h * 0.058 * groesse / 48.0))
        spacing = 0
        vorn, aussen = "&H00FFFFFF", "&H00000000"
        fett = -1
        rand, schatten = max(4, int(fs * 0.14)), max(2, int(fs * 0.06))
        mv = int(h * 0.30)
        blende = "\\fad(60,60)"

    ml = int(b * 0.075)
    zeilen = [_p55_kopf(b, h, schrift, fs, vorn, aussen, fett, spacing,
                        rand, schatten, ml, mv)]
    for s in plan:
        if not s["untertitel"] or not (s["text"] or "").strip():
            continue
        stuecke = vb._tt_stuecke(_ohne_anfuehrung(s["text"]),
                                 max_w=woerter, max_z=max(10, woerter * 6))
        if not stuecke:
            continue
        zeichen = [max(1, len(" ".join(x))) for x in stuecke]
        summe = float(sum(zeichen))
        zeit = s["start"]
        for st, z in zip(stuecke, zeichen):
            d = max(0.45, s["dauer"] * z / summe)
            text = " ".join(st).replace("{", "(").replace("}", ")")
            if caps:
                text = text.upper()
            zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,{%s}%s\n"
                          % (vb._tt_zeit(zeit),
                             vb._tt_zeit(min(zeit + d, s["start"] + s["dauer"])),
                             blende, text))
            zeit += d
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("".join(zeilen))
    print("[Szenen] Untertitel-Stil: %s" % stil)
    return ziel


# ---------- Nachtrag p56: einheitlicher Look ----------

P56_STILE = {
    "aus": "",
    "kalt": ("eq=contrast=1.10:saturation=0.80:gamma=0.97,"
             "colorbalance=rs=-0.03:gs=-0.01:bs=0.07:rm=-0.02:bm=0.05,"
             "vignette=a=PI/4.5"),
    "warm": ("eq=contrast=1.08:saturation=0.94:gamma=0.99,"
             "colorbalance=rs=0.05:gs=0.01:bs=-0.05:rm=0.03:bm=-0.02,"
             "vignette=a=PI/5"),
    "hart": ("eq=contrast=1.26:saturation=0.50:gamma=1.04,"
             "colorbalance=bs=0.04,"
             "vignette=a=PI/4"),
}

P56_KORN = True


def _p56_look(kanal):
    """Die Filterkette fuer den Look, oder leer wenn keiner gewuenscht ist."""
    k = kanal or {}
    if k.get("look_an") is False:
        return ""
    stil = str(k.get("look_stil") or "kalt").strip().lower()
    kette = P56_STILE.get(stil)
    if kette is None:
        kette = P56_STILE["kalt"]
    if not kette:
        return ""
    try:
        korn = int(max(0, min(30, float(k.get("look_korn", 7)))))
    except Exception:
        korn = 7
    if korn and P56_KORN:
        kette += ",noise=alls=%d:allf=t+u" % korn
    return kette + ",format=yuv420p"


# ---------- Nachtrag p57: Untertitel Wort fuer Wort ----------

_p57_ass_alt = _ass


def _p57_kopf(b, h, schrift, fs, rand, ml, mv):
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "PlayResX: %d\n"
        "PlayResY: %d\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: TT,%s,%d,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,"
        "-1,0,0,0,100,100,0,0,1,%d,0,2,%d,%d,%d,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n" % (b, h, schrift, fs, rand, ml, ml, mv))


def _ass(plan, ziel, b, h, kanal=None):
    """Wort fuer Wort, sonst wie bisher."""
    k = kanal or {}
    stil = str(k.get("untertitel_stil") or "klassisch").strip().lower()
    if stil != "wortweise":
        return _p57_ass_alt(plan, ziel, b, h, kanal)

    import video_bauen as vb
    gewaehlt = (k.get("untertitel_schrift") or "auto")
    try:
        schrift = vb._tt_schrift() if gewaehlt in ("", "auto") else gewaehlt
    except Exception:
        schrift = "DejaVu Sans"
    try:
        groesse = max(20.0, min(120.0, float(k.get("untertitel_groesse") or 48)))
    except Exception:
        groesse = 48.0
    try:
        woerter = int(k.get("untertitel_woerter") or 3)
    except Exception:
        woerter = 3
    woerter = max(1, min(3, woerter - 1))

    gross = max(30, int(h * 0.050 * groesse / 48.0))
    klein = max(20, int(gross * 0.72))
    rand = max(3, int(gross * 0.10))
    ml = int(b * 0.055)
    mv = int(h * 0.47)
    hell, grau = "&HFFFFFF&", "&HB4B4B4&"

    zeilen = [_p57_kopf(b, h, schrift, gross, rand, ml, mv)]
    for s in plan:
        if not s["untertitel"] or not (s["text"] or "").strip():
            continue
        stuecke = vb._tt_stuecke(_ohne_anfuehrung(s["text"]),
                                 max_w=woerter, max_z=max(9, woerter * 7))
        if not stuecke:
            continue
        zeichen = [max(1, len(" ".join(x))) for x in stuecke]
        summe = float(sum(zeichen))
        zeit = s["start"]
        ende = s["start"] + s["dauer"]
        for st, z in zip(stuecke, zeichen):
            d = max(0.40, s["dauer"] * z / summe)
            worte = [w.replace("{", "(").replace("}", ")").upper() for w in st]
            laengen = [max(1, len(w)) for w in worte]
            gesamt = float(sum(laengen))
            w_zeit = zeit
            for j, w in enumerate(worte):
                w_dauer = max(0.18, d * laengen[j] / gesamt)
                teile = []
                for i, wort in enumerate(worte):
                    if i == j:
                        teile.append("{\\fs%d\\1c%s}%s" % (gross, hell, wort))
                    else:
                        teile.append("{\\fs%d\\1c%s}%s" % (klein, grau, wort))
                zeilen.append(
                    "Dialogue: 0,%s,%s,TT,,0,0,0,,{\\blur5}%s\n"
                    % (vb._tt_zeit(w_zeit),
                       vb._tt_zeit(min(w_zeit + w_dauer, ende)),
                       " ".join(teile)))
                w_zeit += w_dauer
            zeit += d
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("".join(zeilen))
    print("[Szenen] Untertitel-Stil: wortweise")
    return ziel


# ---------- Nachtrag p58: Untertitel an der echten Stimme ----------

import re as _p58_re
import subprocess as _p58_sub

_p58_ass_alt = _ass

P58_STILE = ("kino", "fett", "wortweise")


def _p58_segmente(pfad, dauer):
    """Wo in dieser Tondatei wirklich gesprochen wird.

    Gibt [(von, bis), ...] in Sekunden, oder None wenn es nicht geht.
    """
    if not pfad or not os.path.exists(str(pfad)) or dauer <= 0.05:
        return None
    try:
        r = _p58_sub.run(["ffmpeg", "-v", "info", "-i", str(pfad), "-af",
                          "silencedetect=noise=-33dB:d=0.16", "-f", "null", "-"],
                         capture_output=True, text=True, timeout=90)
    except Exception:
        return None
    txt = (r.stderr or "") + (r.stdout or "")
    marken = [(m.group(1), float(m.group(2))) for m in
              _p58_re.finditer(r"silence_(start|end):\s*(-?\d+(?:\.\d+)?)", txt)]
    seg, pos = [], 0.0
    for art, wert in marken:
        wert = max(0.0, min(dauer, wert))
        if art == "start":
            if pos is not None and wert - pos > 0.04:
                seg.append((pos, wert))
            pos = None
        else:
            pos = wert
    if pos is not None and dauer - pos > 0.04:
        seg.append((pos, dauer))
    gesamt = sum(b - a for a, b in seg)
    # Nichts erkannt, alles Stille, oder kaum Pausen: dann lohnt es nicht
    if not seg or gesamt < 0.25 * dauer:
        return None
    return seg


def _p58_gewicht(wort):
    """Wie lange dieses Wort ungefaehr zu sprechen dauert."""
    silben = len(_p58_re.findall(r"[aeiouäöüyAEIOUÄÖÜY]+", wort)) or 1
    return float(silben) + 0.12 * len(wort)


def _p58_uhr(seg, t):
    """Rechnet reine Sprechzeit in echte Zeit in der Szene um."""
    rest = max(0.0, t)
    for a, b in seg:
        d = b - a
        if rest <= d:
            return a + rest
        rest -= d
    return seg[-1][1] if seg else t


def _p58_wortzeiten(s, worte):
    """Startzeit je Wort, an der echten Stimme ausgerichtet.

    Faellt auf die alte, gleichmaessige Verteilung zurueck, wenn die Tondatei
    fehlt oder nichts zu messen ist.
    """
    start = float(s.get("start") or 0.0)
    dauer = float(s.get("dauer") or 0.0)
    gew = [_p58_gewicht(w) for w in worte]
    summe = sum(gew) or 1.0
    seg = _p58_segmente(s.get("ton"), dauer)
    if not seg:
        zeiten, lauf = [], 0.0
        for g in gew:
            zeiten.append(start + lauf)
            lauf += dauer * g / summe
        return zeiten + [start + dauer], False
    sprech = sum(b - a for a, b in seg)
    zeiten, lauf = [], 0.0
    for g in gew:
        zeiten.append(start + _p58_uhr(seg, lauf))
        lauf += sprech * g / summe
    return zeiten + [start + dauer], True


def _p58_stil(k, h, b):
    """Die Masse fuer einen der drei Stile."""
    stil = str(k.get("untertitel_stil") or "").strip().lower()
    try:
        groesse = max(20.0, min(120.0, float(k.get("untertitel_groesse") or 48)))
    except Exception:
        groesse = 48.0
    if stil == "kino":
        fs = max(18, int(h * 0.032 * groesse / 48.0))
        return dict(stil=stil, gross=fs, klein=fs, spacing=max(3, int(fs * 0.24)),
                    vorn="&H28FFFFFF", aussen="&HB4000000", fett=0,
                    rand=max(2, int(fs * 0.10)), schatten=0, mv=int(h * 0.47),
                    ml=int(b * 0.075), blende="\\fad(260,260)", caps=True,
                    wortweise=False, wrap=0)
    if stil == "fett":
        fs = max(28, int(h * 0.058 * groesse / 48.0))
        return dict(stil=stil, gross=fs, klein=fs, spacing=0,
                    vorn="&H00FFFFFF", aussen="&H00000000", fett=-1,
                    rand=max(4, int(fs * 0.14)), schatten=max(2, int(fs * 0.06)),
                    mv=int(h * 0.30), ml=int(b * 0.075),
                    blende="\\fad(60,60)", caps=None, wortweise=False, wrap=0)
    fs = max(30, int(h * 0.050 * groesse / 48.0))
    return dict(stil="wortweise", gross=fs, klein=max(20, int(fs * 0.72)),
                spacing=0, vorn="&H00FFFFFF", aussen="&H00000000", fett=-1,
                rand=max(3, int(fs * 0.10)), schatten=0, mv=int(h * 0.47),
                ml=int(b * 0.055), blende="", caps=True, wortweise=True, wrap=2)


def _p58_kopf(b, h, schrift, m):
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: %d\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "PlayResX: %d\n"
        "PlayResY: %d\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: TT,%s,%d,%s,&H00FFFFFF,%s,&H00000000,"
        "%d,0,0,0,100,100,%d,0,1,%d,%d,2,%d,%d,%d,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
        % (m["wrap"], b, h, schrift, m["gross"], m["vorn"], m["aussen"],
           m["fett"], m["spacing"], m["rand"], m["schatten"],
           m["ml"], m["ml"], m["mv"]))


def _ass(plan, ziel, b, h, kanal=None):
    """Untertitel, an den Sprechpausen ausgerichtet."""
    k = kanal or {}
    stil = str(k.get("untertitel_stil") or "klassisch").strip().lower()
    if stil not in P58_STILE or k.get("untertitel_takt") is False:
        return _p58_ass_alt(plan, ziel, b, h, kanal)

    import video_bauen as vb
    gewaehlt = (k.get("untertitel_schrift") or "auto")
    try:
        schrift = vb._tt_schrift() if gewaehlt in ("", "auto") else gewaehlt
    except Exception:
        schrift = "DejaVu Sans"
    try:
        woerter = int(k.get("untertitel_woerter") or 3)
    except Exception:
        woerter = 3
    woerter = max(1, min(6, woerter))
    m = _p58_stil(k, h, b)
    if m["wortweise"]:
        woerter = max(1, min(3, woerter - 1))
    caps = m["caps"]
    if caps is None:
        caps = k.get("untertitel_caps") is not False

    zeilen = [_p58_kopf(b, h, schrift, m)]
    gemessen, gesamt = 0, 0
    for s in plan:
        if not s["untertitel"] or not (s["text"] or "").strip():
            continue
        stuecke = vb._tt_stuecke(_ohne_anfuehrung(s["text"]),
                                 max_w=woerter, max_z=max(10, woerter * 6))
        if not stuecke:
            continue
        gesamt += 1
        flach = [w for st in stuecke for w in st]
        zeiten, echt = _p58_wortzeiten(s, flach)
        if echt:
            gemessen += 1
        i = 0
        for st in stuecke:
            n = len(st)
            worte = [w.replace("{", "(").replace("}", ")") for w in st]
            if caps:
                worte = [w.upper() for w in worte]
            if m["wortweise"]:
                for j in range(n):
                    teile = []
                    for q, wort in enumerate(worte):
                        if q == j:
                            teile.append("{\\fs%d\\1c&HFFFFFF&}%s" % (m["gross"], wort))
                        else:
                            teile.append("{\\fs%d\\1c&HB4B4B4&}%s" % (m["klein"], wort))

                    zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,{\\blur5}%s\n"
                                  % (vb._tt_zeit(zeiten[i + j]),
                                     vb._tt_zeit(max(zeiten[i + j] + 0.12, zeiten[i + j + 1])),
                                     " ".join(teile)))
            else:
                zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,{%s}%s\n"
                              % (vb._tt_zeit(zeiten[i]),
                                 vb._tt_zeit(max(zeiten[i] + 0.2, zeiten[i + n])),
                                 m["blende"], " ".join(worte)))
            i += n
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("".join(zeilen))
    print("[Szenen] Untertitel-Stil: %s, %d von %d Szenen an der Stimme ausgerichtet"
          % (m["stil"], gemessen, gesamt))
    return ziel


# ---------- Nachtrag p60: kein halber Bildschirm, Tiefen anheben ----------

P60_GRENZE = 0.30

_p60_passen_alt = _p44_passen
_p60_look_alt = _p56_look


def _p60_passen(quelle, b, h, wunsch="auto"):
    """Wie bisher, aber bei grosser Abweichung lieber beschneiden."""
    if wunsch in ("ganz", "fuellen"):
        return wunsch
    masse = _p44_masse_der_quelle(quelle)
    if not masse:
        return "fuellen"
    try:
        soll = float(b) / float(h)
        ist = float(masse[0]) / float(masse[1])
    except Exception:
        return "fuellen"
    ab = abs(ist - soll) / soll
    if ab > P60_GRENZE:
        # Der Rahmen wuerde mehr als ein Viertel des Schirms fressen
        return "fuellen"
    return _p60_passen_alt(quelle, b, h, wunsch)


_p44_passen = _p60_passen


def _p56_look(kanal):
    """Wie bisher, dazu ein leichtes Anheben der Tiefen."""
    kette = _p60_look_alt(kanal)
    if not kette:
        return kette
    k = kanal or {}
    try:
        hoch = max(0, min(20, int(float(k.get("look_schatten", 4)))))
    except Exception:
        hoch = 4
    if not hoch:
        return kette
    lift = hoch / 100.0
    kurve = "curves=all='0/%.3f 0.5/0.5 1/1'" % lift
    # vor Korn und format, damit das Korn nicht mit angehoben wird
    if ",noise=" in kette:
        a, b2 = kette.split(",noise=", 1)
        return a + "," + kurve + ",noise=" + b2
    if kette.endswith(",format=yuv420p"):
        return kette[:-len(",format=yuv420p")] + "," + kurve + ",format=yuv420p"
    return kette + "," + kurve


# ---------- Nachtrag p61: Untertitel laeuft nicht in den Nachlauf ----------

_p61_wortzeiten_alt = _p58_wortzeiten


def _p61_tonlaenge(s):
    """Wie lang die Tondatei dieser Szene wirklich ist."""
    pfad = s.get("ton")
    if not pfad:
        return 0.0
    try:
        d = float(_dauer(pfad) or 0.0)
    except Exception:
        return 0.0
    return d if d > 0.05 else 0.0


def _p61_wortzeiten(s, worte):
    """Wie bisher, aber gemessen wird die Tonspur, nicht die Szenendauer.

    Das letzte Wort bleibt bis zum Szenenende stehen.
    """
    start = float(s.get("start") or 0.0)
    dauer = float(s.get("dauer") or 0.0)
    ton = _p61_tonlaenge(s)
    if ton <= 0.05 or dauer <= 0.05 or ton >= dauer - 0.05:
        return _p61_wortzeiten_alt(s, worte)
    # Nur die gesprochene Zeit zum Verteilen benutzen
    kurz = dict(s)
    kurz["dauer"] = ton
    zeiten, echt = _p61_wortzeiten_alt(kurz, worte)
    # ... das letzte Wort aber bis zum Szenenende stehenlassen
    zeiten = list(zeiten)
    zeiten[-1] = start + dauer
    return zeiten, echt


_p58_wortzeiten = _p61_wortzeiten


# ---------- Nachtrag p62: Wortzahl gilt, zwei neue Stile ----------

_p62_ass_alt = _ass

P62_STILE = ("kino", "fett", "wortweise", "knall", "karaoke")


def _p62_farbe(wert, ersatz="#FFD400"):
    """#RRGGBB in das Format, das Untertitel brauchen: &H00BBGGRR."""
    s = str(wert or "").strip().lstrip("#")
    if len(s) != 6:
        s = str(ersatz).lstrip("#")
    try:
        r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
    except Exception:
        return "&H0000D4FF&"
    return "&H00%02X%02X%02X&" % (b, g, r)


def _p62_mass(k, h, b, stil, n):
    """Masse fuer einen Stil, abhaengig von der Wortzahl."""
    try:
        groesse = max(20.0, min(120.0, float(k.get("untertitel_groesse") or 48)))
    except Exception:
        groesse = 48.0
    # je mehr Woerter nebeneinander, desto kleiner, sonst laeuft es raus
    schrumpf = {1: 1.12, 2: 1.0, 3: 0.88, 4: 0.78, 5: 0.70, 6: 0.64}.get(n, 0.78)
    vorn = _p62_farbe(k.get("untertitel_farbe_aktiv"))

    if stil == "kino":
        fs = max(18, int(h * 0.032 * groesse / 48.0 * (0.92 + 0.08 * schrumpf)))
        return dict(gross=fs, klein=fs, spacing=max(3, int(fs * 0.24)),
                    prim="&H28FFFFFF", aussen="&HB4000000", fett=0,
                    rand=max(2, int(fs * 0.10)), schatten=0,
                    mv=int(h * 0.47), ml=int(b * 0.075), wrap=0,
                    blende="\\fad(260,260)", caps=True, art="ganz", vorn=vorn)
    if stil == "fett":
        fs = max(28, int(h * 0.058 * groesse / 48.0 * schrumpf))
        return dict(gross=fs, klein=fs, spacing=0,
                    prim="&H00FFFFFF", aussen="&H00000000", fett=-1,
                    rand=max(4, int(fs * 0.14)), schatten=max(2, int(fs * 0.06)),
                    mv=int(h * 0.30), ml=int(b * 0.075), wrap=0,
                    blende="\\fad(60,60)", caps=None, art="ganz", vorn=vorn)
    if stil == "knall":
        fs = max(30, int(h * 0.056 * groesse / 48.0 * schrumpf))
        return dict(gross=fs, klein=fs, spacing=0,
                    prim="&H00FFFFFF", aussen="&H00000000", fett=-1,
                    rand=max(4, int(fs * 0.15)), schatten=max(2, int(fs * 0.07)),
                    mv=int(h * 0.34), ml=int(b * 0.055), wrap=2,
                    blende="", caps=True, art="wort", vorn=vorn)
    if stil == "karaoke":
        fs = max(28, int(h * 0.050 * groesse / 48.0 * schrumpf))
        return dict(gross=fs, klein=fs, spacing=0,
                    prim="&H00FFFFFF", aussen="&H00000000", fett=-1,
                    rand=max(3, int(fs * 0.13)), schatten=0,
                    mv=int(h * 0.40), ml=int(b * 0.055), wrap=2,
                    blende="", caps=True, art="fuellen", vorn=vorn)
    fs = max(30, int(h * 0.050 * groesse / 48.0 * schrumpf))
    return dict(gross=fs, klein=max(20, int(fs * 0.72)), spacing=0,
                prim="&H00FFFFFF", aussen="&H00000000", fett=-1,
                rand=max(3, int(fs * 0.10)), schatten=0,
                mv=int(h * 0.47), ml=int(b * 0.055), wrap=2,
                blende="", caps=True, art="gross", vorn=vorn)


def _p62_kopf(b, h, schrift, m):
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "WrapStyle: %d\n"
        "ScaledBorderAndShadow: yes\n"
        "YCbCr Matrix: TV.709\n"
        "PlayResX: %d\n"
        "PlayResY: %d\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: TT,%s,%d,%s,&H00FFFFFF,%s,&H00000000,"
        "%d,0,0,0,100,100,%d,0,1,%d,%d,2,%d,%d,%d,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
        % (m["wrap"], b, h, schrift, m["gross"], m["prim"], m["aussen"],
           m["fett"], m["spacing"], m["rand"], m["schatten"],
           m["ml"], m["ml"], m["mv"]))


P62_POP = "{\\fscx88\\fscy88\\t(0,110,\\fscx100\\fscy100)}"


def _ass(plan, ziel, b, h, kanal=None):
    """Untertitel in fuenf Stilen, an den Sprechpausen ausgerichtet."""
    k = kanal or {}
    stil = str(k.get("untertitel_stil") or "klassisch").strip().lower()
    if stil not in P62_STILE or k.get("untertitel_takt") is False:
        return _p62_ass_alt(plan, ziel, b, h, kanal)

    import video_bauen as vb
    gewaehlt = (k.get("untertitel_schrift") or "auto")
    try:
        schrift = vb._tt_schrift() if gewaehlt in ("", "auto") else gewaehlt
    except Exception:
        schrift = "DejaVu Sans"
    try:
        n = int(k.get("untertitel_woerter") or 3)
    except Exception:
        n = 3
    n = max(1, min(6, n))
    m = _p62_mass(k, h, b, stil, n)
    caps = m["caps"]
    if caps is None:
        caps = k.get("untertitel_caps") is not False

    zeilen = [_p62_kopf(b, h, schrift, m)]
    gemessen, gesamt = 0, 0
    for s in plan:
        if not s["untertitel"] or not (s["text"] or "").strip():
            continue
        stuecke = vb._tt_stuecke(_ohne_anfuehrung(s["text"]),
                                 max_w=n, max_z=max(10, n * 7))
        if not stuecke:
            continue
        gesamt += 1
        flach = [w for st in stuecke for w in st]
        zeiten, echt = _p58_wortzeiten(s, flach)
        if echt:
            gemessen += 1
        i = 0
        for st in stuecke:
            anz = len(st)
            worte = [w.replace("{", "(").replace("}", ")") for w in st]
            if caps:
                worte = [w.upper() for w in worte]

            if m["art"] == "ganz":
                zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,{%s}%s\n"
                              % (vb._tt_zeit(zeiten[i]),
                                 vb._tt_zeit(max(zeiten[i] + 0.2, zeiten[i + anz])),
                                 m["blende"], " ".join(worte)))
                i += anz
                continue

            for j in range(anz):
                teile = []
                for q, wort in enumerate(worte):
                    if m["art"] == "gross":
                        if q == j:
                            teile.append("{\\fs%d\\1c&HFFFFFF&}%s" % (m["gross"], wort))
                        else:
                            teile.append("{\\fs%d\\1c&HB4B4B4&}%s" % (m["klein"], wort))
                    elif m["art"] == "wort":
                        if q == j:
                            teile.append("{\\1c%s}%s" % (m["vorn"], wort))
                        else:
                            teile.append("{\\1c&HFFFFFF&}%s" % wort)
                    else:   # fuellen
                        if q <= j:
                            teile.append("{\\1c%s}%s" % (m["vorn"], wort))
                        else:
                            teile.append("{\\1c&HFFFFFF&}%s" % wort)
                vorn_tag = P62_POP if (j == 0 and m["art"] in ("wort", "fuellen")) else ""
                zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,%s%s\n"
                              % (vb._tt_zeit(zeiten[i + j]),
                                 vb._tt_zeit(max(zeiten[i + j] + 0.10, zeiten[i + j + 1])),
                                 vorn_tag, " ".join(teile)))
            i += anz
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("".join(zeilen))
    print("[Szenen] Untertitel-Stil: %s, %d Woerter, %d von %d Szenen an der Stimme"
          % (stil, n, gemessen, gesamt))
    return ziel


# ---------- Nachtrag p65: beide Farben aus dem Kanal ----------

_p65_mass_alt = _p62_mass


def _p65_ruhe(k, stil):
    """Farbe der nicht gesprochenen Woerter."""
    standard = "#B4B4B4" if stil == "wortweise" else "#FFFFFF"
    return _p62_farbe(k.get("untertitel_farbe_ruhe"), standard)


def _p65_aktiv(k, stil):
    """Farbe des gesprochenen Wortes."""
    standard = "#FFFFFF" if stil == "wortweise" else "#FFD400"
    return _p62_farbe(k.get("untertitel_farbe_aktiv"), standard)


def _p62_mass(k, h, b, stil, n):
    m = _p65_mass_alt(k, h, b, stil, n)
    m["vorn"] = _p65_aktiv(k or {}, stil)
    m["ruhe"] = _p65_ruhe(k or {}, stil)
    return m


_p65_ass_alt = _ass


def _ass(plan, ziel, b, h, kanal=None):
    """Wie bisher, aber mit den beiden eingestellten Farben."""
    k = kanal or {}
    stil = str(k.get("untertitel_stil") or "klassisch").strip().lower()
    if stil not in ("wortweise", "knall", "karaoke") or k.get("untertitel_takt") is False:
        return _p65_ass_alt(plan, ziel, b, h, kanal)

    import video_bauen as vb
    gewaehlt = (k.get("untertitel_schrift") or "auto")
    try:
        schrift = vb._tt_schrift() if gewaehlt in ("", "auto") else gewaehlt
    except Exception:
        schrift = "DejaVu Sans"
    try:
        n = int(k.get("untertitel_woerter") or 3)
    except Exception:
        n = 3
    n = max(1, min(6, n))
    m = _p62_mass(k, h, b, stil, n)
    caps = m["caps"]
    if caps is None:
        caps = k.get("untertitel_caps") is not False
    vorn, ruhe = m["vorn"], m["ruhe"]

    zeilen = [_p62_kopf(b, h, schrift, m)]
    gemessen, gesamt = 0, 0
    for s in plan:
        if not s["untertitel"] or not (s["text"] or "").strip():
            continue
        stuecke = vb._tt_stuecke(_ohne_anfuehrung(s["text"]),
                                 max_w=n, max_z=max(10, n * 7))
        if not stuecke:
            continue
        gesamt += 1
        flach = [w for st in stuecke for w in st]
        zeiten, echt = _p58_wortzeiten(s, flach)
        if echt:
            gemessen += 1
        i = 0
        for st in stuecke:
            anz = len(st)
            worte = [w.replace("{", "(").replace("}", ")") for w in st]
            if caps:
                worte = [w.upper() for w in worte]
            for j in range(anz):
                teile = []
                for q, wort in enumerate(worte):
                    if m["art"] == "gross":
                        gr = m["gross"] if q == j else m["klein"]
                        fb = vorn if q == j else ruhe
                        teile.append("{\\fs%d\\1c%s}%s" % (gr, fb, wort))
                    elif m["art"] == "wort":
                        teile.append("{\\1c%s}%s" % (vorn if q == j else ruhe, wort))
                    else:   # fuellen
                        teile.append("{\\1c%s}%s" % (vorn if q <= j else ruhe, wort))
                kopf = P62_POP if (j == 0 and m["art"] in ("wort", "fuellen")) else ""
                zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,%s%s\n"
                              % (vb._tt_zeit(zeiten[i + j]),
                                 vb._tt_zeit(max(zeiten[i + j] + 0.10, zeiten[i + j + 1])),
                                 kopf, " ".join(teile)))
            i += anz
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("".join(zeilen))
    print("[Szenen] Untertitel-Stil: %s, %d Woerter, %d von %d Szenen an der Stimme"
          % (stil, n, gemessen, gesamt))
    return ziel


# ---------- Nachtrag p67: Hoehe, Rand, Schatten, Leuchten ----------

_p67_ass_alt = _ass

# Die Felder einer Style-Zeile, von 0 an gezaehlt, nach "Style: "
P67_AUSSEN, P67_RAND, P67_SCHATTEN, P67_MV = 5, 16, 17, 21


def _p67_zahl(k, feld, kleinst, groesst):
    """Eine Einstellung als Zahl, oder None wenn sie nicht gesetzt ist."""
    w = (k or {}).get(feld)
    if w is None or w == "":
        return None
    try:
        return max(kleinst, min(groesst, float(w)))
    except Exception:
        return None


def _p67_nachziehen(ziel, k, h):
    """Zieht die eingestellten Werte in der fertigen Untertiteldatei nach.

    Style-Zeile: Rand, Schatten, Hoehe und die Randfarbe.
    Dialogue-Zeilen: das Weichzeichnen, das den Schein ergibt. ASS zeichnet
    mit \\blur Kante und Schatten weich, die Fuellung bleibt scharf - genau
    das ist das Leuchten, und zwar in der Randfarbe.
    """
    k = k or {}
    hoehe = _p67_zahl(k, "untertitel_hoehe", 3.0, 92.0)
    rand = _p67_zahl(k, "untertitel_rand", 0.0, 30.0)
    schatten = _p67_zahl(k, "untertitel_schatten", 0.0, 40.0)
    leuchten = _p67_zahl(k, "untertitel_leuchten", 0.0, 40.0)
    farbe = str(k.get("untertitel_randfarbe") or "").strip().lstrip("#")
    if len(farbe) != 6:
        farbe = ""
    if hoehe is None and rand is None and schatten is None \
            and not leuchten and not farbe:
        return 0, 0

    def skala(wert):
        return int(round(wert * h / 1920.0))

    try:
        roh = open(ziel, encoding="utf-8").read()
    except Exception:
        return 0, 0

    stile, zeilen_n, raus = 0, 0, []
    for z in roh.splitlines(True):
        if z.startswith("Style:"):
            ende = "\n" if z.endswith("\n") else ""
            f = z.rstrip("\n").split(",")
            if len(f) > P67_MV:
                if farbe:
                    f[P67_AUSSEN] = _p62_farbe(farbe, "000000")
                if rand is not None:
                    f[P67_RAND] = str(skala(rand))
                if schatten is not None:
                    f[P67_SCHATTEN] = str(skala(schatten))
                if hoehe is not None:
                    f[P67_MV] = str(int(h * hoehe / 100.0))
                z = ",".join(f) + ende
                stile += 1
        elif leuchten and z.startswith("Dialogue:"):
            f = z.split(",", 9)
            if len(f) == 10:
                f[9] = "{\\blur%.1f}" % (leuchten * h / 1920.0) + f[9]
                z = ",".join(f)
                zeilen_n += 1
        raus.append(z)

    if stile or zeilen_n:
        with open(ziel, "w", encoding="utf-8") as f:
            f.write("".join(raus))
    return stile, zeilen_n


def _ass(plan, ziel, b, h, kanal=None):
    """Wie bisher, danach Hoehe, Rand, Schatten und Leuchten nachziehen."""
    r = _p67_ass_alt(plan, ziel, b, h, kanal)
    try:
        stile, zeilen_n = _p67_nachziehen(ziel, kanal or {}, h)
    except Exception as e:
        print("[Szenen] Untertitel nachziehen ging nicht: %s" % e)
        return r
    if stile or zeilen_n:
        print("[Szenen] Untertitel nachgezogen: %d Stil, %d Zeilen mit Schein"
              % (stile, zeilen_n))
    return r


# ---------- Nachtrag p72: Leuchten als eigene Ebene ----------

import re as _p72_re

_p72_nach_alt = _p67_nachziehen
_p72_ass_alt = _ass

# ASS-Farben haben nach &H acht Stellen: zwei fuer die Durchsicht, sechs
# fuer Blau, Gruen, Rot. Darum hier keine feste Anzahl.
P72_FARBE = _p72_re.compile(r"\\1c(&H[0-9A-Fa-f]+&)")


def _p67_nachziehen(ziel, k, h):
    """Wie bisher, aber ohne das alte Weichzeichnen der Kante.

    Das Leuchten macht jetzt die Ebene darunter. Wuerde hier zusaetzlich
    weichgezeichnet, waere der Text selbst unscharf.
    """
    k2 = dict(k or {})
    k2.pop("untertitel_leuchten", None)
    return _p72_nach_alt(ziel, k2, h)


def _p72_wortfarben(k):
    """Die beiden Wortfarben als ASS-Wert, genau wie sie im Text stehen."""
    stil = str((k or {}).get("untertitel_stil") or "klassisch").strip().lower()
    aktiv = _p62_farbe((k or {}).get("untertitel_farbe_aktiv"),
                       "FFFFFF" if stil == "wortweise" else "FFD400")
    ruhe = _p62_farbe((k or {}).get("untertitel_farbe_ruhe"),
                      "B4B4B4" if stil == "wortweise" else "FFFFFF")
    return aktiv, ruhe


def _p72_leuchtebene(ziel, k, h):
    """Legt unter jede Untertitelzeile eine zweite, die nur leuchtet."""
    ruhe = _p67_zahl(k, "untertitel_leuchten", 0.0, 40.0) or 0.0
    aktiv = _p67_zahl(k, "untertitel_leuchten_aktiv", 0.0, 40.0)
    if aktiv is None:
        aktiv = ruhe
    if not ruhe and not aktiv:
        return 0

    def gr(w):
        """Staerke in Bildpunkten, mitskaliert auf die Bildhoehe."""
        return 0.0 if not w else max(0.6, w * h / 1920.0)

    f_aktiv, f_ruhe = _p72_wortfarben(k)

    try:
        roh = open(ziel, encoding="utf-8").read()
    except Exception:
        return 0

    prim = "&H00FFFFFF&"
    for z in roh.splitlines():
        if z.startswith("Style:"):
            s = z.split(",")
            if len(s) > 3 and s[3].strip().startswith("&H"):
                # in der Stil-Zeile steht die Farbe ohne das schliessende &
                prim = s[3].strip().rstrip("&") + "&"
            break

    def ersetz(m):
        c = m.group(1)
        g = gr(aktiv if c == f_aktiv else ruhe)
        return "\\3c%s\\bord%.1f\\blur%.1f" % (c, g, g)

    raus, n = [], 0
    for z in roh.splitlines(True):
        if not z.startswith("Dialogue:"):
            raus.append(z)
            continue
        f = z.rstrip("\n").split(",", 9)
        if len(f) != 10:
            raus.append(z)
            continue
        text = f[9]

        if P72_FARBE.search(text):
            g0, c0 = gr(ruhe), f_ruhe        # Wort fuer Wort, Knall, Karaoke
        else:
            g0, c0 = gr(max(ruhe, aktiv)), prim   # ganze Zeile auf einmal

        kopf = ("{\\1a&HFF&\\4a&HFF&\\shad0\\3c%s\\bord%.1f\\blur%.1f}"
                % (c0, g0, g0))
        schein = list(f)
        schein[0] = "Dialogue: 0"
        schein[9] = kopf + P72_FARBE.sub(ersetz, text)
        oben = list(f)
        oben[0] = "Dialogue: 1"

        raus.append(",".join(schein) + "\n")
        raus.append(",".join(oben) + "\n")
        n += 1

    with open(ziel, "w", encoding="utf-8") as f2:
        f2.write("".join(raus))
    return n


def _ass(plan, ziel, b, h, kanal=None):
    """Wie bisher, danach die Leuchtebene darunterlegen."""
    r = _p72_ass_alt(plan, ziel, b, h, kanal)
    try:
        n = _p72_leuchtebene(ziel, kanal or {}, h)
    except Exception as e:
        print("[Szenen] Leuchtebene ging nicht: %s" % e)
        return r
    if n:
        print("[Szenen] Leuchtebene unter %d Zeilen gelegt" % n)
    return r


# ---------- Nachtrag p74: seitlich, Winkel, Schattenrichtung ----------

import math as _p74_math

_p74_ass_alt = _ass

# Felder der Stil-Zeile, von 0 an gezaehlt
P74_ABSTAND, P74_WINKEL = 13, 14
P74_LINKS, P74_RECHTS, P74_SCHATTEN = 19, 20, 17


def _p74_breite(roh):
    """Die Breite, auf die sich die Untertiteldatei bezieht."""
    for z in roh.splitlines():
        if z.startswith("PlayResX:"):
            try:
                return int(z.split(":", 1)[1].strip())
            except Exception:
                return 1080
        if z.startswith("[V4+"):
            break
    return 1080


def _p74_dazu(ziel, k, h):
    """Schreibt die vier neuen Werte in die fertige Untertiteldatei."""
    seitlich = _p67_zahl(k, "untertitel_seitlich", -45.0, 45.0)
    winkel = _p67_zahl(k, "untertitel_winkel", -30.0, 30.0)
    richtung = _p67_zahl(k, "untertitel_schattenwinkel", 0.0, 359.0)
    abstand = _p67_zahl(k, "untertitel_abstand", 0.0, 30.0)
    if seitlich is None and winkel is None and richtung is None \
            and abstand is None:
        return 0, 0

    try:
        roh = open(ziel, encoding="utf-8").read()
    except Exception:
        return 0, 0

    b = _p74_breite(roh)
    schatten = 0.0
    stile, zeilen_n, raus = 0, 0, []

    for z in roh.splitlines(True):
        if not z.startswith("Style:"):
            raus.append(z)
            continue
        ende = "\n" if z.endswith("\n") else ""
        f = z.rstrip("\n").split(",")
        if len(f) <= P74_RECHTS:
            raus.append(z)
            continue
        try:
            schatten = float(f[P74_SCHATTEN])
        except Exception:
            schatten = 0.0
        if winkel is not None:
            # Plus hebt das Zeilenende an, minus senkt es - so herum
            # gedreht, weil ASS andersherum zaehlt.
            f[P74_WINKEL] = "%.1f" % (-winkel)
        if abstand is not None:
            f[P74_ABSTAND] = str(int(round(abstand * h / 1920.0)))
        if seitlich is not None:
            v = int(b * seitlich / 100.0)
            try:
                li, re = int(float(f[P74_LINKS])), int(float(f[P74_RECHTS]))
            except Exception:
                li = re = 0
            f[P74_LINKS] = str(max(0, li + v))
            f[P74_RECHTS] = str(max(0, re - v))
        raus.append(",".join(f) + ende)
        stile += 1

    # Schattenrichtung: nur auf der obersten Ebene, nie auf der Leuchtebene
    if richtung is not None and schatten > 0:
        text = "".join(raus)
        oben = "Dialogue: 1" if "Dialogue: 1" in text else "Dialogue: 0"
        bogen = _p74_math.radians(richtung)
        xs = schatten * _p74_math.cos(bogen)
        ys = schatten * _p74_math.sin(bogen)
        marke = "{\\xshad%.1f\\yshad%.1f}" % (xs, ys)
        neu = []
        for z in raus:
            if z.startswith(oben):
                f = z.rstrip("\n").split(",", 9)
                if len(f) == 10:
                    f[9] = marke + f[9]
                    z = ",".join(f) + "\n"
                    zeilen_n += 1
            neu.append(z)
        raus = neu

    if stile or zeilen_n:
        with open(ziel, "w", encoding="utf-8") as f2:
            f2.write("".join(raus))
    return stile, zeilen_n


def _ass(plan, ziel, b, h, kanal=None):
    """Wie bisher, danach seitlich, Winkel, Abstand und Schattenrichtung."""
    r = _p74_ass_alt(plan, ziel, b, h, kanal)
    try:
        stile, zeilen_n = _p74_dazu(ziel, kanal or {}, h)
    except Exception as e:
        print("[Szenen] Lage des Untertitels ging nicht: %s" % e)
        return r
    if stile or zeilen_n:
        print("[Szenen] Lage gesetzt: %d Stil, %d Zeilen mit Schattenrichtung"
              % (stile, zeilen_n))
    return r


# ---------- Nachtrag p78: nichts laeuft mehr aus dem Bild ----------

import re as _p78_re

_p78_ass_alt = _ass

P78_BLOCK = _p78_re.compile(r"\{[^}]*\}")
P78_FS = _p78_re.compile(r"\\fs([0-9.]+)")
P78_KLEINST = 40          # weiter als auf 40 % wird nie verkleinert
_p78_schriften = {}
_p78_dateien = {}


def _p78_datei(name):
    """Pfad zur Schriftdatei, die fontconfig fuer diesen Namen nimmt."""
    if name in _p78_dateien:
        return _p78_dateien[name]
    pfad = ""
    try:
        r = subprocess.run(["fc-match", "-f", "%{file}", name],
                           capture_output=True, text=True, timeout=10)
        pfad = (r.stdout or "").strip()
    except Exception:
        pfad = ""
    _p78_dateien[name] = pfad
    return pfad


def _p78_schrift(pfad, groesse):
    """Geladene Schrift und ihre Umrechnung, gemerkt.

    PIL und ASS meinen mit "Schriftgroesse" nicht dasselbe. PIL meint das
    Em-Quadrat, ASS meint Oberlaenge plus Unterlaenge. Bei Inter Display
    Black sind das 21 Prozent Unterschied - ungepruefte Messungen waeren
    also durchweg zu breit, und es wuerde staendig grundlos verkleinert.
    Nachgemessen gegen echte libass-Bilder: mit dieser Umrechnung stimmt
    es auf etwa ein Prozent.
    """
    schluessel = (pfad, int(groesse))
    if schluessel not in _p78_schriften:
        from PIL import ImageFont
        f = ImageFont.truetype(pfad, int(groesse))
        try:
            oben, unten = f.getmetrics()
            um = float(groesse) / float(oben + unten) if (oben + unten) else 1.0
        except Exception:
            um = 1.0
        _p78_schriften[schluessel] = (f, um)
    return _p78_schriften[schluessel]


def _p78_messen(text, pfad, grund_fs, abstand):
    """Breite der Zeile in Bildpunkten, mit allem was Platz braucht.

    Geht den Text durch und merkt sich, welche Schriftgroesse gerade
    gilt - bei Wort fuer Wort ist das gesprochene Wort ja groesser als
    die uebrigen.
    """
    breite, zeichen, fs = 0.0, 0, float(grund_fs)
    rest = text
    while rest:
        m = P78_BLOCK.search(rest)
        if m is None:
            stueck, rest = rest, ""
        else:
            stueck, marken, rest = rest[:m.start()], m.group(0), rest[m.end():]
        if stueck:
            f, um = _p78_schrift(pfad, fs)
            breite += f.getlength(stueck) * um
            zeichen += len(stueck)
        if m is not None:
            f = P78_FS.findall(marken)
            if f:
                try:
                    fs = float(f[-1])
                except Exception:
                    pass
    return breite + abstand * max(0, zeichen - 1)


def _p78_passend(ziel, b):
    """Verkleinert jede Zeile, die sonst aus dem Bild liefe."""
    try:
        roh = open(ziel, encoding="utf-8").read()
    except Exception:
        return 0, []

    schrift, fs, abstand, rand = "", 0.0, 0.0, 0.0
    li, re_ = 0, 0
    for z in roh.splitlines():
        if z.startswith("Style:"):
            f = z.split(",")
            if len(f) > 20:
                schrift = f[1].strip()
                try:
                    fs = float(f[2]); abstand = float(f[13])
                    rand = float(f[16]); li = int(float(f[19])); re_ = int(float(f[20]))
                except Exception:
                    return 0, []
            break
    if not schrift or fs <= 0:
        return 0, []

    pfad = _p78_datei(schrift)
    if not pfad or not os.path.exists(pfad):
        print("[Szenen] Schriftdatei fuer '%s' nicht gefunden, Breite ungeprueft"
              % schrift)
        return 0, []

    platz = max(80.0, b - li - re_ - 2 * rand)
    raus, eng, zu_lang = [], 0, []

    for z in roh.splitlines(True):
        if not z.startswith("Dialogue:"):
            raus.append(z)
            continue
        f = z.rstrip("\n").split(",", 9)
        if len(f) != 10:
            raus.append(z)
            continue
        text = f[9]
        try:
            breit = _p78_messen(text, pfad, fs, abstand)
        except Exception:
            raus.append(z)
            continue
        if breit <= platz or breit <= 0:
            raus.append(z)
            continue

        anteil = platz / breit
        prozent = max(P78_KLEINST, int(anteil * 100))
        faktor = prozent / 100.0
        if prozent <= P78_KLEINST:
            nackt = " ".join(P78_BLOCK.sub("", text).split())
            if nackt and nackt not in zu_lang:
                zu_lang.append(nackt)

        if P78_FS.search(text):
            text = P78_FS.sub(
                lambda m: "\\fs%d" % max(8, int(round(float(m.group(1)) * faktor))),
                text)
        else:
            text = "{\\fs%d}" % max(8, int(round(fs * faktor))) + text
        f[9] = text
        raus.append(",".join(f) + "\n")
        eng += 1

    if eng:
        with open(ziel, "w", encoding="utf-8") as f2:
            f2.write("".join(raus))
    return eng, zu_lang


def _ass(plan, ziel, b, h, kanal=None):
    """Wie bisher, danach nachmessen und zu breite Zeilen einpassen."""
    r = _p78_ass_alt(plan, ziel, b, h, kanal)
    try:
        eng, zu_lang = _p78_passend(ziel, b)
    except Exception as e:
        print("[Szenen] Breite nicht geprueft: %s" % e)
        return r
    if eng:
        print("[Szenen] %d Zeile(n) verkleinert, damit sie ins Bild passen" % eng)
    for w in zu_lang:
        print("[Szenen] ACHTUNG zu lang auch nach dem Verkleinern: %s" % w)
        print("[Szenen]   -> im Text kuerzer schreiben oder Wortzahl senken")
    return r


# ---------- Nachtrag p79: lieber umbrechen als schrumpfen ----------

P79_ZEILEN = 3            # mehr als drei Zeilen ist kein Untertitel mehr
P79_KLEINST = 65          # und verkleinert wird hoechstens auf 65 Prozent

_p79_messen_alt = _p78_messen


def _p78_messen(text, pfad, grund_fs, abstand):
    """Wie bisher - bei umgebrochenen Zeilen zaehlt aber die breiteste.

    Ohne das wuerde der Schrumpfschritt nach dem Umbrechen die Breite
    aller Zeilen zusammenzaehlen und alles noch einmal verkleinern,
    obwohl laengst jede Zeile passt.
    """
    if "\\N" not in text:
        return _p79_messen_alt(text, pfad, grund_fs, abstand)
    return max(_p79_messen_alt(s, pfad, grund_fs, abstand)
               for s in text.split("\\N"))


def _p79_luecken(text):
    """Stellen, an denen man umbrechen darf: Leerzeichen ausserhalb {}."""
    raus, tief = [], 0
    for i, z in enumerate(text):
        if z == "{":
            tief += 1
        elif z == "}":
            tief = max(0, tief - 1)
        elif z == " " and not tief:
            raus.append(i)
    return raus


def _p79_trennen(wort, passt, mass):
    """Trennt ein zu langes Wort mit Bindestrich in Stuecke, die passen."""
    stuecke, rest = [], wort
    while rest and mass(rest) > passt:
        nimm = 0
        for i in range(3, len(rest) - 2):
            if mass(rest[:i] + "-") <= passt:
                nimm = i
            else:
                break
        if nimm < 3:
            break
        if len(rest) - nimm <= 2:      # einen Rest von 1-2 Zeichen vermeiden
            nimm = max(3, nimm - 2)
        stuecke.append(rest[:nimm] + "-")
        rest = rest[nimm:]
        if len(stuecke) >= P79_ZEILEN - 1:
            break
    stuecke.append(rest)
    return stuecke


def _p79_umbrechen(text, platz, pfad, fs, abstand):
    """Bricht die Zeile um, bis sie passt. Gibt (Text, passt_jetzt)."""

    def mass(s):
        return _p78_messen(s, pfad, fs, abstand)

    if mass(text) <= platz:
        return text, True

    # Schritt 2: an der Wortgrenze trennen, moeglichst gleichmaessig
    luecken = _p79_luecken(text)
    if luecken:
        bestes, beste_stelle = None, -1
        for i in luecken:
            links, rechts = text[:i], text[i + 1:]
            schlimmer = max(mass(links), mass(rechts))
            if bestes is None or schlimmer < bestes:
                bestes, beste_stelle = schlimmer, i
        if beste_stelle >= 0 and bestes <= platz:
            return text[:beste_stelle] + "\\N" + text[beste_stelle + 1:], True
        if beste_stelle >= 0 and bestes < mass(text):
            links = text[:beste_stelle]
            rechts = text[beste_stelle + 1:]
            l2, lok = _p79_umbrechen(links, platz, pfad, fs, abstand)
            r2, rok = _p79_umbrechen(rechts, platz, pfad, fs, abstand)
            neu = l2 + "\\N" + r2
            if neu.count("\\N") < P79_ZEILEN:
                return neu, (lok and rok)

    # Schritt 3: ein einzelnes Wort ist zu lang - mit Bindestrich trennen
    marken, wort = "", text
    while wort.startswith("{"):
        zu = wort.find("}")
        if zu < 0:
            break
        marken += wort[:zu + 1]
        wort = wort[zu + 1:]
    if wort and "{" not in wort and " " not in wort:
        stuecke = _p79_trennen(wort, platz, mass)
        if len(stuecke) > 1:
            # Die Farbmarke muss auf jedes Stueck, sonst faellt die zweite
            # Zeile auf die Standardfarbe zurueck.
            neu = "\\N".join(marken + s for s in stuecke)
            return neu, all(mass(marken + s) <= platz for s in stuecke)
    return text, False


_p78_passend_alt = _p78_passend


def _p78_passend(ziel, b):
    """Erst umbrechen, dann - nur wenn es sein muss - verkleinern."""
    try:
        roh = open(ziel, encoding="utf-8").read()
    except Exception:
        return 0, []

    schrift, fs, abstand, rand = "", 0.0, 0.0, 0.0
    li, re_ = 0, 0
    for z in roh.splitlines():
        if z.startswith("Style:"):
            f = z.split(",")
            if len(f) > 20:
                schrift = f[1].strip()
                try:
                    fs = float(f[2]); abstand = float(f[13])
                    rand = float(f[16]); li = int(float(f[19])); re_ = int(float(f[20]))
                except Exception:
                    return 0, []
            break
    if not schrift or fs <= 0:
        return 0, []
    pfad = _p78_datei(schrift)
    if not pfad or not os.path.exists(pfad):
        return _p78_passend_alt(ziel, b)

    platz = max(80.0, b - li - re_ - 2 * rand)
    raus, gebrochen = [], 0

    for z in roh.splitlines(True):
        if not z.startswith("Dialogue:"):
            raus.append(z)
            continue
        f = z.rstrip("\n").split(",", 9)
        if len(f) != 10 or "\\N" in f[9]:
            raus.append(z)
            continue
        try:
            neu, _ok = _p79_umbrechen(f[9], platz, pfad, fs, abstand)
        except Exception:
            raus.append(z)
            continue
        if neu != f[9]:
            f[9] = neu
            z = ",".join(f) + "\n"
            gebrochen += 1
        raus.append(z)

    if gebrochen:
        with open(ziel, "w", encoding="utf-8") as f2:
            f2.write("".join(raus))
        print("[Szenen] %d Zeile(n) umgebrochen statt verkleinert" % gebrochen)

    # Was auch nach dem Umbrechen nicht passt, wird verkleinert - aber die
    # Untergrenze liegt jetzt bei 65 statt 40 Prozent.
    alt = globals().get("P78_KLEINST", 40)
    globals()["P78_KLEINST"] = P79_KLEINST
    try:
        eng, zu_lang = _p78_passend_alt(ziel, b)
    finally:
        globals()["P78_KLEINST"] = alt
    return eng, zu_lang


# ---------- Nachtrag p83: Klammer ohne Ende ----------

import re as _p83_re

# [ bis zum passenden ], sonst bis zum Schluss
P83_GANZ = _p83_re.compile(r"\[([^\[\]]{1,400})\]", _p83_re.S)
P83_OFFEN = _p83_re.compile(r"\[([^\[\]]{1,400})$", _p83_re.S)
P83_REST = _p83_re.compile(r"[\[\]]")

_p83_regie_alt = _regie_trennen


def _regie_trennen(text):
    """Trennt die Regie ab - auch wenn die schliessende Klammer fehlt."""
    ganz = text or ""
    teile = [" ".join(x.split()) for x in P83_GANZ.findall(ganz) if x and x.strip()]
    rest = P83_GANZ.sub(" ", ganz)

    offen = P83_OFFEN.search(rest)
    if offen:
        w = " ".join(offen.group(1).split())
        if w:
            teile.append(w)
        rest = rest[:offen.start()]

    # verirrte einzelne Klammern haben im gesprochenen Text nichts verloren
    rest = " ".join(P83_REST.sub(" ", rest).split())
    return rest, " | ".join(teile)


# ---------- Nachtrag p84: eine Bildbeschreibung ist kein Kamerabefehl ----------

import re as _p84_re_sv

P84_TEIL = _p84_re_sv.compile(r"\s*\|\s*")
P84_SV_BILD = _p84_re_sv.compile(r"^BILD\s*[:\-]\s*", _p84_re_sv.I)
P84_SV_BEWEG = _p84_re_sv.compile(r"^BEWEGUNG\s*[:\-]\s*", _p84_re_sv.I)

_p84_bewegung_alt = _bewegungs_text


def _bewegungs_text(kanal, szene):
    """Wie bisher - aber nur der BEWEGUNG-Teil zaehlt als Anweisung.

    Vorher ging die ganze Klammer an das Bewegungsmodell. Steht dort eine
    Bildbeschreibung ("tausend Muenzen auf schwarzem Tisch"), versucht das
    Modell daraus eine Kamerabewegung zu machen und erfindet Bewegung, die
    im Bild gar nicht angelegt ist.
    """
    regie = (szene.get("regie") or "").strip()
    if not regie:
        return _p84_bewegung_alt(kanal, szene)

    beweg, ohne = [], []
    for x in P84_TEIL.split(regie):
        x = x.strip()
        if not x:
            continue
        if P84_SV_BEWEG.match(x):
            w = P84_SV_BEWEG.sub("", x).strip()
            if w:
                beweg.append(w)
        elif P84_SV_BILD.match(x):
            continue
        else:
            ohne.append(x)

    if beweg:
        return ", ".join(beweg)[:900]
    if ohne:
        return ", ".join(ohne)[:900]
    # Es stand nur eine Bildbeschreibung da - zurueck zur Grundbewegung.
    leer = dict(szene)
    leer["regie"] = ""
    return _p84_bewegung_alt(kanal, leer)
