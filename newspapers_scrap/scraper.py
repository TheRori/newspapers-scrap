# newspapers_scrap/scraper.py
import requests
from bs4 import BeautifulSoup
import time
import random
import logging
import os
from typing import Dict, List, Any, Optional
from newspapers_scrap import config
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

logger = logging.getLogger(__name__)


class NewspaperScraper:
    """Base scraper for newspaper websites"""

    def __init__(self, newspaper_key=None):
        key = newspaper_key or 'e_newspaper_archives'
        self.newspaper_config = config.NEWSPAPERS[key]
        self.base_url = self.newspaper_config['base_url']
        self.headers = config.HEADERS

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Get and parse a page using Selenium with Edge to execute JavaScript"""
        try:
            # Set up Edge options
            edge_options = EdgeOptions()
            edge_options.add_argument("--headless")
            edge_options.add_argument("--no-sandbox")
            edge_options.add_argument("--disable-dev-shm-usage")

            # Add debugging information
            logger.debug("Setting up Edge WebDriver")

            # Initialize Edge browser
            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=edge_options)
            logger.debug("Edge WebDriver initialized successfully")

            # Load the page
            logger.debug(f"Loading page: {url}")
            driver.get(url)

            # Wait for AJAX content to load
            logger.debug("Waiting for AJAX content to load")
            time.sleep(3)  # Adjust the wait time as needed

            # Get the rendered HTML
            html = driver.page_source
            logger.debug(f"Retrieved page HTML (length: {len(html)})")

            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')

            # Close the browser
            driver.quit()

            return soup
        except Exception as e:
            logger.error(f"Error fetching {url} with Selenium: {e}")
            return None

    def scrape_article(self, url: str) -> Dict[str, Any]:
        """Scrape a single article"""
        soup = self.get_page(url)
        if not soup:
            return {}

        article = {
            "url": url,
            "title": self._extract_by_selector(soup, self.newspaper_config['title_selector']),
            "content": self._extract_by_selector(soup, self.newspaper_config['content_selector'], join_texts=True),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        return article

    def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """Search for articles and extract results from all newspapers"""
        # Build query parameters based on the actual URL structure
        params = {
            'a': 'q',
            'hs': '1',
            'r': '1',
            'results': '1',
            'txq': query
        }

        if page > 1:
            params['page'] = str(page)

        # Build search URL
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        search_url = f"{self.base_url}/?{query_string}"

        logger.info(f"Searching with URL: {search_url}")

        soup = self.get_page(search_url)
        if not soup:
            return []

        results = []
        # Update selector to match the actual HTML structure
        result_items = soup.select("div.vlistentry.searchresult")

        for item in result_items:
            # Find the main link in the search result
            link_elem = item.select_one("div.vlistentrymaincell a")
            if not link_elem or not link_elem.get('href'):
                continue

            article_url = link_elem['href']
            # Handle relative URLs
            if not article_url.startswith('http'):
                article_url = self.base_url + article_url

            # Extract title - it's in a span with class containing "Title"
            title_elem = link_elem.select_one("span[class*='-Title-']")
            title = title_elem.text.strip() if title_elem else link_elem.text.strip()

            # Extract newspaper and date information
            info_div = item.select_one("div.vlistentrymaincell > div:nth-of-type(2)")
            newspaper_date = info_div.text.strip() if info_div else ""

            # Split newspaper and date
            parts = newspaper_date.strip().split(' ', 2)
            newspaper = ' '.join(parts[0:2]) if len(parts) >= 2 else parts[0] if parts else ""
            date = parts[-1] if len(parts) >= 3 else ""

            results.append({
                "title": title,
                "url": article_url,
                "newspaper": newspaper,
                "date": date
            })

        return results

    def scrape_article_content(self, url: str) -> str:
        """Extract the full article text content from a newspaper article page"""
        # Use Selenium to get the page with JavaScript executed
        soup = self.get_page(url)
        if not soup:
            return ""

        # Target the container with the article text
        content_container = soup.select_one("#documentdisplayleftpanesectiontextcontainer")
        if not content_container:
            logger.warning(f"Could not find article content container for {url}")
            return ""

        logger.debug(f"Content container HTML: {content_container}")

        # Extract text from the container
        text = content_container.get_text(strip=True, separator="\n\n")
        return text

    def get_article_with_content(self, url: str) -> Dict[str, Any]:
        """Get article metadata and full content"""
        soup = self.get_page(url)
        if not soup:
            return {}

        # Get basic article info
        article = {"url": url, "title": self._extract_by_selector(soup, self.newspaper_config['title_selector']),
                   "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "content": self.scrape_article_content(url)}

        # Get full article content
        return article

    def process_search_results(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """Search for articles and fetch their complete content"""
        search_results = self.search(query, page)
        articles_with_content = []

        for result in search_results:
            logger.info(f"Processing article: {result['title']}")
            # Add delay between requests
            self.add_delay()

            # Get article full content
            article_content = self.scrape_article_content(result['url'])

            # Add content to result
            result['full_content'] = article_content
            articles_with_content.append(result)

        return articles_with_content

    def save_articles_from_search(self, query: str, output_dir: str = None, max_pages: int = 1) -> List[Dict[str, Any]]:
        """Search for articles, extract their content, and save to files"""
        all_results = []

        # Create output directory
        if not output_dir:
            output_dir = os.path.join("data", "articles", query.replace(" ", "_"))
        os.makedirs(output_dir, exist_ok=True)

        # Process each page of search results
        for page in range(1, max_pages + 1):
            logger.info(f"Processing search results page {page} for query '{query}'")

            # Get search results for current page
            search_results = self.search(query, page)
            if not search_results:
                logger.info(f"No results found on page {page}. Stopping pagination.")
                break

            # Process each article
            for i, result in enumerate(search_results):
                logger.info(f"Processing article {i + 1}/{len(search_results)}: {result['title']}")

                # Get article content
                self.add_delay()  # Be respectful with requests
                article_content = self.scrape_article_content(result['url'])

                # Skip if no content found
                if not article_content:
                    logger.warning(f"No content found for article: {result['title']}")
                    continue

                # Create filename for article
                date_str = result.get('date', '').replace(' ', '_').replace(',', '')
                safe_title = ''.join(c if c.isalnum() else '_' for c in result['title'][:30])
                filename = f"{date_str}_{safe_title}.txt"
                filepath = os.path.join(output_dir, filename)

                # Save article to file
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Title: {result['title']}\n")
                    f.write(f"URL: {result['url']}\n")
                    f.write(f"Newspaper: {result.get('newspaper', 'N/A')}\n")
                    f.write(f"Date: {result.get('date', 'N/A')}\n\n")
                    f.write(article_content)

                logger.info(f"Saved article to {filepath}")

                # Add to results
                result['full_content'] = article_content
                result['saved_path'] = filepath
                all_results.append(result)

            # Add delay between pages
            if page < max_pages:
                self.add_delay()

        return all_results

    @staticmethod
    def _extract_by_selector(soup, selector, join_texts=False):
        elements = soup.select(selector)
        if not elements:
            return ""
        if join_texts:
            return "\n\n".join([el.text.strip() for el in elements])
        return elements[0].text.strip()

    @staticmethod
    def add_delay():
        """Add random delay between requests to be respectful"""
        time.sleep(random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX))