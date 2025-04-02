# newspapers_scrap/utils.py
import difflib
import html
import re

import re
import unicodedata
from datetime import datetime
from dateutil import parser as date_parser


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
            'Marz': 'März', 'M\u00e4rz': 'März', 'M�rz': 'März',
            'Marz': 'März', 'Maerz': 'März',
            'Aout': 'Août', 'Ao\u00fbt': 'Août', 'Ao�t': 'Août',
            'Fevrier': 'Février', 'F\u00e9vrier': 'Février', 'F�vrier': 'Février',
            'Decembre': 'Décembre', 'D\u00e9cembre': 'Décembre', 'D�cembre': 'Décembre'
        }

        for error, correction in month_replacements.items():
            cleaned = cleaned.replace(error, correction)

        # Extract just the date part from strings like "de Genève 14. März 1980"
        date_pattern = r'(\d{1,2}[\.\s-]+(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember|Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre)[\.\s-]+\d{4})'
        date_match = re.search(date_pattern, cleaned)

        if date_match:
            date_part = date_match.group(1)
        else:
            # If no match with known month names, try to extract any date-like pattern
            date_part = re.search(r'(\d{1,2}[\.\s-]+\w+[\.\s-]+\d{4})', cleaned)
            date_part = date_part.group(1) if date_part else cleaned

        # Try various date parsing approaches
        try:
            # Try dateutil parser first (most flexible)
            return date_parser.parse(date_part, fuzzy=True)
        except:
            # Try explicit formats
            formats = [
                '%d. %B %Y',  # 14. März 1980
                '%d %B %Y',  # 14 März 1980
                '%d.%m.%Y',  # 14.03.1980
                '%d/%m/%Y',  # 14/03/1980
                '%Y-%m-%d',  # 1980-03-14
            ]

            for fmt in formats:
                try:
                    return datetime.strptime(date_part, fmt)
                except:
                    continue

            # If all parsing attempts fail, extract just year as last resort
            year_match = re.search(r'(\d{4})', cleaned)
            if year_match:
                year = int(year_match.group(1))
                return datetime(year, 1, 1)  # Return Jan 1 of the year
    except Exception as e:
        logger.debug(f"Failed to parse date '{date_str}': {e}")

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