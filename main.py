# ============================================
# Hauptsteuerung: laeuft 24/7, macht Videos
# nach Zeitplan, wiederholt bei API-Ausfall
# ============================================
import time
import json
from datetime import datetime, date
from pathlib import Path
import config
import api_check
import erstelle_video
import telegram_sender

STATUS_DATEI = config.ORDNER_LOGS / "status.json"


def lade_status():
    """Was wurde heute schon gemacht?"""
    if STATUS_DATEI.exists():
        try:
            return json.loads(STATUS_DATEI.read_text())
        except Exception:
            pass
    return {}


def speichere_status(status):
    STATUS_DATEI.parent.mkdir(parents=True, exist_ok=True)
    STATUS_DATEI.write_text(json.dumps(status, indent=2))


def heute_erledigt(kanal):
    """Wieviele Videos hat dieser Kanal heute schon?"""
    status = lade_status()
    heute = date.today().isoformat()
    return status.get(heute, {}).get(kanal["id"], 0)


def merke_erledigt(kanal):
    status = lade_status()
    heute = date.today().isoformat()
    status.setdefault(heute, {})
    status[heute][kanal["id"]] = status[heute].get(kanal["id"], 0) + 1
    # alte Tage aufraeumen (nur 7 Tage behalten)
    tage = sorted(status.keys())
    for alt in tage[:-7]:
        del status[alt]
    speichere_status(status)


def ist_zeit(kanal):
    """Ist die Uhrzeit erreicht?"""
    jetzt = datetime.now().strftime("%H:%M")
    return jetzt >= kanal["uhrzeit"]


def versuche_video(kanal):
    """Versucht ein Video zu machen. Wartet bei fehlenden APIs."""
    versuche = 0
    while versuche < config.MAX_VERSUCHE:
        ok, fehlt = api_check.pruefe_kanal(kanal)
        if ok:
            try:
                return erstelle_video.erstelle(kanal)
            except Exception as fehler:
                print(f"[Fehler] {kanal['name']}: {fehler}")
                telegram_sender.melde_problem(kanal, f"Fehler beim Video: {fehler}")
                return None

        versuche += 1
        print(f"[Warte] {kanal['name']}: {', '.join(fehlt)} - "
              f"Versuch {versuche}/{config.MAX_VERSUCHE}, "
              f"neuer Check in {config.CHECK_INTERVALL_MIN} Min")
        time.sleep(config.CHECK_INTERVALL_MIN * 60)

    telegram_sender.melde_problem(
        kanal,
        f"Heute kein Video - APIs waren {config.MAX_VERSUCHE} Versuche lang nicht erreichbar."
    )
    return None


def durchlauf():
    """Ein Durchlauf: prueft beide Kanaele."""
    for kanal in config.KANAELE:
        soll = kanal["videos_pro_tag"]
        ist = heute_erledigt(kanal)

        if ist >= soll:
            continue
        if not ist_zeit(kanal):
            continue

        print(f"\n{'='*50}")
        print(f"{kanal['emoji']} {kanal['name']}: Video {ist+1}/{soll}")
        print(f"{'='*50}")

        ergebnis = versuche_video(kanal)
        if ergebnis:
            merke_erledigt(kanal)


def main():
    print("=" * 50)
    print("AIUNIVERSE laeuft")
    print(f"Testmodus: {config.TESTMODUS}")
    for k in config.KANAELE:
        print(f"  {k['emoji']} {k['name']} um {k['uhrzeit']} "
              f"({k['videos_pro_tag']}x taeglich)")
    print("=" * 50)

    while True:
        try:
            durchlauf()
        except Exception as fehler:
            print(f"[Hauptfehler] {fehler}")
        time.sleep(config.CHECK_INTERVALL_MIN * 60)


if __name__ == "__main__":
    main()
