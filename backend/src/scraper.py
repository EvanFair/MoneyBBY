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
                    story_id = db.insert_story(title, link, "Hacker News", summary)
                    if story_id:
                        stories_inserted.append({
                            "id": story_id,
                            "title": title,
                            "url": link,
                            "source": "Hacker News"
                        })
                        count += 1
            else:
                print(f"  Failed HN fetch for '{query}': Status {response.status_code}")
        except Exception as e:
            print(f"  Error scraping Hacker News for '{query}': {e}")
    return stories_inserted


def scrape_github_trending(topic, limit):
    """Scrape GitHub search API for trending repos with the given topic, created in the last 7 days."""
    stories_inserted = []
    print(f"Scraping GitHub Trending for topic: {topic}...")
    headers = {"User-Agent": USER_AGENT}

    seven_days_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    url = f"https://api.github.com/search/repositories?q=created:>{seven_days_ago}+topic:{topic}&sort=stars&order=desc"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            items = response.json().get("items", [])
            print(f"  Fetched {len(items)} trending repos from GitHub")
            count = 0
            for item in items:
                if count >= limit:
                    break
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
                    count += 1
        else:
            print(f"  Failed GitHub API: Status {response.status_code}")
    except Exception as e:
        print(f"  Error scraping GitHub Trending: {e}")
    return stories_inserted


def scrape_huggingface_papers(api_url, limit):
    """Scrape Hugging Face daily papers API."""
    stories_inserted = []
    print(f"Scraping Hugging Face daily papers from {api_url}...")
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        if response.status_code == 200:
            papers = response.json()
            print(f"  Fetched {len(papers)} daily papers from Hugging Face")
            count = 0
            for paper in papers:
                if count >= limit:
                    break
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
                    count += 1
        else:
            print(f"  Failed Hugging Face API: Status {response.status_code}")
    except Exception as e:
        print(f"  Error scraping Hugging Face: {e}")
    return stories_inserted


def scrape_google_news(queries_csv, limit):
    """Scrape Google News RSS for each query string. Insert up to `limit` total stories across all queries."""
    stories_inserted = []
    seen_titles = set()
    queries = [q.strip() for q in queries_csv.split(",") if q.strip()]
    print(f"Scraping Google News for queries: {queries}...")
    count = 0

    for query in queries:
        if count >= limit:
            break
        try:
            feed_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(feed_url)
            print(f"  Fetched {len(feed.entries)} Google News entries for query: '{query}'")
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
                if title in seen_titles:
                    continue
                seen_titles.add(title)
                link = entry.link
                summary = entry.get("summary", entry.get("description", ""))

                story_id = db.insert_story(title, link, "Google News", summary)
                if story_id:
                    stories_inserted.append({
                        "id": story_id,
                        "title": title,
                        "url": link,
                        "source": "Google News"
                    })
                    count += 1
        except Exception as e:
            print(f"  Error scraping Google News for '{query}': {e}")
    return stories_inserted


def run_scraper():
    db.init_db()
    sources = db.get_sources()
    all_stories = []

    for source in sources:
        if not source.get("enabled"):
            continue

        source_name = source["name"]
        source_url = source["url"]
        source_type = source["type"]
        limit = source.get("volume_limit", 10)

        if source_type == "rss":
            stories = scrape_rss_feed(source_name, source_url, limit)
        elif source_type == "hn":
            stories = scrape_hacker_news(source_url, limit)
        elif source_type == "github":
            stories = scrape_github_trending(source_url, limit)
        elif source_type == "huggingface":
            stories = scrape_huggingface_papers(source_url, limit)
        elif source_type == "google_news":
            stories = scrape_google_news(source_url, limit)
        else:
            print(f"Unknown source type '{source_type}' for source '{source_name}', skipping.")
            continue

        all_stories.extend(stories)

    print(f"Scrape completed. Ingested {len(all_stories)} new unique stories across all sources.")
    return all_stories


if __name__ == "__main__":
    run_scraper()
