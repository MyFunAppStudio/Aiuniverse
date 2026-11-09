import os, subprocess
def hole_musik(kanal, sekunden, ordner):
    ziel = os.path.join(str(ordner), "auto_musik.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=160:duration=%.2f" % max(2, sekunden),
                    "-ar", "44100", ziel], capture_output=True)
    return ziel
