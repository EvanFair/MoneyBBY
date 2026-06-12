import feedparser
import requests
import json
import os
import sys
from datetime import datetime, timedelta

# Ensure backend/src is in python path to import db
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

RSS_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "ArXiv Machine Learning": "http://export.arxiv.org/rss/cs.CL"
}

HN_API_URL = "https://hn.algolia.com/api/v1/search?tags=story&query={query}&restrictSearchableAttributes=title"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def scrape_rss_feeds():
    stories_inserted = []
    print("Scraping Tech & AI RSS feeds...")
    for source, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            print(f"Fetched {len(feed.entries)} entries from {source}")
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                summary = entry.get("summary", entry.get("description", ""))
                
                story_id = db.insert_story(title, link, source, summary)
                if story_id:
                    stories_inserted.append({
                        "id": story_id,
                        "title": title,
                        "url": link,
                        "source": source
                    })
        except Exception as e:
            print(f"Error scraping RSS feed {source} ({url}): {e}")
    return stories_inserted

def scrape_hacker_news():
    stories_inserted = []
    print("Scraping Hacker News for AI topics...")
    headers = {"User-Agent": USER_AGENT}
    # Query for multiple AI relevant keywords
    queries = ["AI", "LLM", "GPU", "Claude", "Gemini", "OpenAI"]
    
    for query in queries:
        try:
            url = HN_API_URL.format(query=query)
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                hits = response.json().get("hits", [])
                print(f"Fetched {len(hits)} Hacker News stories for query: '{query}'")
                for hit in hits:
                    title = hit.get("title")
                    link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                    points = hit.get("points", 0)
                    
                    # Only insert stories with a minimum rating or interest
                    if points < 5:
                        continue
                        
                    summary = f"Hacker News discussion. Points: {points}. Comments: {hit.get('num_comments')}"
                    story_id = db.insert_story(title, link, "Hacker News", summary)
                    if story_id:
                        stories_inserted.append({
                            "id": story_id,
                            "title": title,
                            "url": link,
                            "source": "Hacker News"
                        })
            else:
                print(f"Failed HN fetch for '{query}': Status {response.status_code}")
        except Exception as e:
            print(f"Error scraping Hacker News for '{query}': {e}")
    return stories_inserted

def scrape_github_trending():
    stories_inserted = []
    print("Scraping GitHub for trending AI repositories...")
    headers = {"User-Agent": USER_AGENT}
    
    # Query GitHub search API for top starred repos created recently with topic 'ai' or 'llm'
    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=created:>{seven_days_ago}+topic:ai&sort=stars&order=desc"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            print(f"Fetched {len(items)} trending AI repositories from GitHub")
            for item in items:
                title = f"New Trending Repo: {item.get('name')}"
                link = item.get("html_url")
                description = item.get("description", "")
                stars = item.get("stargazers_count", 0)
                lang = item.get("language", "Unknown")
                
                summary = f"GitHub Repository: {description}. Language: {lang}. Stars: {stars}."
                story_id = db.insert_story(title, link, "GitHub Trending", summary)
                if story_id:
                    stories_inserted.append({
                        "id": story_id,
                        "title": title,
                        "url": link,
                        "source": "GitHub Trending"
                    })
        else:
            print(f"Failed GitHub API: Status {response.status_code}")
    except Exception as e:
        print(f"Error scraping GitHub Trending: {e}")
    return stories_inserted

def scrape_huggingface_papers():
    stories_inserted = []
    print("Scraping Hugging Face daily papers...")
    headers = {"User-Agent": USER_AGENT}
    url = "https://huggingface.co/api/daily_papers"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            papers = response.json()
            print(f"Fetched {len(papers)} daily papers from Hugging Face")
            for paper in papers[:10]: # Process top 10 papers
                paper_details = paper.get("paper", {})
                title = f"AI Research Paper: {paper_details.get('title')}"
                paper_id = paper_details.get("id")
                link = f"https://huggingface.co/papers/{paper_id}"
                upvotes = paper.get("upvotes", 0)
                summary = paper_details.get("summary", f"Trending AI research paper with {upvotes} Hugging Face upvotes.")
                
                story_id = db.insert_story(title, link, "Hugging Face", summary)
                if story_id:
                    stories_inserted.append({
                        "id": story_id,
                        "title": title,
                        "url": link,
                        "source": "Hugging Face"
                    })
        else:
            print(f"Failed Hugging Face API: Status {response.status_code}")
    except Exception as e:
        print(f"Error scraping Hugging Face: {e}")
    return stories_inserted

def run_scraper():
    db.init_db()
    rss_stories = scrape_rss_feeds()
    hn_stories = scrape_hacker_news()
    github_stories = scrape_github_trending()
    hf_stories = scrape_huggingface_papers()
    
    all_stories = rss_stories + hn_stories + github_stories + hf_stories
    print(f"Scrape completed. Ingested {len(all_stories)} new unique stories across all sources.")
    return all_stories

if __name__ == "__main__":
    run_scraper()
