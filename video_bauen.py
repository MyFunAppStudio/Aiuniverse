# ============================================
# Video bauen: Bilder + Ton -> fertiges Video
# Mit abwechselnden Effekten, schnellen Schnitten
# und eingebrannten Untertiteln
# ============================================
import subprocess
import random
import re
from pathlib import Path
import config
import einstellungen

FPS = 30
BREITE, HOEHE = 1080, 1920   # Standard hochkant, pro Kanal umstellbar
SCHRIFT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def ton_laenge(ton_pfad):
    """Laenge der Tonspur in Sekunden."""
    ergebnis = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(ton_pfad)
    ], capture_output=True, text=True)
    try:
        return float(ergebnis.stdout.strip())
    except ValueError:
        return 30.0


def _effekt(nummer, dauer):
    """Ken-Burns: 6 verschiedene Bewegungen, wechseln sich ab."""
    f = max(2, int(dauer * FPS))
    _gb = int(BREITE * 1.25) // 2 * 2
    _gh = int(HOEHE * 1.25) // 2 * 2
    gross = f"scale={_gb}:{_gh}:force_original_aspect_ratio=increase,crop={_gb}:{_gh}"
    mitte_x = "iw/2-(iw/zoom/2)"
    mitte_y = "ih/2-(ih/zoom/2)"

    varianten = [
        # 0: langsam reinzoomen
        f"{gross},zoompan=z='min(1+0.0010*on,1.16)':d={f}:x='{mitte_x}':y='{mitte_y}':s={BREITE}x{HOEHE}:fps={FPS}"
        f":s={BREITE}x{HOEHE}:fps={FPS}",
        # 1: rauszoomen
        f"{gross},zoompan=z='max(1.16-0.0010*on,1.0)':d={f}:x='{mitte_x}':y='{mitte_y}':s={BREITE}x{HOEHE}:fps={FPS}"
        f":s={BREITE}x{HOEHE}:fps={FPS}",
        # 2: Schwenk nach rechts
        f"{gross},zoompan=z='1.12':d={f}:x='(iw-iw/zoom)*on/{f}':y='{mitte_y}':s={BREITE}x{HOEHE}:fps={FPS}"
        f":s={BREITE}x{HOEHE}:fps={FPS}",
        # 3: Schwenk nach links
        f"{gross},zoompan=z='1.12':d={f}:x='(iw-iw/zoom)*(1-on/{f})':y='{mitte_y}':s={BREITE}x{HOEHE}:fps={FPS}"
        f":s={BREITE}x{HOEHE}:fps={FPS}",
        # 4: Schwenk nach unten + leichter Zoom
        f"{gross},zoompan=z='min(1.08+0.0006*on,1.18)':d={f}:x='{mitte_x}':s={BREITE}x{HOEHE}:fps={FPS}"
        f":y='(ih-ih/zoom)*on/{f}':s={BREITE}x{HOEHE}:fps={FPS}",
        # 5: diagonal
        f"{gross},zoompan=z='min(1.08+0.0006*on,1.18)':d={f}:s={BREITE}x{HOEHE}:fps={FPS}"
        f":x='(iw-iw/zoom)*on/{f}':y='(ih-ih/zoom)*on/{f}'"
        f":s={BREITE}x{HOEHE}:fps={FPS}",
    ]
    return varianten[nummer % len(varianten)]


