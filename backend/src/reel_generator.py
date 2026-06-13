"""
reel_generator.py
-----------------
Generate a vertical (1080x1920, 9:16) Instagram/TikTok Reel from a story.

Pipeline (borrowed from video-use patterns):
  1. Download story image → crop/blur to 1080x1920 background
  2. FFmpeg: Ken Burns zoom + text overlays (category pill, headline, branding)
  3. Mix TTS audio or background music
  4. 30ms audio fades at edges (video-use Rule 3)
  5. Loudness normalise to -14 LUFS / -1 dBTP (social-ready, video-use standard)
  6. Burn 2-word UPPERCASE subtitles at safe MarginV (video-use Rule 1)
  7. Output: backend/output/reel_{story_id}.mp4

Requirements:
    pip install Pillow requests python-dotenv
    FFmpeg must be installed (or available via PATH)

Usage:
    python reel_generator.py --story-id 42
"""

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests

try:
    from PIL import Image, ImageFilter, ImageEnhance
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

# ─── Paths ────────────────────────────────────────────────────────────────────
BACKEND_DIR  = Path(__file__).parent.parent
OUTPUT_DIR   = BACKEND_DIR / "output"
AUDIO_DIR    = BACKEND_DIR / "audio"          # optional bg_music.mp3 here
TEMP_DIR     = BACKEND_DIR / "temp_reel"

load_dotenv(BACKEND_DIR / ".env")

# ─── Video-use constants (ported) ─────────────────────────────────────────────
# Social-media loudness standard (YouTube / IG / TikTok / X)
LOUDNORM_I   = -14.0
LOUDNORM_TP  = -1.0
LOUDNORM_LRA = 11.0

# Subtitle style: 2-word UPPERCASE chunks, safe for all platforms
# MarginV=90 clears TikTok/IG UI overlay (~bottom 30%)
SUB_FORCE_STYLE = (
    "FontName=Arial,FontSize=22,Bold=1,"
    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
    "BorderStyle=1,Outline=2,Shadow=0,"
    "Alignment=2,MarginV=90"
)

REEL_W = 1080
REEL_H = 1920
REEL_FPS = 30
REEL_DURATION = 30  # seconds


# ─── FFmpeg helpers ────────────────────────────────────────────────────────────

def _ffmpeg() -> str:
    """Locate ffmpeg binary. Checks PATH then known Windows install paths."""
    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode == 0:
        return "ffmpeg"
    candidates = [
        r"C:\Users\jobbe\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "ffmpeg"

FFMPEG = _ffmpeg()


def _run(cmd: list, description: str = "") -> bool:
    """Run an FFmpeg command. Returns True on success."""
    label = description or cmd[1] if len(cmd) > 1 else "FFmpeg"
    print(f"  [{label}] Running...")
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"  [{label}] FAILED:\n{result.stderr.decode('utf-8', errors='ignore')[-500:]}")
        return False
    return True


# ─── Image helpers ────────────────────────────────────────────────────────────

def _prepare_background(story: dict, output_path: str) -> bool:
    """
    Download the best story image, blur + darken it to 1080x1920.
    Falls back to a solid dark gradient background if no image available.
    """
    images_json = story.get("images_json")
    img_url = None

    if images_json:
        try:
            imgs = json.loads(images_json)
            if isinstance(imgs, list) and imgs:
                # Prefer dict with 'url' key, fall back to plain string
                first = imgs[0]
                img_url = first.get("url") if isinstance(first, dict) else first
        except Exception:
            pass

    if img_url and PIL_AVAILABLE:
        try:
            resp = requests.get(img_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert("RGB")

            # Crop center to 9:16 aspect
            w, h = img.size
            target_aspect = REEL_W / REEL_H
            src_aspect = w / h
            if src_aspect > target_aspect:
                new_w = int(h * target_aspect)
                left = (w - new_w) // 2
                img = img.crop((left, 0, left + new_w, h))
            else:
                new_h = int(w / target_aspect)
                top = (h - new_h) // 2
                img = img.crop((0, top, w, top + new_h))

            img = img.resize((REEL_W, REEL_H), Image.LANCZOS)
            img = img.filter(ImageFilter.GaussianBlur(radius=6))
            img = ImageEnhance.Brightness(img).enhance(0.45)  # Darken for text legibility
            img.save(output_path)
            print(f"  Background image prepared from: {img_url[:60]}")
            return True
        except Exception as e:
            print(f"  Image download/process failed: {e}. Generating solid background.")

    # Fallback: solid dark background via FFmpeg
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x0c0c12:size={REEL_W}x{REEL_H}:duration=1:rate=1",
        "-vframes", "1",
        output_path
    ]
    return _run(cmd, "Background fallback")


