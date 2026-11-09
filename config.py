from pathlib import Path
BASIS = Path(__file__).resolve().parent
ORDNER_VIDEOS = BASIS / "fertige_videos"
ORDNER_VIDEOS.mkdir(exist_ok=True)
