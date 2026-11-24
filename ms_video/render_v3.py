"""MS erklärt – Version 2: realistische Bilder, Kamerafahrten, Quiz, animierte Infos.

Frame-genauer Renderer: Python zeichnet jedes Bild (Ken-Burns-Zoom/-Schwenk,
Pop-in-Texte, Zähler, Karaoke-Untertitel) und schickt es an ffmpeg.
Fakten: DMSG, https://www.dmsg.de/multiple-sklerose/was-ist-ms
"""
import math
import subprocess
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).parent
PHOTOS = HERE / "photos_v3"
W, H, FPS = 1080, 1920, 30
XF = 0.35  # Überblendung

ORANGE = (255, 140, 66)
GREEN = (46, 196, 120)
RED = (230, 57, 70)
WHITE = (255, 255, 255)
NAVY = (14, 30, 64)
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

# --- Zeitachse -------------------------------------------------------------
# Zwei Quizpausen à 4 s werden in die Sprachaufnahme eingefügt.
Q1_AT, Q2_AT, QDUR = 23.2, 47.3, 4.0


def sh(t):
    """Originalzeit der Sprachaufnahme -> Zeit im fertigen Video."""
    return t + (QDUR if t >= Q1_AT else 0) + (QDUR if t >= Q2_AT else 0)


TOTAL = sh(67.92) + 1.6

# (Bild, Start, Ende, Bewegung) – Bewegung: z0, z1, (cx0, cy0), (cx1, cy1)
SCENES = [
    # Hochkant-Bilder (1152x2048): Zoom-Fahrten auf das jeweilige Motiv
    ("01", 0.0, 7.8, (1.00, 1.18, (0.5, 0.5), (0.5, 0.58))),          # Menge -> Menschen
    ("02", 7.8, 14.5, (1.20, 1.00, (0.5, 0.40), (0.5, 0.5))),         # Gehirn: Rauszoomen
    ("03", 14.5, Q1_AT, (1.00, 1.30, (0.5, 0.5), (0.58, 0.56))),      # Zoom auf die Schadstelle
    ("Q1", Q1_AT, Q1_AT + QDUR, None),
    ("04", sh(23.2), sh(31.3), (1.00, 1.18, (0.5, 0.5), (0.36, 0.5))),   # zur Patientin
    ("05", sh(31.3), sh(42.75), (1.00, 1.28, (0.5, 0.5), (0.62, 0.36))), # Zoom aufs Gesicht
    ("06", sh(42.75), Q2_AT + QDUR, (1.00, 1.32, (0.5, 0.5), (0.45, 0.45))),  # in die MRT-Bilder
    ("Q2", Q2_AT + QDUR, Q2_AT + 2 * QDUR, None),
    ("07", sh(47.3), sh(56.7), (1.15, 1.15, (0.68, 0.5), (0.40, 0.5))),  # Schwenk über die Gruppe
    ("08", sh(56.7), TOTAL, (1.18, 1.00, (0.55, 0.42), (0.5, 0.5))),     # Rauszoomen: Gespräch
]

SUBS = [
    (0.00, 4.90, "Mehr als 280.000 Menschen in Deutschland leben mit Multipler Sklerose."),
    (5.41, 7.50, "Aber was ist MS eigentlich?"),
    (8.17, 11.10, "MS ist eine entzündliche Erkrankung"),
    (11.10, 14.24, "des zentralen Nervensystems, also von Gehirn und Rückenmark."),
    (14.74, 17.50, "Das Immunsystem greift dabei fälschlicherweise"),
    (17.50, 20.39, "die Schutzschicht der Nervenfasern an, das Myelin."),
    (20.79, 22.90, "Dadurch werden Nervensignale gestört."),
    (23.50, 27.95, "Meist wird MS zwischen dem 20. und 40. Lebensjahr festgestellt."),
    (28.38, 31.03, "Frauen erkranken etwa doppelt so häufig wie Männer."),
    (31.59, 34.70, "Erste Anzeichen können Sehstörungen, Kribbeln,"),
    (34.70, 37.96, "Taubheitsgefühle oder Unsicherheit beim Gehen sein."),
    (38.41, 42.48, "Deshalb nennt man MS auch die Krankheit mit den tausend Gesichtern."),
    (43.02, 47.01, "Zu Beginn verläuft sie bei bis zu 90 % der Betroffenen in Schüben."),
    (47.60, 48.14, "Wichtig:"),
    (48.47, 50.90, "MS ist nicht ansteckend, kein Muskelschwund"),
    (50.90, 53.35, "und keine psychische Erkrankung."),
    (53.78, 56.48, "Und sie führt nicht automatisch in den Rollstuhl."),
    (56.94, 60.42, "MS ist bis heute nicht heilbar, aber behandelbar."),
    (60.90, 63.77, "Bei Beschwerden: ab zur Ärztin oder zum Arzt."),
    (64.17, 67.92, "Mehr Infos gibt es bei der Deutschen Multiple Sklerose Gesellschaft."),
]
SUBS = [(sh(a), sh(b), t) for a, b, t in SUBS]

