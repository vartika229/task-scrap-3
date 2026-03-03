import re
import time
import csv
import json
import io
import logging
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

def validate_google_maps_url(url: str) -> bool:
    """Basic validation to ensure the URL points to Google Maps."""
    parsed = urlparse(url)
    return "google" in parsed.netloc and "/maps" in parsed.path

def clean_text(text: str) -> str:
    """Removes special icon characters and extra whitespace."""
    if not text:
        return ""
    # Remove common Google Maps icon characters and normalize whitespace
    cleaned = re.sub(r'[]', '', text)
    return cleaned.strip().replace('\n', ', ')

def _extract_email_from_website(page, website_url: str) -> str:
    """Visits a website and uses regex to find an email address."""
    if not website_url:
        return ""
    try:
        page.goto(website_url, timeout=10000, wait_until="domcontentloaded")
        content = page.content()
        emails = list(set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', content)))
        valid_emails = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))]
        return valid_emails[0] if valid_emails else ""
    except Exception:
        return ""

def run_scrape(url: str, max_results: int = 20, extract_email: bool = False) -> list:
    scraped_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=60000)
            
            # Wait for results to appear
            page.wait_for_selector('a.hfpxzc', timeout=20000)

            processed_urls = set()
            retries = 0
            
            while len(scraped_data) < max_results:
                listings = page.locator('a.hfpxzc').all()
                
                if len(listings) <= len(processed_urls):
                    page.mouse.wheel(0, 4000)
                    time.sleep(2)
                    listings = page.locator('a.hfpxzc').all()
                    if len(listings) <= len(processed_urls):
                        retries += 1
                        if retries > 5: break
                    else:
                        retries = 0

                for listing in listings:
                    if len(scraped_data) >= max_results:
                        break
                        
                    listing_url = listing.get_attribute('href')
                    if listing_url in processed_urls:
                        continue
                    
                    processed_urls.add(listing_url)
                    
                    try:
                        listing.click()
                        # CRITICAL: Wait for the side panel title to change/appear
                        page.wait_for_selector('h1.DUwDvf', timeout=10000)
                        # Small buffer for other data to load
                        time.sleep(1) 

                        data = _extract_panel_details(page, context, extract_email)
                        data["Google Maps URL"] = listing_url
                        scraped_data.append(data)
                    except Exception as e:
                        logger.warning(f"Error extracting listing: {e}")
                        continue

        finally:
            browser.close()

    return scraped_data

def _extract_panel_details(page, context, extract_email: bool) -> dict:
    """Pulls cleaned data from the active side panel."""
    
    # 1. Company Name
    name = page.locator('h1.DUwDvf').first.inner_text() if page.locator('h1.DUwDvf').count() > 0 else "N/A"
    
    # 2. Rating & Reviews (More robust selector)
    rating = ""
    reviews = ""
    rating_container = page.locator('div.F7wGSR').first
    if rating_container.count() > 0:
        label = rating_container.get_attribute('aria-label')
        if label:
            # Format: "4.5 stars 128 reviews"
            match = re.search(r'(\d+\.?\d*)\s*stars?\s*(\d+)?', label)
            if match:
                rating = match.group(1)
                reviews = match.group(2) or ""

    # 3. Category
    category = page.locator('button[jsaction="pane.rating.category"]').first.inner_text() if page.locator('button[jsaction="pane.rating.category"]').count() > 0 else ""

    # 4. Address (Using clean_text to remove the icon)
    addr_loc = page.locator('button[data-item-id="address"]').first
    address = clean_text(addr_loc.inner_text()) if addr_loc.count() > 0 else ""

    # 5. Website
    web_loc = page.locator('a[data-item-id="authority"]').first
    website = web_loc.get_attribute('href') if web_loc.count() > 0 else ""

    # 6. Phone
    phone_loc = page.locator('button[data-item-id^="phone:tel:"]').first
    phone = clean_text(phone_loc.inner_text()) if phone_loc.count() > 0 else ""
    
    email = ""
    if extract_email and website:
        email_page = context.new_page()
        email = _extract_email_from_website(email_page, website)
        email_page.close()

    return {
        "Company Name": name,
        "Mobile Number": phone,
        "Email": email,
        "Website": website,
        "Rating": rating,
        "Number of Reviews": reviews,
        "Category": category,
        "Address": address
    }

def generate_file_bytes(results: list, fmt: str) -> bytes:
    if not results: return b""
    if fmt == "json":
        return json.dumps(results, indent=2).encode('utf-8')
    elif fmt == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
        return output.getvalue().encode('utf-8')
    elif fmt == "xlsx":
        import pandas as pd
        df = pd.DataFrame(results)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()
    return b""