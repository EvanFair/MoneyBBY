import sqlite3
import os
import json
import sys
import subprocess

# Ensure backend/src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

def get_ffmpeg_path():
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return "ffmpeg"
    except FileNotFoundError:
        winget_path = r"C:\Users\jobbe\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe"
        if os.path.exists(winget_path):
            return winget_path
    return "ffmpeg"

def generate_video_for_episode(episode_id, background_image_path=None):
    conn = db.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        print(f"Episode {episode_id} not found in database.")
        return None
        
    episode = dict(row)
    audio_path = episode.get("audio_path")
    
    if not audio_path or not os.path.exists(audio_path):
        print(f"Error: Audio file not found or not yet generated for Episode {episode_id}.")
        return None
        
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. Handle background image
    if not background_image_path or not os.path.exists(background_image_path):
        default_bg_path = os.path.join(backend_dir, "static", "default_bg.jpg")
        if not os.path.exists(default_bg_path):
            print("Warning: No background image found. Placing default solid dark background.")
            try:
                from PIL import Image
                img = Image.new('RGB', (1920, 1080), color=(18, 18, 24)) # Sleek dark blue/grey
                os.makedirs(os.path.dirname(default_bg_path), exist_ok=True)
                img.save(default_bg_path)
                print("Generated a sleek default solid dark background image at:", default_bg_path)
            except ImportError:
                print("PIL library not installed. Cannot auto-generate default_bg.jpg.")
                return None
        background_image_path = default_bg_path
        
    output_dir = os.path.join(backend_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_video_path = os.path.join(output_dir, f"episode_{episode_id}.mp4")
    
    print(f"Rendering video for Episode {episode_id} using FFmpeg...")
    print(f"Audio: {audio_path}")
    print(f"Visual: {background_image_path}")
    
    ffmpeg_bin = get_ffmpeg_path()
    
    # FFmpeg command to combine static image + audio into MP4
    cmd = [
        ffmpeg_bin, "-y",
        "-loop", "1",
        "-i", background_image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        output_video_path
    ]
    
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode == 0:
            print(f"Video rendered successfully: {output_video_path}")
            
            # Update database status
            conn = db.get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE episodes SET video_path = ?, status = 'video_ready' WHERE id = ?",
                (output_video_path, episode_id)
            )
            conn.commit()
            conn.close()
            return output_video_path
        else:
            print(f"FFmpeg rendering failed. Return code: {result.returncode}")
            print(f"Error: {result.stderr.decode('utf-8', errors='ignore')}")
            return None
    except Exception as e:
        print(f"Error executing FFmpeg: {e}")
        return None

if __name__ == "__main__":
    generate_video_for_episode(1)