def _ass_alt(text, gesamt_sek, ziel, stil="modern", kanal=None):
    """ASS-Untertitel im TikTok-Stil: mitlaufende Wort-Hervorhebung."""
    import re
    from pathlib import Path
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return None

    woerter = text.split(" ")
    if not woerter:
        return None

    # Zeilen mit 4-6 Woertern
    zeilen, aktuell = [], []
    for w in woerter:
        aktuell.append(w)
        laenge = sum(len(x) + 1 for x in aktuell)
        if len(aktuell) >= 5 or laenge > 32:
            zeilen.append(aktuell)
            aktuell = []
    if aktuell:
        zeilen.append(aktuell)

    zeichen_gesamt = sum(sum(len(w) + 1 for w in z) for z in zeilen) or 1

    stile = {
        "modern": dict(schrift="DejaVu Sans", groesse=46,
                       gesprochen="&H0000E5FF&", offen="&H00FFFFFF&",
                       rand="&H00000000&", dicke=4, position=60),
        "gross":  dict(schrift="DejaVu Sans", groesse=58,
                       gesprochen="&H0000FF00&", offen="&H00FFFFFF&",
                       rand="&H00000000&", dicke=5, position=80),
        "dezent": dict(schrift="DejaVu Sans", groesse=34,
                       gesprochen="&H00FFFFFF&", offen="&H00BBBBBB&",
                       rand="&H00000000&", dicke=2, position=40),
    }
    s = dict(stile.get(stil, stile["modern"]))
    if kanal:
        if kanal.get("untertitel_schrift"):
            s["schrift"] = kanal["untertitel_schrift"]
        if kanal.get("untertitel_groesse"):
            s["groesse"] = int(kanal["untertitel_groesse"])
        if kanal.get("untertitel_position"):
            s["position"] = int(kanal["untertitel_position"])

    kopf = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Std,{s['schrift']},{s['groesse']},{s['gesprochen']},{s['offen']},{s['rand']},&H64000000&,-1,0,0,0,100,100,0,0,1,{s['dicke']},2,2,60,60,{s['position']},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def zeit(sek):
        sek = max(0, sek)
        st = int(sek // 3600)
        mi = int((sek % 3600) // 60)
        se = sek % 60
        return f"{st}:{mi:02d}:{se:05.2f}"

    zeilen_aus, uhr = [], 0.0
    for zl in zeilen:
        z_zeichen = sum(len(w) + 1 for w in zl)
        dauer = gesamt_sek * z_zeichen / zeichen_gesamt
        dauer = max(0.7, dauer)
        ende = min(uhr + dauer, gesamt_sek)
        # Karaoke: jedes Wort bekommt seine Dauer in Hundertstel
        teile = []
        for w in zl:
            w_anteil = (len(w) + 1) / z_zeichen
            k = max(8, int(round(dauer * w_anteil * 100)))
            teile.append("{\\k%d}%s " % (k, w))
        zeilen_aus.append(
            f"Dialogue: 0,{zeit(uhr)},{zeit(ende)},Std,,0,0,0,,{''.join(teile).strip()}")
        uhr = ende
        if uhr >= gesamt_sek:
            break

    ziel = Path(ziel)
    ziel.write_text(kopf + "\n".join(zeilen_aus) + "\n", encoding="utf-8")
    return ziel


CTA_TEXTE = {
    "Deutsch":      ("FOLGEN fuer mehr", "LIKE wenn es gefaellt", "ABONNIEREN"),
    "Englisch":     ("FOLLOW for more", "LIKE if you enjoyed", "SUBSCRIBE"),
    "Spanisch":     ("SIGUEME para mas", "DALE LIKE", "SUSCRIBETE"),
    "Portugiesisch":("SIGA para mais", "DEIXE seu LIKE", "INSCREVA-SE"),
    "Franzoesisch": ("ABONNE-TOI", "LAISSE un LIKE", "S'ABONNER"),
    "Italienisch":  ("SEGUIMI per altro", "METTI LIKE", "ISCRIVITI"),
    "Hindi":        ("FOLLOW for more", "LIKE if you enjoyed", "SUBSCRIBE"),
    "Niederlaendisch": ("VOLG voor meer", "LIKE als het bevalt", "ABONNEER"),
}


def _cta_filter(kanal, gesamt):
    """Einblendungen fuer Follow, Like und Abonnieren - in der Kanalsprache."""
    sprachen = kanal.get("sprachen") or ["Deutsch"]
    folgen, liken, abo = CTA_TEXTE.get(sprachen[0], CTA_TEXTE["Deutsch"])
    # eigene Texte haben Vorrang
    folgen = (kanal.get("cta_text_folgen") or folgen).strip()
    liken = (kanal.get("cta_text_like") or liken).strip()
    abo = (kanal.get("cta_text_abo") or abo).strip()

    teile = []
    schrift = SCHRIFT.replace(":", r"\\:")

    def kasten(text, von, dauer):
        text = text.replace("'", "").replace(":", "").replace("\\", "")
        bis = von + dauer
        return (f"drawtext=fontfile='{schrift}':text='{text}'"
                f":fontcolor=white:fontsize=40:borderw=4:bordercolor=black@0.9"
                f":box=1:boxcolor=black@0.45:boxborderw=18"
                f":x=(w-text_w)/2:y=80"
                f":enable='between(t,{von:.1f},{bis:.1f})'")

    if kanal.get("anim_follow", True) and gesamt > 12:
        teile.append(kasten(folgen, gesamt * 0.45, 4))
    if kanal.get("anim_like", True):
        teile.append(kasten(liken, max(0, gesamt - 6), 3))

    wann = kanal.get("abo_position", "ende")
    if kanal.get("anim_abo", True):
        if wann == "anfang" and gesamt > 10:
            teile.append(kasten(abo, 4, 3))
        elif wann == "mitte" and gesamt > 14:
            teile.append(kasten(abo, gesamt * 0.6, 3))
        elif gesamt > 12:
            teile.append(kasten(abo, max(0, gesamt - 3), 3))
    return teile


def baue_thumbnail(kanal, bild, titel, ziel):
    """Erzeugt ein Thumbnail: Bild + grosser Titeltext."""
    _setze_format(kanal)
    ziel = Path(ziel)
    if not bild or not Path(bild).exists():
        return None

    text = re.sub(r"\s+", " ", (titel or "").strip())
    text = text.replace("'", "").replace(":", " -").replace("\\", "")
    if len(text) > 60:
        text = text[:57] + "..."

    # in zwei Zeilen brechen
    woerter = text.split(" ")
    z1, z2 = [], []
    for w in woerter:
        if len(" ".join(z1 + [w])) <= 22 or not z1:
            z1.append(w)
        else:
            z2.append(w)
    zeile1, zeile2 = " ".join(z1), " ".join(z2)

    schrift = SCHRIFT.replace(":", r"\\:")
    groesse = int(kanal.get("thumb_groesse", 78))
    farbe = kanal.get("thumb_farbe", "#FFDD00")

    filter_teile = [
        f"scale={BREITE}:{HOEHE}:force_original_aspect_ratio=increase,crop={BREITE}:{HOEHE}",
        "eq=contrast=1.15:saturation=1.25:brightness=0.02",
        "drawbox=x=0:y=h-300:w=iw:h=300:color=black@0.55:t=fill",
    ]
    y1 = "h-250" if zeile2 else "h-190"
    filter_teile.append(
        f"drawtext=fontfile='{schrift}':text='{zeile1}':fontcolor={farbe}"
        f":fontsize={groesse}:borderw=6:bordercolor=black"
        f":x=(w-text_w)/2:y={y1}")
    if zeile2:
        filter_teile.append(
            f"drawtext=fontfile='{schrift}':text='{zeile2}':fontcolor=white"
            f":fontsize={groesse}:borderw=6:bordercolor=black"
            f":x=(w-text_w)/2:y=h-150")

    befehl = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(bild),
              "-vf", ",".join(filter_teile), "-frames:v", "1", str(ziel)]
    e = subprocess.run(befehl, capture_output=True, text=True)
    if e.returncode != 0:
        print("[Thumb] Fehler:", e.stderr[-200:])
        return None
    print(f"[Thumb] erstellt: {ziel.name}")
    return ziel


def baue_video(kanal, bilder, ton_pfad, ziel_pfad, skript=None, szenen=None):
    """Fuegt Bilder + Ton + Effekte + Untertitel zusammen."""
    _tt_ton_setzen(ton_pfad)
    bilder = _bilder_pruefen(bilder)
    _setze_format(kanal)
    bilder = [Path(b) for b in bilder]
    ton_pfad = Path(ton_pfad)
    ziel_pfad = Path(ziel_pfad)
    ziel_pfad.parent.mkdir(parents=True, exist_ok=True)

    if not bilder:
        print("[Video] Keine Bilder vorhanden")
        return None

    gesamt = ton_laenge(ton_pfad)
    schnitte = max(1, int(kanal.get("schnitte_pro_bild", 2)))
    zoom_an = kanal.get("zoom_effekte", True)

    # EIN Effekt pro Bild, laeuft ruhig ueber die ganze Standzeit durch.
    # Schnellere Schnitte = mehr Bilder pro Minute einstellen.
    # Standzeit je Bild: mit Szenen nach Textlaenge gewichtet, damit das Bild
    # genau so lange steht wie der zugehoerige Text gesprochen wird.
    if szenen and len(szenen) == len(bilder):
        zeichen = [max(1, len((x.get("text") or ""))) for x in szenen]
        summe = sum(zeichen)
        laengen = [max(1.2, gesamt * z / summe) for z in zeichen]
        print(f"[Video] {len(bilder)} Szenen - Bilddauer passt zum Text")
    else:
        laengen = [max(1.5, gesamt / len(bilder))] * len(bilder)
        print(f"[Video] {len(bilder)} Bilder gleichmaessig verteilt")

    abschnitte = [(bild, i) for i, bild in enumerate(bilder)]

    befehl = ["ffmpeg", "-y", "-loglevel", "error"]
    for nr, (bild, _) in enumerate(abschnitte):
        if zoom_an:
            # nur EIN Frame - zoompan erzeugt daraus die ganze Bewegung
            befehl += ["-i", str(bild)]
        else:
            befehl += ["-loop", "1", "-t", f"{laengen[nr]:.3f}", "-i", str(bild)]
    befehl += ["-i", str(ton_pfad)]

    teile = []
    for n, (_, effekt_nr) in enumerate(abschnitte):
        if zoom_an:
            filt = (f"[{n}:v]{_effekt(effekt_nr, laengen[n])},"
                    f"trim=duration={laengen[n]:.3f},setpts=PTS-STARTPTS,"
                    f"setsar=1,format=yuv420p[v{n}]")
        else:
            filt = (f"[{n}:v]scale={BREITE}:{HOEHE}:force_original_aspect_ratio=increase,"
                    f"crop={BREITE}:{HOEHE},setsar=1,fps={FPS},format=yuv420p[v{n}]")
        teile.append(filt)

    kette = "".join(f"[v{n}]" for n in range(len(abschnitte)))
    teile.append(f"{kette}concat=n={len(abschnitte)}:v=1:a=0[roh]")

    # Einblendungen (Follow / Like / Abo)
    cta = _cta_filter(kanal, gesamt)
    if cta:
        teile.append("[roh]" + ",".join(cta) + "[mitcta]")
        quelle = "mitcta"
        print(f"[Video] {len(cta)} Einblendungen (Follow/Like/Abo)")
    else:
        quelle = "roh"

    # Untertitel einbrennen
    letzte = quelle
    srt = None
    if skript:
        srt = baue_untertitel_ass(skript, gesamt,
                                  ziel_pfad.parent / "untertitel.ass",
                                  kanal.get("untertitel_stil", "modern"), kanal)
    if srt and srt.exists():
        pfad = str(srt).replace(":", r"\:").replace("'", r"\'")
        teile.append(f"[{quelle}]ass='{pfad}'[vout]")
        letzte = "vout"
        print(f"[Video] Untertitel im Stil '{kanal.get('untertitel_stil','modern')}'")
    else:
        teile.append(f"[{quelle}]copy[vout]")
        letzte = "vout"

    befehl += [
        "-filter_complex", ";".join(teile),
        "-map", f"[{letzte}]",
        "-map", f"{len(abschnitte)}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-shortest", str(ziel_pfad)
    ]

    print("[Video] FFmpeg laeuft...")
    ergebnis = subprocess.run(befehl, capture_output=True, text=True)

    if ergebnis.returncode != 0:
        print("[Video] FEHLER:")
        print(ergebnis.stderr[-700:])
        return None

    mb = ziel_pfad.stat().st_size / (1024 * 1024)
    print(f"[Video] Fertig: {ziel_pfad.name} ({mb:.1f} MB)")
    return ziel_pfad


if __name__ == "__main__":
    print("=" * 45)
    print("VIDEO-BAU TEST")
    print("=" * 45)
    ordner = config.ORDNER_VIDEOS / "_test"
    bilder = sorted(ordner.glob("bild_*.jpg"))
    ton = ordner / "ton.mp3"
    if not bilder or not ton.exists():
        print("Erst 'python3 medien.py' laufen lassen!")
    else:
        e = baue_video(config.KANAL_A, bilder, ton, ordner / "test_video.mp4",
                       skript="Das ist ein Test der Untertitel. "
                              "Sie sollten gut lesbar sein und mitlaufen.")
        print("OK:" if e else "Fehlgeschlagen", e or "")


# ===== Hochformat-Erweiterung (Patch) =====
def _setze_format(kanal):
    """Setzt BREITE/HOEHE auf das Format des Kanals."""
    global BREITE, HOEHE
    try:
        b, h = einstellungen.format_masse(kanal)
    except Exception:
        b, h = 1080, 1920
    BREITE, HOEHE = int(b), int(h)
    return BREITE, HOEHE


def _ass_fix(ziel, kanal=None):
    """Passt eine fertige .ass-Datei an BREITE/HOEHE an."""
    try:
        with open(ziel, encoding="utf-8") as f:
            t = f.read()
    except Exception:
        return
    m = re.search(r"PlayResX:\s*(\d+)", t)
    alt_b = float(m.group(1)) if (m and int(m.group(1)) > 0) else 1280.0
    hoch = HOEHE >= BREITE
    skal = (BREITE / alt_b) * (1.45 if hoch else 1.0)
    gesehen = {"PlayResX": False, "PlayResY": False,
               "WrapStyle": False, "ScaledBorderAndShadow": False}
    feld = []
    aus = []
    for z in t.splitlines():
        s = z.strip()
        low = s.lower()
        if low.startswith("playresx:"):
            aus.append("PlayResX: %d" % BREITE)
            gesehen["PlayResX"] = True
            continue
        if low.startswith("playresy:"):
            aus.append("PlayResY: %d" % HOEHE)
            gesehen["PlayResY"] = True
            continue
        if low.startswith("wrapstyle:"):
            aus.append("WrapStyle: 0")
            gesehen["WrapStyle"] = True
            continue
        if low.startswith("scaledborderandshadow:"):
            aus.append("ScaledBorderAndShadow: yes")
            gesehen["ScaledBorderAndShadow"] = True
            continue
        if low.startswith("format:") and "fontname" in low:
            feld = [x.strip().lower() for x in s.split(":", 1)[1].split(",")]
            aus.append(z)
            continue
        if low.startswith("style:") and feld:
            w = [x.strip() for x in s.split(":", 1)[1].split(",")]
            while len(w) < len(feld):
                w.append("0")

            def hol(name, stand):
                try:
                    return float(w[feld.index(name)])
                except Exception:
                    return stand

            def setz(name, wert):
                if name in feld:
                    w[feld.index(name)] = str(wert)

            setz("fontsize", max(14, int(round(hol("fontsize", 48.0) * skal))))
            setz("outline", max(1, int(round(hol("outline", 3.0) * skal))))
            setz("shadow", int(round(hol("shadow", 0.0) * skal)))
            if hoch:
                setz("marginl", int(BREITE * 0.07))
                setz("marginr", int(BREITE * 0.07))
                setz("marginv", int(HOEHE * 0.18))
                setz("alignment", 2)
            aus.append("Style: " + ",".join(w))
            continue
        aus.append(z)
    t = "\n".join(aus)
    kopf = []
    for k, v in (("PlayResX", BREITE), ("PlayResY", HOEHE),
                 ("WrapStyle", 0), ("ScaledBorderAndShadow", "yes")):
        if not gesehen[k]:
            kopf.append("%s: %s" % (k, v))
    if kopf:
        if "[Script Info]" in t:
            t = t.replace("[Script Info]", "[Script Info]\n" + "\n".join(kopf), 1)
        else:
            t = "[Script Info]\n" + "\n".join(kopf) + "\n" + t
    if hoch:
        neu = []
        for z in t.splitlines():
            if z.startswith("Dialogue:"):
                z = z.replace("\\N", " ")
            neu.append(z)
        t = "\n".join(neu)
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(t + "\n")


def _ass_wrap_alt(*a, **k):
    erg = _ass_alt(*a, **k)
    ziel = k.get("ziel")
    if ziel is None and len(a) > 2:
        ziel = a[2]
    if ziel:
        _ass_fix(ziel, k.get("kanal"))
    return erg

# ===== Profi-Untertitel (Patch TT) =====
_TT_SCHRIFT = None


def _tt_schrift():
    """Beste vorhandene fette Schrift finden."""
    global _TT_SCHRIFT
    if _TT_SCHRIFT:
        return _TT_SCHRIFT
    kandidaten = ["Montserrat ExtraBold", "Montserrat", "Inter Display Black",
                  "Inter Black", "Inter", "Open Sans", "DejaVu Sans"]
    gefunden = "DejaVu Sans"
    for name in kandidaten:
        try:
            r = subprocess.run(["fc-match", "-f", "%{family}", name],
                               capture_output=True, text=True, timeout=10)
            fam = (r.stdout or "").strip()
            if fam and name.split()[0].lower() in fam.lower():
                gefunden = name
                break
        except Exception:
            pass
    _TT_SCHRIFT = gefunden
    return gefunden


def _tt_zeit(s):
    if s < 0:
        s = 0
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    r = s - h * 3600 - m * 60
    return "%d:%02d:%05.2f" % (h, m, r)


def _tt_stuecke(text, max_w=3, max_z=15):
    """Text in kurze Haeppchen von 2-3 Woertern schneiden."""
    worte = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    raus, akt = [], []
    for w in worte:
        probe = akt + [w]
        if akt and (len(probe) > max_w or len(" ".join(probe)) > max_z):
            raus.append(akt)
            akt = [w]
        else:
            akt = probe
        if akt and w[-1:] in ".!?:;":
            raus.append(akt)
            akt = []
    if akt:
        raus.append(akt)
    return raus


def _tt_ass_kopf(fs, rand, schatten, ml, mv, schrift):
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
        "Style: TT,%s,%d,&H0000D4FF,&H00FFFFFF,&H00000000,&H96000000,"
        "-1,0,0,0,100,100,0,0,1,%d,%d,2,%d,%d,%d,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n" % (BREITE, HOEHE, schrift, fs, rand, schatten, ml, ml, mv)
    )


