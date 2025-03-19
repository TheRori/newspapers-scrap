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
    parser = argparse.ArgumentParser(description='Search for newspaper articles')
    parser.add_argument('query', help='Search query text')
    parser.add_argument('--newspapers', type=str, nargs='+', help='Newspaper codes to search (e.g., LLE for La Liberté)')
    parser.add_argument('--output', type=str, help='Output directory to save articles', default=None)
    parser.add_argument('--pages', type=int, help='Maximum pages to search', default=1)
    parser.add_argument('--proxies', type=str, default=None, help='Path to JSON file containing proxy configurations')
    parser.add_argument('--cantons', type=str, nargs='+', help='Canton codes to search (e.g., GE for Geneva)')
    parser.add_argument('--deq', type=str, help='Filter by decade (e.g., 197 for 1970-1979, 200 for 2000-2009)')
    parser.add_argument('--yeq', type=str, help='Filter by specific year (e.g., 1972, 2002)')

    args = parser.parse_args()

    proxy_manager = None
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
    results = await scraper.save_articles_from_search(
        query=args.query,
        output_dir=args.output,
        max_pages=args.pages,
        newspapers=args.newspapers,
        cantons=args.cantons,
        deq=args.deq,
        yeq=args.yeq
    )

    # Print summary
    duration = time.time() - start_time
    logger.info(f"Processing complete. {len(results) if results else 0} articles processed in {duration:.2f} seconds")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()