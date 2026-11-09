# Nachbau der echten Bausteine aus Stefans video_bauen.py
import re, subprocess
BREITE, HOEHE, FPS = 1080, 1920, 30
_TT_SCHRIFT = None

def _setze_format(kanal):
    global BREITE, HOEHE
    f = (kanal or {}).get("format", "9:16")
    BREITE, HOEHE = {"9:16": (1080, 1920), "16:9": (1920, 1080),
                     "1:1": (1080, 1080), "4:5": (1080, 1350)}.get(f, (1080, 1920))

def _tt_schrift():
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
    worte = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    raus, akt = [], []
    for w in worte:
        probe = akt + [w]
        if akt and (len(probe) > max_w or len(" ".join(probe)) > max_z):
            raus.append(akt)
            akt = [w]
        else:
            akt = probe
        if akt and w[-1:] in ".!?:;,":
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
        "Effect, Text\n" % (BREITE, HOEHE, schrift, fs, rand, schatten, ml, ml, mv))

def baue_thumbnail(kanal, bild, titel, ziel):
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(bild),
                    "-vf", "scale=640:-2", str(ziel)], capture_output=True)
    print("[Thumbnail]", titel, "->", ziel)
    return str(ziel)
