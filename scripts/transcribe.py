#!/usr/bin/env python3
"""
תמלול סיפורי צדיקים - הרב אריה מאיר
------------------------------------
מתמלל את כל קבצי ה-MP3 בתיקייה (כולל תת-תיקיות) עם מודל העברית של ivrit-ai,
ושומר ליד כל קובץ:
  TrackXX.txt   - טקסט רציף עם חותמות זמן כל ~30 שניות
  TrackXX.json  - מקטעים מלאים (התחלה, סוף, טקסט)
קבצים שכבר תומללו מדולגים, כך שאפשר לעצור ולהמשיך בכל שלב.

התקנה (פעם אחת):
  pip install faster-whisper

הרצה:
  # פיילוט - דיסק אחד:
  python transcribe_rav_arie.py "G:/My Drive/AI/דיסקים הרב אריה/סיפורי צדיקים - הרב אריה מאיר/35ת- חנוכה מעטים כנגד רבים"

  # כל האוסף:
  python transcribe_rav_arie.py "G:/My Drive/AI/דיסקים הרב אריה/סיפורי צדיקים - הרב אריה מאיר"

אם Google Drive for Desktop מותקן, התמלולים נשמרים ישר בתיקייה המסונכרנת
ועולים לדרייב לבד. אחרת: להוריד את התיקייה, להריץ, ולהעלות את קבצי ה-txt/json.

אפשרויות:
  --model    ברירת מחדל ivrit-ai/whisper-large-v3-turbo-ct2
  --device   auto / cuda / cpu
"""
import argparse
import json
import sys
import time
from pathlib import Path


def fmt(t: float) -> str:
    t = int(t)
    return f"{t // 3600:02d}:{(t % 3600) // 60:02d}:{t % 60:02d}"


def pick_device(requested: str):
    if requested != "auto":
        return requested, ("float16" if requested == "cuda" else "int8")
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:
        pass
    return "cpu", "int8"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--model", default="ivrit-ai/whisper-large-v3-turbo-ct2")
    ap.add_argument("--device", default="auto", choices=["auto", "cuda", "cpu"])
    ap.add_argument("--out", help="תיקיית יעד לתמלולים (ברירת מחדל: ליד קובץ השמע)")
    ap.add_argument("--commit", action="store_true", help="git commit+push אחרי כל קובץ (ל-GitHub Actions)")
    args = ap.parse_args()

    root = Path(args.folder)
    if not root.exists():
        sys.exit(f"התיקייה לא נמצאה: {root}")

    files = sorted(p for p in root.rglob("*") if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".flac", ".wma"))

    def dest(mp3: Path, ext: str) -> Path:
        if args.out:
            d = Path(args.out) / mp3.parent.name
            d.mkdir(parents=True, exist_ok=True)
            return d / (mp3.stem + ext)
        return mp3.with_suffix(ext)

    todo = [p for p in files if not dest(p, ".txt").exists()]
    print(f"נמצאו {len(files)} קבצים, {len(todo)} ממתינים לתמלול.")
    if not todo:
        return

    from faster_whisper import WhisperModel

    device, ctype = pick_device(args.device)
    print(f"טוען מודל {args.model} על {device} ({ctype})...")
    model = WhisperModel(args.model, device=device, compute_type=ctype)

    for i, mp3 in enumerate(todo, 1):
        print(f"\n[{i}/{len(todo)}] {mp3.parent.name} / {mp3.name}")
        t0 = time.time()
        segments, info = model.transcribe(
            str(mp3),
            language="he",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segs, lines, buf, buf_start = [], [], [], 0.0
        for s in segments:
            segs.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
            if not buf:
                buf_start = s.start
            buf.append(s.text.strip())
            if s.end - buf_start >= 30:
                lines.append(f"[{fmt(buf_start)}] " + " ".join(buf))
                buf = []
            print(f"\r  {fmt(s.end)} / {fmt(info.duration)}", end="", flush=True)
        if buf:
            lines.append(f"[{fmt(buf_start)}] " + " ".join(buf))

        header = f"# {mp3.parent.name} - {mp3.stem}\n# משך: {fmt(info.duration)}\n\n"
        dest(mp3, ".json").write_text(
            json.dumps({"disc": mp3.parent.name, "track": mp3.stem,
                        "duration": info.duration, "segments": segs},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        # txt נכתב אחרון - הוא הסימן שהקובץ הושלם
        dest(mp3, ".txt").write_text(header + "\n\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n  ✓ הסתיים תוך {fmt(time.time() - t0)}")
        if args.commit:
            import subprocess
            subprocess.run(["git", "add", args.out or str(root)], check=True)
            subprocess.run(["git", "commit", "-m", f"תמלול: {mp3.parent.name} / {mp3.stem}"], check=False)
            import random
            for _ in range(8):
                subprocess.run(["git", "pull", "--rebase", "-q"], check=False)
                if subprocess.run(["git", "push", "-q"]).returncode == 0:
                    break
                time.sleep(random.uniform(5, 20))

    print("\nסיום. כל התמלולים נשמרו ליד קבצי השמע.")


if __name__ == "__main__":
    main()
