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

def _extract_email_from_website(page, website_url: str) -> str:
    """Visits a website and uses regex to find an email address."""
    if not website_url:
        return ""
    try:
        # Short timeout so we don't hang on slow websites
        page.goto(website_url, timeout=10000)
        content = page.content()
        # Regex for standard email formats
        emails = list(set(re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', content)))
        # Filter out common false positives (image extensions)
        valid_emails = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg'))]
        return valid_emails[0] if valid_emails else ""
    except Exception as e:
        logger.warning(f"Could not extract email from {website_url}: {e}")
        return ""

def run_scrape(url: str, max_results: int = 20, extract_email: bool = False) -> list:
    """
    Main Playwright scraper.
    Navigates to the Maps URL, scrolls the feed, and extracts business details.
    """
    scraped_data = []

    with sync_playwright() as p:
        # Use headless=True in production. Set to False if you want to watch the browser.
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        try:
            page.goto(url, timeout=60000)
            
            # Wait for the main feed or a single listing to load
            try:
                page.wait_for_selector('div[role="feed"]', timeout=15000)
                is_feed = True
            except:
                is_feed = False

            if not is_feed:
                # Handle single location URL fallback (if the user pasted a specific business URL)
                logger.info("No feed detected. Attempting single location extraction.")
                data = _extract_listing_details(page, page, context, extract_email)
                if data["Company Name"] != "N/A":
                    scraped_data.append(data)
                return scraped_data

            # --- Feed Scrolling Logic ---
            previously_counted = 0
            retries = 0
            
            while len(scraped_data) < max_results:
                # Find all current listing links in the feed (these are usually the 'a' tags wrapping the card)
                listings = page.locator('div[role="feed"] > div > div > a').all()
                
                if len(listings) == previously_counted:
                    # Scroll the specific feed container
                    page.mouse.wheel(0, 8000)
                    time.sleep(2.5) # Wait for network requests
                    listings = page.locator('div[role="feed"] > div > div > a').all()
                    
                    if len(listings) == previously_counted:
                        retries += 1
                        if retries > 3: # Break if we tried scrolling 3 times with no new results
                            break 
                    else:
                        retries = 0

                previously_counted = len(listings)

                # Process new listings
                for i in range(len(scraped_data), min(len(listings), max_results)):
                    listing = listings[i]
                    try:
                        # Click to open side panel
                        listing.click()
                        page.wait_for_timeout(2000) # Give side panel time to populate DOM
                        
                        data = _extract_listing_details(page, listing, context, extract_email)
                        if data["Company Name"] != "N/A":
                            scraped_data.append(data)

                    except Exception as e:
                        logger.error(f"Failed to process a listing item: {e}")
                        continue

        finally:
            browser.close()

    return scraped_data

def _extract_listing_details(page, locator_element, context, extract_email: bool) -> dict:
    """Helper function to pull data from the active side panel."""
    # Company Name
    name_loc = page.locator('h1.DUwDvf')
    name = name_loc.first.inner_text() if name_loc.count() > 0 else "N/A"
    
    # Phone
    phone_loc = page.locator('button[data-item-id^="phone:tel:"]')
    phone = phone_loc.first.inner_text() if phone_loc.count() > 0 else ""

    # Website
    website_loc = page.locator('a[data-item-id="authority"]')
    website = website_loc.first.get_attribute('href') if website_loc.count() > 0 else ""

    # Address
    address_loc = page.locator('button[data-item-id="address"]')
    address = address_loc.first.inner_text() if address_loc.count() > 0 else ""
    
    # Rating & Reviews
    rating, reviews = "", ""
    rating_loc = page.locator('div.F7wGSR')
    if rating_loc.count() > 0:
        rating_text = rating_loc.first.get_attribute('aria-label') or ""
        if "stars" in rating_text or "star" in rating_text:
            parts = rating_text.split("star")
            rating = parts[0].strip()
            reviews = parts[1].replace("s", "").replace("Reviews", "").replace("Review", "").strip() if len(parts) > 1 else ""

    # Category
    category_loc = page.locator('button[jsaction="pane.rating.category"]')
    category = category_loc.first.inner_text() if category_loc.count() > 0 else ""
    
    listing_url = page.url
    email = ""
    
    # Optional Email Extraction
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
        "Address": address,
        "Google Maps URL": listing_url
    }

def generate_file_bytes(results: list, fmt: str) -> bytes:
    """Converts the list of dictionaries into a byte string for downloading."""
    if not results:
        return b""

    if fmt == "json":
        return json.dumps(results, indent=2).encode('utf-8')
    
    elif fmt == "csv":
        output = io.StringIO()
        if len(results) > 0:
            writer = csv.DictWriter(output, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        return output.getvalue().encode('utf-8')
    
    elif fmt == "xlsx":
        try:
            import pandas as pd
            df = pd.DataFrame(results)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()
        except ImportError:
            # Fallback to CSV if pandas/openpyxl is missing
            return generate_file_bytes(results, "csv")
    
    return b""