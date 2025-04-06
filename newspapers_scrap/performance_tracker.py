import time
from collections import defaultdict
from datetime import datetime

from newspapers_scrap.utils import clean_and_parse_date  # import your robust date parser

class PerformanceTracker:
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.articles_per_year = defaultdict(int)

    def start_tracking(self):
        self.start_time = time.time()

    def stop_tracking(self):
        self.end_time = time.time()

    def track_article(self, article_date):
        parsed_date = clean_and_parse_date(article_date)
        if parsed_date:
            year = parsed_date.year
            self.articles_per_year[year] += 1
        else:
            # Default fallback, e.g., current year or logging the issue
            year = datetime.now().year
            self.articles_per_year[year] += 1

    def generate_summary(self):
        total_time = self.end_time - self.start_time
        total_articles = sum(self.articles_per_year.values())
        summary = {
            'total_time': total_time,
            'total_articles': total_articles,
            'articles_per_year': dict(self.articles_per_year)
        }
        return summary
