import os
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

D1_DATABASE_ID = os.getenv('CLOUDFLARE_D1_DATABASE_ID')
CLOUDFLARE_ACCOUNT_ID = os.getenv('CLOUDFLARE_ACCOUNT_ID')
CLOUDFLARE_API_TOKEN = os.getenv('CLOUDFLARE_API_TOKEN')

# Constants
CLOUDFLARE_BASE_URL = f"https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/d1/database/{D1_DATABASE_ID}"
ROOT_SITEMAP_URL = "https://replicate.com/sitemap.xml"

HEADERS = {
    "Authorization": f"Bearer {CLOUDFLARE_API_TOKEN}",
    "Content-Type": "application/json",
}

# Semaphore for controlling concurrency
MAX_CONCURRENT_REQUESTS = 50  # Adjust based on system capabilities
semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# Helper: Parse a sitemap and return all <loc> URLs
async def parse_sitemap(url, session):
    async with semaphore:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                text = await response.text()
                soup = BeautifulSoup(text, "xml")
                return [loc.text for loc in soup.find_all("loc")]
        except aiohttp.ClientError as e:
            print(f"[ERROR] Failed to fetch sitemap {url}: {e}")
            return []

# Image-to-ImageImage-to-TextImage-to-VideoText-to-ImageText-to-TextText-to-AudioText-to-VideoAudio-to-ImageAudio-to-TextAudio-to-AudioAudio-to-VideoVideo-to-ImageVideo-to-TextVideo-to-AudioVideo-to-Video


# Helper: Fetch model page and extract run count
async def get_model_runs(url, session):
    async with semaphore:
        try:
            async with session.get(url) as response:
                response.raise_for_status()
                text = await response.text()
                soup = BeautifulSoup(text, "html.parser")
              # https://www.aimodels.fyi/models/huggingFace/flux.1-dev-black-forest-labs
                run_span = soup.find("div", class_="css-19dcitr")
                if run_span:
                    t = run_span.get_text(strip=True).lower()
                    if 'k' in t:
                        t = int(float(t.replace('k', '')) * 1000)
                    elif 'm' in t:
                        t = int(float(t.replace('m', '')) * 1000000)

                    t = re.search(r'\d+', str(t)).group(0)
                    t = int(t)
                    return t
                else:
                    print(f"[WARNING] No run count found on page: {url}")
                    return None
        except aiohttp.ClientError as e:
            print(f"[ERROR] Failed to fetch model page {url}: {e}")
            return None

# Helper: Create table in the database
async def create_table_if_not_exists(session):
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS aimodelsfyi_model_data (
        id SERIAL PRIMARY KEY,
        model_url TEXT UNIQUE,
        run_count INTEGER,
        createAt TEXT,
        updateAt TEXT
    );
    """
    payload = {"sql": create_table_sql}
    url = f"{CLOUDFLARE_BASE_URL}/query"
    try:
        async with session.post(url, headers=HEADERS, json=payload) as response:
            response.raise_for_status()
            print("[INFO] Table aimodelsfyi_model_data checked/created successfully.")
    except aiohttp.ClientError as e:
        print(f"[ERROR] Failed to create table: {e}")

# Helper: Insert or update model data
async def upsert_model_data(model_url, run_count, session):
    current_time = datetime.utcnow().isoformat()
    sql = f"""
    INSERT INTO aimodelsfyi_model_data (model_url, run_count, createAt, updateAt)
    VALUES ('{model_url}', {run_count}, '{current_time}', '{current_time}')
    ON CONFLICT (model_url) DO UPDATE
    SET run_count = {run_count}, 
        updateAt = '{current_time}',
        createAt = aimodelsfyi_model_data.createAt;
    """
    payload = {"sql": sql}
    url = f"{CLOUDFLARE_BASE_URL}/query"
    try:
        async with session.post(url, headers=HEADERS, json=payload) as response:
            response.raise_for_status()
            print(f"[INFO] Data upserted for {model_url} with {run_count} runs.")
    except aiohttp.ClientError as e:
        print(f"[ERROR] Failed to upsert data for {model_url}: {e}")

# Main workflow
async def process_model_url(model_url, session):
    print(f"[INFO] Processing model: {model_url}")
    if '/models/' in model_url ==False:
        continue
    run_count = await get_model_runs(model_url, session)
    if run_count is not None:
        await upsert_model_data(model_url, run_count, session)

async def main():
    print("[INFO] Starting sitemap parsing...")
    ROOT_SITEMAP_URL='https://www.aimodels.fyi/sitemap.xml'

    async with aiohttp.ClientSession() as session:
        await create_table_if_not_exists(session)

        # Parse the root sitemap
        subsitemaps = await parse_sitemap(ROOT_SITEMAP_URL, session)
        if not subsitemaps:
            print("[ERROR] No subsitemaps found.")
            return

        tasks = []

        for subsitemap_url in subsitemaps:
            if subsitemap_url != 'https://www.aimodels.fyi/sitemap-0.xml':
                print(f"[INFO] Skipping unsupported sitemap: {subsitemap_url}")
                continue

            print(f"[INFO] Parsing subsitemap: {subsitemap_url}")
            model_urls = await parse_sitemap(subsitemap_url, session)

            for model_url in model_urls:
                tasks.append(process_model_url(model_url, session))

        await asyncio.gather(*tasks)
    print("[INFO] Sitemap parsing complete.")

# Run the script
if __name__ == "__main__":
    asyncio.run(main())
