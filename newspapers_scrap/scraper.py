# newspapers_scrap/scraper.py
import requests
from bs4 import BeautifulSoup
import time
import random
import logging
import os
from typing import Dict, List, Any, Optional
from newspapers_scrap import config

logger = logging.getLogger(__name__)


class NewspaperScraper:
    """Base scraper for newspaper websites"""

    def __init__(self, newspaper_key=None):
        key = newspaper_key or 'e_newspaper_archives'
        self.newspaper_config = config.NEWSPAPERS[key]
        self.base_url = self.newspaper_config['base_url']
        self.headers = config.HEADERS

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Get and parse a page with BeautifulSoup"""
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
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
        # Build query parameters
        params = config.SEARCH_PARAMS.copy()
        params['txq'] = query.replace(' ', '+')
        if page > 1:
            params['page'] = str(page)

        # Build query string
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        search_url = f"{self.base_url}/?{query_string}"

        logger.info(f"Searching with URL: {search_url}")

        soup = self.get_page(search_url)
        if not soup:
            return []

        results = []
        result_items = soup.select(config.SEARCH_RESULT_ITEM_SELECTOR)

        for item in result_items:
            title_elem = item.select_one(config.SEARCH_RESULT_TITLE_SELECTOR)
            url_elem = item.select_one(config.SEARCH_RESULT_LINK_SELECTOR)

            if title_elem and url_elem and url_elem.get('href'):
                result_url = url_elem['href']
                if not result_url.startswith('http'):
                    result_url = self.base_url.rstrip('/') + result_url

                # Extract newspaper and date (they're in the same div)
                newspaper_date_text = self._extract_by_selector(item, config.SEARCH_RESULT_NEWSPAPER_SELECTOR, False)

                # The newspaper date text looks like: "Berner Tagwacht 19 June 1991"
                newspaper = newspaper_date_text.split(' ', 1)[0] if newspaper_date_text else ""
                date = newspaper_date_text.split(' ', 1)[
                    1] if newspaper_date_text and ' ' in newspaper_date_text else ""

                results.append({
                    "title": title_elem.text.strip() if title_elem else "",
                    "url": result_url,
                    "snippet": self._extract_by_selector(item, config.SEARCH_RESULT_SNIPPET_SELECTOR, False),
                    "newspaper": newspaper,
                    "date": date
                })

        return results

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