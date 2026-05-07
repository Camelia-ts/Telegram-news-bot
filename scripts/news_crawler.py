import json
import os
import time
import urllib.request
import urllib.parse
from xml.etree import ElementTree

STORAGE_FILE = '.local_storage.json'
ITEMS_PER_CATEGORY = 10

CATEGORIES = {
    "Macro & Politics": "Global economy OR FED OR geopolitical",
    "Crypto Markets": "crypto prices OR ETF inflows OR exchange news",
    "Regulation & Legal": "cryptocurrency SEC OR CFTC OR regulation laws",
    "Security & Exploits": "crypto hack OR smart contract vulnerability OR defillama",
    "Airdrops & Opportunities": "crypto airdrop OR snapshot OR whitelist protocol testnet"
}

def load_local_storage():
    """Load previously seen titles and URLs from local storage to prevent duplicates."""
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r') as f:
                return set(json.load(f))
        except BaseException:
            return set()
    return set()

def save_local_storage(seen_items):
    """Save seen titles to local storage."""
    with open(STORAGE_FILE, 'w') as f:
        json.dump(list(seen_items), f)

def generate_summary(title, description=""):
    """
    Placeholder for an AI summarizer.
    In a real scenario, you would pass the descriptions/content into an LLM
    like Gemini or OpenAI to get a clean 1-sentence summary.
    """
    if description and len(description) > 50:
        return description[:100].strip() + "..."
    return title # Fallback simply returns the title if there's no description

def fetch_google_news(query):
    """
    Fetch news from Google News RSS using 'when:1d' which is the RSS 
    equivalent of 'tbs=qdr:d' (last 24 hours).
    """
    safe_query = urllib.parse.quote(f"{query} when:1d")
    url = f"https://news.google.com/rss/search?q={safe_query}&hl=en-US&gl=US&ceid=US:en"
    
    results = []
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ElementTree.fromstring(xml_data)
            
            for item in root.findall('.//item'):
                title = item.find('title').text
                link = item.find('link').text
                desc = item.find('description').text if item.find('description') is not None else ""
                
                results.append({
                    "Title": title,
                    "Summary": generate_summary(title, desc), 
                    "URL": link
                })
    except Exception as e:
        print(f"Error fetching Google News for {query}: {e}")
    return results

def fetch_x_news(query):
    """
    Placeholder for fetching news from X (Twitter).
    Since X requires authentication, you would implement the X API v2 here
    using libraries like `tweepy`, searching for recent engagement-heavy tweets.
    """
    # Example pseudo-code for Tweepy integration:
    # client = tweepy.Client(bearer_token=os.environ.get("X_BEARER_TOKEN"))
    # tweets = client.search_recent_tweets(query=f"{query} -is:retweet has:links", max_results=15)
    return []

def main():
    seen_items = load_local_storage()
    final_output = []

    for category, query in CATEGORIES.items():
        category_data = {
            "Category": category,
            "News": []
        }
        
        # Combine sources
        candidates = fetch_google_news(query) + fetch_x_news(query)
        collected_items = 0
        
        for item in candidates:
            if collected_items >= ITEMS_PER_CATEGORY:
                break
                
            # Deduplication Check
            # Using lowercase title for loose duplicate checking
            dedup_key = item["Title"].strip().lower()
            
            if dedup_key not in seen_items:
                seen_items.add(dedup_key)
                
                # We enforce the structure constraints
                category_data["News"].append({
                    "Title": item["Title"],
                    "Summary": item["Summary"],
                    "URL": item["URL"]
                })
                collected_items += 1
                
        final_output.append(category_data)

    save_local_storage(seen_items)
    
    # Print exactly the structured output without any conversational text
    print(json.dumps(final_output, indent=4))

if __name__ == "__main__":
    main()