def baue_untertitel_ass(*a, **k):
    """Grosse, fette Haeppchen-Untertitel mit Wort-Highlight."""
    text = k.get("text") if "text" in k else (a[0] if len(a) > 0 else "")
    gesamt = k.get("gesamt_sek") if "gesamt_sek" in k else (a[1] if len(a) > 1 else 0)
    ziel = k.get("ziel") if "ziel" in k else (a[2] if len(a) > 2 else None)
    kanal = k.get("kanal") if "kanal" in k else (a[4] if len(a) > 4 else None)
    gesamt = float(gesamt or 0)
    if not ziel:
        return None
    if kanal:
        try:
            _setze_format(kanal)
        except Exception:
            pass

    e = {}
    try:
        e = (einstellungen.laden().get(kanal) or {}) if kanal else {}
    except Exception:
        e = {}
    try:
        fak = float(e.get("untertitel_groesse", 48) or 48) / 48.0
    except Exception:
        fak = 1.0
    fak = max(0.5, min(2.0, fak))
    caps = e.get("untertitel_caps", True)

    hoch = HOEHE >= BREITE
    fs = max(20, int(BREITE * (0.088 if hoch else 0.052) * fak))
    rand = max(2, int(fs * 0.12))
    schatten = max(1, int(fs * 0.035))
    ml = int(BREITE * 0.08)
    mv = int(HOEHE * (0.30 if hoch else 0.09))

    stuecke = _tt_stuecke(text)
    if not stuecke or gesamt <= 0:
        with open(ziel, "w", encoding="utf-8") as f:
            f.write(_tt_ass_kopf(fs, rand, schatten, ml, mv, _tt_schrift()))
        return ziel

    gewicht = [max(4, sum(len(w) for w in s) + len(s)) for s in stuecke]
    summe = float(sum(gewicht))
    zeilen = []
    t0 = 0.0
    for i, st in enumerate(stuecke):
        dauer = gesamt * gewicht[i] / summe
        dauer = max(0.38, dauer)
        t1 = min(gesamt, t0 + dauer)
        if t1 <= t0:
            break
        wz = [max(8, int(round((t1 - t0) * 100 * (len(w) + 1) /
                               float(sum(len(x) + 1 for x in st))))) for w in st]
        rest = int(round((t1 - t0) * 100)) - sum(wz)
        if wz:
            wz[-1] = max(8, wz[-1] + rest)
        inhalt = "".join("{\\k%d}%s " % (wz[j], (w.upper() if caps else w))
                         for j, w in enumerate(st)).strip()
        vor = ("{\\fad(70,70)\\fscx84\\fscy84"
               "\\t(0,130,\\fscx100\\fscy100)}")
        zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,%s%s"
                      % (_tt_zeit(t0), _tt_zeit(t1), vor, inhalt))
        t0 = t1
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(_tt_ass_kopf(fs, rand, schatten, ml, mv, _tt_schrift()) + "\n".join(zeilen) + "\n")
    return ziel