def _generate_silent_audio(duration: int, output_path: str) -> bool:
    """Generate a silent audio track of given duration."""
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={duration}",
        "-t", str(duration),
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    return _run(cmd, "Silent audio")


# ─── SRT subtitle builder (video-use style: 2-word UPPERCASE chunks) ──────────

def _build_srt_from_script(script_text: str, duration: int) -> str:
    """
    Turn a plain text script into an SRT file using 2-word UPPERCASE chunks
    timed evenly across the video duration.
    """
    words = re.sub(r'\s+', ' ', script_text).strip().split()
    if not words:
        return ""

    # Group into 2-word chunks (break on sentence punctuation)
    chunks = []
    current = []
    PUNCT = set(".,!?;:")
    for word in words:
        current.append(word)
        ends_punct = word and word[-1] in PUNCT
        if len(current) >= 2 or ends_punct:
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))

    if not chunks:
        return ""

    # Distribute chunks evenly across available duration
    # (keep last 3 seconds clear for CTA/branding)
    usable_duration = max(duration - 3, 5)
    chunk_duration  = usable_duration / len(chunks)

    lines = []
    for i, chunk in enumerate(chunks):
        start = i * chunk_duration
        end   = min(start + chunk_duration - 0.1, usable_duration)
        text  = chunk.upper().rstrip(",;:")
        lines.append(f"{i+1}")
        lines.append(f"{_srt_time(start)} --> {_srt_time(end)}")
        lines.append(text)
        lines.append("")

    return "\n".join(lines)


def _srt_time(seconds: float) -> str:
    ms  = int(round(seconds * 1000))
    h   = ms // 3_600_000; ms %= 3_600_000
    m   = ms // 60_000;    ms %= 60_000
    s   = ms // 1_000;     ms %= 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


# ─── Main reel builder ────────────────────────────────────────────────────────

