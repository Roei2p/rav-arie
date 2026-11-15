#!/usr/bin/env python3
"""
הפקת קליפים אנכיים (1080x1920) עם כתוביות בעברית.

קלט: clips/clips.json (קטעים, זמנים וכתוביות מוגהות), clips/bg/<id>.png, fonts/*.ttf
שמע: תיקייה עם קבצי TrackXX.mp3 המקוריים.

  python scripts/make_clips.py --audio audio/35 --out out/clips
  python scripts/make_clips.py --audio audio/35 --out /tmp --only clip1-menachem-frank --preview 30 8
"""
import argparse, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H = 1080, 1920


def ts(t):
    t = max(0.0, t)
    h, r = divmod(t, 3600); m, s = divmod(r, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def chunk(text, start, end, maxc=24):
    words, out, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > maxc:
            out.append(cur); cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    total = sum(len(c) for c in out) or 1
    t, res = start, []
    for c in out:
        d = (end - start) * len(c) / total
        res.append((t, t + d, c)); t += d
    return res


RLM = "\u200f"


def rtl(t):
    return RLM + t + RLM


def build_ass(clip, series, dur):
    style = (
        "[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        "Style: Series,Heebo,40,&H0044B5F2,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,0,0,8,90,90,170,-1\n"
        "Style: Title,Frank Ruhl Libre Black,104,&H00FFFFFF,&H000000FF,&H00000000,&H78000000,0,0,0,0,100,100,0,0,1,0,6,8,80,80,236,-1\n"
        "Style: Sub,Heebo Black,78,&H00FFFFFF,&H000000FF,&H00101010,&H96000000,0,0,0,0,100,100,0,0,1,3,5,5,80,80,0,-1\n"
        "Style: Credit,Heebo,38,&H00C8D2DC,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,0,0,2,90,90,120,-1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    ev = []
    ev.append(f"Dialogue: 1,{ts(0)},{ts(dur)},Series,,0,0,0,,{{\\fad(500,0)}}{rtl(series)}")
    ev.append(f"Dialogue: 1,{ts(0)},{ts(dur)},Title,,0,0,0,,{{\\fad(700,0)}}{rtl(clip['title'])}")
    ev.append(f"Dialogue: 1,{ts(0)},{ts(dur)},Credit,,0,0,0,," + rtl("מעטים כנגד רבים · חנוכה"))
    # כתוביות: יחסית לתחילת הקליפ, מוחזקות עד הכתובית הבאה בהפסקות קצרות
    subs = []
    for s, e, t in clip["lines"]:
        subs += chunk(t, s - clip["start"], e - clip["start"])
    for i, (s, e, t) in enumerate(subs):
        nxt = subs[i + 1][0] if i + 1 < len(subs) else dur
        if nxt - e < 0.8:
            e = nxt
        ev.append(f"Dialogue: 2,{ts(s)},{ts(min(e, dur))},Sub,,0,0,0,,{{\\pos(540,1180)\\fad(120,80)}}{rtl(t)}")
    return style + "\n".join(ev) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only")
    ap.add_argument("--preview", nargs=2, type=float, metavar=("AT", "LEN"))
    a = ap.parse_args()
    cfg = json.loads((ROOT / "clips/clips.json").read_text(encoding="utf-8"))
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    fonts = str(ROOT / "fonts")
    for c in cfg["clips"]:
        if a.only and c["id"] != a.only:
            continue
        dur = c["end"] - c["start"]
        ass = out / f"{c['id']}.ass"
        ass.write_text(build_ass(c, cfg["series"], dur), encoding="utf-8")
        src = Path(a.audio) / f"{c['track']}.mp3"
        if not src.exists():
            src = Path(a.audio) / f"{c['track'].lower()}.mp3"
        ss, length = c["start"], dur
        vstart = 0.0
        if a.preview:
            vstart, length = a.preview
            ss += vstart
        fade_out = max(0.0, length - 0.9)
        fc = (
            f"[0:v]scale=1296:2304,zoompan=z='min(1+0.00018*(on+{int(vstart*30)}),1.12)':d=1:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={W}x{H}:fps=30[bg];"
            f"[1:a]asplit[a1][a2];"
            f"[a2]dynaudnorm=f=150,showwaves=s=900x150:mode=cline:scale=sqrt:draw=full:colors=0xF2B544:rate=30,format=rgba,colorchannelmixer=aa=0.75[w];"
            f"[bg][w]overlay=90:1440:shortest=1[v0];"
            f"[v0]setpts=PTS+{vstart}/TB,ass='{ass}':fontsdir='{fonts}',setpts=PTS-STARTPTS,"
            f"fade=t=in:st=0:d=0.6,fade=t=out:st={fade_out}:d=0.9[v];"
            f"[a1]afade=t=in:st=0:d=0.4,afade=t=out:st={fade_out}:d=0.9[a]"
        )
        dst = out / f"{c['id']}.mp4"
        cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
               "-loop", "1", "-framerate", "30", "-i", str(ROOT / "clips/bg" / f"{c['id']}.png"),
               "-ss", f"{ss:.2f}", "-t", f"{length:.2f}", "-i", str(src),
               "-filter_complex", fc, "-map", "[v]", "-map", "[a]",
               "-t", f"{length:.2f}",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(dst)]
        print("▶", c["id"], f"{length:.0f}s"); sys.stdout.flush()
        subprocess.run(cmd, check=True)
        print("  ✓", dst, f"{dst.stat().st_size/1e6:.1f}MB")


if __name__ == "__main__":
    main()