# ===== Untertitel-Timing nach echtem Sprechfluss (TT_V2) =====
_TT_TON = None


def _tt_ton_setzen(pfad):
    global _TT_TON
    _TT_TON = str(pfad) if pfad else None
    return _TT_TON


def _tt_silben(wort):
    w = wort.lower()
    gruppen = re.findall(r"[aeiouyäöü]+", w)
    n = len(gruppen)
    return n if n > 0 else 1


def _tt_dauer(pfad):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                            "format=duration", "-of", "csv=p=0", str(pfad)],
                           capture_output=True, text=True, timeout=30)
        return float((r.stdout or "0").strip())
    except Exception:
        return 0.0


def _tt_sprachsegmente(pfad, gesamt):
    """Abschnitte, in denen wirklich gesprochen wird."""
    stille = []
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(pfad),
                            "-af", "silencedetect=noise=-33dB:d=0.16", "-f", "null", "-"],
                           capture_output=True, text=True, timeout=120)
        txt = (r.stderr or "")
        anf = None
        for m in re.finditer(r"silence_(start|end):\s*(-?[0-9.]+)", txt):
            art, wert = m.group(1), float(m.group(2))
            if art == "start":
                anf = wert
            elif anf is not None:
                stille.append((max(0.0, anf), max(0.0, wert)))
                anf = None
        if anf is not None:
            stille.append((max(0.0, anf), gesamt))
    except Exception:
        stille = []

    seg, pos = [], 0.0
    for s, e in stille:
        if s > pos:
            seg.append((pos, min(s, gesamt)))
        pos = max(pos, e)
    if pos < gesamt:
        seg.append((pos, gesamt))
    seg = [(s, e) for s, e in seg if e - s > 0.12]
    if not seg:
        seg = [(0.0, gesamt)]
    return seg


