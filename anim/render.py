#!/usr/bin/env python3
"""רינדור קליפ מונפש: אנימציה ב-canvas -> פריימים -> ffmpeg, עם השמע מהקליפ הקיים.
python render.py <clip-id> [--frames t1,t2,...]   (frames = רק תמונות בדיקה)"""
import base64, json, subprocess, sys, os
from playwright.sync_api import sync_playwright

ROOT = "/home/claude/rav-arie"
THEME = {"clip1-menachem-frank": ("amber", 11), "clip2-margarine": ("violet", 23),
         "clip3-silver-menorahs": ("teal", 37), "clip4-washington": ("royal", 41)}


def pages_for(clip, maxc=30):
    chunks = []
    for s, e, text in clip["lines"]:
        s -= clip["start"]; e -= clip["start"]
        words, cur, out = text.split(), [], []
        for w in words:
            if cur and len(" ".join(cur + [w])) > maxc:
                out.append(cur); cur = [w]
            else:
                cur.append(w)
        if cur: out.append(cur)
        total = sum(len(" ".join(c)) for c in out) or 1
        t = s
        for c in out:
            d = (e - s) * len(" ".join(c)) / total
            wl = sum(len(w) for w in c) or 1
            tw, ws = t, []
            for w in c:
                dw = d * len(w) / wl
                ws.append({"w": w, "t0": round(tw, 3), "t1": round(tw + dw, 3)}); tw += dw
            chunks.append({"s": t, "e": t + d, "w": ws}); t += d
    for i, p in enumerate(chunks):
        nxt = chunks[i + 1]["s"] if i + 1 < len(chunks) else p["e"] + 0.6
        p["e"] = nxt if nxt - p["e"] < 1.0 else p["e"] + 0.4
        p["s"] = round(p["s"] - 0.05, 3)
    return chunks


def main():
    cid = sys.argv[1]
    cfg = json.load(open(f"{ROOT}/clips/clips.json", encoding="utf-8"))
    clip = next(c for c in cfg["clips"] if c["id"] == cid)
    theme, seed = THEME[cid]
    dur = round(clip["end"] - clip["start"], 2)
    data = {"title": clip["title"], "dur": dur, "theme": theme, "seed": seed, "pages": pages_for(clip)}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": 1080, "height": 1920})
        pg.goto("file:///home/claude/anim/anim.html")
        pg.evaluate("document.fonts.load('800 78px Rubik','אב')")
        pg.evaluate("Promise.all([document.fonts.load('900 92px Frank','אב'),document.fonts.load('700 38px Rubik','אב'),document.fonts.load('500 44px Rubik','אב')])")
        pg.evaluate("d=>setup(d)", data)
        if "--frames" in sys.argv:
            ts = [float(v) for v in sys.argv[sys.argv.index("--frames") + 1].split(",")]
            for t in ts:
                u = pg.evaluate(f"frame({t})")
                open(f"/tmp/prev/a_{cid}_{t}.jpg", "wb").write(base64.b64decode(u.split(",")[1]))
            b.close(); return
        os.makedirs(f"{ROOT}/web/anim", exist_ok=True)
        tmp = f"{ROOT}/web/anim/{cid}.part.mp4"
        audio = f"{ROOT}/web/clips/{cid}.mp4"
        ff = subprocess.Popen(["ffmpeg", "-nostdin", "-y", "-loglevel", "error",
                               "-f", "image2pipe", "-framerate", "30", "-c:v", "mjpeg", "-i", "-",
                               "-i", audio, "-map", "0:v", "-map", "1:a",
                               "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                               "-c:a", "copy", "-shortest", "-movflags", "+faststart", tmp], stdin=subprocess.PIPE)
        n = int(dur * 30)
        for i in range(n):
            u = pg.evaluate(f"frame({i/30:.4f})")
            ff.stdin.write(base64.b64decode(u.split(",")[1]))
            if i % 300 == 0:
                print(f"{cid} {i}/{n}", flush=True)
        ff.stdin.close(); rc = ff.wait(); b.close()
        if rc == 0:
            os.replace(tmp, f"{ROOT}/web/anim/{cid}.mp4"); print("✓", cid)
        else:
            sys.exit(f"ffmpeg failed {rc}")


if __name__ == "__main__":
    main()
