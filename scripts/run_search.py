import argparse
import os
import sys
import time
import logging
import asyncio

from newspapers_scrap import scraper
from newspapers_scrap.scraper import NewspaperScraper
from newspapers_scrap.config.config import env
from newspapers_scrap.security import ProxyManager

# Set up logging
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler(sys.stdout)],
                    force=True)
logger = logging.getLogger(__name__)



async def async_main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Search and scrape newspaper articles')
    parser.add_argument('query', type=str, help='Search term')
    parser.add_argument('--pages', type=int,
                        default=env.scraping.limits.max_search_pages,
                        help='Maximum number of search pages to process')
    parser.add_argument('--newspapers', type=str, nargs='+',
                        default=['e-newspaperarchives.ch'],
                        help='Newspaper sources to search')

    parser.add_argument('--proxies', type=str, default=None,
                        help='Path to JSON file containing proxy configurations')
    args = parser.parse_args()


    if args.proxies:
        import json
        try:
            with open(args.proxies, 'r') as f:
                proxy_list = json.load(f)
                proxy_manager = ProxyManager(proxy_list)
                logger.info(f"Loaded {len(proxy_list)} proxies")
        except Exception as e:
            logger.error(f"Failed to load proxies: {e}")

    # Track timing
    start_time = time.time()

    # Create scraper instance with the new config
    scraper = NewspaperScraper(config=env)

    # Search for articles and save them
    results = await scraper.save_articles_from_search(query=args.query, max_pages=args.pages)

    # Print summary
    duration = time.time() - start_time
    logger.info(f"Processing complete. {len(results)} articles processed in {duration:.2f} seconds")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()