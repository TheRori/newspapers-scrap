from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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


# Define the log_search_period function before it's used
def log_search_period(args):
    """Log the search period for detection by app.py stream_process function"""
    if args.date_range:
        print(f"Searching for period: {args.date_range}")
    elif hasattr(args, 'decade') and args.decade:
        print(f"Searching for period: {args.decade}")
    elif args.all_time:
        print("Searching for period: All time")


def log_search_period(args):
    """Log the search period for detection by app.py stream_process function"""
    if args.date_range:
        print(f"Searching for period: {args.date_range}")
    elif hasattr(args, 'decade') and args.decade:
        print(f"Searching for period: {args.decade}")
    elif args.all_time:
        print("Searching for period: All time")


# Fonction pour vérifier si un signal d'arrêt a été reçu
def check_stop_signal():
    if os.path.exists('stop_signal.txt'):
        logger.info("Stop signal detected")
        return True
    return False


async def async_main():
    """Main async function that runs the search"""
    global current_scraper
    total_years = 0
    completed_years = 0
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Search for newspaper articles')
    parser.add_argument('query', help='Search query text')
    parser.add_argument('--newspapers', type=str, nargs='+', help='Newspaper codes to search')
    parser.add_argument('--output', type=str, help='Output directory to save articles', default=None)
    parser.add_argument('--max_articles', type=int, help='Maximum articles to retrieve', default=None)
    parser.add_argument('--proxies', type=str, default=None, help='Path to JSON file with proxy configurations')
    parser.add_argument('--laq', type=str, default='fr',
                        help='Language for search query (default: fr)')
    parser.add_argument('--cantons', type=str, nargs='+', help='Canton codes to search')
    parser.add_argument('--date_range', type=str, help='Date range in format YYYY-YYYY')
    parser.add_argument('--search_by', choices=['year', 'decade'], default='year',
                        help='Search by year or decade')
    parser.add_argument('--correction', type=str, choices=['mistral', 'symspell'],
                        help='Spell correction method to use')
    parser.add_argument('--no-correction', action='store_true',
                        help='Disable spell correction')
    parser.add_argument('--all_time', action='store_true', help='Search all time')
    parser.add_argument('--start_from', type=int, default=0,
                        help='Result number to start from (skip earlier results)')

    args = parser.parse_args()
    logger.debug('Searching for newspaper articles')

    # Create a single performance tracker for the entire search period
    from newspapers_scrap.performance_tracker import PerformanceTracker
    from newspapers_scrap.report_generator import ScrapingReportGenerator

    global_tracker = PerformanceTracker()
    global_tracker.start_tracking()
    global_tracker.track_search_query(args.query)

    search_query = args.query
    output_dir = args.output

    # After parsing arguments, calculate total years in search
    if args.all_time:
        total_years = 1  # Just one comprehensive search
    elif args.date_range:
        start_year, end_year = map(int, args.date_range.split('-'))
        if args.search_by == 'decade':
            # Will be processed by decade but track by years
            total_years = end_year - start_year + 1
        else:
            # Track by individual years
            total_years = end_year - start_year + 1
    else:
        total_years = 1  # Single year search

    # Log overall task information once at the beginning
    print(f"SEARCH_SCOPE: total_years={total_years}")

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
    all_results = []

    try:
        if args.all_time:
            # Search without date filtering
            logger.info("Searching all time")
            try:
                current_scraper = NewspaperScraper(
                    apply_spell_correction=not args.no_correction,
                    correction_method=args.correction,
                )

                # Use the global tracker
                current_scraper.performance_tracker = global_tracker

                results = await current_scraper.save_articles_from_search(
                    query=args.query,
                    output_dir=args.output,
                    max_articles=args.max_articles,
                    newspapers=args.newspapers,
                    cantons=args.cantons,
                    laq=args.laq,
                    start_from=args.start_from
                )
                if results:
                    all_results.append(results)
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
                            completed_years += 1
                            print(f"YEAR_PROGRESS: current_year={completed_years} total_years={total_years}")

                            try:
                                current_scraper = NewspaperScraper(
                                    apply_spell_correction=not args.no_correction,
                                    correction_method=args.correction,
                                )

                                # Use the global tracker
                                current_scraper.performance_tracker = global_tracker

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
                                    decade=decade,
                                    laq=args.laq,
                                    start_from=args.start_from
                                )

                                if decade_results:
                                    all_results.append(decade_results)
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
                            completed_years += 1
                            print(f"YEAR_PROGRESS: current_year={completed_years} total_years={total_years}")
                            try:
                                current_scraper = NewspaperScraper(
                                    apply_spell_correction=not args.no_correction,
                                    correction_method=args.correction,
                                )

                                # Use the global tracker
                                current_scraper.performance_tracker = global_tracker

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
                                    year=str(year),
                                    laq=args.laq,
                                    start_from=args.start_from
                                )

                                if year_results:
                                    all_results.append(year_results)
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

                    # Use the global tracker
                    current_scraper.performance_tracker = global_tracker

                    # Vérifier le signal d'arrêt avant de commencer
                    if check_stop_signal():
                        logger.info("Stopping search due to stop signal")
                        return

                    results = await current_scraper.save_articles_from_search(
                        query=args.query,
                        output_dir=args.output,
                        max_articles=args.max_articles,
                        newspapers=args.newspapers,
                        cantons=args.cantons,
                        laq=args.laq,
                        start_from=args.start_from
                    )
                    if results:
                        all_results.append(results)
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
    finally:
        # Stop tracking and generate a comprehensive report
        global_tracker.stop_tracking()
        summary = global_tracker.generate_summary()

        # Generate the report with aggregated data from all years
        report_generator = ScrapingReportGenerator(output_dir=f"{output_dir}/reports" if output_dir else "reports")
        try:
            report_path = report_generator.generate_report(summary, query=search_query)
            logger.info(f"Generated comprehensive report for entire search period at: {report_path}")
        except Exception as e:
            logger.error(f"Failed to generate report: {e}")

    # Print summary
    duration = time.time() - start_time
    total_articles = 0
    if all_results:
        for result in all_results:
            if isinstance(result, dict) and 'count' in result:
                total_articles += result['count']
            elif isinstance(result, list):
                # If result is a list, count its length
                total_articles += len(result)
    logger.info(f"Processing complete. {total_articles} articles processed in {duration:.2f} seconds")


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

# This code needs to be inside the async_main function to access the variables


# Modify the async_main function to call log_search_period