# --- Hilfsfunktionen ------------------------------------------------------


@lru_cache(None)
def F(path, size):
    return ImageFont.truetype(path, size)


def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = max(0.0, min(1.0, x))
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def ease_io(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


@lru_cache(None)
def pill(text, size=56, fg=WHITE, bg=(0, 0, 0, 170), bold=True, pad=(36, 20), radius=34, maxw=940):
    f = F(BOLD if bold else REG, size)
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        test = (cur + " " + w_).strip()
        if d0.textlength(test, font=f) <= maxw - 2 * pad[0]:
            cur = test
        else:
            lines.append(cur)
            cur = w_
    lines.append(cur)
    lh = int(size * 1.22)
    tw = max(int(d0.textlength(l, font=f)) for l in lines)
    img = Image.new("RGBA", (tw + 2 * pad[0], lh * len(lines) + 2 * pad[1]), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if bg:
        d.rounded_rectangle([0, 0, img.width - 1, img.height - 1], radius=radius, fill=bg)
    stroke = 0 if bg else max(3, size // 16)  # Kontur für Text ohne Kasten
    for i, l in enumerate(lines):
        d.text((img.width / 2, pad[1] + lh * i + lh / 2), l, font=f, fill=fg, anchor="mm",
               stroke_width=stroke, stroke_fill=(10, 18, 40, 230))
    return img


def put(frame, el, cx, cy, t, dur=0.4, anchor="c", rot=0.0, fade_out=None):
    """Pop-in eines Elements ab lokaler Zeit t>=0 (Skalierung mit Überschwingen)."""
    if t < 0:
        return
    s = ease_back(t / dur)
    a = ease_out(t / (dur * 0.6))
    if fade_out is not None and t > fade_out:
        a *= max(0.0, 1 - (t - fade_out) / 0.3)
    if s <= 0.01 or a <= 0.01:
        return
    img = el
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if abs(s - 1) > 0.005:
        img = img.resize((max(1, int(img.width * s)), max(1, int(img.height * s))), Image.BILINEAR)
    if a < 0.999:
        alpha = img.getchannel("A").point(lambda v: int(v * a))
        img = img.copy()
        img.putalpha(alpha)
    x = int(cx) if anchor == "l" else int(cx - img.width / 2)
    frame.alpha_composite(img, (max(0, x), int(cy - img.height / 2)))


# --- Bilder & Kamerafahrt -------------------------------------------------


@lru_cache(None)
def photo(key):
    im = Image.open(PHOTOS / f"{key}.jpg").convert("RGB")
    s = max(W / im.width, H / im.height)
    if s > 1:  # nur hochskalieren, wenn das Bild kleiner als das Video ist
        im = im.resize((math.ceil(im.width * s), math.ceil(im.height * s)), Image.LANCZOS)
    return im


@lru_cache(None)
def blurred(key):
    im = photo(key).resize((540, int(540 * photo(key).height / photo(key).width)), Image.BILINEAR)
    im = im.filter(ImageFilter.GaussianBlur(14))
    return Image.blend(im, Image.new("RGB", im.size, NAVY), 0.45).resize(photo(key).size, Image.BILINEAR)


def camera(src, z, cx, cy):
    # Grundausschnitt: 9:16-Fenster, das das Bild ganz ausfüllt
    bw = min(src.width, src.height * W / H)
    bh = bw * H / W
    cw, ch = bw / z, bh / z
    x = min(max(cx * src.width - cw / 2, 0), src.width - cw)
    y = min(max(cy * src.height - ch / 2, 0), src.height - ch)
    return src.resize((W, H), Image.BILINEAR, box=(x, y, x + cw, y + ch))


@lru_cache(None)
def shade():
    """Verlauf oben/unten, damit Texte immer lesbar sind."""
    g = Image.new("L", (1, H))
    for y in range(H):
        top = max(0.0, 1 - y / 760) * 200
        bot = max(0.0, (y - 1150) / 770) * 215
        g.putpixel((0, y), int(min(230, top + bot)))
    a = g.resize((W, H))
    img = Image.new("RGBA", (W, H), (5, 12, 30, 0))
    img.putalpha(a)
    return img


def base_frame(i, t):
    key, a, b, mv = SCENES[i]
    p = (t - a) / (b - a)
    if key.startswith("Q"):
        nxt = SCENES[i + 1][0]
        z = 1.05 + 0.05 * p
        fr = camera(blurred(nxt), z, 0.5, 0.5)
    else:
        z0, z1, (x0, y0), (x1, y1) = mv
        e = ease_io(p)
        fr = camera(photo(key), z0 + (z1 - z0) * e, x0 + (x1 - x0) * e, y0 + (y1 - y0) * e)
    return fr.convert("RGBA")


# --- Overlays je Szene ----------------------------------------------------


def fmt(n):
    return f"{int(n):,}".replace(",", ".")


def countdown(fr, t, cx, cy):
    # t: 0..3 -> 3,2,1
    if t < 0 or t >= 3:
        return
    n = 3 - int(t)
    frac = t - int(t)
    d = ImageDraw.Draw(fr)
    r = 110
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 150))
    d.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * (1 - frac), fill=ORANGE, width=14)
    s = 1 + 0.25 * (1 - ease_out(frac / 0.3))
    d.text((cx, cy), str(n), font=F(BOLD, int(120 * s)), fill=WHITE, anchor="mm")


