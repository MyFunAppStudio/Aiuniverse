import re, subprocess
def erzeuge_stimme(kanal, text, ziel, stimme_id=None):
    """Nachbau: erzeugt Ton in der Laenge, die echtes Sprechen braucht."""
    worte = [w for w in re.split(r"\s+", (text or "").strip()) if w]
    dauer = max(0.8, len(worte) / 2.6 + 0.6)
    teile = []
    for i, w in enumerate(worte):
        f = 220 + (len(w) * 23) % 180
        teile.append("sine=frequency=%d:duration=%.3f" % (f, dauer / len(worte) * 0.82))
        teile.append("anullsrc=r=44100:cl=mono:d=%.3f" % (dauer / len(worte) * 0.18))
    graph = "".join("[%d:a]" % i for i in range(len(teile))) + "concat=n=%d:v=0:a=1[o]" % len(teile)
    befehl = ["ffmpeg", "-y", "-loglevel", "error"]
    for t in teile:
        befehl += ["-f", "lavfi", "-i", t]
    befehl += ["-filter_complex", graph, "-map", "[o]", "-ar", "44100", "-ac", "1", str(ziel)]
    subprocess.run(befehl, capture_output=True)
    return str(ziel)
