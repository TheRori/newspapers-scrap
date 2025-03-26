# newspapers_scrap/utils/diff_generator.py
import difflib
import html

def generate_html_diff(original_text, corrected_text):
    """
    Generate HTML that highlights the differences between original and corrected text
    with proper handling of UTF-8 characters.
    """
    if original_text is None or corrected_text is None:
        return "<p>No differences to display (missing original or corrected text)</p>"

    # Ensure both texts are properly encoded
    if isinstance(original_text, bytes):
        original_text = original_text.decode('utf-8')
    if isinstance(corrected_text, bytes):
        corrected_text = corrected_text.decode('utf-8')

    # Process text by paragraphs to maintain structure
    original_paragraphs = original_text.split('\n')
    corrected_paragraphs = corrected_text.split('\n')

    result_html = []

    # For each paragraph, generate a diff
    for i in range(max(len(original_paragraphs), len(corrected_paragraphs))):
        original_para = original_paragraphs[i] if i < len(original_paragraphs) else ""
        corrected_para = corrected_paragraphs[i] if i < len(corrected_paragraphs) else ""

        # Skip if paragraphs are identical
        if original_para == corrected_para:
            if original_para.strip():
                result_html.append(f"<p>{html.escape(original_para)}</p>")
            continue

        # Split paragraphs into words for comparison
        original_words = original_para.split()
        corrected_words = corrected_para.split()

        # Generate diff for this paragraph
        diff = difflib.ndiff(original_words, corrected_words)

        # Convert diff to HTML
        html_parts = []
        for line in diff:
            if line.startswith('+ '):
                # Added words in green
                word = html.escape(line[2:])
                html_parts.append(f'<span class="added">{word}</span>')
            elif line.startswith('- '):
                # Removed words in red
                word = html.escape(line[2:])
                html_parts.append(f'<span class="removed">{word}</span>')
            elif line.startswith('  '):
                # Unchanged words
                word = html.escape(line[2:])
                html_parts.append(f'<span class="unchanged">{word}</span>')

        result_html.append(f"<p>{' '.join(html_parts)}</p>")

    return "\n".join(result_html)