def quiz(fr, t, question, opt_a, opt_b):
    put(fr, pill("QUIZ – rate mit!", 52, NAVY, ORANGE + (255,)), W / 2, 330, t)
    put(fr, pill(question, 66, WHITE, None, maxw=980), W / 2, 560, t - 0.15)
    put(fr, pill(f"A   {opt_a}", 60, NAVY, (255, 255, 255, 240), pad=(60, 30), radius=48), W / 2, 860, t - 0.35)
    put(fr, pill(f"B   {opt_b}", 60, NAVY, (255, 255, 255, 240), pad=(60, 30), radius=48), W / 2, 1030, t - 0.5)
    countdown(fr, t - 0.6, W / 2, 1310)
    if t > 3.6:
        put(fr, pill("Auflösung gleich …", 44, WHITE, (0, 0, 0, 150), bold=False), W / 2, 1310, t - 3.6, dur=0.25)
    put(fr, pill("Schreib deine Antwort in die Kommentare", 36, WHITE, None, bold=False), W / 2, 1480, t - 0.8)


def overlays(fr, i, t):
    key = SCENES[i][0]
    if key == "01":
        k = ease_out((t - 0.3) / 2.2)
        put(fr, pill("Mehr als", 60, (210, 225, 245), None), W / 2, 470, t - 0.1)
        put(fr, pill(fmt(280000 * k), 170, ORANGE, None, pad=(10, 0)), W / 2, 620, t - 0.2, dur=0.3)
        put(fr, pill("Menschen in Deutschland leben mit MS", 54), W / 2, 800, t - 0.8)
        put(fr, pill("Was ist MS?", 92, NAVY, ORANGE + (255,), pad=(50, 26), radius=50), W / 2, 1050, t - 5.41)
    elif key == "02":
        put(fr, pill("Zentrales Nervensystem", 64, NAVY, ORANGE + (255,)), W / 2, 330, t - 0.3)
        put(fr, pill("Gehirn  +  Rückenmark", 56), W / 2, 470, t - (11.6 - 7.8))
    elif key == "03":
        put(fr, pill("Myelin = Schutzschicht der Nervenfasern", 52), W / 2, 340, t - 0.5)
        put(fr, pill("⚡ Nervensignale gestört", 62, NAVY, ORANGE + (255,)), W / 2, 500, t - (20.79 - 14.5))
    elif key == "Q1":
        quiz(fr, t, "Wer erkrankt häufiger an MS?", "Frauen", "Männer")
    elif key == "04":
        t0 = SCENES[i][1]
        put(fr, pill("Diagnose meist mit", 46, (210, 225, 245), None, bold=False), W / 2, 300, t - (sh(23.5) - t0))
        put(fr, pill("20 – 40 Jahren", 110, ORANGE, None, pad=(10, 0)), W / 2, 410, t - (sh(25.12) - t0))
        put(fr, pill("✓  Richtig ist A: Frauen", 62, WHITE, GREEN + (240,)), W / 2, 600, t - (sh(28.38) - t0))
        put(fr, pill("etwa doppelt so häufig wie Männer", 46), W / 2, 720, t - (sh(28.9) - t0))
    elif key == "05":
        t0 = SCENES[i][1]
        put(fr, pill("Mögliche erste Anzeichen", 52, NAVY, ORANGE + (255,)), W / 2, 300, t - 0.3)
        chips = [("Sehstörungen", 33.04), ("Kribbeln", 34.08), ("Taubheitsgefühl", 34.84), ("Unsicherheit beim Gehen", 36.4)]
        for j, (txt, ot) in enumerate(chips):
            put(fr, pill("•  " + txt, 54), W / 2, 430 + j * 120, t - (sh(ot) - t0))
        put(fr, pill("„Krankheit der 1000 Gesichter“", 58, NAVY, (255, 255, 255, 235)), W / 2, 960, t - (sh(40.4) - t0))
    elif key == "06":
        t0 = SCENES[i][1]
        st = sh(44.6) - t0
        k = ease_out((t - st) / 1.4)
        put(fr, pill("bei bis zu", 54, (210, 225, 245), None), W / 2, 330, t - st + 0.2)
        put(fr, pill(f"{int(round(90 * k))} %", 190, ORANGE, None, pad=(10, 0)), W / 2, 510, t - st)
        put(fr, pill("verläuft MS anfangs in Schüben", 56), W / 2, 700, t - (sh(46.4) - t0))
    elif key == "Q2":
        quiz(fr, t, "Mythos oder Fakt: „MS ist ansteckend.“", "Mythos", "Fakt")
    elif key == "07":
        t0 = SCENES[i][1]
        put(fr, pill("MYTHOS!", 110, WHITE, RED + (245,), pad=(50, 20), radius=24), W / 2, 360, t - (sh(48.47) - t0), dur=0.3, rot=8)
        items = [("✗  nicht ansteckend", 49.28), ("✗  kein Muskelschwund", 50.56), ("✗  keine psychische Erkrankung", 51.84), ("✗  nicht automatisch Rollstuhl", 54.72)]
        for j, (txt, ot) in enumerate(items):
            put(fr, pill(txt, 48), W / 2, 560 + j * 115, t - (sh(ot) - t0))
    elif key == "08":
        t0 = SCENES[i][1]
        put(fr, pill("Nicht heilbar –", 76, WHITE, None), W / 2, 330, t - (sh(56.94) - t0))
        put(fr, pill("aber behandelbar", 84, NAVY, ORANGE + (255,), pad=(44, 22)), W / 2, 460, t - (sh(59.28) - t0))
        put(fr, pill("Bei Beschwerden ärztlich abklären lassen", 46), W / 2, 625, t - (sh(60.9) - t0))
        put(fr, pill("Infos & Beratung:  dmsg.de", 58, NAVY, (255, 255, 255, 240), pad=(44, 26)), W / 2, 830, t - (sh(64.3) - t0))
        put(fr, pill("Was willst du als Nächstes über MS wissen?  ↓ Kommentar", 44, WHITE, (0, 0, 0, 150), maxw=900), W / 2, 1060, t - (sh(66.2) - t0))
        put(fr, pill("Quelle: DMSG · Kein Ersatz für ärztlichen Rat · Bilder & Stimme KI-generiert", 28, (220, 230, 245), None, bold=False, maxw=1000), W / 2, 1835, t - 0.5)


