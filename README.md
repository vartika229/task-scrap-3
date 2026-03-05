# Google Maps Business Scraper
A powerful, asynchronous web scraper built with Python, Flask, and Playwright. Extract high-quality business leads directly from Google Maps into structured CSV, Excel, or JSON files.

# Running with Docker (Easiest):
If you have Docker installed, you can run the scraper immediately without any setup by pulling the pre-built image from Docker Hub:
1. Login to docker through the terminal.
2. Pull and Run
   "docker run --platform linux/amd64 -p 8000:8000 shuklavartika010/google-maps-scraper:v1"
3. Access the App
   Visit http://localhost:8000 in your browser.

# Quick Start (Local Development):
If you prefer to run the code locally with Python:
1. Clone & Navigate
   "git clone <your-repo-url>
   cd google-maps-scraper"
2. Setup Virtual Environment
"python -m venv venv"
#Windows:
".\venv\Scripts\activate"
#Mac/Linux:
"source venv/bin/activate"
3. Install Dependencies
   "python -m pip install --upgrade pip"
"pip install -r requirements.txt"
"playwright install chromium"
4. Run the App
   "python app.py"
Visit "http://localhost:8000" in your browser.

# Tech StackBackend: 
1. Flask (Python 3.12+)
2. Scraping Engine: Playwright (Headless Chromium)
3. Data Processing: Pandas & OpenPyxl
4. Frontend: Tailwind CSS & JavaScript (Fetch API)

# Features & Extraction Details:
This tool extracts the following fields for every business listing:
1. Company Name: Official business title.
2. Mobile Number: Cleaned contact number.
3. Email: Deep-crawled from the business website (if enabled).
4. Website: Direct link to the official site.
5. Rating: Star rating (e.g., 4.7).
6. Reviews: Total number of customer reviews.
7. Category: Business type (e.g., "Software Company").
8. Address: Normalized, single-line physical address.
9. Google Maps URL: Direct permalink to the listing.

# Troubleshooting:
1. Windows Build Errors- If you see errors related to pandas, numpy, or greenlet:
a. Use Python 3.12: Python 3.13 is very new and some binaries for Windows aren't ready yet.
b. Install C++ Build Tools: Ensure the Microsoft C++ Build Tools are installed with the "Desktop development with C++" workload.
2. Data Format Issues- If you see strange symbols (like ) in your CSV:The scraper includes a cleaning function in Maps_scraper.py to strip these out. If you find new ones, you can update the regex in that file to include the new characters.
3. Docker Logs- To see real-time logs from your container:
"docker ps  # find your container ID"
"docker logs -f <container_id>"
