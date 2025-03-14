# newspapers_scrap/config.py

# Base URLs
E_NEWSPAPER_ARCHIVES_BASE_URL = 'https://www.e-newspaperarchives.ch'

# Scraping configurations
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# Rate limiting settings
REQUEST_DELAY_MIN = 1.0  # seconds
REQUEST_DELAY_MAX = 3.0  # seconds

# Search configurations
SEARCH_PARAMS = {
    'a': 'q',      # Action: query
    'hs': '1',     # Historical search
    'r': '1',      # Results format
    'results': '1' # Show results
}

# Result page selectors
# Update these in config.py
SEARCH_RESULT_ITEM_SELECTOR = 'ol.searchresults > li'
SEARCH_RESULT_TITLE_SELECTOR = '.vlistentrymaincell div > a'
SEARCH_RESULT_LINK_SELECTOR = '.vlistentrymaincell div > a'
SEARCH_RESULT_NEWSPAPER_SELECTOR = '.vlistentrymaincell > div:nth-child(2)'
SEARCH_RESULT_SNIPPET_SELECTOR = '.imgsearchsnippet'

# Target newspapers
NEWSPAPERS = {
    'e_newspaper_archives': {
        'base_url': E_NEWSPAPER_ARCHIVES_BASE_URL,
        'search_url': f"{E_NEWSPAPER_ARCHIVES_BASE_URL}/",
        'article_selector': 'div.document',
        'title_selector': 'h1.article-title',
        'content_selector': 'div.content-area',
        'date_selector': 'div.date',
        'newspaper_selector': 'div.newspaper-name',
    },
    # Add more newspaper configurations as needed
}

# File paths - match these with what's in dataset.py
RAW_DATA_DIR = 'data/raw'
PROCESSED_DATA_DIR = 'data/processed'
LOGS_DIR = 'logs'

# Maximum number of pages to scrape per search query
MAX_SEARCH_PAGES = 10

# Maximum number of results to process per search
MAX_RESULTS_PER_SEARCH = 100