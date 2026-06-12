import os
import requests
import json
import sys
from dotenv import load_dotenv

# Ensure backend/src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

# Load environment variables
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "meta-llama/llama-3-70b-instruct:free")

def clean_story(title, raw_summary):
    # If no API key is set, we will use a fallback rule-based mechanism for development testing
    if not API_KEY or API_KEY == "your_openrouter_api_key_here":
        print("Warning: No API Key found in .env. Using fallback mock classifier.")
        # Simple heuristic fallback
        is_pos = True
        cat = "General Wholesome"
        summary_clean = f"A wholesome story: {title}. {raw_summary[:150]}..."
        return {"is_positive": is_pos, "category": cat, "clean_summary": summary_clean}

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    system_prompt = """You are an editor for a Wholesome/Good News podcast.
Your job is to analyze scraped stories and determine if they are suitable.

Analyze the story and output a JSON object with:
1. "is_positive": (boolean) True if the story is genuinely uplifting, wholesome, inspiring, or good news. False if it has depressing undercurrents (e.g. death, tragedy, war, crime), is politically polarizing, or is commercial advertisement/spam.
2. "category": (string) One of: "Animals", "Human Kindness", "Nature & Environment", "Science & Innovation", "General Wholesome".
3. "clean_summary": (string) A 3-4 sentence clean, engaging, narrative-driven summary written for a host to read aloud. Avoid news jargon, clickbait headlines, and ads. Focus on the human story and wholesome outcome.

Respond ONLY with valid JSON. Do not include markdown formatting or backticks around the JSON."""

    user_content = f"Title: {title}\nRaw Text: {raw_summary}"

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.2
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            content = result["choices"][0]["message"]["content"].strip()
            
            # Clean up potential markdown formatting backticks if the LLM outputted them
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            return json.loads(content)
        else:
            print(f"LLM API Error: Status {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Error calling LLM: {e}")
        return None

def run_cleaner():
    print("Running AI Cleaner on scraped stories...")
    # Fetch stories with status 'scraped'
    scraped_stories = db.get_stories_by_status("scraped")
    print(f"Found {len(scraped_stories)} new stories to clean.")
    
    cleaned_count = 0
    rejected_count = 0
    
    for story in scraped_stories[:10]: # Process top 10 for safety/speed in sprint testing
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
                print("-> REJECTED (Not wholesome/spam)")
                rejected_count += 1
        else:
            print("-> Skipped due to API error")
            
    print(f"Cleaner summary: {cleaned_count} approved, {rejected_count} rejected.")

if __name__ == "__main__":
    run_cleaner()
