import feedparser
import requests
import json
import os
import sys

# Ensure backend/src is in python path to import db
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

FEEDS = {
    "Good News Network": "https://www.goodnewsnetwork.org/category/news/feed/",
    "Optimist Daily": "https://www.optimistdaily.com/feed/"
}

REDDIT_URL = "https://www.reddit.com/r/UpliftingNews/hot.json?limit=10"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 GoodNewsBot/1.0"

def scrape_rss_feeds():
    stories_inserted = []
    print("Scraping RSS feeds...")
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            print(f"Fetched {len(feed.entries)} entries from {source}")
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                # Strip HTML tags from summary if present
                summary = entry.get("summary", entry.get("description", ""))
                
                # Insert to db
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

def scrape_reddit():
    stories_inserted = []
    print("Scraping /r/UpliftingNews...")
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(REDDIT_URL, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            posts = data.get("data", {}).get("children", [])
            print(f"Fetched {len(posts)} posts from /r/UpliftingNews")
            for post in posts:
                post_data = post.get("data", {})
                if post_data.get("is_self") or post_data.get("stickied"):
                    continue # Skip stickied posts or self-posts
                
                title = post_data.get("title")
                link = post_data.get("url")
                summary = post_data.get("selftext", "")
                if not summary:
                    summary = f"Reddit Uplifting News Post. Source URL: {link}"
                
                story_id = db.insert_story(title, link, "/r/UpliftingNews", summary)
                if story_id:
                    stories_inserted.append({
                        "id": story_id,
                        "title": title,
                        "url": link,
                        "source": "/r/UpliftingNews"
                    })
        else:
            print(f"Failed to fetch Reddit: Status code {response.status_code}")
    except Exception as e:
        print(f"Error scraping Reddit: {e}")
    return stories_inserted

def run_scraper():
    db.init_db()
    rss_stories = scrape_rss_feeds()
    reddit_stories = scrape_reddit()
    all_stories = rss_stories + reddit_stories
    print(f"Scrape completed. Inserted {len(all_stories)} new stories.")
    return all_stories

if __name__ == "__main__":
    run_scraper()
