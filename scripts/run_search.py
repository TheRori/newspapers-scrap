import argparse
import os
import sys
import time
import logging
import asyncio
from newspapers_scrap.scraper import NewspaperScraper
from newspapers_scrap.config.config import env

# Set up logging
logging.basicConfig(level=logging.INFO,
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
    args = parser.parse_args()

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