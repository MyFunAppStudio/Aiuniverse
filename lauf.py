"""Startet einen Lauf fuer einen beliebigen Kanal: python3 lauf.py <key> [thema]"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config, einstellungen, erstelle_video


def kanal_paket(key):
    basis = getattr(config, "KANAL_A", None) if key == "a" else getattr(config, "KANAL_B", None)
    if not isinstance(basis, dict):
        basis = getattr(config, "KANAL_B", None) or getattr(config, "KANAL_A", None) or {}
    kd = dict(basis)
    kd.update(einstellungen.laden().get(key) or {})
    kd["id"] = key
    kd.setdefault("name", key)
    kd.setdefault("emoji", "\U0001F3AC")
    return kd


if __name__ == "__main__":
    k = sys.argv[1] if len(sys.argv) > 1 else "b"
    thema = sys.argv[2] if len(sys.argv) > 2 else None
    erstelle_video.erstelle(kanal_paket(k), thema)
