# Web Crawler for CSCI 572 - HW2

A multi-threaded Python web crawler that crawls news websites, collects statistics, and generates detailed reports.

## Features

- ✅ Multi-threaded crawling (configurable number of threads)
- ✅ Respects robots.txt
- ✅ Politeness delays between requests
- ✅ Filters by content type (HTML, PDF, DOC, images)
- ✅ Thread-safe statistics collection
- ✅ Generates required CSV files and report
- ✅ Domain filtering (stays within target site)
- ✅ Handles redirects, timeouts, and errors gracefully

## Requirements

- Python 3.7+
- Libraries: requests, beautifulsoup4, lxml

## Installation

1. **Clone or download this repository**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Edit the `main()` function at the bottom of `crawler.py` to configure your settings:

```python
# Choose which site to crawl
SITE_NAME = 'nytimes'  # Options: 'nytimes', 'wsj', 'foxnews', 'usatoday', 'latimes'

# Update your information
STUDENT_NAME = 'Your Name Here'
USC_ID = '1234567890'

# Adjust crawler parameters (optional)
MAX_PAGES = 10000
NUM_THREADS = 7
POLITENESS_DELAY = 2.0
```

## Usage

Run the crawler:

```python
# At the bottom of crawler.py
SITE_NAME = 'foxnews'  # Change this
STUDENT_NAME = 'Your Name'  # Update this
USC_ID = '1234567890'  # Update this
```

Then run:
```bash
python crawler.py
```

## Output Files

The crawler creates an `output/` directory with the following files:

1. **fetch_[sitename].csv** - All URLs attempted with status codes
   - Columns: URL, Status
   
2. **visit_[sitename].csv** - Successfully downloaded pages
   - Columns: URL, Size (bytes), # Outlinks, Content-Type
   
3. **urls_[sitename].csv** - All discovered URLs (not submitted)
   - Columns: URL, Indicator (OK/N_OK)
   
4. **CrawlReport_[sitename].txt** - Statistics summary
   - Fetch statistics
   - Outgoing URLs statistics
   - Status codes breakdown
   - File sizes distribution
   - Content types encountered

## How It Works

1. **Initialization**: Starts with a seed URL and sets up thread-safe queues
2. **Multi-threaded Crawling**: Spawns worker threads that:
   - Fetch URLs from the queue
   - Download page content
   - Extract links from HTML
   - Add new URLs to the queue (if within domain)
   - Collect statistics
3. **Statistics Collection**: Thread-safe collector tracks all required metrics
4. **Output Generation**: Writes CSV files and report in required format

## Key Components

### WebCrawler Class
- Manages the crawling process
- Handles URL queue and threading
- Enforces politeness and robots.txt compliance
- Filters by domain and content type

### StatisticsCollector Class
- Thread-safe statistics tracking
- Collects fetch attempts, visits, and discovered URLs
- Counts status codes, file sizes, and content types
- Prevents duplicate visits

## Tips for Success

### Choosing Parameters

**For testing (quick run):**
```python
MAX_PAGES = 100
NUM_THREADS = 3
POLITENESS_DELAY = 1.0
```

**For submission (full run):**
```python
MAX_PAGES = 10000
NUM_THREADS = 7
POLITENESS_DELAY = 2.0
```

### Expected Runtime

Crawl time (hours) = MAX_PAGES / 3600 × POLITENESS_DELAY × (NUM_THREADS adjustment factor)

Example: 10,000 pages with 2s delay ≈ 5-6 hours

### Troubleshooting

**Issue: "Module not found" error**
```bash
pip install -r requirements.txt
```

**Issue: Crawler runs too slowly**
- Reduce `POLITENESS_DELAY` to 1.5s (but be careful!)
- Increase `NUM_THREADS` to 10

**Issue: Too many timeouts**
- Increase `POLITENESS_DELAY` to 2.5s or 3.0s
- Check your internet connection
- Try using USC VPN if off-campus

**Issue: Output directory not found**
- The script creates it automatically, but you can create it manually:
  ```bash
  mkdir output
  ```

**Issue: Crawl stops before reaching max pages**
- Normal if the site has fewer pages than MAX_PAGES
- Check that variation is within 10% per assignment requirements

## Submission Checklist

Before submitting, ensure you have:

- [ ] Updated `STUDENT_NAME` and `USC_ID` in config
- [ ] Chosen the correct `SITE_NAME` for your assignment
- [ ] Run the crawler to completion (10,000 pages)
- [ ] Generated all output files in the `output/` directory
- [ ] Verified the output files contain data:
  - [ ] `fetch_[sitename].csv` (~10,000 rows)
  - [ ] `visit_[sitename].csv` (successful fetches only)
  - [ ] `CrawlReport_[sitename].txt` (statistics summary)
- [ ] Create `crawl.zip` with:
  - CrawlReport_[sitename].txt
  - fetch_[sitename].csv
  - visit_[sitename].csv
  - crawler.py (source code - required per HW update)

**DO NOT include:** urls_[sitename].csv (per assignment requirements)

## Advanced Usage

### Crawling Multiple Sites

To crawl multiple sites sequentially, modify the `main()` function:

```python
for site in ['nytimes', 'wsj', 'foxnews']:
    SITE_NAME = site
    SEED_URL = SEED_URLS[site]
    # ... create and run crawler
```

### Custom Content Type Filtering

Edit the `allowed_content_types` list in the `WebCrawler.__init__()` method or in `config.py`.

## Notes

- This crawler was built with assistance from **GitHub Copilot (Claude Sonnet)** as encouraged by the assignment
- The crawler respects robots.txt by default
- URLs with commas are automatically cleaned (replaced with underscores)
- Content-type charset information is automatically removed from outputs
- The crawler avoids revisiting URLs (deduplication)

## License

Academic use only - CSCI 572 Homework Assignment

## Author

Built for USC CSCI 572 - Information Retrieval and Web Search Engines

---

**Good luck with your crawling! 🕷️**