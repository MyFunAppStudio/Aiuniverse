# AiUniverse

Automatische Videoproduktion auf eigenem Server. Erzeugt aus einem Thema
Text, Szenenbilder, Clips, Stimme und ein fertiges Video im Hochformat.

Laeuft auf einem Ubuntu-Server unter `/root/aiuniverse`, bedient wird es
ueber ein Dashboard im Browser auf Port 8091.

## Aktualisieren

Auf dem Server:

```sh
sh /root/aiuniverse/aktualisiere.sh
```

Holt die neueste Fassung, prueft sie und startet das Dashboard neu.
Zurueck auf den vorherigen Stand geht ueber `git reset --hard <stand>`;
das Skript nennt den passenden Befehl, falls etwas klemmt.

## Was NICHT in diesem Repo liegt

Bewusst ausgeschlossen, siehe `.gitignore`:

| Ordner | Inhalt |
|---|---|
| `regeln/` | API-Schluessel, Dashboard-Passwort, Kanal-Einstellungen, Szenen |
| `eigene/` | hochgeladene Bilder, Darstellerbilder, erzeugte Clips |
| `fertige_videos/`, `gs/`, `pr/` | erzeugte Medien und Zwischenstaende |
| `*.bak_*` | Sicherungskopien aelterer Patches |

Die Schluessel verlassen den Server nicht.

## Aufbau

| Datei | Aufgabe |
|---|---|
| `dashboard2.py` / `dashboard2.html` | Oberflaeche und Weboberflaeche |
| `einstellungen.py` | Kanaele, Modelle, Slots |
| `schluessel.py` | Zugriff auf die hinterlegten Schluessel |
| `text_generator.py` | Text zum Thema |
| `geschichte.py` | zerlegt den Text in Szenen, baut Bildprompts |
| `bilder.py` | erzeugt die Szenenbilder |
| `darsteller.py` | zwei wiederkehrende Figuren mit Kleidungssaetzen |
| `animation.py` | Clips aus Bildern, auch Referenzclips mit Darstellern |
| `szenen.py` | Szenenliste je Kanal |
| `szenen_video.py` | baut aus Szenen, Stimme und Musik das Video |
| `figuren.py` | aeltere, freigestellte Figuren zum Aufkleben |
| `themen.py`, `vorlagen.py` | Themenliste und Vorlagen |
| `telegram_sender.py` | Versand des fertigen Videos |
