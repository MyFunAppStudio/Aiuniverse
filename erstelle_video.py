"""Nachbau der Struktur von Stefans erstelle_video.py."""
from datetime import datetime
import config, medien, musik, video_bauen, telegram_sender, text_generator


def erstelle(kanal, eigenes_thema=None):
    print("--- AUTOMATISCH (hier nur Platzhalter) ---")
    return None


# ---------- Eigene Szenen (Patch S3) ----------
import os
import szenen as _sz
import szenen_video as _szv

_sz_erstelle_alt = erstelle


def _sz_titel(kanal, daten):
    for s in daten.get("szenen", []):
        t = (s.get("text") or "").strip()
        if t:
            return t[:70]
    return (kanal.get("name") or "Video")


def _sz_erstelle(kanal, eigenes_thema=None):
    from datetime import datetime
    import json as _j
    kid = kanal.get("id") or kanal.get("_key") or "x"
    ordner = config.ORDNER_VIDEOS / ("%s_%s" % (kid, datetime.now().strftime("%Y%m%d_%H%M%S")))
    ordner.mkdir(parents=True, exist_ok=True)
    print("--- EIGENE SZENEN ---")
    daten = _sz.fuer_anzeige(kanal)
    if not daten.get("szenen"):
        print("Keine Szenen angelegt - im Dashboard unter Prompt Bilder hochladen")
        return None
    video = _szv.baue(kanal, ordner / "video.mp4", ordner)
    if not video:
        print("Video-Bau fehlgeschlagen")
        return None
    titel = _sz_titel(kanal, daten)
    erste = None
    for s in daten["szenen"]:
        if s.get("typ") == "bild":
            erste = _sz.datei_pfad(kanal, s["datei"])
            break
    if erste and os.path.exists(erste):
        try:
            video_bauen.baue_thumbnail(kanal, erste, titel, ordner / "thumbnail.jpg")
        except Exception as e:
            print("Thumbnail nicht moeglich:", e)
    try:
        paket = {"titel": titel, "skript": " ".join((s.get("text") or "")
                 for s in daten["szenen"] if s.get("text")),
                 "modus": "szenen", "szenen": len(daten["szenen"])}
        with open(ordner / "paket.json", "w", encoding="utf-8") as f:
            _j.dump(paket, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("paket.json:", e)
    try:
        telegram_sender.sende_video(kanal, str(video), titel)
    except Exception as e:
        print("Telegram:", e)
    print("FERTIG:", video)
    return str(video)


def erstelle(kanal, eigenes_thema=None):
    if (kanal or {}).get("modus") in ("szenen", "geschichte"):
        return _sz_erstelle(kanal, eigenes_thema)
    return _sz_erstelle_alt(kanal, eigenes_thema)
