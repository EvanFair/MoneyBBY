import sqlite3
import os
import json
import asyncio
import sys
import subprocess
import edge_tts

# Ensure backend/src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

VOICES = {
    "Alex": "en-US-AndrewNeural", # Clear professional host
    "Joy": "en-US-EmmaNeural",    # Friendly, cheerful female
    "Bob": "en-US-BrianNeural"    # Calm, analytical male
}

async def synthesize_text_async(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def synthesize_text(text, voice, output_path):
    try:
        asyncio.run(synthesize_text_async(text, voice, output_path))
        return True
    except Exception as e:
        print(f"Error synthesizing text: {e}")
        return False

def concat_mp3_binary(file_list, output_path):
    """
    Stitches multiple MP3 files together by directly concatenating their binary frames.
    No external dependencies required. Very fast and robust.
    """
    try:
        with open(output_path, "wb") as outfile:
            for fname in file_list:
                if os.path.exists(fname):
                    with open(fname, "rb") as infile:
                        outfile.write(infile.read())
        return True
    except Exception as e:
        print(f"Binary MP3 concatenation failed: {e}")
        return False

def get_ffmpeg_path():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return "ffmpeg"
    except FileNotFoundError:
        winget_path = r"C:\Users\jobbe\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
        if os.path.exists(winget_path):
            return winget_path
    return "ffmpeg"

def concat_mp3_ffmpeg(file_list, output_path):
    """
    Stitches multiple MP3 files using FFmpeg if available.
    """
    # Create temp concat list file
    list_file_path = "temp_concat_list.txt"
    try:
        with open(list_file_path, "w", encoding="utf-8") as f:
            for fname in file_list:
                # FFmpeg requires escaping single quotes and using absolute paths
                abs_path = os.path.abspath(fname).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")
        
        ffmpeg_bin = get_ffmpeg_path()
        cmd = [ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", output_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Clean up list file
        if os.path.exists(list_file_path):
            os.remove(list_file_path)
            
        return result.returncode == 0
    except Exception as e:
        print(f"FFmpeg MP3 concatenation failed: {e}")
        if os.path.exists(list_file_path):
            os.remove(list_file_path)
        return False


def generate_audio_for_episode(episode_id):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"Episode with ID {episode_id} not found.")
        return None
        
    episode = dict(row)
    script = json.loads(episode["script_json"])
    
    print(f"Synthesizing audio for Episode {episode_id}: '{episode['title']}'...")
    
    temp_files = []
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(backend_dir, "temp_audio")
    os.makedirs(temp_dir, exist_ok=True)
    
    for idx, turn in enumerate(script):
        speaker = turn["speaker"]
        text = turn["text"]
        voice = VOICES.get(speaker, "en-US-AndrewNeural")
        
        temp_file = os.path.join(temp_dir, f"line_{idx}.mp3")
        print(f"-> Synthesizing line {idx} ({speaker})...")
        
        success = synthesize_text(text, voice, temp_file)
        if success:
            temp_files.append(temp_file)
            
    if not temp_files:
        print("Error: No audio segments were synthesized.")
        return None
        
    # Final output path
    output_dir = os.path.join(backend_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"episode_{episode_id}.mp3")
    
    # Try FFmpeg first, fallback to binary concat
    print("Stitching audio segments...")
    success = concat_mp3_ffmpeg(temp_files, output_path)
    if not success:
        print("FFmpeg not available or failed. Falling back to binary concatenation...")
        success = concat_mp3_binary(temp_files, output_path)
        
    # Clean up temp files
    for fname in temp_files:
        try:
            os.remove(fname)
        except Exception:
            pass
            
    if success:
        print(f"Audio file created successfully: {output_path}")
        # Update episode status
        conn = db.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE episodes SET audio_path = ?, status = 'audio_ready' WHERE id = ?",
            (output_path, episode_id)
        )
        conn.commit()
        conn.close()
        return output_path
    else:
        print("Stitching audio failed.")
        return None

if __name__ == "__main__":
    # Test audio generation for Episode 1
    generate_audio_for_episode(1)
