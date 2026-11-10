# ============================================
# API-Check: prueft ob alle noetigen Keys da sind
# ============================================
import config
import einstellungen

def pruefe_kanal(kanal):
    """Prueft ob alle noetigen Keys fuer diesen Kanal da sind.
    Gibt zurueck: (alles_ok, liste_der_fehlenden)"""
    if config.TESTMODUS:
        return True, []

    fehlt = []
    noetig = [("text", "Text/Skript"), ("stimme", "Stimme"), ("bilder", "Bilder")]
    for slot, bez in noetig:
        api = einstellungen.aktive_api(kanal, slot)
        if not api:
            fehlt.append(f"{bez}: keine AI aktiv")
        elif not api.get("key"):
            fehlt.append(f"{bez}: Key fehlt ({api.get('name','?')})")

    return len(fehlt) == 0, fehlt


def bericht(kanal):
    """Gibt einen lesbaren Text zurueck."""
    ok, fehlt = pruefe_kanal(kanal)
    if config.TESTMODUS:
        return True, f"{kanal['emoji']} {kanal['name']}: TESTMODUS (keine echten APIs noetig)"
    if ok:
        return True, f"{kanal['emoji']} {kanal['name']}: alle APIs bereit"
    return False, f"{kanal['emoji']} {kanal['name']}: FEHLT -> " + ", ".join(fehlt)


if __name__ == "__main__":
    print("=" * 45)
    print("API-CHECK")
    print("=" * 45)
    if config.TESTMODUS:
        print("TESTMODUS ist AN - es werden keine echten APIs gebraucht.")
        print("-" * 45)
    for k in config.KANAELE:
        ok, text = bericht(k)
        print(text)
    print("=" * 45)