def _tt_wand(seg):
    """Umrechner: Sprechzeit -> echte Zeit im Video."""
    laengen = [e - s for s, e in seg]
    summe = sum(laengen) or 1.0

    def wand(t):
        t = max(0.0, min(summe, t))
        rest = t
        for i, (s, e) in enumerate(seg):
            d = laengen[i]
            if rest <= d or i == len(seg) - 1:
                return s + min(rest, d)
            rest -= d
        return seg[-1][1]

    return wand, summe


def baue_untertitel_ass(*a, **k):
    """Haeppchen-Untertitel, zeitlich am echten Sprechfluss ausgerichtet."""
    text = k.get("text") if "text" in k else (a[0] if len(a) > 0 else "")
    gesamt = k.get("gesamt_sek") if "gesamt_sek" in k else (a[1] if len(a) > 1 else 0)
    ziel = k.get("ziel") if "ziel" in k else (a[2] if len(a) > 2 else None)
    kanal = k.get("kanal") if "kanal" in k else (a[4] if len(a) > 4 else None)
    gesamt = float(gesamt or 0)
    if not ziel:
        return None
    if kanal:
        try:
            _setze_format(kanal)
        except Exception:
            pass

    e = {}
    try:
        e = (einstellungen.laden().get(kanal) or {}) if kanal else {}
    except Exception:
        e = {}
    try:
        fak = float(e.get("untertitel_groesse", 48) or 48) / 48.0
    except Exception:
        fak = 1.0
    fak = max(0.5, min(2.0, fak))
    caps = e.get("untertitel_caps", True)
    try:
        pro = int(e.get("untertitel_woerter", 3) or 3)
    except Exception:
        pro = 3
    pro = max(1, min(5, pro))

    hoch = HOEHE >= BREITE
    fs = max(20, int(BREITE * (0.088 if hoch else 0.052) * fak))
    rand = max(2, int(fs * 0.12))
    schatten = max(1, int(fs * 0.035))
    ml = int(BREITE * 0.08)
    mv = int(HOEHE * (0.30 if hoch else 0.09))

    kopf = _tt_ass_kopf(fs, rand, schatten, ml, mv, _tt_schrift())
    stuecke = _tt_stuecke(text, max_w=pro, max_z=15)
    if not stuecke:
        with open(ziel, "w", encoding="utf-8") as f:
            f.write(kopf)
        return ziel

    # echte Tonlaenge und Sprechabschnitte
    ton = _TT_TON if (_TT_TON and os.path.exists(_TT_TON)) else None
    if ton:
        d = _tt_dauer(ton)
        if d > 0.5:
            gesamt = d
    if gesamt <= 0:
        gesamt = max(1.0, len(stuecke) * 0.8)
    seg = _tt_sprachsegmente(ton, gesamt) if ton else [(0.0, gesamt)]
    wand, sprechzeit = _tt_wand(seg)

    # Saetze bilden (Haeppchen bis zum Satzzeichen)
    saetze, akt = [], []
    for st in stuecke:
        akt.append(st)
        if st and st[-1][-1:] in ".!?":
            saetze.append(akt)
            akt = []
    if akt:
        saetze.append(akt)

    def gewicht(st):
        g = sum(_tt_silben(w) for w in st) + 0.35 * len(st)
        if st and st[-1][-1:] in ".!?":
            g += 0.45
        elif st and st[-1][-1:] in ",;:":
            g += 0.25
        return max(0.6, g)

    # Satzgrenzen auf die Sprechabschnitte legen
    if len(saetze) == len(seg):
        bereiche = list(seg)
    else:
        sg = [sum(gewicht(x) for x in s_) for s_ in saetze]
        ges = float(sum(sg)) or 1.0
        luecken = [(seg[i][1] + seg[i + 1][0]) / 2.0 for i in range(len(seg) - 1)]
        grenzen, lauf = [], 0.0
        for g in sg[:-1]:
            lauf += g
            z = wand(sprechzeit * lauf / ges)
            if luecken:
                nah = min(luecken, key=lambda x: abs(x - z))
                if abs(nah - z) < 0.9:
                    z = nah
            grenzen.append(z)
        grenzen = sorted(set(grenzen))
        kanten = [seg[0][0]] + grenzen + [seg[-1][1]]
        bereiche = [(kanten[i], max(kanten[i] + 0.3, kanten[i + 1]))
                    for i in range(len(kanten) - 1)]
        while len(bereiche) < len(saetze):
            bereiche.append((seg[-1][1] - 0.3, seg[-1][1]))
        bereiche = bereiche[:len(saetze)]

    zeilen = []
    for si, satz in enumerate(saetze):
        a0, a1 = bereiche[si]
        sg = [gewicht(x) for x in satz]
        su = float(sum(sg)) or 1.0
        lauf = a0
        for j, st in enumerate(satz):
            d = (a1 - a0) * sg[j] / su
            t0 = lauf
            t1 = a1 if j == len(satz) - 1 else min(a1, lauf + d)
            lauf = t1
            if t1 - t0 < 0.28:
                t1 = t0 + 0.28
            zent = [max(10, int(round((t1 - t0) * 100 * _tt_silben(w) /
                                      float(sum(_tt_silben(x) for x in st) or 1))))
                    for w in st]
            diff = int(round((t1 - t0) * 100)) - sum(zent)
            if zent:
                zent[-1] = max(10, zent[-1] + diff)
            inhalt = "".join("{\\k%d}%s " % (zent[q], (w.upper() if caps else w))
                             for q, w in enumerate(st)).strip()
            vor = "{\\fad(60,60)\\fscx86\\fscy86\\t(0,120,\\fscx100\\fscy100)}"
            zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,%s%s"
                          % (_tt_zeit(t0), _tt_zeit(t1), vor, inhalt))
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(kopf + "\n".join(zeilen) + "\n")
    return ziel
