import logging_config
import logging
import sys

logger = logging.getLogger(__name__)
# Ajouter un handler stdout s'il n'y en a pas
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
import argparse
import os
import time
import asyncio

from newspapers_scrap import scraper
from newspapers_scrap.scraper import NewspaperScraper
from newspapers_scrap.config.config import env
from newspapers_scrap.security import ProxyManager

# Variable globale pour stocker le scraper
current_scraper = None


# Fonction pour vérifier si un signal d'arrêt a été reçu
def check_stop_signal():
    if os.path.exists('stop_signal.txt'):
        logger.info("Stop signal detected")
        return True
    return False

async def async_main():
    global current_scraper
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Search for newspaper articles')
    parser.add_argument('query', help='Search query text')
    parser.add_argument('--newspapers', type=str, nargs='+', help='Newspaper codes to search')
    parser.add_argument('--output', type=str, help='Output directory to save articles', default=None)
    parser.add_argument('--max_articles', type=int, help='Maximum articles to retrieve', default=None)
    parser.add_argument('--proxies', type=str, default=None, help='Path to JSON file with proxy configurations')
    parser.add_argument('--cantons', type=str, nargs='+', help='Canton codes to search')
    parser.add_argument('--date_range', type=str, help='Date range in format YYYY-YYYY')
    parser.add_argument('--search_by', choices=['year', 'decade'], default='year',
                        help='Search by year or decade')
    parser.add_argument('--correction', type=str, choices=['mistral', 'symspell'],
                        help='Spell correction method to use')
    parser.add_argument('--no-correction', action='store_true',
                        help='Disable spell correction')
    parser.add_argument('--all_time', action='store_true', help='Search all time')

    args = parser.parse_args()
    logger.debug('Searching for newspaper articles')
    
    # Log the search period for detection by app.py
    log_search_period(args)

    # Initialize proxy manager if needed
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
    results = []

    try:
        if args.all_time:
            # Search without date filtering
            logger.info("Searching all time")
            try:
                current_scraper = NewspaperScraper(
                    apply_spell_correction=not args.no_correction,
                    correction_method=args.correction,
                )

                results = await current_scraper.save_articles_from_search(
                    query=args.query,
                    output_dir=args.output,
                    max_articles=args.max_articles,
                    newspapers=args.newspapers,
                    cantons=args.cantons
                )
            except Exception as e:
                logger.error(f"Error in search: {e}")
            finally:
                # Ensure resources are properly closed
                try:
                    if current_scraper:
                        await current_scraper._close_playwright()
                except Exception as e:
                    logger.error(f"Error closing scraper: {e}")
        else:
            # Process date range
            if args.date_range:
                try:
                    start_year, end_year = map(int, args.date_range.split('-'))

                    # Ensure start_year <= end_year
                    if start_year > end_year:
                        start_year, end_year = end_year, start_year

                    logger.info(f"Searching for years from {start_year} to {end_year}")

                    if args.search_by == 'decade':
                        # Search by decades
                        logger.info("Using decade-based search")
                        for decade_start in range(start_year // 10 * 10, end_year + 1, 10):
                            decade = str(decade_start)[:3]  # Format: "197" for 1970s
                            decade_end = min(decade_start + 9, end_year)
                            logger.info(f"Searching decade {decade}0s ({decade_start}-{decade_end})")

                            try:
                                current_scraper = NewspaperScraper(
                                    apply_spell_correction=not args.no_correction,
                                    correction_method=args.correction,
                                )

                                # Vérifier le signal d'arrêt avant de commencer
                                if check_stop_signal():
                                    logger.info("Stopping search due to stop signal")
                                    break
                                
                                # Search for the entire decade
                                decade_results = await current_scraper.save_articles_from_search(
                                    query=args.query,
                                    output_dir=args.output,
                                    max_articles=args.max_articles,
                                    newspapers=args.newspapers,
                                    cantons=args.cantons,
                                    decade=decade
                                )

                                if decade_results:
                                    results.extend(decade_results)
                            except Exception as e:
                                logger.error(f"Error searching decade {decade}0s: {e}")
                            finally:
                                # Ensure resources are properly closed even if an error occurs
                                try:
                                    if current_scraper:
                                        await current_scraper._close_playwright()
                                except Exception as e:
                                    logger.error(f"Error closing scraper: {e}")
                    else:
                        # Search by individual years
                        logger.info("Using year-based search")
                        for year in range(start_year, end_year + 1):
                            logger.info(f"Searching year {year}")

                            try:
                                current_scraper = NewspaperScraper(
                                    apply_spell_correction=not args.no_correction,
                                    correction_method=args.correction,
                                )

                                # Vérifier le signal d'arrêt avant de commencer
                                if check_stop_signal():
                                    logger.info("Stopping search due to stop signal")
                                    break
                                    
                                # Search for a specific year
                                year_results = await current_scraper.save_articles_from_search(
                                    query=args.query,
                                    output_dir=args.output,
                                    max_articles=args.max_articles,
                                    newspapers=args.newspapers,
                                    cantons=args.cantons,
                                    year=str(year)
                                )

                                if year_results:
                                    results.extend(year_results)
                            except Exception as e:
                                logger.error(f"Error searching year {year}: {e}")
                            finally:
                                # Ensure resources are properly closed even if an error occurs
                                try:
                                    if current_scraper:
                                        await current_scraper._close_playwright()
                                except Exception as e:
                                    logger.error(f"Error closing scraper: {e}")
                except ValueError:
                    logger.error(f"Invalid date range format: {args.date_range}. Expected YYYY-YYYY")
                    return
            else:
                # Standard search without date filtering
                try:
                    current_scraper = NewspaperScraper(
                        apply_spell_correction=not args.no_correction,
                        correction_method=args.correction,
                    )

                    # Vérifier le signal d'arrêt avant de commencer
                    if check_stop_signal():
                        logger.info("Stopping search due to stop signal")
                        return
                        
                    results = await current_scraper.save_articles_from_search(
                        query=args.query,
                        output_dir=args.output,
                        max_articles=args.max_articles,
                        newspapers=args.newspapers,
                        cantons=args.cantons
                    )
                except Exception as e:
                    logger.error(f"Error in search: {e}")
                finally:
                    # Ensure resources are properly closed
                    try:
                        if current_scraper:
                            await current_scraper._close_playwright()
                    except Exception as e:
                        logger.error(f"Error closing scraper: {e}")

    except Exception as e:
        logger.error(f"Unhandled exception during search: {e}")

    # Print summary
    duration = time.time() - start_time
    logger.info(f"Processing complete. {len(results) if results else 0} articles processed in {duration:.2f} seconds")

def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

# This code needs to be inside the async_main function to access the variables
def log_search_period(args):
    """Log the search period for detection by app.py stream_process function"""
    if args.date_range:
        print(f"Searching for period: {args.date_range}")
    elif hasattr(args, 'decade') and args.decade:
        print(f"Searching for period: {args.decade}")
    elif args.all_time:
        print("Searching for period: All time")

# Modify the async_main function to call log_search_period
