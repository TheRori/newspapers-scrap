# newspapers_scrap/utils/diff_generator.py
import difflib
import html
import re


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