"""
Web Crawler for News Sites
CSCI 572 - HW2

This crawler visits news websites, collects statistics, and generates reports.
Supports multi-threading, respects robots.txt, and filters by content type.

Author: Jesse Fulcher (7451958545) - Generated with assistance from GitHub Copilot (Claude Sonnet)
"""

import re
import ssl
import requests
import csv
import time
import os
import threading
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser
from queue import Queue, Empty
from collections import Counter

# Fix for SSL certificate issues on macOS
ssl._create_default_https_context = ssl._create_unverified_context


class StatisticsCollector:
    """Thread-safe statistics collector for crawl data"""
    
    def __init__(self):
        self.lock = threading.Lock()
        
        # Fetch statistics
        self.fetch_attempts = [] 
        
        # Visit statistics  
        self.successful_visits = [] 
        
        # URLs discovered
        self.discovered_urls = [] 
        
        # Status code counter
        self.status_codes = Counter()
        
        # File size ranges
        self.file_sizes = {
            '< 1KB': 0,
            '1KB ~ <10KB': 0,
            '10KB ~ <100KB': 0,
            '100KB ~ <1MB': 0,
            '>= 1MB': 0
        }
        
        # Content types
        self.content_types = Counter()
        
        # Unique URLs tracking
        self.unique_urls_extracted = set()
        self.unique_urls_within_site = set()
        self.unique_urls_outside_site = set()
        self.visited_urls = set() 
        
    def add_fetch_attempt(self, url, status_code):
        """Record a fetch attempt"""
        with self.lock:
            self.fetch_attempts.append((url, status_code))
            self.status_codes[status_code] += 1
    
    def add_successful_visit(self, url, size, outlinks, content_type):
        """Record a successful visit"""
        with self.lock:
            clean_content_type = content_type.split(';')[0].strip()
            self.successful_visits.append((url, size, outlinks, clean_content_type))
            self.content_types[clean_content_type] += 1
            self.visited_urls.add(url)
            
            # Categorize file size
            size_kb = size / 1024
            if size_kb < 1:
                self.file_sizes['< 1KB'] += 1
            elif size_kb < 10:
                self.file_sizes['1KB ~ <10KB'] += 1
            elif size_kb < 100:
                self.file_sizes['10KB ~ <100KB'] += 1
            elif size_kb < 1024:
                self.file_sizes['100KB ~ <1MB'] += 1
            else:
                self.file_sizes['>= 1MB'] += 1
    
    def add_discovered_url(self, url, is_within_site):
        """Record a discovered URL"""
        with self.lock:
            indicator = 'OK' if is_within_site else 'N_OK'
            self.discovered_urls.append((url, indicator))
            self.unique_urls_extracted.add(url)
            
            if is_within_site:
                self.unique_urls_within_site.add(url)
            else:
                self.unique_urls_outside_site.add(url)
    
    def is_visited(self, url):
        """Check if URL has been visited"""
        with self.lock:
            return url in self.visited_urls
    
    def get_statistics(self):
        """Get all collected statistics"""
        with self.lock:
            fetches_succeeded = sum(1 for _, code in self.fetch_attempts if 200 <= code < 300)
            fetches_failed = len(self.fetch_attempts) - fetches_succeeded
            
            return {
                'fetch_attempts': len(self.fetch_attempts),
                'fetches_succeeded': fetches_succeeded,
                'fetches_failed': fetches_failed,
                'total_urls_extracted': len(self.discovered_urls),
                'unique_urls_extracted': len(self.unique_urls_extracted),
                'unique_urls_within_site': len(self.unique_urls_within_site),
                'unique_urls_outside_site': len(self.unique_urls_outside_site),
                'status_codes': dict(self.status_codes),
                'file_sizes': dict(self.file_sizes),
                'content_types': dict(self.content_types)
            }


