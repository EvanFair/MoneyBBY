"""
tts.py — Text-to-speech synthesis for AIPulse episodes using edge-tts.
Script turns use keys: {"agent": "Alex", "line": "...", "voice": "en-US-AndrewNeural"}
"""
import os
import json
import asyncio
import sys
import subprocess
import edge_tts

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

# Default voice fallbacks per agent
VOICES = {
    "Alex": "en-US-AndrewNeural",
    "Joy":  "en-US-EmmaNeural",
    "Bob":  "en-US-BrianNeural",
}


async def _synthesize_async(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def synthesize_text(text, voice, output_path):
    try:
        asyncio.run(_synthesize_async(text, voice, output_path))
        return True
    except Exception as e:
        print(f"  TTS error: {e}")
        return False


def get_ffmpeg_path():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return "ffmpeg"
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    # Common Windows WinGet path
    winget = (r"C:\Users\Public\AppData\Local\Microsoft\WinGet\Packages"
              r"\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
              r"\ffmpeg-7.1-full_build\bin\ffmpeg.exe")
    if os.path.exists(winget):
        return winget
    return "ffmpeg"


def _concat_ffmpeg(file_list, output_path):
    list_file = output_path + "_concat.txt"
    try:
        with open(list_file, "w", encoding="utf-8") as f:
            for fname in file_list:
                abs_path = os.path.abspath(fname).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        cmd = [get_ffmpeg_path(), "-y", "-f", "concat", "-safe", "0",
               "-i", list_file, "-c", "copy", output_path]
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return r.returncode == 0
    except Exception as e:
        print(f"  FFmpeg concat failed: {e}")
        return False
    finally:
        if os.path.exists(list_file):
            os.remove(list_file)


def _concat_binary(file_list, output_path):
    try:
        with open(output_path, "wb") as out:
            for fname in file_list:
                if os.path.exists(fname):
                    with open(fname, "rb") as inp:
                        out.write(inp.read())
        return True
    except Exception as e:
        print(f"  Binary concat failed: {e}")
        return False


def generate_audio_for_episode(episode_id):
    """Generate MP3 audio for an episode. Returns output path or None."""
    episode = db.get_episode_by_id(episode_id)
    if not episode:
        print(f"Episode {episode_id} not found.")
        return None

    script = json.loads(episode["script_json"])
    print(f"Synthesizing audio for Episode {episode_id}: '{episode['title']}'...")

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir  = os.path.join(backend_dir, "temp_audio")
    output_dir = os.path.join(backend_dir, "output")
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    temp_files = []
    for idx, turn in enumerate(script):
        # Support both key names for compatibility
        agent = turn.get("agent") or turn.get("speaker", "Alex")
        line  = turn.get("line")  or turn.get("text", "")
        voice = turn.get("voice") or VOICES.get(agent, "en-US-AndrewNeural")

        if not line.strip():
            continue

        tmp = os.path.join(temp_dir, f"ep{episode_id}_line{idx}.mp3")
        print(f"  Line {idx} [{agent}]: {line[:60]}...")
        if synthesize_text(line, voice, tmp):
            temp_files.append(tmp)

    if not temp_files:
        print("  No audio segments synthesized.")
        return None

    output_path = os.path.join(output_dir, f"episode_{episode_id}.mp3")
    print("  Concatenating segments...")
    ok = _concat_ffmpeg(temp_files, output_path) or _concat_binary(temp_files, output_path)

    for f in temp_files:
        try: os.remove(f)
        except: pass

    if ok and os.path.exists(output_path):
        print(f"  Audio ready: {output_path}")
        conn = db.get_db_connection()
        conn.execute("UPDATE episodes SET audio_path=?, status='audio_ready' WHERE id=?",
                     (output_path, episode_id))
        conn.commit(); conn.close()
        return output_path
    else:
        print("  Audio generation failed.")
        return None


if __name__ == "__main__":
    db.init_db()
    generate_audio_for_episode(1)
