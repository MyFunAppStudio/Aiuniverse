# -*- coding: utf-8 -*-
"""Einblendungen (Folgen, Like, Abo) als Grafik - komplett per Code gezeichnet.

Keine Downloads, keine API. Die fertigen PNGs liegen mit Transparenz in
/einblendungen und werden nur neu gebaut, wenn sich etwas aendert.
"""
import hashlib
import os
import re

BASIS = os.path.dirname(os.path.abspath(__file__))
ORDNER = os.path.join(BASIS, "einblendungen")
S = 4
SCHRIFTEN = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
             "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"]

ARTEN = [["folgen", "Folgen (Plus)"], ["like", "Like (Herz)"],
         ["daumen", "Daumen hoch"], ["abo", "Abo (Glocke)"], ["nur_text", "nur Text"]]
ART_NAMEN = [a[0] for a in ARTEN]
PLAETZE = [["links_unten", "links unten"], ["mitte_unten", "mitte unten"],
           ["rechts_unten", "rechts unten"], ["links_oben", "links oben"],
           ["mitte_oben", "mitte oben"], ["rechts_oben", "rechts oben"]]
PLATZ_NAMEN = [p[0] for p in PLAETZE]


def _schrift(px):
    from PIL import ImageFont
    for p in SCHRIFTEN:
        if os.path.exists(p):
            return ImageFont.truetype(p, px)
    return ImageFont.load_default()


def _rr(d, b, r, f):
    d.rounded_rectangle([v * S for v in b], radius=r * S, fill=f)


def _el(d, b, f):
    d.ellipse([v * S for v in b], fill=f)


def _pg(d, p, f):
    d.polygon([(x * S, y * S) for x, y in p], fill=f)


def _herz(d, cx, cy, r, f):
    _el(d, (cx - r, cy - r * 0.82, cx, cy + r * 0.18), f)
    _el(d, (cx, cy - r * 0.82, cx + r, cy + r * 0.18), f)
    _pg(d, [(cx - r * 0.97, cy - r * 0.26), (cx + r * 0.97, cy - r * 0.26),
            (cx, cy + r * 0.92)], f)


def _daumen(d, cx, cy, r, f):
    _rr(d, (cx - r * 0.95, cy - r * 0.02, cx - r * 0.45, cy + r * 0.88), r * 0.14, f)
    _rr(d, (cx - r * 0.32, cy - r * 0.18, cx + r * 0.92, cy + r * 0.88), r * 0.26, f)
    _rr(d, (cx - r * 0.3, cy - r * 0.95, cx + r * 0.12, cy - r * 0.05), r * 0.2, f)


def _glocke(d, cx, cy, r, f):
    _el(d, (cx - r * 0.16, cy - r * 0.98, cx + r * 0.16, cy - r * 0.66), f)
    d.pieslice([(cx - r * 0.72) * S, (cy - r * 0.86) * S,
                (cx + r * 0.72) * S, (cy + r * 0.44) * S], 180, 360, fill=f)
    _rr(d, (cx - r * 0.72, cy - r * 0.22, cx + r * 0.72, cy + r * 0.3), r * 0.08, f)
    _rr(d, (cx - r * 0.95, cy + r * 0.3, cx + r * 0.95, cy + r * 0.52), r * 0.11, f)
    _el(d, (cx - r * 0.22, cy + r * 0.54, cx + r * 0.22, cy + r * 0.98), f)


def _plus(d, cx, cy, r, f):
    _rr(d, (cx - r * 0.9, cy - r * 0.22, cx + r * 0.9, cy + r * 0.22), r * 0.22, f)
    _rr(d, (cx - r * 0.22, cy - r * 0.9, cx + r * 0.22, cy + r * 0.9), r * 0.22, f)


ICONS = {"folgen": _plus, "like": _herz, "daumen": _daumen, "abo": _glocke}


def _farbe(wert, standard=(255, 106, 26, 255)):
    """#RRGGBB oder RRGGBB zu RGBA."""
    s = re.sub(r"[^0-9A-Fa-f]", "", str(wert or ""))
    if len(s) != 6:
        return standard
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), 255)


def _hell(rgb):
    return (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]) / 255.0


def bau(art, text, hoehe, farbe=(255, 106, 26, 255)):
    """Pille mit Icon und Text. Gibt ein RGBA-Bild zurueck."""
    from PIL import Image, ImageDraw
    textfarbe = (20, 11, 4, 255) if _hell(farbe) > 0.5 else (255, 255, 255, 255)
    h = max(28, int(hoehe))
    pad = h * 0.36
    fs = max(10, int(h * 0.42))
    f = _schrift(fs * S)
    text = (text or "").strip()
    mess = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    tw = (mess.textlength(text, font=f) / float(S)) if text else 0.0
    hat = art in ICONS
    ir = h * 0.24
    w = pad + (ir * 2 + pad * 0.5 if hat else 0) + tw + pad
    im = Image.new("RGBA", (int(w + 4) * S, int(h + 4) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    _rr(d, (3, 4, w + 1, h + 2), h / 2.0, (0, 0, 0, 80))
    _rr(d, (1, 1, w - 1, h), h / 2.0, farbe)
    mitte = (h + 1) / 2.0
    x = 1 + pad
    if hat:
        ICONS[art](d, x + ir, mitte, ir, textfarbe)
        x += ir * 2 + pad * 0.5
    if text:
        d.text((x * S, (mitte - fs * 0.63) * S), text, font=f, fill=textfarbe)
    return im.resize((int(w + 4), int(h + 4)), Image.LANCZOS)


def datei(art, text, hoehe, farbe_hex=""):
    """Pfad zur fertigen PNG, baut sie beim ersten Mal. None bei Problemen."""
    art = (art or "folgen").strip().lower()
    if art not in ART_NAMEN:
        art = "folgen"
    rgba = _farbe(farbe_hex)
    schl = "%s|%s|%d|%s" % (art, text or "", int(hoehe), rgba)
    name = "eb_%s.png" % hashlib.md5(schl.encode("utf-8")).hexdigest()[:14]
    p = os.path.join(ORDNER, name)
    if os.path.exists(p) and os.path.getsize(p) > 200:
        return p
    try:
        os.makedirs(ORDNER, exist_ok=True)
        bau(art, text, hoehe, rgba).save(p)
    except Exception as e:
        print("[Einblendung] konnte nicht gebaut werden:", e)
        return None
    return p


def zeiten(kanal, gesamt, dauer=2.6):
    """Wann die Einblendung zu sehen ist, als Liste von (start, ende)."""
    raus = []
    d = max(0.8, min(8.0, float(dauer or 2.6)))
    if gesamt < 2.0:
        return raus
    if kanal.get("cta_anfang"):
        raus.append((0.8, min(0.8 + d, gesamt - 0.2)))
    if kanal.get("cta_mitte"):
        m = max(0.0, gesamt / 2.0 - d / 2.0)
        raus.append((m, min(m + d, gesamt - 0.2)))
    if kanal.get("cta_ende") is not False and kanal.get("cta_ende") is not None:
        if kanal.get("cta_ende"):
            e = max(0.0, gesamt - d - 0.4)
            raus.append((e, max(e + 0.5, gesamt - 0.1)))
    # Ueberschneidungen zusammenfassen
    raus.sort()
    sauber = []
    for a, b in raus:
        if b <= a + 0.3:
            continue
        if sauber and a <= sauber[-1][1] + 0.2:
            sauber[-1] = (sauber[-1][0], max(sauber[-1][1], b))
        else:
            sauber.append((a, b))
    return sauber