class WebCrawler:
    """Multi-threaded web crawler for news sites"""
    
    def __init__(self, seed_url, site_name, max_pages=10000, max_depth=16, 
                 num_threads=7, politeness_delay=2.0):
        """
        Initialize the crawler
        
        Args:
            seed_url: Starting URL to crawl
            site_name: Name of the site (e.g., 'nytimes', 'wsj')
            max_pages: Maximum number of pages to fetch
            max_depth: Maximum depth to crawl
            num_threads: Number of crawler threads
            politeness_delay: Delay between requests in seconds
        """
        self.seed_url = seed_url
        self.site_name = site_name
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.num_threads = num_threads
        self.politeness_delay = politeness_delay
        
        # Parse the domain from seed URL
        parsed = urlparse(seed_url)
        self.domain = parsed.netloc
        self.base_url = f"{parsed.scheme}://{parsed.netloc}"
        
        # URL queue: (url, depth)
        self.url_queue = Queue()
        self.url_queue.put((seed_url, 0))
        
        # Statistics collector
        self.stats = StatisticsCollector()
        
        # Control flags
        self.stop_crawling = False
        self.pages_fetched = 0
        self.fetch_lock = threading.Lock()
        
        # Robots.txt parser
        self.robot_parser = RobotFileParser()
        self.robot_parser.set_url(urljoin(self.base_url, '/robots.txt'))
        try:
            self.robot_parser.read()
            print(f"✓ Successfully read robots.txt from {self.base_url}")
        except Exception as e:
            print(f"⚠ Could not read robots.txt: {e}")
        
        # User agent
        self.user_agent = 'USC-CSCI572-Crawler'
        self.headers = {
            'User-Agent': self.user_agent
        }
        
        # Allowed content types
        self.allowed_content_types = [
            'text/html',
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/gif',
            'image/jpeg',
            'image/jpg',
            'image/png',
            'image/webp',
            'image/svg+xml'
        ]
        
        # File extensions to filter
        self.excluded_extensions = re.compile(
            r'.*\.(css|js|json|xml|bmp|mp3|mp4|wav|avi|mov|mpeg|ram|m4v|'
            r'wmv|rm|smil|swf|wma|zip|rar|gz|tar|7z|exe|bin|dmg|iso)$',
            re.IGNORECASE
        )
    
    def is_valid_url(self, url):
        """Check if URL should be crawled"""
        # Remove fragment
        url, _ = urldefrag(url)
        
        # Check if already visited
        if self.stats.is_visited(url):
            return False
        
        # Check for excluded extensions
        if self.excluded_extensions.match(url):
            return False
        
        # Check robots.txt
        if not self.robot_parser.can_fetch(self.user_agent, url):
            return False
        
        return True
    
    def is_within_site(self, url):
        """Check if URL is within the target news site"""
        parsed = urlparse(url)
        return parsed.netloc == self.domain or parsed.netloc.endswith(f'.{self.domain}')
    
    def fetch_page(self, url):
        """
        Fetch a page and return response
        
        Returns:
            tuple: (status_code, content, content_type, size) or None if failed
        """
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=10,
                allow_redirects=True
            )
            
            status_code = response.status_code
            content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
            size = len(response.content)
            
            return status_code, response.content, content_type, size
            
        except requests.Timeout:
            return 408, None, None, 0  
        except requests.ConnectionError:
            return 503, None, None, 0  
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return 500, None, None, 0

    def extract_links(self, html_content, base_url):
        """Extract all links from HTML content"""
        links = []
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for tag in soup.find_all(['a', 'link'], href=True):
                href = tag['href']
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, href)
                # Remove fragment
                absolute_url, _ = urldefrag(absolute_url)
                if absolute_url.startswith('http'):
                    links.append(absolute_url)
        except Exception as e:
            print(f"Error parsing HTML: {e}")
        
        return links
    
    def should_process_content_type(self, content_type):
        """Check if content type should be processed"""
        return any(allowed in content_type.lower() for allowed in self.allowed_content_types)
    
    def crawl_worker(self, thread_id):
        """Worker thread for crawling"""
        print(f"Thread {thread_id} started")
        
        empty_queue_count = 0
        max_empty_attempts = 5  
        
        while not self.stop_crawling:
            # Check if we've reached max pages
            with self.fetch_lock:
                if self.pages_fetched >= self.max_pages:
                    self.stop_crawling = True
                    break
            
            # Get URL from queue
            try:
                url, depth = self.url_queue.get(timeout=2)
                # Reset counter on successful get
                empty_queue_count = 0  
            except Empty:
                empty_queue_count += 1
                # If queue has been empty multiple times and we've fetched some pages, exit
                if empty_queue_count >= max_empty_attempts and self.pages_fetched > 0:
                    break
                continue
            
            # Check depth limit
            if depth > self.max_depth:
                self.url_queue.task_done()
                continue
            
            # Check if URL is valid and within site
            if not self.is_within_site(url):
                self.url_queue.task_done()
                continue
            
            if not self.is_valid_url(url):
                self.url_queue.task_done()
                continue
            
            # Increment fetch counter
            with self.fetch_lock:
                if self.pages_fetched >= self.max_pages:
                    self.stop_crawling = True
                    self.url_queue.task_done()
                    break
                self.pages_fetched += 1
                current_count = self.pages_fetched
            
            # Politeness delay
            time.sleep(self.politeness_delay)
            
            # Fetch the page
            status_code, content, content_type, size = self.fetch_page(url)
            
            # Record fetch attempt
            self.stats.add_fetch_attempt(url, status_code)
            
            if current_count % 100 == 0:
                print(f"[Thread {thread_id}] Fetched {current_count}/{self.max_pages} pages - {url[:80]}...")
            
            # Process successful fetches
            if 200 <= status_code < 300 and content:
                # Check content type
                if self.should_process_content_type(content_type):
                    # Extract links if HTML
                    outlinks = []
                    if 'text/html' in content_type:
                        outlinks = self.extract_links(content, url)
                        
                        # Add discovered URLs to statistics
                        for link in outlinks:
                            is_within = self.is_within_site(link)
                            self.stats.add_discovered_url(link, is_within)
                            
                            # Add to queue if within site and not visited
                            if is_within and not self.stats.is_visited(link):
                                self.url_queue.put((link, depth + 1))
                    
                    # Record successful visit
                    self.stats.add_successful_visit(url, size, len(outlinks), content_type)
            
            self.url_queue.task_done()
        
        print(f"Thread {thread_id} finished")
    
    def start_crawling(self):
        """Start the crawling process with multiple threads"""
        print(f"\n{'='*70}")
        print(f"Starting crawl of {self.seed_url}")
        print(f"Site: {self.site_name}")
        print(f"Max pages: {self.max_pages}")
        print(f"Max depth: {self.max_depth}")
        print(f"Threads: {self.num_threads}")
        print(f"Politeness delay: {self.politeness_delay}s")
        print(f"{'='*70}\n")
        
        start_time = time.time()
        
        # Create and start worker threads
        threads = []
        for i in range(self.num_threads):
            thread = threading.Thread(target=self.crawl_worker, args=(i+1,))
            thread.start()
            threads.append(thread)
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        elapsed_time = time.time() - start_time
        
        print(f"\n{'='*70}")
        print(f"Crawling completed in {elapsed_time:.2f} seconds ({elapsed_time/60:.2f} minutes)")
        print(f"Pages fetched: {self.pages_fetched}")
        print(f"{'='*70}\n")
    
    def write_csv_files(self, output_dir='.'):
        """Write the CSV output files"""
        print("Writing CSV files...")
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Write fetch_*.csv
        fetch_file = os.path.join(output_dir, f'fetch_{self.site_name}.csv')
        with open(fetch_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['URL', 'Status'])
            for url, status in self.stats.fetch_attempts:
                # Replace commas in URLs with underscores
                clean_url = url.replace(',', '_')
                writer.writerow([clean_url, status])
        print(f"✓ Written {fetch_file}")
        
        # Write visit_*.csv
        visit_file = os.path.join(output_dir, f'visit_{self.site_name}.csv')
        with open(visit_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['URL', 'Size (bytes)', '# Outlinks', 'Content-Type'])
            for url, size, outlinks, content_type in self.stats.successful_visits:
                clean_url = url.replace(',', '_')
                writer.writerow([clean_url, size, outlinks, content_type])
        print(f"✓ Written {visit_file}")
        
        # Write urls_*.csv (not submitted but useful for debugging)
        urls_file = os.path.join(output_dir, f'urls_{self.site_name}.csv')
        with open(urls_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['URL', 'Indicator'])
            for url, indicator in self.stats.discovered_urls:
                clean_url = url.replace(',', '_')
                writer.writerow([clean_url, indicator])
        print(f"✓ Written {urls_file}")
    
    def write_report(self, output_dir='.', student_name='', usc_id=''):
        """Write the crawl report"""
        print("Writing crawl report...")
        
        stats = self.stats.get_statistics()
        
        report_file = os.path.join(output_dir, f'CrawlReport_{self.site_name}.txt')
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"Name: {student_name}\n")
            f.write(f"USC ID: {usc_id}\n")
            f.write(f"News site crawled: {self.domain}\n")
            f.write(f"Number of threads: {self.num_threads}\n")
            f.write(f"\n")
            
            f.write(f"Fetch Statistics\n")
            f.write(f"================\n")
            f.write(f"# fetches attempted: {stats['fetch_attempts']}\n")
            f.write(f"# fetches succeeded: {stats['fetches_succeeded']}\n")
            f.write(f"# fetches failed or aborted: {stats['fetches_failed']}\n")
            f.write(f"\n")
            
            f.write(f"Outgoing URLs:\n")
            f.write(f"==============\n")
            f.write(f"Total URLs extracted: {stats['total_urls_extracted']}\n")
            f.write(f"# unique URLs extracted: {stats['unique_urls_extracted']}\n")
            f.write(f"# unique URLs within News Site: {stats['unique_urls_within_site']}\n")
            f.write(f"# unique URLs outside News Site: {stats['unique_urls_outside_site']}\n")
            f.write(f"\n")
            
            f.write(f"Status Codes:\n")
            f.write(f"=============\n")
            # Sort status codes
            for code in sorted(stats['status_codes'].keys()):
                count = stats['status_codes'][code]
                # Get status code description
                code_desc = {
                    200: 'OK',
                    301: 'Moved Permanently',
                    302: 'Found',
                    304: 'Not Modified',
                    401: 'Unauthorized',
                    403: 'Forbidden',
                    404: 'Not Found',
                    408: 'Request Timeout',
                    500: 'Internal Server Error',
                    503: 'Service Unavailable'
                }.get(code, '')
                
                if code_desc:
                    f.write(f"{code} {code_desc}: {count}\n")
                else:
                    f.write(f"{code}: {count}\n")
            f.write(f"\n")
            
            f.write(f"File Sizes:\n")
            f.write(f"===========\n")
            for size_range in ['< 1KB', '1KB ~ <10KB', '10KB ~ <100KB', '100KB ~ <1MB', '>= 1MB']:
                f.write(f"{size_range}: {stats['file_sizes'][size_range]}\n")
            f.write(f"\n")
            
            f.write(f"Content Types:\n")
            f.write(f"==============\n")
            for content_type, count in sorted(stats['content_types'].items()):
                f.write(f"{content_type}: {count}\n")
        
        print(f"✓ Written {report_file}")


