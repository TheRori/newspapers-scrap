import logging
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from newspapers_scrap.config.config import env

logger = logging.getLogger(__name__)


def organize_article(
        article_text: str,
        url: str,
        search_term: str,
        article_title: str,
        newspaper_name: str,
        date_str: str,
        canton: Optional[str] = None,
        apply_spell_correction: bool = True,
        correction_method: str = 'mistral',
        language: str = 'fr'
) -> Dict:
    """
    Organize an article into the data structure and return its metadata

    Args:
        article_text: The article text to organize
        url: The URL where the article was found
        search_term: The search term used to find the article
        article_title: The title of the article
        newspaper_name: The name of the newspaper
        date_str: The date of the article as a string
        canton: Optional canton information
        apply_spell_correction: Whether to apply spell correction
        correction_method: Which spell correction method to use ('mistral' or 'symspell')
        language: The language of the article
    """
    import unicodedata
    import tempfile

    # Update in newspapers_scrap/data_manager/organizer.py (spell correction section)
    if apply_spell_correction:
        logger.info(f"Applying spell correction using method: {correction_method}")
        try:
            if correction_method.lower() == 'mistral':
                logger.info("Using Mistral AI for spell correction")
                from newspapers_scrap.data_manager.ocr_cleaner.mistral_checker import correct_text_ai
                # Use temporary files for text correction
                with tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', delete=False) as temp_in, \
                        tempfile.NamedTemporaryFile(mode='w+', encoding='utf-8', delete=False) as temp_out:
                    temp_in.write(article_text)
                    temp_in_path = temp_in.name
                    temp_out_path = temp_out.name
                    logger.info(f"Created temporary files: in={temp_in_path}, out={temp_out_path}")

                # Close both files before passing to correct_text
                logger.info("Starting Mistral correction process")
                success = correct_text_ai(temp_in_path, temp_out_path)

                if success:
                    # Read the corrected text
                    with open(temp_out_path, 'r', encoding='utf-8') as f:
                        corrected_text = f.read()
                        logger.info(f"Retrieved corrected text ({len(corrected_text)} characters)")
                else:
                    logger.warning("Mistral correction process failed, using original text")
                    corrected_text = article_text

                # Clean up temporary files
                logger.debug(f"Removing temporary files")
                os.unlink(temp_in_path)
                os.unlink(temp_out_path)

            elif correction_method.lower() == 'symspell':
                logger.info(f"Using SymSpell for spell correction (language: {language})")
                from newspapers_scrap.data_manager.ocr_cleaner.symspell_checker import SpellCorrector
                spell_corrector = SpellCorrector(language=language)
                logger.info("SymSpell corrector initialized, starting correction")
                corrected_text = spell_corrector.correct_text_sym(article_text)
                logger.info(f"SymSpell correction complete ({len(corrected_text)} characters)")

            else:
                logger.warning(f"Unknown correction method: {correction_method}. Using no correction.")
                corrected_text = article_text

            # Check if any corrections were made
            has_corrections = corrected_text != article_text
            if has_corrections:
                diff_chars = abs(len(corrected_text) - len(article_text))
                logger.info(f"Corrections applied. Character difference: {diff_chars}")
            else:
                logger.info("No spelling corrections found or needed")
        except Exception as e:
            logger.error(f"Spell correction failed: {str(e)}", exc_info=True)
            corrected_text = article_text
            has_corrections = False
    else:
        logger.info("Spell correction skipped (disabled)")
        corrected_text = article_text
        has_corrections = False

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

    try:
        locale.setlocale(locale.LC_TIME, original_locale)
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')

    if not date_obj:
        date_obj = datetime.now()
        print(f"Warning: Could not parse date '{date_str}', using current date")

    def normalize_filename(text):
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        text = re.sub(r'[\s\'"]', '_', text)
        text = re.sub(r'[^a-zA-Z0-9_-]', '', text)
        return text.lower()

    newspaper_id = normalize_filename(newspaper_name)
    article_id = f"article_{date_obj.strftime('%Y%m%d')}_{newspaper_id}"

    # Get data directories from config - using existing path implementation
    raw_data_dir = Path(env.storage.paths.raw_data_dir)
    processed_data_dir = Path(env.storage.paths.processed_data_dir)
    topics_data_dir = Path(env.storage.paths.topics_data_dir)

    # Ensure directories exist
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    processed_data_dir.mkdir(parents=True, exist_ok=True)
    topic_dir = topics_data_dir / normalize_filename(search_term)
    topic_dir.mkdir(parents=True, exist_ok=True)

    # Define file paths with normalized names
    raw_path = raw_data_dir / f"{article_id}.txt"
    processed_path = processed_data_dir / f"{article_id}.json"

    # Save raw content
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write(article_text)  # Save original uncorrected text

    # Create processed content (with metadata)
    processed_data = {
        "id": article_id,
        "title": article_title,
        "newspaper": newspaper_name,
        "date": date_obj.strftime("%Y-%m-%d"),
        "topics": [search_term],
        "url": url,
        "raw_path": str(raw_path),
        "content": corrected_text,  # Use corrected text
        "original_content": article_text if has_corrections else None,  # Store original if different
        "spell_corrected": has_corrections,
        "word_count": len(corrected_text.split()),
        "canton": canton
    }

    # Save processed content
    with open(processed_path, "w", encoding="utf-8") as f:
        json.dump(processed_data, ensure_ascii=False, indent=2, fp=f)
        logger.info(f"Processed content saved to: {processed_path}")

    # Create topic reference with normalized path
    topic_ref_path = topic_dir / f"{article_id}.json"

    try:
        if topic_ref_path.exists():
            topic_ref_path.unlink()
        topic_ref_path.symlink_to(processed_path.absolute())
    except (OSError, AttributeError):
        with open(topic_ref_path, "w", encoding="utf-8") as f:
            ref_data = {"reference_path": str(processed_path)}
            json.dump(ref_data, f, ensure_ascii=False, indent=2)

    metadata = {**processed_data}
    metadata.pop("content", None)
    metadata.pop("original_content", None)  # Remove original content from metadata
    return metadata