```markdown
# Newspaper Scraper

A Python tool for scraping and analyzing newspaper archives.

## Project Overview

This application allows you to search through historical newspaper archives, extract articles, and process the content for analysis. It provides a configurable framework for working with different newspaper sources.

## Features

- Search newspaper archives using custom queries
- Extract article content, titles, dates and newspaper information
- Configurable for different newspaper sources
- Respectful scraping with built-in delays
```
## Project Structure

```
newspapers_scrap/
├── config.py           # Configuration settings
├── scraper.py          # Core scraping functionality
└── ...

scripts/
├── run_search.py       # Script to execute searches
└── ...

data/
├── raw/                # Raw scraped data storage
└── processed/          # Processed data storage

logs/                   # Log files
```

## Getting Started

### Prerequisites

- Python 3.x
- pip

### Installation

1. Clone this repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

### Usage

Run a basic search:

```bash
  python scripts/run_search.py
```

## Configuration

The project is configurable via `newspapers_scrap/config.py` where you can adjust:

- Request headers and delays
- Search parameters
- Website selectors for different elements
- Target newspaper configurations
- File paths for data storage
- Search limits

## License

MIT License

## Disclaimer

This tool is intended for research purposes only. Always respect website terms of service and robots.txt when scraping content.
```