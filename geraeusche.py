# -*- coding: utf-8 -*-
"""Schnittgeraeusche fuer AiUniverse.

Erzeugt kurze Toene komplett per Code - kein Download, keine API, keine
Fremddateien. Die fertigen Toene liegen als WAV in /geraeusche und werden
nur einmal gebaut.
"""
import array
import math
import os
import random
import wave

BASIS = os.path.dirname(os.path.abspath(__file__))
ORDNER = os.path.join(BASIS, "geraeusche", "schnitt")
RATE = 48000

ARTEN = [["aus", "kein Geraeusch"],
         ["whoosh", "Whoosh, weich"],
         ["swoosh", "Swoosh, hell"],
         ["pop", "Pop, rund"],
         ["klick", "Klick, trocken"]]
NAMEN = [a[0] for a in ARTEN]


# ---------- Bausteine ----------
def _bandrauschen(n, tief_hz, hoch_hz, saat):
    """Rauschen zwischen zwei Frequenzen, beide duerfen sich bewegen."""
    rnd = random.Random(saat)
    tief_y, hoch_y = 0.0, 0.0
    raus = [0.0] * n
    for i in range(n):
        t = i / float(max(1, n - 1))
        fh = hoch_hz(t) if callable(hoch_hz) else hoch_hz
        ft = tief_hz(t) if callable(tief_hz) else tief_hz
        ah = 1.0 - math.exp(-2.0 * math.pi * max(40.0, fh) / RATE)
        at = 1.0 - math.exp(-2.0 * math.pi * max(20.0, ft) / RATE)
        x = rnd.uniform(-1.0, 1.0)
        hoch_y += ah * (x - hoch_y)
        tief_y += at * (x - tief_y)
        raus[i] = hoch_y - tief_y
    return raus


def _whoosh(dauer=0.34):
    n = int(RATE * dauer)
    roh = _bandrauschen(n, lambda t: 180 + 700 * math.sin(math.pi * t),
                        lambda t: 900 + 4200 * math.sin(math.pi * t), 11)
    return [v * (math.sin(math.pi * (i / float(max(1, n - 1)))) ** 1.7)
            for i, v in enumerate(roh)]


def _swoosh(dauer=0.24):
    n = int(RATE * dauer)
    roh = _bandrauschen(n, lambda t: 600 + 1800 * t,
                        lambda t: 2600 + 6000 * t, 23)
    raus = []
    for i, v in enumerate(roh):
        t = i / float(max(1, n - 1))
        raus.append(v * (math.sin(math.pi * t) ** 1.2) * math.exp(-1.2 * t))
    return raus


def _pop(dauer=0.12):
    n = int(RATE * dauer)
    raus, ph = [], 0.0
    for i in range(n):
        t = i / float(RATE)
        f = 95.0 + 430.0 * math.exp(-30.0 * t)
        ph += 2.0 * math.pi * f / RATE
        raus.append(math.sin(ph) * math.exp(-28.0 * t))
    return raus


def _klick(dauer=0.045):
    n = int(RATE * dauer)
    rnd = random.Random(5)
    vor, raus = 0.0, []
    for i in range(n):
        t = i / float(RATE)
        x = rnd.uniform(-1.0, 1.0)
        hell = x - vor          # einfache Hoehenanhebung
        vor = x
        raus.append(hell * math.exp(-150.0 * t))
    return raus


BAUER = {"whoosh": _whoosh, "swoosh": _swoosh, "pop": _pop, "klick": _klick}


# ---------- WAV ----------
def _normiert(werte, spitze=0.82):
    groesst = max((abs(v) for v in werte), default=0.0)
    if groesst <= 1e-9:
        return werte
    f = spitze / groesst
    return [v * f for v in werte]


def _als_ganz(werte):
    aus = array.array("h")
    for v in werte:
        aus.append(max(-32767, min(32767, int(v * 32767.0))))
    return aus


def _schreibe(pfad, werte):
    w = wave.open(pfad, "wb")
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(_als_ganz(werte).tobytes())
    finally:
        w.close()


def _lies(pfad):
    """WAV als int16-Array, notfalls auf Mono gemischt."""
    w = wave.open(pfad, "rb")
    try:
        kanaele = w.getnchannels()
        breite = w.getsampwidth()
        roh = w.readframes(w.getnframes())
    finally:
        w.close()
    if breite != 2:
        return array.array("h")
    a = array.array("h")
    a.frombytes(roh)
    if kanaele <= 1:
        return a
    aus = array.array("h")
    for i in range(0, len(a) - kanaele + 1, kanaele):
        aus.append(int(sum(a[i:i + kanaele]) / float(kanaele)))
    return aus


def datei(art):
    """Pfad zum Geraeusch, baut es beim ersten Mal. None heisst: keins."""
    art = (art or "").strip().lower()
    if art in ("", "aus", "nein", "kein"):
        return None
    if art not in BAUER:
        art = "whoosh"
    try:
        os.makedirs(ORDNER, exist_ok=True)
    except Exception:
        return None
    p = os.path.join(ORDNER, art + ".wav")
    if os.path.exists(p) and os.path.getsize(p) > 400:
        return p
    try:
        _schreibe(p, _normiert(BAUER[art]()))
    except Exception as e:
        print("[Geraeusch] konnte %s nicht bauen: %s" % (art, e))
        return None
    return p


def alle_bauen():
    """Legt alle Geraeusche an, damit sie beim Rendern schon da sind."""
    return [a for a in BAUER if datei(a)]


# ---------- Spur ----------
def spur(ziel, gesamt, zeiten, art="whoosh", pegel=0.35):
    """Baut eine Tonspur der Laenge gesamt mit je einem Geraeusch pro Zeit.

    Wird der Reihe nach geschrieben, nie als ganzer Puffer im Speicher -
    wichtig auf dem kleinen Server.
    """
    quelle = datei(art)
    if not quelle or gesamt <= 0.05:
        return None
    ton = _lies(quelle)
    if not len(ton):
        return None
    ende = int(gesamt * RATE)
    punkte = sorted({int(max(0.0, t) * RATE) for t in (zeiten or []) if 0.0 <= t < gesamt})
    if not punkte:
        return None
    faktor = max(0.0, min(2.0, float(pegel)))
    leise = array.array("h", [0]) * 4096
    w = wave.open(str(ziel), "wb")
    try:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        pos = 0

        def stille(bis):
            nonlocal pos
            rest = bis - pos
            while rest > 0:
                k = min(rest, 4096)
                w.writeframes(leise[:k].tobytes())
                pos += k
                rest -= k

        for p in punkte:
            if p < pos or p >= ende:
                continue
            stille(p)
            stueck = array.array("h", [max(-32767, min(32767, int(v * faktor))) for v in ton])
            platz = ende - pos
            if platz <= 0:
                break
            if len(stueck) > platz:
                stueck = stueck[:platz]
            w.writeframes(stueck.tobytes())
            pos += len(stueck)
        stille(ende)
    finally:
        w.close()
    return str(ziel)
