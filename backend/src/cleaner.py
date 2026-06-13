import os
import requests
import json
import sys
import random
import re
import io
from PIL import Image
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Ensure backend/src is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import db

# Load environment variables
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(backend_dir, ".env"))

API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("LLM_MODEL", "meta-llama/llama-3-70b-instruct:free")


IMAGES_DIR = os.path.join(backend_dir, 'static', 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

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

# Patterns to skip for ad/tracker images
_SKIP_PATTERNS = re.compile(r'pixel|tracking|spacer|logo|icon|avatar|1x1', re.IGNORECASE)

# Patterns to skip generic placeholder social thumbnails, gradient banners, or generic page screenshots
_SKIP_IMAGE_URL_PATTERNS = re.compile(
    r'social-thumbnails|gradient\.png|placeholder|logo-square|favicon|default_bg|header-bg|menu|banner',
    re.IGNORECASE
)


def extract_article_details(url):
    """GET the article URL, parse with BeautifulSoup, extract full_text and image_urls."""
    result = {'full_text': '', 'image_urls': []}
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Extract full_text from <p> tags
        paragraphs = soup.find_all('p')
        full_text = ' '.join(p.get_text(strip=True) for p in paragraphs)
        result['full_text'] = full_text[:5000]

        # Extract images
        image_urls = []

        # Try og:image first (if not a generic placeholder/social thumbnail)
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            og_url = urljoin(url, og_image['content'])
            if not _SKIP_IMAGE_URL_PATTERNS.search(og_url):
                image_urls.append(og_url)

        # Then all <img> tags
        for img in soup.find_all('img', src=True):
            src = img['src']

            # Skip data: URIs
            if src.startswith('data:'):
                continue

            # Skip common ad/tracker patterns
            if _SKIP_PATTERNS.search(src):
                continue

            # Filter out generic layouts/bannering
            abs_url = urljoin(url, src)
            if _SKIP_IMAGE_URL_PATTERNS.search(abs_url):
                continue

            # Check dimensions if available
            width = img.get('width')
            height = img.get('height')
            try:
                if width and int(width) < 250:
                    continue
                if height and int(height) < 250:
                    continue
            except (ValueError, TypeError):
                pass

            if abs_url not in image_urls:
                image_urls.append(abs_url)

        result['image_urls'] = image_urls[:5]
    except Exception as e:
        print(f"  Error extracting article details from {url}: {e}")

    return result


def download_images(image_urls, story_id):
    """Download images to IMAGES_DIR. Returns list of dicts with url, local_path, width, height, and aspect_ratio."""
    downloaded = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    for index, img_url in enumerate(image_urls):
        try:
            resp = requests.get(img_url, headers=headers, timeout=10)
            resp.raise_for_status()
            
            # Verify and parse size using PIL
            img = Image.open(io.BytesIO(resp.content))
            width, height = img.size
            
            # Filter by size >= 250px
            if width < 250 or height < 250:
                print(f"  Skipping image {img_url}: size too small ({width}x{height})")
                continue
                
            # Filter out ex