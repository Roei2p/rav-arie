#!/usr/bin/env python3
"""חיתוך קטעי שמע לקליפים מתוך השמע המקורי.
לכל clips/disc*.json: מוריד את תיקיית הדיסק מהדרייב (אם עוד לא הורדה) וחותך כל קליף ל-web/cuts/<id>.m4a.
קטעים שכבר נחתכו מדולגים."""
import glob, json, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
out = ROOT / "web/cuts"; out.mkdir(parents=True, exist_ok=True)
for cfgp in sorted(glob.glob(str(ROOT / "clips/disc*.json"))):
    cfg = json.loads(Path(cfgp).read_text(encoding="utf-8"))
    todo = [c for c in cfg["clips"] if not (out / f"{c['id']}.m4a").exists()]
    if not todo:
        print("✓", cfgp); continue
    src = ROOT / "src" / cfg["drive_folder"]
    if not src.exists():
        for _ in range(4):
            if subprocess.run(["gdown", "--folder", f"https://drive.google.com/drive/folders/{cfg['drive_folder']}", "-O", str(src)]).returncode == 0:
                break
    files = {p.stem.lower(): p for p in src.rglob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a")}
    for c in todo:
        a = files[c["track"].lower()]
        dst = out / f"{c['id']}.m4a"; tmp = out / f"{c['id']}.part.m4a"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{c['start']:.2f}", "-t", f"{c['end']-c['start']:.2f}",
                        "-i", str(a), "-c:a", "aac", "-b:a", "160k", "-ac", "2", str(tmp)], check=True)
        tmp.replace(dst); print("✓", dst.name)
