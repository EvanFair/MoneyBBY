import os
import requests
import json
import sys
import random
from dotenv import load_dotenv

# Ensure backend/src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

# Load environment variables
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "meta-llama/llama-3-70b-instruct:free")

CATEGORIES = [
    "Model Release",
    "Open Source Repository",
    "Research Paper",
    "Hardware & GPU Infrastructure",
    "Developer Tooling & SDKs",
    "AI SaaS & Consumer Product",
    "Industry & Startups",
    "Robotics & Embodied AI",
    "Safety & Alignment"
]

def clean_story(title, raw_summary):
    if not API_KEY or API_KEY == "your_openrouter_api_key_here":
        # Fallback heuristic classifier for development/offline testing
        is_pos = True
        
        # Simple heuristic mapping for categories
        lower_title = title.lower()
        if "repo" in lower_title or "github" in lower_title:
            cat = "Open Source Repository"
        elif "paper" in lower_title or "research" in lower_title or "arxiv" in lower_title:
            cat = "Research Paper"
        elif "gpu" in lower_title or "nvidia" in lower_title or "hardware" in lower_title or "vram" in lower_title:
            cat = "Hardware & GPU Infrastructure"
        elif "model" in lower_title or "claude" in lower_title or "llama" in lower_title or "gpt" in lower_title:
            cat = "Model Release"
        else:
            cat = random.choice(CATEGORIES)
            
        summary_clean = f"An interesting development in the AI space: {title}. This covers recent advancements that could have significant impacts for builders."
        return {"is_positive": is_pos, "category": cat, "clean_summary": summary_clean}

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = f"""You are a technical editor for an AI news podcast targeting developers and tech enthusiasts.
Your job is to analyze scraped articles and determine if they represent valuable tech news or interesting developments in the AI space.

Analyze the story and output a JSON object with:
1. "is_positive": (boolean) True if the story represents a valuable AI release, research, repo, hardware news, startup news, or dev tool. False if it is unrelated to AI/LLMs/computing, is spam/ad, or lacks actual tech substance.
2. "category": (string) Must be EXACTLY one of these categories: {", ".join(f'"{c}"' for c in CATEGORIES)}.
3. "clean_summary": (string) A 3-4 sentence clean, concise, technical summary written for a host to read aloud on a podcast. Focus on the specifications, capabilities, and the value-add for developers or builders. Keep it highly informative.

Respond ONLY with valid JSON. Do not include markdown formatting or backticks around the JSON."""

    user_content = f"Title: {title}\nRaw Details: {raw_summary}"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            # Ensure category is in valid set, else default
            if parsed.get("category") not in CATEGORIES:
                parsed["category"] = "Model Release"
            return parsed
        else:
            print(f"LLM API Error: Status {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return None

def run_cleaner():
    print("Running AI Technical Cleaner on scraped tech stories...")
    scraped_stories = db.get_stories_by_status("scraped")
    print(f"Found {len(scraped_stories)} new tech stories to clean.")
    
    cleaned_count = 0
    rejected_count = 0
    
    for story in scraped_stories[:15]: # Process top 15 in test cycles
        print(f"Processing: {story['title'][:50]}...")
        cleaned = clean_story(story['title'], story['summary'])
        if cleaned:
            if cleaned.get("is_positive"):
                db.update_story_status(
                    story_id=story['id'],
                    status="approved",
                    clean_summary=cleaned.get("clean_summary"),
                    category=cleaned.get("category")
                )
                print(f"-> APPROVED as [{cleaned.get('category')}]: {cleaned.get('clean_summary')[:80]}...")
                cleaned_count += 1
            else:
                db.update_story_status(story['id'], "rejected")
                print("-> REJECTED (Not tech/spam)")
                rejected_count += 1
        else:
            print("-> Skipped due to API error")
            
    print(f"Cleaner summary: {cleaned_count} approved, {rejected_count} rejected.")

if __name__ == "__main__":
    run_cleaner()
