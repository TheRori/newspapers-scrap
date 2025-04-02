import hashlib
import logging
import os
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from newspapers_scrap.config.config import env
from newspapers_scrap.utils import clean_and_parse_date

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
    import glob

    # Apply spell correction if enabled
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
        correction_method = "none"  # Explicitly mark as no correction

        # Parse the date with the robust parser
    current_date = datetime.now()
    parsed_date = clean_and_parse_date(date_str, default_date=current_date)

    if parsed_date == current_date and date_str:
        logger.warning(f"Could not parse date '{date_str}', using current date")

    # Format the date for storage
    formatted_date = parsed_date.strftime('%Y-%m-%d')

    def normalize_filename(text):
        text = unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore').decode('ASCII')
        text = re.sub(r'[\s\'"]', '_', text)
        text = re.sub(r'[^a-zA-Z0-9_-]', '', text)
        return text.lower()

    content_hash = hashlib.md5((url + article_text[:200]).encode('utf-8')).hexdigest()[:8]
    newspaper_id = normalize_filename(newspaper_name)
    base_article_id = f"article_{formatted_date}_{newspaper_id}_{content_hash}"

    # Add versioning: base ID + correction method + language if not "none"
    version_suffix = f"_{correction_method}"
    if correction_method != "none" and language != "fr":
        version_suffix += f"_{language}"

    article_id = f"{base_article_id}{version_suffix}"

    # Get data directories from config - using existing path implementation
    raw_data_dir = Path(env.storage.paths.raw_data_dir)
    processed_data_dir = Path(env.storage.paths.processed_data_dir)
    topics_data_dir = Path(env.storage.paths.topics_data_dir)
    versions_data_dir = Path(env.storage.paths.processed_data_dir) / "versions"

    # Ensure directories exist
    raw_data_dir.mkdir(parents=True, exist_ok=True)
    processed_data_dir.mkdir(parents=True, exist_ok=True)
    versions_data_dir.mkdir(parents=True, exist_ok=True)
    topic_dir = topics_data_dir / normalize_filename(search_term)
    topic_dir.mkdir(parents=True, exist_ok=True)

    # Define path for article versions directory
    article_versions_dir = versions_data_dir / base_article_id
    article_versions_dir.mkdir(parents=True, exist_ok=True)

    # Define file paths with normalized names
    raw_path = raw_data_dir / f"{base_article_id}.txt"
    version_path = article_versions_dir / f"{article_id}.json"

    # The main processed file will always point to the latest version
    processed_path = processed_data_dir / f"{base_article_id}.json"

    # First, save the raw content if it doesn't exist yet
    if not raw_path.exists():
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(article_text)  # Save original uncorrected text
            logger.info(f"Raw content saved to: {raw_path}")

    # Check for existing versions and get their information
    existing_versions = []
    version_files = glob.glob(str(article_versions_dir / "*.json"))

    for vf in version_files:
        try:
            with open(vf, "r", encoding="utf-8") as f:
                version_data = json.load(f)
                existing_versions.append({
                    "id": version_data["id"],
                    "correction_method": version_data["correction_method"],
                    "language": version_data["language"],
                    "path": vf
                })
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Error reading version file {vf}: {str(e)}")

    # Create processed content (with metadata)
    processed_data = {
        "id": article_id,
        "base_id": base_article_id,
        "title": article_title,
        "newspaper": newspaper_name,
        "date": formatted_date,
        "topics": [search_term],
        "url": url,
        "raw_path": str(raw_path),
        "content": corrected_text,
        "original_content": article_text,
        "spell_corrected": has_corrections,
        "correction_method": correction_method,
        "language": language,
        "word_count": len(corrected_text.split()),
        "canton": canton,
        "created_at": datetime.now().isoformat(),
        "versions": [v["id"] for v in existing_versions] + [article_id]
    }

    # Save this version
    with open(version_path, "w", encoding="utf-8") as f:
        json.dump(processed_data, ensure_ascii=False, indent=2, fp=f)
        logger.info(f"Version saved to: {version_path}")

    # Always update the main processed file to point to this latest version
    with open(processed_path, "w", encoding="utf-8") as f:
        json.dump(processed_data, ensure_ascii=False, indent=2, fp=f)
        logger.info(f"Main processed content updated: {processed_path}")

    # Create topic reference with normalized path (pointing to main processed file)
    topic_ref_path = topic_dir / f"{base_article_id}.json"

    try:
        if topic_ref_path.exists():
            topic_ref_path.unlink()
        topic_ref_path.symlink_to(processed_path.absolute())
    except (OSError, AttributeError):
        with open(topic_ref_path, "w", encoding="utf-8") as f:
            ref_data = {"reference_path": str(processed_path)}
            json.dump(ref_data, f, ensure_ascii=False, indent=2)

    # Return metadata without the content for the API response
    metadata = {**processed_data}
    metadata.pop("content", None)
    return metadata