"""Erzeugt 9:16-Grafikfolien (1080x1920) fuer das MS-Erklaervideo.

Eigene Grafiken statt Stockmaterial: medizinisch korrekt, keine Klischeebilder.
Alle Fakten: DMSG, https://www.dmsg.de/multiple-sklerose/was-ist-ms
"""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
OUT = Path(__file__).parent / "slides"
OUT.mkdir(exist_ok=True)

BG_TOP = (14, 30, 64)
BG_BOT = (33, 82, 140)
ORANGE = (255, 140, 66)   # MS-Bewusstseinsfarbe Orange
WHITE = (255, 255, 255)
SOFT = (200, 220, 245)

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def background():
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        c = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(3))
        d.line([(0, y), (W, y)], fill=c)
    # Platz fuer Untertitel unten freihalten (y > 1450), Branding oben
    d.rounded_rectangle([60, 90, 300, 150], radius=30, fill=ORANGE)
    d.text((180, 120), "MS erklärt", font=font(BOLD, 34), fill=WHITE, anchor="mm")
    return img, d


def wrap(d, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if d.textlength(test, font=f) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def centered(d, text, y, f, fill=WHITE, max_w=920, gap=1.25):
    for line in wrap(d, text, f, max_w):
        d.text((W / 2, y), line, font=f, fill=fill, anchor="mm")
        y += int(f.size * gap)
    return y


def save(img, name):
    img.save(OUT / name)
    print("slide", name)


# 1 Hook
img, d = background()
centered(d, "Mehr als", 520, font(BOLD, 70), SOFT)
centered(d, "280.000", 680, font(BOLD, 200), ORANGE)
y = centered(d, "Menschen in Deutschland leben mit MS", 900, font(BOLD, 64))
centered(d, "Was ist Multiple Sklerose?", y + 90, font(REG, 52), SOFT)
save(img, "01_hook.png")

# 2 ZNS
img, d = background()
centered(d, "Entzündliche Erkrankung des", 380, font(REG, 54), SOFT)
centered(d, "zentralen Nervensystems", 470, font(BOLD, 70))
# stilisiertes Gehirn + Rueckenmark
d.ellipse([340, 620, 740, 940], outline=ORANGE, width=14)
d.arc([400, 680, 680, 880], 200, 340, fill=ORANGE, width=8)
d.arc([400, 700, 680, 900], 20, 160, fill=ORANGE, width=8)
d.rounded_rectangle([515, 930, 565, 1330], radius=25, fill=ORANGE)
d.text((800, 780), "Gehirn", font=font(BOLD, 48), fill=WHITE, anchor="lm")
d.text((620, 1150), "Rückenmark", font=font(BOLD, 48), fill=WHITE, anchor="lm")
save(img, "02_zns.png")

# 3 Myelin
img, d = background()
centered(d, "Das Immunsystem greift", 360, font(REG, 56), SOFT)
centered(d, "die Myelinschicht an", 450, font(BOLD, 72))
cy = 820
d.line([(80, cy), (1000, cy)], fill=WHITE, width=16)  # Nervenfaser
for i, x in enumerate(range(110, 980, 150)):
    damaged = i in (2, 4)
    col = (120, 120, 140) if damaged else ORANGE
    if damaged:
        d.rounded_rectangle([x, cy - 45, x + 120, cy + 45], radius=40, outline=col, width=6)
        d.text((x + 60, cy - 110), "⚡", font=font(REG, 70), fill=(255, 220, 80), anchor="mm")
    else:
        d.rounded_rectangle([x, cy - 45, x + 120, cy + 45], radius=40, fill=col)
d.text((W / 2, 1000), "intakt          beschädigt", font=font(REG, 44), fill=SOFT, anchor="mm")
centered(d, "Nervensignale werden gestört", 1180, font(BOLD, 60))
save(img, "03_myelin.png")

# 4 Alter / Frauen
img, d = background()
centered(d, "Diagnose meist zwischen", 380, font(REG, 56), SOFT)
centered(d, "20 und 40", 540, font(BOLD, 170), ORANGE)
centered(d, "Jahren", 690, font(BOLD, 64))
d.line([(200, 830), (880, 830)], fill=SOFT, width=3)
centered(d, "Frauen erkranken etwa", 940, font(REG, 56), SOFT)
centered(d, "2 × so häufig", 1080, font(BOLD, 120), ORANGE)
centered(d, "wie Männer", 1210, font(BOLD, 64))
save(img, "04_alter.png")

# 5 Symptome
img, d = background()
centered(d, "Mögliche erste Anzeichen", 330, font(BOLD, 66))
items = ["Sehstörungen", "Kribbeln", "Taubheitsgefühl", "Unsicherheit beim Gehen"]
y = 620
for it in items:
    d.ellipse([150, y - 22, 194, y + 22], fill=ORANGE)
    d.text((230, y), it, font=font(BOLD, 60), fill=WHITE, anchor="lm")
    y += 150
centered(d, "„Krankheit der tausend Gesichter“", y + 60, font(REG, 52), SOFT)
save(img, "05_symptome.png")

# 6 Schuebe
img, d = background()
centered(d, "Zu Beginn bei bis zu", 400, font(REG, 56), SOFT)
centered(d, "90 %", 590, font(BOLD, 220), ORANGE)
centered(d, "schubförmiger Verlauf", 790, font(BOLD, 66))
pts, base = [], 1180
for x in range(100, 981, 8):
    bump = sum(160 * math.exp(-((x - c) ** 2) / 1800) for c in (280, 560, 820))
    pts.append((x, base - bump))
d.line(pts, fill=ORANGE, width=10, joint="curve")
d.line([(100, base), (980, base)], fill=SOFT, width=3)
d.text((W / 2, base + 60), "Schub   ·   Erholung   ·   Schub", font=font(REG, 40), fill=SOFT, anchor="mm")
save(img, "06_schuebe.png")

# 7 Mythen
img, d = background()
centered(d, "MS ist NICHT …", 330, font(BOLD, 80), ORANGE)
y = 540
for it in ["ansteckend", "Muskelschwund", "eine psychische Erkrankung", "automatisch Rollstuhl"]:
    d.text((150, y), "✗", font=font(BOLD, 70), fill=ORANGE, anchor="lm")
    y2 = y
    for line in wrap(d, it, font(BOLD, 60), 760):
        d.text((240, y2), line, font=font(BOLD, 60), fill=WHITE, anchor="lm")
        y2 += 75
    y = y2 + 85
save(img, "07_mythen.png")

# 8 Abschluss
img, d = background()
centered(d, "Nicht heilbar –", 420, font(BOLD, 84))
centered(d, "aber behandelbar", 530, font(BOLD, 84), ORANGE)
centered(d, "Bei Beschwerden: ärztlich abklären lassen", 720, font(REG, 52), SOFT)
d.rounded_rectangle([140, 880, 940, 1060], radius=40, fill=WHITE)
d.text((W / 2, 940), "Infos & Beratung", font=font(REG, 44), fill=BG_TOP, anchor="mm")
d.text((W / 2, 1005), "dmsg.de", font=font(BOLD, 64), fill=BG_TOP, anchor="mm")
centered(d, "Quelle: DMSG Bundesverband · Kein Ersatz für ärztlichen Rat · Erstellt mit KI-Stimme", 1250, font(REG, 32), SOFT, max_w=860)
save(img, "08_ende.png")
