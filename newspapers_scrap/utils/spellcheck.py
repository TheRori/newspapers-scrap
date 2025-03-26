# newspapers_scrap/utils/spellcheck.py
import os
import logging
from pathlib import Path
from symspellpy.symspellpy import SymSpell, Verbosity
from newspapers_scrap.config.config import env

logger = logging.getLogger(__name__)

class SpellCorrector:

    def __init__(self, language='fr', dictionary_path=None, max_edit_distance=2, prefix_length=7):
        """Initialize SymSpell corrector with specified dictionary."""
        self.symspell = SymSpell(max_edit_distance, prefix_length)
        self.max_edit_distance = max_edit_distance

        if dictionary_path:
            dictionary_path = str(dictionary_path)
        else:
            dictionary_path = str(env.storage.paths.models_dir + f'/{language}.txt')

        logger.info(f"Loading dictionary from {dictionary_path}")

        try:
            load_success = self.symspell.load_dictionary(dictionary_path, term_index=0,
                                                      count_index=1, encoding='utf-8')
            if not load_success:
                raise ValueError(f"Failed to load SymSpell dictionary from {dictionary_path}")
            logger.info("Dictionary loaded successfully")
        except Exception as e:
            logger.error(f"Error loading dictionary: {str(e)}")
            raise

    def correct_text(self, text):
        """Correct spelling errors in the given text."""
        if not text:
            return text
        logger.info(f"Start correcting spelling errors on text of length {len(text)}")
        paragraphs = text.split('\n')
        logger.info(f"Split into {len(paragraphs)} paragraphs")

        corrected_paragraphs = []
        for i, p in enumerate(paragraphs):
            if i % 10 == 0:  # Log progress periodically
                logger.info(f"Correcting paragraph {i}/{len(paragraphs)}")
            if p.strip():  # Skip empty paragraphs
                corrected_paragraphs.append(self._correct_paragraph(p))
            else:
                corrected_paragraphs.append(p)  # Preserve empty lines

        logger.info("Spell correction completed")
        return '\n'.join(corrected_paragraphs)

    def _correct_paragraph(self, paragraph):
        """Correct a single paragraph using SymSpell."""
        # Preserve whitespace and punctuation
        import re
        tokens = re.findall(r'\b\w+\b|[^\w\s]|\s+', paragraph)
        result = []

        for token in tokens:
            if re.match(r'\b\w+\b', token):  # Only correct words
                result.append(self._correct_word(token))
            else:
                result.append(token)  # Preserve punctuation and whitespace

        return ''.join(result)

    def _correct_word(self, word):
        """Correct a single word, preserving original casing and skipping if already correct."""
        word_lc = word.lower()

        suggestions = self.symspell.lookup(word_lc, Verbosity.CLOSEST, max_edit_distance=self.max_edit_distance)

        if suggestions:
            best = suggestions[0].term
            if best == word_lc:
                return word  # déjà correct
            self._corrections_made = True
            return self._match_case(best, word)
        return word

    def _match_case(self, corrected, original):
        """Match the case of the corrected word to the original."""
        if original.istitle():
            return corrected.capitalize()
        elif original.isupper():
            return corrected.upper()
        else:
            return corrected