# --- Untertitel (Karaoke) -------------------------------------------------


import json as _json

_TW = [w for w in _json.load(open(HERE / "words.json", encoding="utf-8"))["words"] if w.get("type") == "word"]


def _build_word_index():
    """Ordnet jedem Untertitel-Wort den gemessenen Zeitstempel zu (gleiche Wortanzahl)."""
    idx, out = 0, []
    for a, b, text in SUBS:
        seg = []
        for w_ in text.split():
            tw = _TW[idx]
            seg.append((w_, sh(tw["start"]), sh(tw["end"])))
            idx += 1
        out.append(seg)
    assert idx == len(_TW), (idx, len(_TW))
    return out


_WORDS = None


def word_times(a, b, text):
    global _WORDS
    if _WORDS is None:
        _WORDS = _build_word_index()
    return _WORDS[[t for _, _, t in SUBS].index(text)]


@lru_cache(None)
def sub_layout(idx):
    a, b, text = SUBS[idx]
    f = F(BOLD, 58)
    d0 = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    wt = word_times(a, b, text)
    lines, cur, curw = [], [], 0
    space = d0.textlength(" ", font=f)
    for j, (w_, _, _) in enumerate(wt):
        ww = d0.textlength(w_, font=f)
        if cur and curw + space + ww > 880:
            lines.append(cur)
            cur, curw = [], 0
        cur.append((j, w_, ww))
        curw += (space if curw else 0) + ww
    lines.append(cur)
    return wt, lines, space


