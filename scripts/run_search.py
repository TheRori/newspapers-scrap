# scripts/run_search.py
import argparse
import time
import logging
from newspapers_scrap.scraper import NewspaperScraper
from newspapers_scrap.config.config import env  # Import the new config

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Search and scrape newspaper articles')
    parser.add_argument('query', type=str, help='Search term')
    parser.add_argument('--pages', type=int,
                        default=env.scraping.limits.max_search_pages,  # Use config value
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
    results = scraper.save_articles_from_search(query=args.query, max_pages=args.pages)

    # Print summary
    duration = time.time() - start_time
    logger.info(f"Processing complete. {len(results)} articles processed in {duration:.2f} seconds")

if __name__ == "__main__":
    main()