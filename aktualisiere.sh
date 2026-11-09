#!/bin/sh
# ===================================================================
#  AiUniverse aktualisieren
#
#  Holt die neueste Fassung aus GitHub, prueft, ob alles laedt, und
#  startet das Dashboard neu. Das ist der einzige Befehl, den du nach
#  einer Aenderung brauchst:
#
#      sh /root/aiuniverse/aktualisiere.sh
#
#  Deine Schluessel und Einstellungen in regeln/ und deine Bilder und
#  Videos in eigene/ werden dabei NICHT angefasst. Die liegen gar nicht
#  im Repo.
# ===================================================================
B=/root/aiuniverse
cd "$B" || { echo "ACHT  $B gibt es nicht."; exit 1; }

laeuft() {
  pgrep -f "aiuniverse/geschichte_lauf.py" >/dev/null 2>&1 && return 0
  pgrep -f "aiuniverse/lauf.py" >/dev/null 2>&1 && return 0
  pgrep -f "aiuniverse/erstelle_video.py" >/dev/null 2>&1 && return 0
  return 1
}
if laeuft; then
  echo "ACHT  Es laeuft gerade etwas. Warte, bis die Leiste weg ist."
  exit 1
fi

alt=$(git rev-parse --short HEAD 2>/dev/null)
echo "=== Stand vorher: ${alt:-unbekannt} ==="

echo "--- hole Aenderungen ---"
if ! git fetch origin main --quiet; then
  echo "ACHT  GitHub nicht erreichbar oder keine Berechtigung."
  exit 1
fi

neu=$(git rev-parse --short origin/main)
if [ "$alt" = "$neu" ]; then
  echo "OK    Schon auf dem neuesten Stand ($neu). Nichts zu tun."
  exit 0
fi

git reset --hard origin/main --quiet || {
  echo "ACHT  Uebernehmen ging schief."
  exit 1
}
echo "OK    Jetzt auf $neu"
echo
echo "--- was sich geaendert hat ---"
git log --oneline "$alt..$neu" 2>/dev/null | head -20
echo

echo "--- Probe: laedt noch alles? ---"
python3 - <<'PYENDE'
import sys
sys.path.insert(0, "/root/aiuniverse")
fehlt = []
for m in ["einstellungen", "schluessel", "szenen", "darsteller", "figuren",
          "geschichte", "bilder", "animation", "szenen_video", "text_generator",
          "dashboard2"]:
    try:
        __import__(m)
    except Exception as e:
        fehlt.append("%s: %s" % (m, e))
if fehlt:
    print("ACHT  Diese Module laden nicht:")
    for z in fehlt:
        print("      " + z)
    raise SystemExit(1)
print("OK    alle Module laden")
PYENDE
if [ $? -ne 0 ]; then
  echo
  echo "ACHT  Etwas stimmt nicht. Zurueck auf den vorherigen Stand mit:"
  echo "      cd /root/aiuniverse && git reset --hard $alt && systemctl restart dashboard2"
  exit 1
fi

if laeuft; then
  echo "INFO  inzwischen laeuft etwas - Dashboard wird NICHT neu gestartet."
else
  systemctl restart dashboard2 2>/dev/null && echo "OK    Dashboard neu gestartet" \
    || echo "INFO  bitte selbst neu starten: systemctl restart dashboard2"
fi

echo
echo "=========== FERTIG ==========="
echo "Seite im Browser neu laden."
echo
echo "Falls doch etwas klemmt, zurueck auf vorher:"
echo "  cd /root/aiuniverse && git reset --hard $alt && systemctl restart dashboard2"
