# ============================================
# Erstellt EIN komplettes Video von A bis Z
# ============================================
import sys
import json
from datetime import datetime
from pathlib import Path
import config
import api_check
import text_generator
import medien
import video_bauen
import musik
import telegram_sender


def erstelle(kanal, eigenes_thema=None):
    """Baut ein komplettes Video mit allen Texten."""
    start = datetime.now()
    print("=" * 50)
    print(f"{kanal['emoji']} {kanal['name']} - neues Video")
    print("=" * 50)

    # 1. APIs pruefen
    ok, fehlt = api_check.pruefe_kanal(kanal)
    if not ok:
        print(f"ABBRUCH - fehlende APIs: {', '.join(fehlt)}")
        return None

    # 2. Arbeitsordner
    zeitstempel = start.strftime("%Y-%m-%d_%H-%M")
    ordner = config.ORDNER_VIDEOS / f"{kanal['id']}_{zeitstempel}"
    ordner.mkdir(parents=True, exist_ok=True)
    print(f"Ordner: {ordner.name}\n")

    # 3. Texte von Claude
    print("--- SCHRITT 1: Texte ---")
    paket = text_generator.erzeuge_paket(kanal, eigenes_thema)
    print(f"Titel: {paket['titel']}\n")

    # 4. Bilder
    print("--- SCHRITT 2: Bilder ---")
    bilder = medien.erzeuge_bilder(kanal, paket["bild_prompts"], ordner)
    print(f"{len(bilder)} Bilder fertig\n")

    # 5. Stimme
    print("--- SCHRITT 3: Stimme ---")
    ton = medien.erzeuge_stimme(kanal, paket["skript"], ordner / "stimme.mp3")
    print("Stimme fertig\n")

    # 5b. Musik druntermischen
    print("--- Musik und Ton ---")
    dauer = musik._laenge(ton)
    stueck = musik.hole_musik(kanal, dauer, ordner)
    amb = musik.hole_ambience(kanal)
    ton = musik.mische(kanal, ton, stueck, ordner / "ton_fertig.m4a", dauer, amb)
    print()

    # 6. Video bauen
    print("--- SCHRITT 4: Video ---")
    video = video_bauen.baue_video(kanal, bilder, ton, ordner / "video.mp4",
                                   skript=paket.get("skript", ""),
                                   szenen=paket.get("szenen"))
    if not video:
        print("Video-Bau fehlgeschlagen")
        return None
    print()

    # 7. Texte speichern
    if bilder:
        video_bauen.baue_thumbnail(kanal, bilder[0],
                                   paket.get("titel", ""),
                                   ordner / "thumbnail.jpg")
        print()

    print("--- SCHRITT 5: Texte speichern ---")
    texte = f"""=== {kanal['name']} ===
Erstellt: {start.strftime('%d.%m.%Y %H:%M')}

--- TITEL ---
{paket['titel']}

--- YOUTUBE BESCHREIBUNG ---
{paket['beschreibung_youtube']}

--- TIKTOK ---
{paket['beschreibung_tiktok']}

--- INSTAGRAM ---
{paket['beschreibung_instagram']}

--- HASHTAGS ---
{' '.join(paket['hashtags'])}

--- PINNED COMMENT ---
{paket['pinned_comment']}

--- HINWEIS ---
Beim Hochladen KI-Kennzeichnung setzen!
YouTube: "Altered or synthetic content"
TikTok: AIGC-Label
Instagram: "Made with AI"
"""
    (ordner / "texte.txt").write_text(texte, encoding="utf-8")
    (ordner / "paket.json").write_text(json.dumps(paket, indent=2, ensure_ascii=False), encoding="utf-8")
    print("texte.txt gespeichert\n")

    # 8. Telegram
    print("--- SCHRITT 6: Telegram ---")
    telegram_sender.sende_video(kanal, video, f"{paket['titel']}\n\n{' '.join(paket['hashtags'])}")

    dauer = (datetime.now() - start).seconds
    print("\n" + "=" * 50)
    print(f"FERTIG in {dauer}s")
    print(f"Video:  {video}")
    print(f"Texte:  {ordner / 'texte.txt'}")
    print("=" * 50)
    return video


if __name__ == "__main__":
    welcher = sys.argv[1] if len(sys.argv) > 1 else "a"
    thema = sys.argv[2] if len(sys.argv) > 2 else None
    kanal = config.KANAL_A if welcher == "a" else config.KANAL_B
    erstelle(kanal, thema)


# ===== Geschwisterkanaele laufen mit (Patch T3) =====
import glob as _gs_glob
import json as _gs_json
import os as _gs_os
import einstellungen as _gs_e
import kanaele as _gs_k
import medien as _gs_m

_gs_erstelle_alt = erstelle


def _gs_neuester(kid):
    try:
        muster = str(config.ORDNER_VIDEOS / (kid + "_*"))
        ordner = sorted(_gs_glob.glob(muster))
        return ordner[-1] if ordner else None
    except Exception:
        return None


def _gs_thema(ordner):
    try:
        with open(_gs_os.path.join(ordner, "paket.json"), encoding="utf-8") as f:
            return (_gs_json.load(f).get("titel") or "").strip() or None
    except Exception:
        return None


def erstelle(kanal, eigenes_thema=None):
    erg = _gs_erstelle_alt(kanal, eigenes_thema)
    try:
        eltern = kanal.get("id") or kanal.get("_key")
        kinder = _gs_k.kinder(eltern)
        if not kinder:
            return erg
        ordner = _gs_neuester(eltern)
        bilder = sorted(_gs_glob.glob(_gs_os.path.join(ordner or "", "bild_*.jpg")))
        thema = _gs_thema(ordner) if ordner else None
        if not bilder:
            print("[Geschwister] keine Bilder zum Weiterverwenden - uebersprungen")
            return erg
        daten = _gs_e.laden()
        for kid in kinder:
            print("[Geschwister] %s - gleiche Bilder, eigene Sprache" % kid)
            kd = dict(kanal)
            kd.update(daten.get(kid) or {})
            kd["id"] = kid
            alt = _gs_m.erzeuge_bilder
            _gs_m.erzeuge_bilder = lambda k, p, o, _b=list(bilder): list(_b)
            try:
                _gs_erstelle_alt(kd, thema)
            finally:
                _gs_m.erzeuge_bilder = alt
    except Exception as ex:
        print("[Geschwister] uebersprungen: %s" % ex)
    return erg


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