def subtitles(fr, t):
    for idx, (a, b, _) in enumerate(SUBS):
        if a - 0.05 <= t <= b + 0.15:
            wt, lines, space = sub_layout(idx)
            f = F(BOLD, 58)
            lh = 76
            total_h = lh * len(lines) + 36
            widths = [sum(w for _, _, w in ln) + space * (len(ln) - 1) for ln in lines]
            bw = max(widths) + 60
            y0 = 1560 - total_h / 2
            d = ImageDraw.Draw(fr)
            d.rounded_rectangle([W / 2 - bw / 2, y0, W / 2 + bw / 2, y0 + total_h], radius=26, fill=(0, 0, 0, 165))
            for li, ln in enumerate(lines):
                x = W / 2 - widths[li] / 2
                y = y0 + 18 + lh * li + lh / 2
                for j, w_, ww in ln:
                    _, ws, we = wt[j]
                    col = ORANGE if ws <= t < we + 0.05 else WHITE
                    d.text((x, y), w_, font=f, fill=col, anchor="lm")
                    x += ww + space
            return


# --- Rahmen: Branding, KI-Hinweis, Fortschrittsbalken ---------------------


def chrome(fr, t):
    d = ImageDraw.Draw(fr)
    d.rectangle([0, 0, W, 12], fill=(255, 255, 255, 60))
    d.rectangle([0, 0, int(W * t / TOTAL), 12], fill=ORANGE)
    fr.alpha_composite(pill("MS erklärt", 32, WHITE, ORANGE + (255,), pad=(24, 12), radius=24), (50, 60))
    fr.alpha_composite(pill("KI-generiert", 24, WHITE, (0, 0, 0, 120), bold=False, pad=(16, 8), radius=16), (W - 210, 66))