import os

# ===== Untertitel-Zuordnung ueber die laengsten Pausen (TT_V3) =====
def _tt_teil_segmente(seg, a0, a1):
    """Sprechabschnitte innerhalb eines Zeitbereichs."""
    raus = []
    for s, e in seg:
        s2, e2 = max(s, a0), min(e, a1)
        if e2 - s2 > 0.05:
            raus.append((s2, e2))
    return raus or [(a0, a1)]


def baue_untertitel_ass(*a, **k):
    """Haeppchen-Untertitel, Saetze an den laengsten Sprechpausen verankert."""
    text = k.get("text") if "text" in k else (a[0] if len(a) > 0 else "")
    gesamt = k.get("gesamt_sek") if "gesamt_sek" in k else (a[1] if len(a) > 1 else 0)
    ziel = k.get("ziel") if "ziel" in k else (a[2] if len(a) > 2 else None)
    kanal = k.get("kanal") if "kanal" in k else (a[4] if len(a) > 4 else None)
    gesamt = float(gesamt or 0)
    if not ziel:
        return None

    # kanal darf Buchstabe oder Einstellungs-Paket sein
    e = {}
    if isinstance(kanal, dict):
        e = kanal
    elif kanal:
        try:
            _setze_format(kanal)
        except Exception:
            pass
        try:
            e = einstellungen.laden().get(kanal) or {}
        except Exception:
            e = {}

    try:
        fak = float(e.get("untertitel_groesse", 48) or 48) / 48.0
    except Exception:
        fak = 1.0
    fak = max(0.5, min(2.0, fak))
    caps = e.get("untertitel_caps", True)
    try:
        pro = int(e.get("untertitel_woerter", 3) or 3)
    except Exception:
        pro = 3
    pro = max(1, min(5, pro))

    hoch = HOEHE >= BREITE
    fs = max(20, int(BREITE * (0.088 if hoch else 0.052) * fak))
    rand = max(2, int(fs * 0.12))
    schatten = max(1, int(fs * 0.035))
    ml = int(BREITE * 0.08)
    mv = int(HOEHE * (0.30 if hoch else 0.09))
    kopf = _tt_ass_kopf(fs, rand, schatten, ml, mv, _tt_schrift())

    stuecke = _tt_stuecke(text, max_w=pro, max_z=15)
    if not stuecke:
        with open(ziel, "w", encoding="utf-8") as f:
            f.write(kopf)
        return ziel

    ton = _TT_TON if (_TT_TON and os.path.exists(_TT_TON)) else None
    if ton:
        d = _tt_dauer(ton)
        if d > 0.5:
            gesamt = d
    if gesamt <= 0:
        gesamt = max(1.0, len(stuecke) * 0.8)
    seg = _tt_sprachsegmente(ton, gesamt) if ton else [(0.0, gesamt)]

    saetze, akt = [], []
    for st in stuecke:
        akt.append(st)
        if st and st[-1][-1:] in ".!?":
            saetze.append(akt)
            akt = []
    if akt:
        saetze.append(akt)

    def gewicht(st):
        g = sum(_tt_silben(w) for w in st) + 0.35 * len(st)
        if st and st[-1][-1:] in ".!?":
            g += 0.45
        elif st and st[-1][-1:] in ",;:":
            g += 0.25
        return max(0.6, g)

    if len(seg) >= len(saetze):
        # die (n-1) laengsten Pausen sind die Satzgrenzen
        luecken = sorted(((seg[i + 1][0] - seg[i][1], i) for i in range(len(seg) - 1)),
                         reverse=True)
        schnitt = sorted(i for _, i in luecken[:max(0, len(saetze) - 1)])
        bereiche, start = [], 0
        for idx in schnitt + [len(seg) - 1]:
            bereiche.append((seg[start][0], seg[idx][1]))
            start = idx + 1
    else:
        # weniger Pausen als Saetze: anteilig aufteilen
        wand, sprechzeit = _tt_wand(seg)
        sg = [sum(gewicht(x) for x in s_) for s_ in saetze]
        ges = float(sum(sg)) or 1.0
        kanten, lauf = [seg[0][0]], 0.0
        for g in sg[:-1]:
            lauf += g
            kanten.append(wand(sprechzeit * lauf / ges))
        kanten.append(seg[-1][1])
        bereiche = [(kanten[i], max(kanten[i] + 0.3, kanten[i + 1]))
                    for i in range(len(kanten) - 1)]
    while len(bereiche) < len(saetze):
        bereiche.append((seg[-1][1] - 0.3, seg[-1][1]))

    zeilen = []
    for si, satz in enumerate(saetze):
        a0, a1 = bereiche[si]
        teil = _tt_teil_segmente(seg, a0, a1)
        twand, tzeit = _tt_wand(teil)
        sg = [gewicht(x) for x in satz]
        su = float(sum(sg)) or 1.0
        lauf = 0.0
        for j, st in enumerate(satz):
            t0 = twand(lauf)
            lauf += tzeit * sg[j] / su
            t1 = a1 if j == len(satz) - 1 else twand(lauf)
            if t1 - t0 < 0.28:
                t1 = min(a1, t0 + 0.28)
            if t1 <= t0:
                t1 = t0 + 0.28
            sil = float(sum(_tt_silben(x) for x in st) or 1)
            zent = [max(10, int(round((t1 - t0) * 100 * _tt_silben(w) / sil))) for w in st]
            diff = int(round((t1 - t0) * 100)) - sum(zent)
            if zent:
                zent[-1] = max(10, zent[-1] + diff)
            inhalt = "".join("{\\k%d}%s " % (zent[q], (w.upper() if caps else w))
                             for q, w in enumerate(st)).strip()
            vor = "{\\fad(60,60)\\fscx86\\fscy86\\t(0,120,\\fscx100\\fscy100)}"
            zeilen.append("Dialogue: 0,%s,%s,TT,,0,0,0,,%s%s"
                          % (_tt_zeit(t0), _tt_zeit(t1), vor, inhalt))
    with open(ziel, "w", encoding="utf-8") as f:
        f.write(kopf + "\n".join(zeilen) + "\n")
    return ziel

