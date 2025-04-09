import time
import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Any, Optional

from newspapers_scrap.utils import clean_and_parse_date  # import your robust date parser

logger = logging.getLogger(__name__)

class PerformanceTracker:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.articles_per_year = defaultdict(int)
        self.articles_per_newspaper = defaultdict(int)
        self.articles_per_canton = defaultdict(int)
        self.request_times = []
        self.delay_times = []
        self.processing_times = []
        self.search_terms = []
        self.error_count = 0
        self.retry_count = 0
        self.current_query = None
        self.current_article_start_time = None
        self.current_request_start_time = None
        self.current_delay_start_time = None

    def start_tracking(self):
        """Start tracking a complete scraping session"""
        self.start_time = time.time()
        logger.info("Performance tracking started")

    def stop_tracking(self):
        """Stop tracking the scraping session"""
        self.end_time = time.time()
        logger.info(f"Performance tracking stopped. Total duration: {self.end_time - self.start_time:.2f} seconds")

    def track_search_query(self, query: str):
        """Track a new search query"""
        self.current_query = query
        self.search_terms.append(query)
        logger.info(f"Tracking new search query: {query}")

    def track_article(self, article_date: str, newspaper: str = "Unknown", canton: Optional[str] = None):
        """Track an article with its metadata"""
        # Track by year
        parsed_date = clean_and_parse_date(article_date)
        if parsed_date:
            year = parsed_date.year
            self.articles_per_year[year] += 1
        else:
            # Default fallback, e.g., current year or logging the issue
            year = datetime.now().year
            self.articles_per_year[year] += 1
            
        # Track by newspaper and canton
        self.articles_per_newspaper[newspaper] += 1
        if canton:
            self.articles_per_canton[canton] += 1

    def start_article_processing(self):
        """Start tracking the processing time for an article"""
        self.current_article_start_time = time.time()

    def stop_article_processing(self):
        """Stop tracking the processing time for an article"""
        if self.current_article_start_time:
            processing_time = time.time() - self.current_article_start_time
            self.processing_times.append(processing_time)
            self.current_article_start_time = None

    def start_request(self):
        """Start tracking a network request"""
        self.current_request_start_time = time.time()

    def stop_request(self, success: bool = True):
        """Stop tracking a network request"""
        if self.current_request_start_time:
            request_time = time.time() - self.current_request_start_time
            self.request_times.append(request_time)
            self.current_request_start_time = None
            if not success:
                self.error_count += 1

    def start_delay(self):
        """Start tracking a delay between requests"""
        self.current_delay_start_time = time.time()

    def stop_delay(self):
        """Stop tracking a delay between requests"""
        if self.current_delay_start_time:
            delay_time = time.time() - self.current_delay_start_time
            self.delay_times.append(delay_time)
            self.current_delay_start_time = None

    def track_retry(self):
        """Track a retry attempt"""
        self.retry_count += 1

    def generate_summary(self) -> Dict[str, Any]:
        """Generate a comprehensive summary of the scraping performance"""
        if not self.end_time:
            self.stop_tracking()
            
        total_time = self.end_time - self.start_time
        total_articles = sum(self.articles_per_year.values())
        
        # Calculate averages
        avg_request_time = sum(self.request_times) / len(self.request_times) if self.request_times else 0
        avg_delay_time = sum(self.delay_times) / len(self.delay_times) if self.delay_times else 0
        avg_processing_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
        
        # Calculate total time spent in each phase
        total_request_time = sum(self.request_times)
        total_delay_time = sum(self.delay_times)
        total_processing_time = sum(self.processing_times)
        
        # Calculate articles per minute
        articles_per_minute = (total_articles / total_time) * 60 if total_time > 0 else 0
        
        summary = {
            'total_time': total_time,
            'total_articles': total_articles,
            'articles_per_year': dict(self.articles_per_year),
            'articles_per_newspaper': dict(self.articles_per_newspaper),
            'articles_per_canton': dict(self.articles_per_canton),
            'search_terms': self.search_terms,
            'error_count': self.error_count,
            'retry_count': self.retry_count,
            'request_stats': {
                'count': len(self.request_times),
                'total_time': total_request_time,
                'average_time': avg_request_time,
                'min_time': min(self.request_times) if self.request_times else 0,
                'max_time': max(self.request_times) if self.request_times else 0,
            },
            'delay_stats': {
                'count': len(self.delay_times),
                'total_time': total_delay_time,
                'average_time': avg_delay_time,
                'min_time': min(self.delay_times) if self.delay_times else 0,
                'max_time': max(self.delay_times) if self.delay_times else 0,
            },
            'processing_stats': {
                'count': len(self.processing_times),
                'total_time': total_processing_time,
                'average_time': avg_processing_time,
                'min_time': min(self.processing_times) if self.processing_times else 0,
                'max_time': max(self.processing_times) if self.processing_times else 0,
            },
            'performance_metrics': {
                'articles_per_minute': articles_per_minute,
                'success_rate': (total_articles / (total_articles + self.error_count)) * 100 if (total_articles + self.error_count) > 0 else 0,
            }
        }
        
        logger.info(f"Generated performance summary: {len(self.articles_per_year)} years, {total_articles} articles, {total_time:.2f} seconds")
        return summary
