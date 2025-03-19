import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from newspapers_scrap.config.config import env


def organize_article(
        article_text: str,
        url: str,
        search_term: str,
        article_title: str,
        newspaper_name: str,
        date_str: str,
        canton: Optional[str] = None
) -> Dict:
    """
    Organize an article into the data structure and return its metadata
    """
    # Parse date with multiple language support
    date_obj = None

    # Try different locales for date parsing
    locales = ['en_US.UTF-8', 'fr_FR.UTF-8', 'de_DE.UTF-8']

    import locale
    original_locale = locale.getlocale(locale.LC_TIME)

    for loc in locales:
        try:
            locale.setlocale(locale.LC_TIME, loc)
            date_obj = datetime.strptime(date_str, "%d. %B %Y")
            break
        except (ValueError, locale.Error):
            continue

    # Restore original locale
    try:
        locale.setlocale(locale.LC_TIME, original_locale)
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')

    # Default to current date if parsing fails
    if not date_obj:
        date_obj = datetime.now()
        print(f"Warning: Could not parse date '{date_str}', using current date")

    newspaper_id = newspaper_name.lower().replace(' ', '_').replace("'", '')
    article_id = f"article_{date_obj.strftime('%Y%m%d')}_{newspaper_id}"

    # Get data directories from config
    raw_data_dir = Path(env.storage.paths.raw_data_dir)
    processed_data_dir = Path(env.storage.paths.processed_data_dir)
    topics_data_dir = Path(env.storage.paths.topics_data_dir)

    # Ensure directories exist
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    processed_data_dir.mkdir(parents=True, exist_ok=True)
    topic_dir = topics_data_dir / search_term
    topic_dir.mkdir(parents=True, exist_ok=True)

    # Define file paths
    raw_path = raw_data_dir / f"{article_id}.txt"
    processed_path = processed_data_dir / f"{article_id}.json"

    # Save raw content
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(article_text)

    # Create processed content (with metadata)
    processed_data = {
        "id": article_id,
        "title": article_title,
        "newspaper": newspaper_name,
        "date": date_obj.strftime("%Y-%m-%d"),
        "topics": [search_term],
        "url": url,
        "raw_path": str(raw_path),
        "content": article_text,
        "word_count": len(article_text.split()),
        "canton": canton
    }

    # Save processed content
    with open(processed_path, "w", encoding="utf-8") as f:
        json.dump(processed_data, ensure_ascii=False, indent=2, fp=f)

    # Create topic reference (symlink or reference file)
    topic_ref_path = topic_dir / f"{article_id}.json"

    # Option 1: Create symlink (Unix/Linux systems)
    try:
        if topic_ref_path.exists():
            topic_ref_path.unlink()
        topic_ref_path.symlink_to(processed_path.absolute())
    except (OSError, AttributeError):
        # Option 2: Create reference file (Windows or if symlinks fail)
        with open(topic_ref_path, "w", encoding="utf-8") as f:
            ref_data = {"reference_path": str(processed_path)}
            json.dump(ref_data, f, ensure_ascii=False, indent=2)

    # Return metadata for database storage
    metadata = {**processed_data}
    metadata.pop("content", None)  # Don't duplicate content in metadata
    return metadata