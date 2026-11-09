# -*- coding: utf-8 -*-
"""Schluessel finden, ohne ihn noch einmal eintippen zu muessen.

Ein neuer Modelleintrag beim gleichen Anbieter braucht denselben Schluessel
wie ein Eintrag, der schon da ist. Dieses Modul sucht ihn in dieser
Reihenfolge: der Eintrag selbst, ein anderer Eintrag beim gleichen Anbieter,
die .env-Datei, die Umgebung. Es gibt den Schluessel nur an den Code weiter,
nie an die Oberflaeche.
"""
import os

BASIS = os.path.dirname(os.path.abspath(__file__))

# Woran man den Anbieter an der Adresse erkennt
ANBIETER = [("fal", ("fal.run", "fal-ai", "fal.ai")),
            ("eleven", ("elevenlabs", "eleven-labs")),
            ("hedra", ("hedra",)),
            ("replicate", ("replicate",)),
            ("anthropic", ("anthropic", "claude")),
            ("openai", ("openai", "api.openai")),
            ("freesound", ("freesound",))]


def anbieter(url):
    """Welcher Anbieter hinter einer Adresse steckt. Leer, wenn unbekannt."""
    u = (url or "").lower()
    for name, merkmale in ANBIETER:
        for m in merkmale:
            if m in u:
                return name
    return ""


def _env_lesen():
    d = {}
    try:
        with open(os.path.join(BASIS, ".env"), encoding="utf-8") as f:
            for z in f:
                z = z.strip()
                if z and not z.startswith("#") and "=" in z:
                    n, v = z.split("=", 1)
                    d[n.strip()] = v.strip()
    except Exception:
        pass
    return d


def aus_umgebung(teil):
    """Schluessel, dessen Name das Stueck enthaelt. Leer, wenn keiner da ist."""
    t = (teil or "").upper()
    if not t:
        return ""
    quellen = _env_lesen()
    quellen.update(dict(os.environ))
    for k, v in quellen.items():
        kk = k.upper()
        if t in kk and v and ("KEY" in kk or "TOKEN" in kk or "SECRET" in kk):
            return v.strip()
    return ""


def fuer(kanal, eintrag):
    """Der Schluessel, mit dem dieser Eintrag angesprochen wird."""
    e = eintrag or {}
    k = (e.get("key") or "").strip()
    if k:
        return k
    a = anbieter(e.get("url"))
    if not a:
        return ""
    apis = ((kanal or {}).get("apis") or {})
    if isinstance(apis, dict):
        for liste in apis.values():
            for x in (liste or []):
                if isinstance(x, dict) and anbieter(x.get("url")) == a:
                    kk = (x.get("key") or "").strip()
                    if kk:
                        return kk
    return aus_umgebung(a)


def woher(kanal, eintrag):
    """Nur zum Anzeigen: woher der Schluessel kommt. Nie der Schluessel selbst."""
    e = eintrag or {}
    if (e.get("key") or "").strip():
        return "eigener Eintrag"
    a = anbieter(e.get("url"))
    if not a:
        return ""
    apis = ((kanal or {}).get("apis") or {})
    if isinstance(apis, dict):
        for liste in apis.values():
            for x in (liste or []):
                if isinstance(x, dict) and anbieter(x.get("url")) == a:
                    if (x.get("key") or "").strip():
                        return "anderer %s-Eintrag" % a
    return "Serverdatei" if aus_umgebung(a) else ""
