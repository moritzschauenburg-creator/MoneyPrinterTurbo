"""Setzt Folien, Sprachaufnahme und Untertitel zum fertigen 9:16-Video zusammen.

Zeiten stammen aus `ffmpeg silencedetect` auf voice.mp3 (Pausen zwischen Saetzen).
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
FPS = 30
XF = 0.4  # Ueberblendung in Sekunden

# (Folie, Start, Ende) in Sekunden – Schnitt jeweils in der Mitte einer Sprechpause
SLIDES = [
    ("01_hook.png", 0.0, 7.8),
    ("02_zns.png", 7.8, 14.5),
    ("03_myelin.png", 14.5, 23.2),
    ("04_alter.png", 23.2, 31.3),
    ("05_symptome.png", 31.3, 42.75),
    ("06_schuebe.png", 42.75, 47.3),
    ("07_mythen.png", 47.3, 56.7),
    ("08_ende.png", 56.7, 70.0),
]

# Untertitel: (Start, Ende, Text) – Sprechsegmente aus silencedetect
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


def ts(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def write_ass(path):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,62,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,3,18,0,2,90,90,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [f"Dialogue: 0,{ts(a)},{ts(b)},Default,,0,0,0,,{t}" for a, b, t in SUBS]
    path.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")


def main():
    ass = HERE / "untertitel.ass"
    write_ass(ass)

    cmd = ["ffmpeg", "-y", "-v", "error"]
    n = len(SLIDES)
    for i, (img, a, b) in enumerate(SLIDES):
        dur = (b - a) + (XF if i < n - 1 else 0)
        cmd += ["-loop", "1", "-t", f"{dur:.3f}", "-i", str(HERE / "slides" / img)]
    cmd += ["-i", str(HERE / "voice.mp3")]

    parts = []
    for i, (img, a, b) in enumerate(SLIDES):
        dur = (b - a) + (XF if i < n - 1 else 0)
        frames = int(dur * FPS)
        # sanfter Zoom 100 % -> 104 % (Ken-Burns-Effekt)
        parts.append(
            f"[{i}:v]scale=2160:3840,zoompan=z='1+0.04*on/{frames}':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s=1080x1920:fps={FPS},"
            f"setsar=1,format=yuv420p[v{i}]"
        )
    prev, offset = "v0", 0.0
    for i in range(1, n):
        offset += SLIDES[i - 1][2] - SLIDES[i - 1][1]
        out = f"x{i}"
        parts.append(f"[{prev}][v{i}]xfade=transition=fade:duration={XF}:offset={offset:.3f}[{out}]")
        prev = out
    parts.append(f"[{prev}]ass={ass}[vout]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[vout]", "-map", f"{n}:a",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-af", "apad=pad_dur=2",
        "-t", f"{SLIDES[-1][2]:.2f}", "-movflags", "+faststart",
        str(HERE / "MS_erklaert_9x16.mp4"),
    ]
    subprocess.run(cmd, check=True)
    print("fertig:", HERE / "MS_erklaert_9x16.mp4")


if __name__ == "__main__":
    main()