def frame_at(t):
    i = max(j for j, s in enumerate(SCENES) if s[1] <= t)
    fr = base_frame(i, t)
    fr.alpha_composite(shade())
    overlays(fr, i, t - SCENES[i][1])
    # Überblendung von der vorigen Szene
    if i > 0 and t - SCENES[i][1] < XF:
        prev = base_frame(i - 1, t)
        prev.alpha_composite(shade())
        overlays(prev, i - 1, t - SCENES[i - 1][1])
        fr = Image.blend(prev, fr, ease_io((t - SCENES[i][1]) / XF))
    subtitles(fr, t)
    chrome(fr, t)
    return fr.convert("RGB")


# --- Audio ----------------------------------------------------------------


def build_audio(out):
    voice = HERE / "voice.mp3"
    ticks = [Q1_AT + 0.6 + k for k in range(3)] + [Q2_AT + QDUR + 0.6 + k for k in range(3)]
    dings = [sh(28.38), sh(48.47)]
    whooshes = [s[1] for s in SCENES[1:]]
    inputs = ["-i", str(voice), "-i", str(HERE / "music.mp3")]
    filt = [
        f"[0:a]atrim=0:{Q1_AT},asetpts=PTS-STARTPTS[s1]",
        f"[0:a]atrim={Q1_AT}:{Q2_AT},asetpts=PTS-STARTPTS,adelay={int(sh(Q1_AT)*1000)}:all=1[s2]",
        f"[0:a]atrim={Q2_AT},asetpts=PTS-STARTPTS,adelay={int(sh(Q2_AT)*1000)}:all=1[s3]",
    ]
    q = f"between(t,{Q1_AT},{Q1_AT+QDUR})+between(t,{Q2_AT+QDUR},{Q2_AT+2*QDUR})"
    filt.append(f"[1:a]atrim=0:{TOTAL},asetpts=PTS-STARTPTS,volume='if({q},0.30,0.085)':eval=frame,afade=t=in:d=1,afade=t=out:st={TOTAL-2.5}:d=2.5[mus]")
    labels = ["[s1]", "[s2]", "[s3]", "[mus]"]
    n = 0
    for tt in ticks:
        filt.append(f"sine=f=1200:d=0.07,volume=0.35,afade=t=out:st=0.03:d=0.04,adelay={int(tt*1000)}:all=1[e{n}]")
        labels.append(f"[e{n}]"); n += 1
    for tt in dings:
        filt.append(f"sine=f=1320:d=0.5,volume=0.3,afade=t=out:st=0.05:d=0.45,adelay={int(tt*1000)}:all=1[e{n}]")
        labels.append(f"[e{n}]"); n += 1
        filt.append(f"sine=f=1760:d=0.45,volume=0.2,afade=t=out:st=0.05:d=0.4,adelay={int(tt*1000)+90}:all=1[e{n}]")
        labels.append(f"[e{n}]"); n += 1
    for tt in whooshes:
        filt.append(f"anoisesrc=d=0.4:c=pink:a=0.25,highpass=f=600,lowpass=f=5000,afade=t=in:d=0.15,afade=t=out:st=0.15:d=0.25,volume=0.35,adelay={int(max(0, tt-0.2)*1000)}:all=1[e{n}]")
        labels.append(f"[e{n}]"); n += 1
    filt.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[aout]")
    subprocess.run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filt), "-map", "[aout]", str(out)], check=True)


def main(preview_times=None):
    if preview_times:
        for tt in preview_times:
            frame_at(tt).save(HERE / f"preview_{tt:05.1f}.png")
        return
    audio = HERE / "audio_v3.wav"
    build_audio(audio)
    out = HERE / "MS_erklaert_v3_9x16.mp4"
    p = subprocess.Popen([
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
        "-i", str(audio),
        "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-af", "apad", "-t", f"{TOTAL:.2f}", "-movflags", "+faststart", str(out),
    ], stdin=subprocess.PIPE)
    nframes = int(TOTAL * FPS)
    for k in range(nframes):
        p.stdin.write(frame_at(k / FPS).tobytes())
        if k % 300 == 0:
            print(f"{k}/{nframes}", flush=True)
    p.stdin.close()
    p.wait()
    print("fertig:", out)


if __name__ == "__main__":
    import sys
    main([float(x) for x in sys.argv[1:]] or None)