def generate_reel_for_story(story_id: int, output_path: str = None) -> str | None:
    """
    Generate a 1080x1920 vertical Reel MP4 for a story.
    Returns the output path on success, None on failure.
    """
    story = db.get_story_by_id(story_id)
    if not story:
        print(f"[Reel] Story {story_id} not found.")
        return None

    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = str(OUTPUT_DIR / f"reel_{story_id}.mp4")

    print(f"\n[Reel] Generating reel for story #{story_id}: {story['title'][:60]}")

    # Temporary file paths
    bg_path      = str(TEMP_DIR / f"bg_{story_id}.jpg")
    audio_path   = str(TEMP_DIR / f"audio_{story_id}.mp3")
    pre_norm     = str(TEMP_DIR / f"prenorm_{story_id}.mp4")
    srt_path     = str(TEMP_DIR / f"subs_{story_id}.srt")

    # ── 1. Prepare background image ─────────────────────────────────────────
    if not _prepare_background(story, bg_path):
        print("[Reel] Background preparation failed.")
        return None

    # ── 2. Audio: use TTS episode audio or background music ─────────────────
    bg_music = AUDIO_DIR / "bg_music.mp3"
    audio_ok = False

    if bg_music.exists():
        # Trim/loop bg music to REEL_DURATION
        cmd = [
            FFMPEG, "-y",
            "-stream_loop", "-1", "-i", str(bg_music),
            "-t", str(REEL_DURATION),
            "-af", f"afade=t=in:st=0:d=0.5,afade=t=out:st={REEL_DURATION-0.5}:d=0.5,volume=0.6",
            "-c:a", "aac", "-b:a", "128k",
            audio_path
        ]
        audio_ok = _run(cmd, "BG music trim")

    if not audio_ok:
        audio_ok = _generate_silent_audio(REEL_DURATION, audio_path)

    if not audio_ok:
        print("[Reel] Audio preparation failed.")
        return None

    # ── 3. Build text overlay content ───────────────────────────────────────
    category    = (story.get("category") or "AI & Tech").upper()
    headline    = story.get("title") or "AI Update"
    source_name = story.get("source") or "AIPulse"
    summary     = story.get("clean_summary") or story.get("summary") or headline

    # Truncate headline for overlay legibility (~45 chars, then word-break)
    if len(headline) > 45:
        headline = headline[:45].rsplit(" ", 1)[0] + "…"

    # ── 4. Build SRT subtitles ───────────────────────────────────────────────
    srt_content = _build_srt_from_script(summary, REEL_DURATION)
    if srt_content:
        Path(srt_path).write_text(srt_content, encoding="utf-8")
    else:
        srt_path = None

    # ── 5. FFmpeg: Ken Burns + drawtext overlays → pre-norm video ───────────
    #
    # Ken Burns: slow zoom-in from 1.0x to 1.08x over the full duration
    # drawtext filters (layered, bottom to top in filter chain):
    #   • Semi-transparent dark scrim (bottom half)
    #   • Category pill badge (lime green, top area)
    #   • Main headline (large white bold, center)
    #   • Source credit (small, bottom-left)
    #   • Branding handle (small, bottom-right)

    # Escape text for FFmpeg drawtext
    def esc(s): return s.replace("'", "\\'").replace(":", "\\:").replace(",", "\\,")

    ken_burns = (
        f"scale={REEL_W*2}:{REEL_H*2},"
        f"zoompan=z='min(zoom+0.0008,1.08)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d={REEL_DURATION * REEL_FPS}:s={REEL_W}x{REEL_H}:fps={REEL_FPS}"
    )

    # Scrim: dark gradient over bottom 55%
    scrim = (
        f"drawbox=x=0:y={int(REEL_H*0.45)}:w={REEL_W}:h={int(REEL_H*0.55)}"
        f":color=black@0.65:t=fill"
    )

    # Category pill (top-center green badge)
    pill_y = 140
    pill_text = f"drawtext=text='{esc(category)}':fontcolor=0x0c0c12:fontsize=32:fontface=Arial:bold=1:x=(w-text_w)/2:y={pill_y}:box=1:boxcolor=0xC4FF00@1.0:boxborderw=18"

    # Main headline (center-screen, large white)
    headline_y = int(REEL_H * 0.35)
    # Split headline at ~25 chars for 2-line display
    if len(headline) > 25:
        split_pt = headline[:25].rsplit(" ", 1)
        hl_line1 = split_pt[0] if len(split_pt) > 1 else headline[:25]
        hl_line2 = headline[len(hl_line1):].strip()
    else:
        hl_line1 = headline
        hl_line2 = ""

    draw_hl1 = (
        f"drawtext=text='{esc(hl_line1)}':fontcolor=white:fontsize=68:fontface=Arial"
        f":bold=1:x=(w-text_w)/2:y={headline_y}:shadowcolor=black@0.8:shadowx=3:shadowy=3"
    )
    draw_hl2 = ""
    if hl_line2:
        draw_hl2 = (
            f"drawtext=text='{esc(hl_line2)}':fontcolor=white:fontsize=68:fontface=Arial"
            f":bold=1:x=(w-text_w)/2:y={headline_y+90}:shadowcolor=black@0.8:shadowx=3:shadowy=3"
        )

    # AIPulse brand mark (top-left)
    brand_txt = (
        f"drawtext=text='⚡ AIPulse':fontcolor=0xC4FF00:fontsize=36:fontface=Arial"
        f":bold=1:x=40:y=50"
    )

    # Source credit (bottom-left)
    source_txt = (
        f"drawtext=text='Source\\: {esc(source_name)}':fontcolor=white@0.7:fontsize=28"
        f":fontface=Arial:x=40:y=h-80"
    )

    # Follow CTA (bottom-right)
    cta_txt = (
        f"drawtext=text='Follow for daily AI':fontcolor=0xC4FF00:fontsize=28"
        f":fontface=Arial:bold=1:x=w-text_w-40:y=h-80"
    )

    # Chain all filters
    vf_parts = [ken_burns, scrim, brand_txt, pill_text, draw_hl1]
    if draw_hl2:
        vf_parts.append(draw_hl2)
    vf_parts += [source_txt, cta_txt]
    vf_filter = ",".join(vf_parts)

    # 30ms audio fades at edges (video-use Rule 3)
    af_filter = f"afade=t=in:st=0:d=0.03,afade=t=out:st={REEL_DURATION-0.03:.3f}:d=0.03"

    cmd_video = [
        FFMPEG, "-y",
        "-loop", "1", "-i", bg_path,
        "-i", audio_path,
        "-vf", vf_filter,
        "-af", af_filter,
        "-t", str(REEL_DURATION),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(REEL_FPS),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        pre_norm
    ]

    if not _run(cmd_video, "Video render"):
        print("[Reel] Video render failed.")
        return None

    # ── 6. Burn SRT subtitles (video-use Rule 1: subtitles LAST) ────────────
    sub_output = pre_norm
    if srt_path and os.path.exists(srt_path):
        sub_out = str(TEMP_DIR / f"subbed_{story_id}.mp4")
        srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
        cmd_subs = [
            FFMPEG, "-y",
            "-i", pre_norm,
            "-vf", f"subtitles='{srt_escaped}':force_style='{SUB_FORCE_STYLE}'",
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-movflags", "+faststart",
            sub_out
        ]
        if _run(cmd_subs, "Subtitle burn"):
            sub_output = sub_out
        else:
            print("[Reel] Subtitle burn failed — continuing without subtitles.")

    # ── 7. Loudness normalise to -14 LUFS (video-use social standard) ───────
    print("  [Loudnorm] Normalising to -14 LUFS / -1 dBTP...")
    norm_ok = _loudnorm_two_pass(sub_output, output_path)
    if not norm_ok:
        # Fallback: just copy without normalisation
        import shutil as _sh
        _sh.copy2(sub_output, output_path)
        print("  [Loudnorm] Skipped — copied as-is.")

    # ── 8. Cleanup temp files ────────────────────────────────────────────────
    for f in [bg_path, audio_path, pre_norm,
              str(TEMP_DIR / f"subbed_{story_id}.mp4")]:
        try:
            if os.path.exists(f):
                os.remove(f)
        except Exception:
            pass

    if os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[Reel] Done: {output_path} ({size_mb:.1f} MB)")
        db.update_story_reel_path(story_id, output_path)
        return output_path

    print("[Reel] Output file not found after render.")
    return None


