# newspapers_scrap/scraper.py
import re

import logging_config
import logging

from newspapers_scrap.performance_tracker import PerformanceTracker
from newspapers_scrap.utils import clean_and_parse_date

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

    def __init__(self, newspaper_key=None, config=None, apply_spell_correction=False, correction_method=None):
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
        self.performance_tracker = PerformanceTracker()

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
                     cantons: List[str] = None, decade: str = None, year: str = None) -> Dict[str, Any]:
        """
        Search for articles and extract results from specified newspapers and cantons

        Args:
            query: The search query text
            page: The page number for pagination
            newspapers: List of newspaper codes to restrict the search to
            cantons: List of canton codes to restrict the search to
            decade: Decade to search (e.g., "197" for 1970s)
            year: Specific year to search (e.g., "1975")

        Returns:
            Dictionary containing articles and total_results count
        """
        search_params = self.config.urls.search.params
        params = {
            'a': search_params.a,
            'hs': search_params.hs,
            'results': search_params.results,
            'txq': query,
            'l': 'de'
        }

        # Calculate the starting result index for pagination
        # Each page has 20 results, so page 1 starts at r=1, page 2 at r=21, etc.
        start_index = ((page - 1) * 20) + 1
        params['r'] = str(start_index)

        # Add newspaper filters if specified
        if newspapers:
            params['puq'] = ','.join(newspapers)

        # Add canton filters if specified
        if cantons:
            params['ccq'] = ','.join(cantons)

        # Add decade filter if specified (e.g., '197' for 1970s)
        if decade:
            params['deq'] = decade

        # Add year filter if specified (e.g., '1975')
        if year:
            params['yeq'] = year

        query_string = '&'.join([f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items()])
        search_url = f"{self.base_url}/?{query_string}"
        logger.info(f"Searching with URL: {search_url}")
        soup = await self.get_page(search_url)
        if not soup:
            return {"articles": [], "total_results": 0}

        # Extract search results and total count
        articles = self._extract_search_results(soup)
        total_results = self._extract_total_results(soup)

        return {
            "articles": articles,
            "total_results": total_results
        }

    def _extract_total_results(self, soup: BeautifulSoup) -> int:
        """Extract the total number of results from the search results header"""
        try:
            # Look for the search results header
            header = soup.select_one('#searchresultsheader')
            if header:
                summary = header.select_one('#searchresultssummary')
                if summary:
                    # Parse text like "Ergebnisse 41 - 60 von 271 für Apple"
                    summary_text = summary.text.strip()
                    logger.debug(f"Extracted summary text: {summary_text}")
                    # Find the number after "von" and before "für"
                    match = re.search(r'von\s+([0-9,\.]+)\s+f[üu�]r', summary_text)
                    if match:
                        num_str = match.group(1).replace(',', '').replace('.', '')
                        return int(num_str)
            # If we can't find it or parse it, check if there are any results
            result_items = soup.select(self.config.selectors.search_selectors.result_item)
            if result_items:
                return len(result_items)  # Return at least the count of current results

            return 0
        except Exception as e:
            logger.warning(f"Could not extract total results count: {e}")
            return 0

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

    @staticmethod
    def parse_article_date(date_str):
        """
        Parse date strings from article metadata into datetime objects.

        Args:
            date_str: String containing date information

        Returns:
            Parsed date in YYYY-MM-DD format or None if parsing fails
        """
        try:
            # Use the existing clean_and_parse_date utility function
            parsed_date = clean_and_parse_date(date_str)
            if parsed_date:
                return parsed_date.strftime('%Y-%m-%d')
            return None
        except Exception as e:
            logger.warning(f"Failed to parse date '{date_str}': {e}")
            return None

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
                                        max_articles: int = None, newspapers: List[str] = None,
                                        cantons: List[str] = None, decade: str = None,
                                        year: str = None) -> List[Dict[str, Any]]:
        """
        Search for articles, extract their content, and save using the organizer

        Args:
            query: The search query text
            output_dir: Directory to save the articles (override default location)
            max_articles: Maximum articles to process (None = process all found)
            newspapers: List of newspaper codes to restrict the search to
            cantons: List of canton codes to restrict the search to
            decade: Decade to search (e.g., "197" for 1970s)
            year: Specific year to search (e.g., "1975")

        Returns:
            List of article metadata
        """
        try:
            self.performance_tracker.start_tracking()  # Start tracking
            all_results = []
            config_max = self.config.scraping.limits.max_results_per_search

            # Get first page of results to determine total count
            page = 1

            # Create a copy of the search parameters
            search_params = {
                'query': query,
                'page': page,
                'newspapers': newspapers,
                'cantons': cantons
            }

            # Add decade or year filter if specified
            if decade:
                search_params['decade'] = decade
            if year:
                search_params['year'] = year

            search_result = await self.search(**search_params)
            total_results = search_result["total_results"]
            articles = search_result["articles"]

            # If no results found, return empty list
            if total_results == 0:
                logger.info(f"No results found for query '{query}'")
                return []

            # Determine max articles to process
            if max_articles is None:
                # Use config limit if no specific limit is provided
                max_articles = min(total_results, config_max)
            else:
                # Honor user-specified limit, but cap at total available
                max_articles = min(max_articles, total_results)

            logger.info(f"Found {total_results} total results for query '{query}', processing up to {max_articles}")

            # Process articles
            total_collected = 0

            while total_collected < max_articles:
                if not articles:
                    # If no more articles on current page, go to next page
                    page += 1
                    await self.add_delay()

                    # Update page number in search parameters
                    search_params['page'] = page
                    search_result = await self.search(**search_params)
                    articles = search_result["articles"]

                    if not articles:
                        logger.info(f"No more results found on page {page}. Stopping pagination.")
                        break

                # Get the next article to process
                article = articles.pop(0)

                logger.info(f"Processing article {total_collected + 1}/{max_articles}: {article['title']}")
                await self.add_delay()
                article_content = await self.scrape_article_content(article['url'])

                if not article_content:
                    logger.warning(f"No content found for article: {article['title']}")
                    continue

                # Process and save the article
                metadata = organize_article(
                    article_text=article_content,
                    url=article['url'],
                    search_term=query,
                    article_title=article['title'],
                    newspaper_name=article.get('newspaper', 'Unknown'),
                    date_str=article.get('date', ''),
                    canton=cantons[0] if cantons else None,
                    apply_spell_correction=self.apply_spell_correction,
                    correction_method=self.correction_method,
                )

                self.performance_tracker.track_article(article.get('date', ''))  # Track the article date

                all_results.append(metadata)
                total_collected += 1

                # Check if we've reached the maximum
                if total_collected >= max_articles:
                    break

            return all_results
        finally:
            self.performance_tracker.stop_tracking()  # Stop tracking
            summary = self.performance_tracker.generate_summary()  # Generate summary
            logger.info(f"Scraping summary: {summary}")
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

    def save_articles_sync(self, query: str, output_dir: str = None, max_articles: int = None,
                           newspapers: List[str] = None, cantons: List[str] = None):
        """Synchronous wrapper for the async save_articles_from_search method"""
        return asyncio.run(self.save_articles_from_search(query, output_dir, max_articles,
                                                          newspapers, cantons))
