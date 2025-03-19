import random
import re
import asyncio
import logging
import aiohttp
import json
import time
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class UserAgentManager:
    """Manages a collection of realistic user agents for rotation"""

    def __init__(self):
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1'
        ]

    def get_random_user_agent(self) -> str:
        """Return a random user agent from the collection"""
        return random.choice(self.user_agents)


class ProxyManager:
    """Manages proxy configuration if available"""

    def __init__(self, proxies: List[Dict[str, str]] = None, bright_data_manager= None):
        self.proxies = proxies or []
        self.bright_data_manager = bright_data_manager

    def get_random_proxy(self) -> Optional[Dict[str, Any]]:
        """Return either BrightData proxy or a random proxy configuration"""
        # Prefer BrightData if available
        if self.bright_data_manager and self.bright_data_manager.proxy_url:
            return self.bright_data_manager.get_proxy_config()

        # Fall back to regular proxies
        if not self.proxies:
            return None

        proxy = random.choice(self.proxies)
        return {
            "server": f"{proxy.get('protocol', 'http')}://{proxy.get('host')}:{proxy.get('port')}",
            "username": proxy.get('username'),
            "password": proxy.get('password')
        }

    async def rotate_ip(self) -> bool:
        """Rotate IP if using BrightData"""
        if self.bright_data_manager:
            return await self.bright_data_manager.rotate_ip()
        return False


class BrowserFingerprint:
    """Generates realistic browser fingerprints"""

    def __init__(self):
        self.viewports = [
            {'width': 1920, 'height': 1080},
            {'width': 1366, 'height': 768},
            {'width': 1536, 'height': 864},
            {'width': 1440, 'height': 900},
            {'width': 1280, 'height': 720}
        ]
        self.locales = ['en-US', 'en-GB', 'en-CA', 'de-DE', 'fr-FR']
        self.timezones = ['America/New_York', 'Europe/London', 'Europe/Berlin', 'Asia/Tokyo', 'Australia/Sydney']

    def get_random_fingerprint(self) -> Dict[str, Any]:
        """Generate a random browser fingerprint"""
        return {
            'viewport': random.choice(self.viewports),
            'locale': random.choice(self.locales),
            'timezone_id': random.choice(self.timezones)
        }


import urllib.parse
import aiohttp
from urllib.robotparser import RobotFileParser
import logging

logger = logging.getLogger(__name__)


class SimpleRobotsParser:
    """Basic robots.txt parser that logs warnings but doesn't block requests"""

    def __init__(self, user_agent="NewspaperResearchBot/1.0"):
        self.user_agent = user_agent
        self.rules_cache = {}

    async def fetch_robots_txt(self, base_url):
        """Fetch and parse robots.txt file"""
        try:
            robots_url = urllib.parse.urljoin(base_url, "/robots.txt")
            if robots_url in self.rules_cache:
                return self.rules_cache[robots_url]

            async with aiohttp.ClientSession() as session:
                async with session.get(robots_url, timeout=10) as response:
                    if response.status == 200:
                        content = await response.text()
                        parser = RobotFileParser()
                        parser.parse(content.splitlines())
                        self.rules_cache[robots_url] = parser
                        return parser
        except Exception as e:
            logger.warning(f"Error fetching robots.txt: {e}")

        # Return empty parser if we can't fetch
        empty_parser = RobotFileParser()
        empty_parser.allow_all = True
        self.rules_cache[base_url] = empty_parser
        return empty_parser

    async def check_url(self, url):
        """Check if URL is allowed, log warning but don't block"""
        parsed_url = urllib.parse.urlparse(url)
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"

        parser = await self.fetch_robots_txt(base_url)
        path = parsed_url.path
        if parsed_url.query:
            path = f"{path}?{parsed_url.query}"

        if not parser.can_fetch(self.user_agent, path):
            logger.warning(f"⚠️ URL {url} is disallowed by robots.txt, but proceeding anyway")
            return False
        return True

    async def get_crawl_delay(self, base_url):
        """Get crawl delay if specified"""
        parser = await self.fetch_robots_txt(base_url)
        delay = parser.crawl_delay(self.user_agent)
        if delay:
            logger.info(f"Robots.txt specifies {delay}s delay for {base_url}")
        return delay if delay is not None else 1  # Default to 1s


async def smart_delay(min_delay: float, max_delay: float) -> None:
    """Add variable delay between requests with randomized patterns"""
    base_delay = random.uniform(min_delay, max_delay)

    # Occasionally add extra delay to simulate human breaks (10% chance)
    if random.random() < 0.1:
        extra_delay = random.uniform(2, 5)
        logger.debug(f"Taking a slightly longer break ({base_delay + extra_delay:.2f}s)")
        await asyncio.sleep(base_delay + extra_delay)
    else:
        await asyncio.sleep(base_delay)


def exponential_backoff(retry_count: int, base_wait: float = 1.0) -> float:
    """Calculate exponential backoff time based on retry count"""
    return base_wait * (2 ** retry_count) * (0.5 + random.random())