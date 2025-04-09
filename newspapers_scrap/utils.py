# newspapers_scrap/utils.py
import difflib
import html
import re

import re
import unicodedata
from datetime import datetime
from dateutil import parser as date_parser
import logging

logger = logging.getLogger(__name__)


def clean_and_parse_date(date_str, default_date=None):
    """
    Clean and parse dates from OCR text with potential encoding issues

    Args:
        date_str: String containing date information
        default_date: Default date to use if parsing fails

    Returns:
        datetime object or default_date if parsing fails
    """
    if not date_str:
        return default_date

    # Normalize unicode characters and remove control characters
    try:
        # Normalize unicode and convert to ASCII where possible
        normalized = unicodedata.normalize('NFKD', date_str)
        cleaned = ''.join(c for c in normalized if not unicodedata.combining(c))

        # Replace common OCR errors in month names
        month_replacements = {
            # German months
            'Marz': 'März', 'M\u00e4rz': 'März', 'M�rz': 'März', 'Maerz': 'März',
            'Januar': 'Januar', 'Janner': 'Januar', 'J\u00e4nner': 'Januar', 'J�nner': 'Januar',
            'Februar': 'Februar',
            'April': 'April',
            'Mai': 'Mai',
            'Juni': 'Juni',
            'Juli': 'Juli',
            'August': 'August',
            'September': 'September',
            'Oktober': 'Oktober',
            'November': 'November',
            'Dezember': 'Dezember',

            # French months
            'Janvier': 'Janvier',
            'Fevrier': 'Février', 'F\u00e9vrier': 'Février', 'F�vrier': 'Février',
            'Mars': 'Mars',
            'Avril': 'Avril',
            'Mai': 'Mai',
            'Juin': 'Juin',
            'Juillet': 'Juillet',
            'Aout': 'Août', 'Ao\u00fbt': 'Août', 'Ao�t': 'Août',
            'Septembre': 'Septembre',
            'Octobre': 'Octobre',
            'Novembre': 'Novembre',
            'Decembre': 'Décembre', 'D\u00e9cembre': 'Décembre', 'D�cembre': 'Décembre'
        }

        for error, correction in month_replacements.items():
            cleaned = cleaned.replace(error, correction)

        # Extract just the date part from strings like "de Genève 14. März 1980" or "La liberté, 19. Juli 1990"
        date_pattern = r'(\d{1,2}\s*\.\s*(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre)\s+\d{4})'
        date_match = re.search(date_pattern, cleaned)

        if date_match:
            date_part = date_match.group(1)
            logger.debug(f"Matched date pattern: {date_part}")
        else:
            # If no match with known month names, try to extract any date-like pattern
            date_part = re.search(r'(\d{1,2}[\.\s-]+\w+[\.\s-]+\d{4})', cleaned)
            date_part = date_part.group(1) if date_part else cleaned
            logger.debug(f"Using generic date pattern: {date_part}")

        # Create month translation dictionaries
        de_month_map = {
            'Januar': 1, 'Februar': 2, 'März': 3, 'April': 4, 'Mai': 5, 'Juni': 6,
            'Juli': 7, 'August': 8, 'September': 9, 'Oktober': 10, 'November': 11, 'Dezember': 12
        }

        fr_month_map = {
            'Janvier': 1, 'Février': 2, 'Mars': 3, 'Avril': 4, 'Mai': 5, 'Juin': 6,
            'Juillet': 7, 'Août': 8, 'Septembre': 9, 'Octobre': 10, 'Novembre': 11, 'Décembre': 12
        }

        # Try manual parsing first for German/French date formats
        manual_date_pattern = r'(\d{1,2})\s*\.\s*([\w]+)\s+(\d{4})'
        manual_match = re.search(manual_date_pattern, date_part)

        if manual_match:
            day = int(manual_match.group(1))
            month_name = manual_match.group(2)
            year = int(manual_match.group(3))

            month_num = None
            if month_name in de_month_map:
                month_num = de_month_map[month_name]
            elif month_name in fr_month_map:
                month_num = fr_month_map[month_name]

            if month_num:
                logger.debug(f"Manual parsing successful: {day}.{month_num}.{year}")
                return datetime(year, month_num, day)

        # Try dateutil parser (most flexible)
        try:
            return date_parser.parse(date_part, fuzzy=True)
        except Exception as e:
            logger.debug(f"dateutil.parser failed: {e}")

            # Try explicit formats with locale
            formats = [
                '%d.%m.%Y',  # 14.03.1980
                '%d/%m/%Y',  # 14/03/1980
                '%Y-%m-%d',  # 1980-03-14
            ]

            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_part, fmt)
                    logger.debug(f"Successfully parsed with format {fmt}")
                    return parsed_date
                except Exception as e:
                    logger.debug(f"Format {fmt} failed: {e}")
                    continue

            # If all parsing attempts fail, extract just year as last resort
            year_match = re.search(r'(\d{4})', cleaned)
            if year_match:
                year = int(year_match.group(1))
                logger.debug(f"Falling back to year only: {year}")
                return datetime(year, 1, 1)  # Return Jan 1 of the year
    except Exception as e:
        logger.error(f"Failed to parse date '{date_str}': {e}")

    return default_date


def generate_html_diff(original_text, corrected_text):
    """
    Generate HTML that highlights the differences between original and corrected text
    with proper handling of UTF-8 characters and line breaks.
    """
    if original_text is None or corrected_text is None:
        return "<p>No differences to display (missing original or corrected text)</p>"

    # Ensure both texts are properly encoded
    if isinstance(original_text, bytes):
        original_text = original_text.decode('utf-8')
    if isinstance(corrected_text, bytes):
        corrected_text = corrected_text.decode('utf-8')

    # Normalize whitespace to reduce false positives
    def normalize_text(text):
        # Replace multiple spaces with a single space
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    # Process the entire text as tokens rather than splitting by paragraphs
    original_tokens = normalize_text(original_text).split()
    corrected_tokens = normalize_text(corrected_text).split()

    # Use SequenceMatcher for better diff generation
    matcher = difflib.SequenceMatcher(None, original_tokens, corrected_tokens)

    result_html = ['<p>']

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            # Unchanged text
            for word in original_tokens[i1:i2]:
                result_html.append(f'<span class="unchanged">{html.escape(word)}</span>')
        elif tag == 'replace':
            # Changed text
            for word in original_tokens[i1:i2]:
                result_html.append(f'<span class="removed">{html.escape(word)}</span>')
            for word in corrected_tokens[j1:j2]:
                result_html.append(f'<span class="added">{html.escape(word)}</span>')
        elif tag == 'delete':
            # Deleted text
            for word in original_tokens[i1:i2]:
                result_html.append(f'<span class="removed">{html.escape(word)}</span>')
        elif tag == 'insert':
            # Added text
            for word in corrected_tokens[j1:j2]:
                result_html.append(f'<span class="added">{html.escape(word)}</span>')

    result_html.append('</p>')

    return ' '.join(result_html)
