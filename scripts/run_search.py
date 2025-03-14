# scripts/run_search.py
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from newspapers_scrap.scraper import NewspaperScraper
from newspapers_scrap import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    logger.info("Starting newspaper search process")
    scraper = NewspaperScraper()

    search_query = "hello world"
    logger.info(f"Searching for: '{search_query}'")

    search_results = scraper.search(search_query)
    logger.info(f"Found {len(search_results)} results for query '{search_query}'")

    # Print results with logger instead of print
    for i, result in enumerate(search_results, 1):
        logger.info(f"--- Result {i} ---")
        logger.info(f"Title: {result['title']}")
        logger.info(f"URL: {result['url']}")
        logger.info(f"Newspaper: {result.get('newspaper', 'N/A')}")
        logger.info(f"Date: {result.get('date', 'N/A')}")

        # Only log snippet if it exists and isn't empty
        if result.get('snippet'):
            logger.info(f"Snippet: {result.get('snippet')}")

    logger.info("Adding delay before next operation")
    NewspaperScraper.add_delay()
    logger.info("Search process completed")


if __name__ == "__main__":
    main()