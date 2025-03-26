# newspapers_scrap/scraper.py
import logging_config
import logging
logger = logging.getLogger(__name__)
import os
import time
import random
import asyncio
import urllib
from typing import Optional, List, Any, Dict, Coroutine

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from newspapers_scrap.config.config import env
from newspapers_scrap.data_manager import organize_article
from newspapers_scrap.security import UserAgentManager, ProxyManager, BrowserFingerprint, smart_delay, \
    exponential_backoff, SimpleRobotsParser



class NewspaperScraper:
    """Base scraper for newspaper websites"""

    def __init__(self, newspaper_key=None, config=None, apply_spell_correction=False, correction_method=None, language='fr'):
        self.config = config or env
        key = newspaper_key or 'e_newspaper_archives'
        self.newspaper_config = self.config.selectors.newspapers.e_newspaper_archives
        self.base_url = self.newspaper_config.base_url
        self.headers = self.config.scraping.request.headers.user_agent
        self.delay_min = self.config.scraping.limits.request_delay_min
        self.delay_max = self.config.scraping.limits.request_delay_max
        self._playwright = None
        self._browser = None
        self.ua_manager = UserAgentManager()
        self.fingerprint_manager = BrowserFingerprint()
        self.robots_parser = SimpleRobotsParser(user_agent="NewspaperResearchBot/1.0")
        self.respect_robots_delay = True
        self.proxy_manager = ProxyManager()
        self.current_user_agent = None
        self.current_fingerprint = None
        self.apply_spell_correction = apply_spell_correction
        self.correction_method = correction_method
        self.language = language

    async def _init_playwright(self):
        """Initialize Playwright with standard browser"""
        if not self._playwright:
            self._playwright = await async_playwright().start()

            # Get random user agent and fingerprint
            self.current_user_agent = self.ua_manager.get_random_user_agent()
            self.current_fingerprint = self.fingerprint_manager.get_random_fingerprint()

            # Use standard browser launch instead of BrightData
            self._browser = await self._playwright.chromium.launch(
                headless=True,  # Set to False for debugging
                args=['--disable-dev-shm-usage']
            )

            logger.info("Launched standard Chromium browser")

    async def _close_playwright(self):
        """Close browser and playwright instances"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def get_page(self, url, max_retries=3):
        """Fetch a webpage using Playwright with robots.txt warnings"""
        logger.info(f"Starting to fetch page: {url}")

        # Check robots.txt but don't block
        await self.robots_parser.check_url(url)
        logger.info(f"Checked robots.txt for {url}")

        # Check for robots.txt crawl delay
        if self.respect_robots_delay:
            parsed_url = urllib.parse.urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            delay = await self.robots_parser.get_crawl_delay(base_url)
            if delay:
                self.delay_min = self.delay_max = delay
                logger.info(f"Respecting crawl delay of {delay} seconds for {base_url}")

        retry_count = 0

        while retry_count < max_retries:
            try:
                # Make sure playwright is initialized
                await self._init_playwright()
                logger.info("Playwright initialized")

                # Create context with realistic browser fingerprinting
                context = await self._browser.new_context(
                    user_agent=self.current_user_agent,
                    viewport=self.current_fingerprint['viewport'],
                    locale=self.current_fingerprint['locale'],
                    timezone_id=self.current_fingerprint['timezone_id']
                )
                logger.info("Browser context created with fingerprinting")

                # Add common headers to appear more like a real browser
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => false
                    });
                """)
                logger.info("Added script to hide webdriver property")

                # Create a new page and navigate to URL
                page = await context.new_page()
                logger.info(f"New page created, navigating to {url}")
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                logger.info(f"Page navigation completed with status {response.status}")

                # Check if we hit a rate limit or other error
                if response.status >= 400:
                    retry_count += 1
                    await context.close()
                    wait_time = exponential_backoff(retry_count)
                    logger.warning(f"Got status {response.status}, retrying after {wait_time:.2f}s")
                    await asyncio.sleep(wait_time)
                    continue

                # Add random scrolling behavior like a human
                page_height = await page.evaluate('document.body.scrollHeight')
                view_port_height = self.current_fingerprint['viewport']['height']
                logger.info(f"Page height: {page_height}, Viewport height: {view_port_height}")

                # Scroll down in steps
                for i in range(0, page_height, view_port_height // 2):
                    await page.evaluate(f'window.scrollTo(0, {i})')
                    logger.info(f"Scrolled to position {i}")
                    # Random pause between scrolls like a human would
                    await asyncio.sleep(random.uniform(0.1, 0.5))

                # Wait for the page to load completely
                await page.wait_for_load_state("networkidle")
                logger.info("Page load state: networkidle")

                # Get page content and parse with BeautifulSoup
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')
                logger.info("Page content fetched and parsed with BeautifulSoup")

                # Close the context to free resources
                await context.close()
                logger.info("Browser context closed")

                return soup

            except Exception as e:
                retry_count += 1
                logger.error(f"Error fetching {url} with Playwright: {e}")
                wait_time = exponential_backoff(retry_count)
                if retry_count < max_retries:
                    logger.info(f"Retrying after {wait_time:.2f} seconds...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Max retries reached for {url}")
                    return None

    async def search(self, query: str, page: int = 1, newspapers: List[str] = None,
                     cantons: List[str] = None, deq: int = None, yeq: int = None) -> List[Dict[str, Any]]:
        """
        Search for articles and extract results from specified newspapers and cantons

        Args:
            query: The search query text
            page: The page number for pagination
            newspapers: List of newspaper codes to restrict the search to
            cantons: List of canton codes to restrict the search to
            deq: Filter by decade (e.g., 197 for 1970-1979, 200 for 2000-2009)
            yeq: Filter by specific year (e.g., 1972, 2002)
        """
        search_params = self.config.urls.search.params
        params = {
            'a': search_params.a,
            'hs': search_params.hs,
            'r': search_params.r,
            'results': search_params.results,
            'txq': query
        }

        # Add newspaper filters if specified
        if newspapers:
            params['puq'] = ','.join(newspapers)

        # Add canton filters if specified
        if cantons:
            params['ccq'] = ','.join(cantons)

        # Add decade filter if specified
        if deq is not None:
            params['deq'] = str(deq)

        # Add year filter if specified
        if yeq is not None:
            params['yeq'] = str(yeq)

        if page > 1:
            params['page'] = str(page)

        query_string = '&'.join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
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
        headers_selector = article_selectors.headers

        # Get the main content container
        content_container = soup.select_one(content_selector)
        if not content_container:
            logger.warning(f"Could not find article content for {url}")
            return ""

        # Remove header elements from the content
        for header in content_container.select(headers_selector):
            header.decompose()

        # Get the cleaned text
        text = content_container.get_text(separator='\n\n', strip=True)

        return text

    from newspapers_scrap.data_manager.organizer import organize_article

    async def save_articles_from_search(self, query: str, output_dir: str = None,
                                        max_searches: int = 1, newspapers: List[str] = None,
                                        cantons: List[str] = None, deq: int = None,
                                        yeq: int = None) -> List[Dict[str, Any]]:
        """
        Search for articles, extract their content, and save using the organizer

        Args:
            query: The search query text
            output_dir: Directory to save the articles (override default location)
            max_searches: Maximum searches to perform
            newspapers: List of newspaper codes to restrict the search to
            cantons: List of canton codes to restrict the search to
            deq: Filter by decade (e.g., 197 for 1970-1979, 200 for 2000-2009)
            yeq: Filter by specific year (e.g., 1972, 2002)

        Returns:
            List of article metadata
        """
        try:
            all_results = []
            max_pages = self.config.scraping.limits.max_search_pages
            max_results = min(max_searches, self.config.scraping.limits.max_results_per_search)

            for page in range(1, max_pages + 1):
                logger.info(f"Processing search results page {page} for query '{query}'")
                search_results = await self.search(query, page, newspapers, cantons, deq, yeq)
                if not search_results:
                    logger.info(f"No results found on page {page}. Stopping pagination.")
                    break

                for i, result in enumerate(search_results[:max_results]):
                    logger.info(f"Processing article {i + 1}/{max_results}: {result['title']}")
                    await self.add_delay()
                    article_content = await self.scrape_article_content(result['url'])
                    if not article_content:
                        logger.warning(f"No content found for article: {result['title']}")
                        continue

                    # Pass spell correction parameters to the organize_article function
                    metadata = organize_article(
                        article_text=article_content,
                        url=result['url'],
                        search_term=query,
                        article_title=result['title'],
                        newspaper_name=result.get('newspaper', 'Unknown'),
                        date_str=result.get('date', ''),
                        canton=cantons[0] if cantons else None,
                        apply_spell_correction=self.apply_spell_correction,
                        correction_method=self.correction_method,
                        language=self.language
                    )

                    all_results.append(metadata)

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
        """Add smart delay between requests to be respectful"""
        await smart_delay(self.delay_min, self.delay_max)

    def save_articles_sync(self, query: str, output_dir: str = None, max_pages: int = 1,
                           newspapers: List[str] = None, cantons: List[str] = None,
                           deq: int = None, yeq: int = None):
        """Synchronous wrapper for the async save_articles_from_search method"""
        return asyncio.run(self.save_articles_from_search(query, output_dir, max_pages,
                                                          newspapers, cantons, deq, yeq))
