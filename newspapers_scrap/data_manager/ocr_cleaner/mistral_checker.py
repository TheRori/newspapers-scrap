# Update in newspapers_scrap/data_manager/ocr_cleaner/mistral_checker.py
import logging
from newspapers_scrap.mistral_api.client import call_mistral_correction

logger = logging.getLogger(__name__)


def correct_text_ai(path_in: str, path_out: str):
    logger.info(f"Starting AI-based text correction: {path_in} -> {path_out}")

    try:
        with open(path_in, "r", encoding="utf-8") as f:
            texte = f.read()
            logger.info(f"Read {len(texte)} characters from {path_in}")

        logger.info("Calling Mistral API for correction")
        texte_corrige = call_mistral_correction(texte)

        with open(path_out, "w", encoding="utf-8") as f:
            f.write(texte_corrige)
            logger.info(f"Wrote {len(texte_corrige)} characters to {path_out}")

        diff_chars = abs(len(texte_corrige) - len(texte))
        logger.info(f"Text correction complete. Character difference: {diff_chars}")

        return True
    except Exception as e:
        logger.error(f"Error in AI text correction: {str(e)}")
        return False