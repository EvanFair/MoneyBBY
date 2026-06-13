import feedparser
import requests
import json
import os
import sys
import time
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def scrape_rss_feed(source_name, feed_url, limit):
    stories_inserted = []
    print(f"Scraping RSS: {source_name}...")
    try:
        feed = feedparser.parse(feed_url)
        print(f"  Fetched {len(feed.entries)} entries")
        count = 0
        for entry in feed.entries:
            if count >= limit:
                break
            published_parsed = entry.get("published_parsed") or entry.get("updated_parsed")
            if published_parsed:
                dt = datetime.fromtimestamp(time.mktime(published_parsed))
                if dt < datetime.now() - timedelta(days=7):
                    continue
            title = getattr(entry, 'title', '')
            link  = getattr(entry, 'link', '')
            summary = entry.get("summary", entry.get("description", ""))
            if not title or not link:
                continue
            story_id = db.insert_story(title, link, source_name, summary)
            if story_id:
                stories_inserted.append({"id": story_id, "title": title, "url": link, "source": source_name})
                count += 1
    except Exception as e:
        print(f"  Error scraping RSS {source_name}: {e}")
    return stories_inserted


def scrape_hacker_news(keywords_csv, limit):
    stories_inserted = []
    seen_titles = set()
    print(f"Scraping Hacker News: {keywords_csv}...")
    headers = {"User-Agent": USER_AGENT}
    keywords = [kw.strip() for kw in keywords_csv.split(",") if kw.strip()]
    seven_days_ago_ts = int((datetime.now() - timedelta(days=7)).timestamp())
    count = 0

    for query in keywords:
        if count >= limit:
            break
        try:
            url = (f"https://hn.algolia.com/api/v1/search?tags=story"
                   f"&query={requests.utils.quote(query)}"
                   f"&restrictSearchableAttributes=title"
                   f"&numericFilters=created_at_i>{seven_days_ago_ts}")
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            hits = resp.json().get("hits", [])
            print(f"  {len(hits)} HN stories for '{query}'")
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
                summary = f"HN discussion. Points: {points}. Comments: {hit.get('num_comments', 0)}"
                story_id = db.insert_story(title, link, "Hacker News", summary)
                if story_id:
                    stories_inserted.append({"id": story_id, "title": title, "url": link, "source": "Hacker News"})
                    count += 1
        except Exception as e:
            print(f"  Error scraping HN query '{query}': {e}")
    return stories_inserted


def scrape_github_trending(topic, limit):
    stories_inserted = []
    print(f"Scraping GitHub Trending: {topic}...")
    try:
        url = f"https://github.com/trending?since=daily&spoken_language_code=en"
        if topic:
            url += f"&q={requests.utils.quote(topic)}"
        headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  GitHub trending returned {resp.status_code}")
            return stories_inserted

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        repos = soup.select("article.Box-row")
        count = 0
        for repo in repos:
            if count >= limit:
                break
            h2 = repo.find("h2")
            if not h2:
                continue
            repo_name = h2.get_text(strip=True).replace("\n", "").replace(" ", "")
            link = "https://github.com/" + repo_name.lstrip("/")
            desc_el = repo.find("p")
            desc = desc_el.get_text(strip=True) if desc_el else ""
            stars_el = repo.find("a", {"href": lambda h: h and h.endswith("/stargazers")})
            stars_text = stars_el.get_text(strip=True) if stars_el else "0"
            summary = f"GitHub trending repo. {desc} Stars: {stars_text}"
            title = repo_name
            story_id = db.insert_story(title, link, "GitHub Trending", summary)
            if story_id:
                stories_inserted.append({"id": story_id, "title": title, "url": link, "source": "GitHub Trending"})
                count += 1
    except Exception as e:
        print(f"  Error scraping GitHub trending: {e}")
    return stories_inserted


def scrape_huggingface_papers(api_url, limit):
    stories_inserted = []
    print("Scraping Hugging Face daily papers...")
    try:
        resp = requests.get(api_url, timeout=10)
        if resp.status_code != 200:
            print(f"  HuggingFace API returned {resp.status_code}")
            return stories_inserted
        papers = resp.json()
        if isinstance(papers, dict):
            papers = papers.get("papers", [])
        count = 0
        for paper in papers:
            if count >= limit:
                break
            title   = paper.get("paper", {}).get("title") or paper.get("title", "")
            arxiv_id = paper.get("paper", {}).get("id") or paper.get("id", "")
            summary = paper.get("paper", {}).get("summary") or paper.get("abstract", "")
            link = f"https://huggingface.co/papers/{arxiv_id}" if arxiv_id else ""
            if not title or not link:
                continue
            story_id = db.insert_story(title, link, "Hugging Face", summary[:500])
            if story_id:
                stories_inserted.append({"id": story_id, "title": title, "url": link, "source": "Hugging Face"})
                count += 1
    except Exception as e:
        print(f"  Error scraping HuggingFace: {e}")
    return stories_inserted


def scrape_google_news(queries_csv, limit):
    stories_inserted = []
    print(f"Scraping Google News: {queries_csv}...")
    headers = {"User-Agent": USER_AGENT}
    queries = [q.strip() for q in queries_csv.split(",") if q.strip()]
    seen = set()
    count = 0
    for query in queries:
        if count >= limit:
            break
        try:
            q_enc = requests.utils.quote(query)
            url = f"https://news.google.com/rss/search?q={q_enc}&hl=en-US&gl=US&ceid=US:en"
            feed = feedparser.parse(url)
            for entry in feed.entries:
                if count >= limit:
                    break
                title = getattr(entry, 'title', '')
                link  = getattr(entry, 'link', '')
                if not title or link in seen:
                    continue
                seen.add(link)
                summary = entry.get("summary", "")
                story_id = db.insert_story(title, link, "Google News", summary)
                if story_id:
                    stories_inserted.append({"id": story_id, "title": title, "url": link, "source": "Google News"})
                    count += 1
        except Exception as e:
            print(f"  Error scraping Google News for '{query}': {e}")
    return stories_inserted


def run_scraper():
    """Main entry point: reads enabled sources from DB and scrapes each one."""
    print("\n=== SCRAPER STARTING ===")
    sources = db.get_enabled_sources()
    if not sources:
        print("No enabled sources found. Add sources via the Settings tab.")
        return []

    all_stories = []
    for src in sources:
        stype  = src["type"]
        name   = src["name"]
        url    = src["url"]
        limit  = src.get("volume_limit", 10)
        try:
            if stype == "rss":
                stories = scrape_rss_feed(name, url, limit)
            elif stype == "hn":
                stories = scrape_hacker_news(url, limit)
            elif stype == "github":
                stories = scrape_github_trending(url, limit)
            elif stype == "huggingface":
                stories = scrape_huggingface_papers(url, limit)
            elif stype == "google_news":
                stories = scrape_google_news(url, limit)
            else:
                print(f"  Unknown source type: {stype}")
                stories = []
            all_stories.extend(stories)
            print(f"  → {len(stories)} new stories from {name}")
        except Exception as e:
            print(f"  Error processing source {name}: {e}")

    print(f"\n=== SCRAPER DONE: {len(all_stories)} new stories total ===\n")
    return all_stories


if __name__ == "__main__":
    db.init_db()
    run_scraper()
