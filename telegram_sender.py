# ============================================
# Telegram: sendet fertige Videos + Texte
# ============================================
import json
import urllib.request
import urllib.parse
from pathlib import Path
import config

MAX_MB = 50


def _post(token, methode, daten):
    """Schickt eine Anfrage an Telegram."""
    url = f"https://api.telegram.org/bot{token}/{methode}"
    payload = urllib.parse.urlencode(daten).encode()
    try:
        with urllib.request.urlopen(url, payload, timeout=30) as antwort:
            return json.loads(antwort.read().decode())
    except Exception as fehler:
        return {"ok": False, "fehler": str(fehler)}


def sende_text(kanal, text):
    """Schickt eine Nachricht."""
    token = kanal.get("telegram_token", "")
    chat = kanal.get("telegram_chat", "")
    if not token or not chat:
        print(f"[Telegram] {kanal['name']}: kein Token/Chat -> uebersprungen")
        print(f"[Telegram] Waere gesendet: {text[:120]}")
        return False
    ergebnis = _post(token, "sendMessage", {"chat_id": chat, "text": text})
    if ergebnis.get("ok"):
        print(f"[Telegram] {kanal['name']}: Nachricht gesendet")
        return True
    print(f"[Telegram] {kanal['name']}: Fehler -> {ergebnis}")
    return False


def sende_video(kanal, video_pfad, beschreibung=""):
    """Schickt ein Video. Zu gross -> nur Hinweis."""
    token = kanal.get("telegram_token", "")
    chat = kanal.get("telegram_chat", "")
    pfad = Path(video_pfad)

    if not token or not chat:
        print(f"[Telegram] {kanal['name']}: kein Token/Chat -> uebersprungen")
        return False

    if not pfad.exists():
        print(f"[Telegram] Datei nicht gefunden: {pfad}")
        return False

    groesse_mb = pfad.stat().st_size / (1024 * 1024)
    if groesse_mb > MAX_MB:
        hinweis = (
            f"{kanal['emoji']} Video fertig, aber zu gross fuer Telegram "
            f"({groesse_mb:.1f} MB).\n\nLiegt auf dem Server:\n{pfad}\n\n{beschreibung}"
        )
        return _notfall(kanal, pfad, beschreibung, groesse_mb)

    print(f"[Telegram] {kanal['name']}: sende Video ({groesse_mb:.1f} MB)...")
    ergebnis = _post_datei(token, "sendVideo", {
        "chat_id": chat, "caption": _bildunterschrift(kanal, pfad, beschreibung),
        "supports_streaming": "true"}, "video", pfad, "video/mp4")
    if ergebnis.get("ok"):
        print(f"[Telegram] {kanal['name']}: Video gesendet")
        return True
    print(f"[Telegram] Video-Upload fehlgeschlagen -> {ergebnis}")
    return _notfall(kanal, pfad, beschreibung, groesse_mb)


def melde_problem(kanal, problem):
    """Meldet ein Problem."""
    return sende_text(kanal, f"WARNUNG {kanal['emoji']} {kanal['name']}\n\n{problem}")


if __name__ == "__main__":
    print("=" * 45)
    print("TELEGRAM TEST")
    print("=" * 45)
    for k in config.KANAELE:
        token = k.get("telegram_token", "")
        status = "eingetragen" if token else "noch leer"
        print(f"{k['emoji']} {k['name']}: Token {status}")
        sende_text(k, f"Test von {k['name']}")
    print("=" * 45)


# ---------- Datei-Upload (Patch S6) ----------
import os as _os
import time as _time


def _bildunterschrift(kanal, pfad, beschreibung):
    text = "%s %s" % (kanal.get("emoji", ""), (beschreibung or "Video fertig").strip())
    link = _link(kanal, pfad)
    if link:
        text += "\n\n" + link
    return text[:1024]


def _link(kanal, pfad):
    basis = (kanal.get("dashboard_adresse") or "").strip().rstrip("/")
    if not basis:
        return ""
    return "%s/laden/%s" % (basis, Path(pfad).parent.name)


def _post_datei(token, methode, felder, feldname, pfad, mime):
    """Schickt eine Datei als multipart an Telegram."""
    grenze = "AiUniverse%d" % int(_time.time() * 1000)
    teile = []
    for k, v in felder.items():
        teile.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (grenze, k, v)).encode("utf-8"))
    teile.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
                  "Content-Type: %s\r\n\r\n"
                  % (grenze, feldname, _os.path.basename(str(pfad)), mime)).encode("utf-8"))
    try:
        with open(str(pfad), "rb") as f:
            teile.append(f.read())
    except Exception as fehler:
        return {"ok": False, "fehler": str(fehler)}
    teile.append(("\r\n--%s--\r\n" % grenze).encode("utf-8"))
    koerper = b"".join(teile)
    url = "https://api.telegram.org/bot%s/%s" % (token, methode)
    anfrage = urllib.request.Request(url, koerper, {
        "Content-Type": "multipart/form-data; boundary=%s" % grenze,
        "Content-Length": str(len(koerper))})
    try:
        with urllib.request.urlopen(anfrage, timeout=300) as antwort:
            return json.loads(antwort.read().decode())
    except Exception as fehler:
        return {"ok": False, "fehler": str(fehler)}


def _notfall(kanal, pfad, beschreibung, groesse_mb):
    """Zu gross oder Upload gescheitert: Vorschaubild plus Zeile zum Herunterladen."""
    token = kanal.get("telegram_token", "")
    chat = kanal.get("telegram_chat", "")
    text = _bildunterschrift(kanal, pfad, beschreibung)
    vorschau = Path(pfad).parent / "thumbnail.jpg"
    if vorschau.exists() and token and chat:
        e = _post_datei(token, "sendPhoto", {"chat_id": chat, "caption": text},
                        "photo", str(vorschau), "image/jpeg")
        if e.get("ok"):
            print("[Telegram] Vorschaubild gesendet (%.1f MB Video)" % groesse_mb)
            return True
    return sende_text(kanal, text + ("\n\n%.1f MB" % groesse_mb))