# ─── Loudness normalisation (ported from video-use helpers/render.py) ─────────

def _measure_loudness(video_path: str) -> dict | None:
    filter_str = f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}:print_format=json"
    proc = subprocess.run(
        [FFMPEG, "-y", "-hide_banner", "-nostats", "-i", video_path,
         "-af", filter_str, "-vn", "-f", "null", "-"],
        capture_output=True, text=True
    )
    stderr = proc.stderr
    start, end = stderr.rfind("{"), stderr.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        data = json.loads(stderr[start:end+1])
    except json.JSONDecodeError:
        return None
    needed = {"input_i", "input_tp", "input_lra", "input_thresh", "target_offset"}
    return data if needed.issubset(data) else None


def _loudnorm_two_pass(input_path: str, output_path: str) -> bool:
    print(f"  [Loudnorm pass 1] Measuring {Path(input_path).name}...")
    m = _measure_loudness(input_path)
    if m is None:
        # One-pass fallback
        f = f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
    else:
        print(f"  Measured: I={m['input_i']} LUFS  TP={m['input_tp']}")
        f = (
            f"loudnorm=I={LOUDNORM_I}:TP={LOUDNORM_TP}:LRA={LOUDNORM_LRA}"
            f":measured_I={m['input_i']}:measured_TP={m['input_tp']}"
            f":measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}"
            f":offset={m['target_offset']}:linear=true"
        )

    cmd = [
        FFMPEG, "-y", "-hide_banner", "-nostats",
        "-i", input_path,
        "-c:v", "copy",
        "-af", f,
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        output_path
    ]
    return _run(cmd, "Loudnorm pass 2")


# ─── CLI ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate an Instagram Reel from a story")
    parser.add_argument("--story-id", type=int, required=True, help="Story ID from aipulse.db")
    parser.add_argument("--output",   type=str, default=None,  help="Output MP4 path (optional)")
    args = parser.parse_args()

    result = generate_reel_for_story(args.story_id, args.output)
    if result:
        print(f"\nReel ready: {result}")
    else:
        print("\nReel generation failed.")
        sys.exit(1)
