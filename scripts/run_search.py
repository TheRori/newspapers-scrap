# scripts/run_search.py
import argparse
import time
import logging
from newspapers_scrap.scraper import NewspaperScraper
from newspapers_scrap.config.config import env  # Import the new config
from newspapers_scrap.data_manager.organizer import organize_article

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

    # Search for articles
    results = []
    logger.info(f"Searching for '{args.query}' across {args.pages} pages")

    # Get search results
    search_results = scraper.search(args.query, page=1)

    # Process each article
    for result in search_results:
        logger.info(f"Processing article: {result['title']}")

        # Get article content
        scraper.add_delay()
        article_content = scraper.scrape_article_content(result['url'])

        if not article_content:
            logger.warning(f"No content found for article: {result['title']}")
            continue

        # Use organizer to manage the file storage
        metadata = organize_article(
            article_text=article_content,
            url=result['url'],
            search_term=args.query,
            article_title=result['title'],
            newspaper_name=result.get('newspaper', 'Unknown'),
            date_str=result.get('date', '')
        )

        # Add to results list
        result['processed'] = True
        results.append(result)

    # Print summary
    duration = time.time() - start_time
    logger.info(f"Processing complete. {len(results)} articles processed in {duration:.2f} seconds")


if __name__ == "__main__":
    main()