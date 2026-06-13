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

PERSONALITIES_DIR = os.path.join(backend_dir, "personalities")

def load_personality(filename):
    path = os.path.join(PERSONALITIES_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return f"Role: {filename.split('_')[1].split('.')[0]}"

def run_agent_turn(agent_name, personality_prompt, context_story, dialogue_history):
    if not API_KEY or API_KEY == "your_openrouter_api_key_here":
        # Fallback template-based responses for local testing
        if agent_name == "Alex":
            if len(dialogue_history) == 0:
                return f"Welcome back to AIPulse. Let's talk about our next story: {context_story['title']}. Here is what happened: {context_story['clean_summary']}"
            else:
                return f"Thanks for those insights, everyone. Let's move on to the next segment."
        elif agent_name == "Joy":
            return f"Oh, that is absolutely wonderful! It warms my heart to see how people and animals can help each other like that. We need more wholesome news like this every single day."
        elif agent_name == "Bob":
            return f"From a practical standpoint, this outcome was only possible because they planned the logistics properly and used the correct tools. The data shows this will save resources long-term."
        return "Interesting point."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    # Format dialogue history for the prompt
    history_str = ""
    for turn in dialogue_history:
        history_str += f"{turn['speaker']}: \"{turn['text']}\"\n"

    system_prompt = f"""You are acting as an AI host on a news podcast.
Here is your personality configuration:
{personality_prompt}

Guidelines:
- Read the story details and the conversation history.
- Write your next turn in the conversation.
- You MUST stay in character.
- Speak naturally. React directly to what the other hosts said.
- Output ONLY your spoken text. Do not include your name prefix (e.g. do NOT write 'Joy: ...' or 'Bob: ...'). Just output the dialogue text itself.
- Keep your response brief, between 2 to 4 sentences."""

    user_content = f"""Story Details:
Title: {context_story['title']}
Category: {context_story['category']}
Summary: {context_story['clean_summary']}

Conversation History so far:
{history_str if history_str else "[Conversation starting now]"}

Write your next line:"""

    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        else:
            print(f"Agent turn failed for {agent_name}: {response.status_code}")
            return f"[Error generating response for {agent_name}]"
    except Exception as e:
        print(f"Error in agent turn: {e}")
        return f"[Connection error for {agent_name}]"

def generate_script_for_stories(stories):
    # Load personality prompts
    anchor_persona = load_personality("personality_anchor.md")
    optimist_persona = load_personality("personality_optimist.md")
    realist_persona = load_personality("personality_realist.md")

    script = []
    
    # 1. Episode Intro
    intro_story = stories[0] if stories else {"title": "Today's AI News", "clean_summary": "", "category": "General"}
    intro_prompt = f"{anchor_persona}\n\nTask: Introduce the podcast episode 'AIPulse' and welcome the audience."
    intro_line = run_agent_turn("Alex", intro_prompt, intro_story, [])
    script.append({"speaker": "Alex", "text": intro_line})

    # 2. Process each story
    for idx, story in enumerate(stories):
        # Alex introduces/reads the story
        alex_intro_prompt = f"{anchor_persona}\n\nTask: Introduce this story and summarize it briefly for Joy and Bob to discuss."
        alex_line = run_agent_turn("Alex", alex_intro_prompt, story, script)
        script.append({"speaker": "Alex", "text": alex_line})

        # Joy reacts (Optimist)
        joy_line = run_agent_turn("Joy", optimist_persona, story, script)
        script.append({"speaker": "Joy", "text": joy_line})

        # Bob reacts (Realist)
        bob_line = run_agent_turn("Bob", realist_persona, script[-1] if len(script) > 0 else story, script)
        script.append({"speaker": "Bob", "text": bob_line})

    # 3. Episode Outro
    outro_prompt = f"{anchor_persona}\n\nTask: Wrap up the episode, thank the listeners, and sign off."
    outro_line = run_agent_turn("Alex", outro_prompt, stories[-1] if stories else intro_story, script)
    script.append({"speaker": "Alex", "text": outro_line})

    return script

def create_daily_episode(episode_title="Daily AIPulse Tech Round-up"):
    # Fetch approved stories
    approved = db.get_stories_by_status("approved")
    if not approved:
        print("No approved stories found. Please run scraper and clean/approve stories first.")
        return None
        
    print(f"Generating episode '{episode_title}' using {len(approved)} approved stories...")
    script = generate_script_for_stories(approved)
    
    # Save to SQLite
    episode_id = db.create_episode(episode_title, script)
    print(f"Episode created successfully! ID: {episode_id}")
    
    # Update stories status to 'used' so they aren't reused
    for story in approved:
        db.update_story_status(story["id"], "used")
        
    return episode_id, script

if __name__ == "__main__":
    create_daily_episode()
