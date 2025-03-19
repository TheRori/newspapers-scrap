# newspapers_scrap/scraper.py
import requests
from bs4 import BeautifulSoup
import time
import random
import logging
import os
from typing import Dict, List, Any, Optional
from newspapers_scrap.config.config import env
from selenium import webdriver
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

logger = logging.getLogger(__name__)

class NewspaperScraper:
    """Base scraper for newspaper websites"""

    def __init__(self, newspaper_key=None, config=None):
        self.config = config or env
        key = newspaper_key or 'e_newspaper_archives'
        self.newspaper_config = self.config.selectors.newspapers.e_newspaper_archives
        self.base_url = self.newspaper_config.base_url
        self.headers = self.config.scraping.request.headers.user_agent
        self.delay_min = self.config.scraping.limits.request_delay_min
        self.delay_max = self.config.scraping.limits.request_delay_max

    def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Get and parse a page using Selenium with Edge to execute JavaScript"""
        try:
            edge_options = EdgeOptions()
            edge_options.add_argument("--headless")
            edge_options.add_argument("--no-sandbox")
            edge_options.add_argument("--disable-dev-shm-usage")
            edge_options.add_argument(f"user-agent={self.headers}")

            service = EdgeService(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=edge_options)
            driver.get(url)
            time.sleep(3)  # Adjust the wait time as needed
            html = driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            driver.quit()
            return soup
        except Exception as e:
            logger.error(f"Error fetching {url} with Selenium: {e}")
            return None

    def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
        """Search for articles and extract results from all newspapers"""
        search_params = self.config.urls.search.params
        params = {
            'a': search_params.a,
            'hs': search_params.hs,
            'r': search_params.r,
            'results': search_params.results,
            'txq': query
        }
        if page > 1:
            params['page'] = str(page)
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        search_url = f"{self.base_url}/?{query_string}"
        logger.info(f"Searching with URL: {search_url}")
        soup = self.get_page(search_url)
        if not soup:
            return []
        return self._extract_search_results(soup)

    def _extract_search_results(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract search results from the soup object"""
        results = []
        search_selectors = self.config.selectors.search_selectors
        result_items = soup.select(search_selectors.result_item)
        for item in result_items:
            link_elem = item.select_one(search_selectors.result_link)
            if not link_elem or not link_elem.get('href'):
                continue
            article_url = link_elem['href']
            if not article_url.startswith('http'):
                article_url = self.base_url + article_url
            title_elem = link_elem.select_one(search_selectors.result_title)
            title = title_elem.text.strip() if title_elem else link_elem.text.strip()
            info_div = item.select_one(search_selectors.result_newspaper)
            newspaper_date = info_div.text.strip() if info_div else ""
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
        soup = self.get_page(url)
        if not soup:
            logger.warning(f"Could not fetch page content for {url}")
            return ""
        article_selectors = self.config.selectors.article_selectors
        content_selector = article_selectors.article_text
        content_container = soup.select_one(content_selector)
        if not content_container:
            logger.warning(f"Could not find article content container for {url} with the selector: {content_selector}")
            return ""
        paragraphs = content_container.find_all('p')
        if paragraphs:
            text = "\n\n".join([p.get_text(strip=True) for p in paragraphs])
        else:
            text = content_container.get_text(strip=True, separator="\n\n")
        return text

    def save_articles_from_search(self, query: str, output_dir: str = None, max_pages: int = 1) -> List[Dict[str, Any]]:
        """Search for articles, extract their content, and save to files"""
        all_results = []
        if not output_dir:
            raw_data_dir = self.config.storage.paths.raw_data_dir
            output_dir = os.path.join(raw_data_dir, "articles", query.replace(" ", "_"))
        os.makedirs(output_dir, exist_ok=True)
        max_pages = min(max_pages, self.config.scraping.limits.max_search_pages)
        for page in range(1, max_pages + 1):
            logger.info(f"Processing search results page {page} for query '{query}'")
            search_results = self.search(query, page)
            if not search_results:
                logger.info(f"No results found on page {page}. Stopping pagination.")
                break
            max_results = min(len(search_results), self.config.scraping.limits.max_results_per_search)
            for i, result in enumerate(search_results[:max_results]):
                logger.info(f"Processing article {i + 1}/{max_results}: {result['title']}")
                self.add_delay()
                article_content = self.scrape_article_content(result['url'])
                if not article_content:
                    logger.warning(f"No content found for article: {result['title']}")
                    continue
                date_str = result.get('date', '').replace(' ', '_').replace(',', '')
                safe_title = ''.join(c if c.isalnum() else '_' for c in result['title'][:30])
                filename = f"{date_str}_{safe_title}.txt"
                filepath = os.path.join(output_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Title: {result['title']}\n")
                    f.write(f"URL: {result['url']}\n")
                    f.write(f"Newspaper: {result.get('newspaper', 'N/A')}\n")
                    f.write(f"Date: {result.get('date', 'N/A')}\n\n")
                    f.write(article_content)
                    logger.info(f"Saved article to {filepath}")
                result['full_content'] = article_content
                result['saved_path'] = filepath
                all_results.append(result)
            if page < max_pages:
                self.add_delay()
        return all_results

    @staticmethod
    def _extract_by_selector(soup, selector, join_texts=False):
        """Extract text content from a BeautifulSoup object using a CSS selector"""
        elements = soup.select(selector)
        if not elements:
            return ""
        if join_texts:
            return "\n\n".join([el.text.strip() for el in elements])
        return elements[0].text.strip()

    def add_delay(self):
        """Add random delay between requests to be respectful"""
        time.sleep(random.uniform(self.delay_min, self.delay_max))