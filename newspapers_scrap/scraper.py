# newspapers_scrap/scraper.py
import os
import time
import logging
import random
import asyncio
from typing import Optional, List, Any, Dict, Coroutine

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from newspapers_scrap.config.config import env

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
        self._playwright = None
        self._browser = None

    async def _init_playwright(self):
        """Initialize playwright and browser if not already done"""
        if self._playwright is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=True
            )

    async def _close_playwright(self):
        """Close browser and playwright instances"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def get_page(self, url: str) -> Optional[BeautifulSoup]:
        """Get and parse a page using Playwright to execute JavaScript"""
        try:
            # Make sure playwright is initialized
            await self._init_playwright()

            # Create a new context with custom user agent
            context = await self._browser.new_context(
                user_agent=self.headers,
                viewport={'width': 1280, 'height': 720}
            )

            # Create a new page and navigate to URL
            page = await context.new_page()
            await page.goto(url, wait_until="networkidle")

            # Wait for the page to load completely
            await page.wait_for_load_state("networkidle")

            # Get page content and parse with BeautifulSoup
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # Close the context to free resources
            await context.close()

            return soup

        except Exception as e:
            logger.error(f"Error fetching {url} with Playwright: {e}")
            return None

    async def search(self, query: str, page: int = 1) -> List[Dict[str, Any]]:
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
        soup = await self.get_page(search_url)
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

    async def scrape_article_content(self, url: str) -> str:
        """Extract the full article text content from a newspaper article page"""
        soup = await self.get_page(url)
        if not soup:
            logger.warning(f"Could not fetch page content for {url}")
            return ""
        article_selectors = self.config.selectors.article_selectors
        content_selector = article_selectors.article_text

        text = self._extract_by_selector(soup, content_selector, join_texts=True)
        if not text:
            logger.warning(f"Could not find article content for {url}")
        return text

    async def save_articles_from_search(self, query: str, output_dir: str = None, max_pages: int = 1) -> None:
        """Search for articles, extract their content, and save to files"""
        try:
            all_results = []
            if not output_dir:
                raw_data_dir = self.config.storage.paths.raw_data_dir
                output_dir = os.path.join(raw_data_dir, "articles", query.replace(" ", "_"))
            os.makedirs(output_dir, exist_ok=True)
            max_pages = min(max_pages, self.config.scraping.limits.max_search_pages)

            for page in range(1, max_pages + 1):
                logger.info(f"Processing search results page {page} for query '{query}'")
                search_results = await self.search(query, page)
                if not search_results:
                    logger.info(f"No results found on page {page}. Stopping pagination.")
                    break
                max_results = min(len(search_results), self.config.scraping.limits.max_results_per_search)

                for i, result in enumerate(search_results[:max_results]):
                    logger.info(f"Processing article {i + 1}/{max_results}: {result['title']}")
                    await self.add_delay()
                    article_content = await self.scrape_article_content(result['url'])
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
                    await self.add_delay()

            return all_results
        finally:
            # Always ensure browser and playwright are closed
            await self._close_playwright()

    @staticmethod
    def _extract_by_selector(soup, selector, join_texts=False):
        """Extract text content from a BeautifulSoup object using a CSS selector"""
        elements = soup.select(selector)
        if not elements:
            return ""
        if join_texts:
            return "\n\n".join([el.text.strip() for el in elements])
        return elements[0].text.strip()

    async def add_delay(self):
        """Add random delay between requests to be respectful"""
        await asyncio.sleep(random.uniform(self.delay_min, self.delay_max))

    def save_articles_sync(self, query: str, output_dir: str = None, max_pages: int = 1) -> List[Dict[str, Any]]:
        """Synchronous wrapper for the async save_articles_from_search method"""
        return asyncio.run(self.save_articles_from_search(query, output_dir, max_pages))