def main():
    """Main function to run the crawler"""
    
    # Seed URLs for different news sites
    SEED_URLS = {
        'nytimes': 'https://www.nytimes.com',
        'wsj': 'https://www.wsj.com',
        'foxnews': 'https://www.foxnews.com',
        'usatoday': 'https://www.usatoday.com',
        'latimes': 'https://www.latimes.com'
    }
    
    # Choose which site to crawl
    SITE_NAME = 'nytimes'  
    SEED_URL = SEED_URLS[SITE_NAME]
    
    # Crawler parameters
    MAX_PAGES = 10000 
    MAX_DEPTH = 16
    NUM_THREADS = 7
    POLITENESS_DELAY = 2.0  # seconds
    
    # Student information
    STUDENT_NAME = 'Jesse Fulcher'
    USC_ID = '7451958545'
    
    # Output directory
    OUTPUT_DIR = './output'
    
    # Create crawler
    crawler = WebCrawler(
        seed_url=SEED_URL,
        site_name=SITE_NAME,
        max_pages=MAX_PAGES,
        max_depth=MAX_DEPTH,
        num_threads=NUM_THREADS,
        politeness_delay=POLITENESS_DELAY
    )
    
    # Start crawling
    crawler.start_crawling()
    
    # Write output files
    crawler.write_csv_files(OUTPUT_DIR)
    crawler.write_report(OUTPUT_DIR, STUDENT_NAME, USC_ID)
    
    print("\n✓ Crawling complete! Check the output directory for results.")


if __name__ == '__main__':
    main()
