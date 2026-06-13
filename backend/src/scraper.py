import feedparser
import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta

# Ensure backend/src is in python path to import db
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def scrape_rss_feed(source_name, feed_url, limit):
    """Scrape a single RSS feed and insert up to `limit` stories."""
    stories_inserted = []
    print(f"Scraping RSS feed: {source_name} ({feed_url})...")
    try:
        feed = feedparser.parse(feed_url)
        print(f"  Fetched {len(feed.entries)} entries from {source_name}")
        count = 0
        for entry in feed.entries:
            if count >= limit:
                break
            # Filter by date (last 7 days)
            published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
            if published_parsed:
                dt = datetime.fromtimestamp(time.mktime(published_parsed))
                if dt < datetime.now() - timedelta(days=7):
                    continue

            title = entry.title
            link = entry.link
            summary = entry.get("summary", entry.get("description", ""))

            story_id = db.insert_story(title, link, source_name, summary)
            if story_id:
                stories_inserted.append({
                    "id": story_id,
                    "title": title,
                    "url": link,
                    "source": source_name
                })
                count += 1
    except Exception as e:
        print(f"  Error scraping RSS feed {source_name}: {e}")
    return stories_inserted


def scrape_hacker_news(keywords_csv, limit):
    """Scrape Hacker News for stories matching keywords. Insert up to `limit` total (deduped)."""
    stories_inserted = []
    seen_titles = set()
    print(f"Scraping Hacker News for keywords: {keywords_csv}...")
    headers = {"User-Agent": USER_AGENT}
    keywords = [kw.strip() for kw in keywords_csv.split(",") if kw.strip()]
    seven_days_ago_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    count = 0

    for query in keywords:
        if count >= limit:
            break
        try:
            url = f"https://hn.algolia.com/api/v1/search?tags=story&query={query}&restrictSearchableAttributes=title&numericFilters=created_at_i>{seven_days_ago_ts}"
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                hits = response.json().get("hits", [])
                print(f"  Fetched {len(hits)} Hacker News stories for query: '{query}'")
                for hit in hits:
                    if count >= limit:
                        break
                    title = hit.get("title")
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)
                    link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                    points = hit.get("points", 0)

                    if points < 5:
                        continue

                    summary = f"Hacker News discussion. Points: {points}. Comments: {hit.get('num_comments')}"
       