# ===== Bildpruefung (BP) =====
def _bp_hell(pfad):
    try:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(pfad),
                            "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
                            "-f", "null", "-"], capture_output=True, text=True, timeout=60)
        m = re.search(r"YAVG=([0-9.]+)", r.stderr or "")
        return float(m.group(1)) if m else 128.0
    except Exception:
        return 128.0


def _bp_ok(pfad):
    try:
        if not os.path.exists(pfad) or os.path.getsize(pfad) < 20000:
            return False
    except Exception:
        return False
    return _bp_hell(pfad) >= 22.0


def _bilder_pruefen(bilder):
    b = [str(x) for x in (bilder or [])]
    if not b:
        return bilder
    gut = [_bp_ok(x) for x in b]
    if all(gut):
        return bilder
    schlecht = [i for i, g in enumerate(gut) if not g]
    print("[Video] %d unbrauchbare Bilder: %s" % (len(schlecht),
          ", ".join(os.path.basename(b[i]) for i in schlecht)))
    if not any(gut):
        print("[Video] ALLE Bilder unbrauchbar")
        return bilder
    raus = list(b)
    for i in schlecht:
        j = next((k for k in range(i - 1, -1, -1) if gut[k]), None)
        if j is None:
            j = next((k for k in range(i + 1, len(b)) if gut[k]), None)
        raus[i] = b[j]
        print("[Video] %s ersetzt durch %s" % (os.path.basename(b[i]),
              os.path.basename(b[j])))
    return raus
