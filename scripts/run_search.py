# scripts/run_search.py
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
from newspapers_scrap.scraper import NewspaperScraper
from newspapers_scrap import config

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main():
    newspaper_key = 'e_newspaper_archives'
    scraper = NewspaperScraper(newspaper_key)

    search_query = "informatique"
    logger.info(f"Searching for: '{search_query}'")

    # Search, extract content and save articles
    articles = scraper.save_articles_from_search(
        query=search_query,
        output_dir="data/articles/informatique",
        max_pages=3  # Adjust based on how many pages you want to process
    )

    logger.info(f"Successfully saved {len(articles)} articles")


if __name__ == "__main__":
    main()

if __name__ == "__main__":
    main()