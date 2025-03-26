# Update in newspapers_scrap/mistral_api/client.py
import requests
import logging
from newspapers_scrap.config.config import env

logger = logging.getLogger(__name__)

HEADERS = {
    "Authorization": f"Bearer {env.mistral.MISTRAL_API_KEY}",
    "Content-Type": "application/json"
}


def call_mistral_correction(texte_ocr: str) -> str:
    logger.info(f"Calling Mistral API for text correction ({len(texte_ocr)} characters)")

    prompt = f"""Corrige uniquement les erreurs d'OCR dans ce texte, sans changer le style, toujours en respectant la langue :

{texte_ocr}

Texte corrigé :
"""
    data = {
        "model": env.mistral.MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
    }

    try:
        logger.info(f"Using Mistral model: {env.mistral.MODEL_NAME}")
        response = requests.post("https://api.mistral.ai/v1/chat/completions", headers=HEADERS, json=data)

        if response.ok:
            corrected_text = response.json()["choices"][0]["message"]["content"].strip()
            logger.info(f"Mistral API returned corrected text ({len(corrected_text)} characters)")
            return corrected_text
        else:
            logger.error(f"Mistral API error: {response.status_code} - {response.text}")
            raise Exception(f"Erreur API Mistral : {response.status_code} - {response.text}")
    except Exception as e:
        logger.error(f"Exception during Mistral API call: {str(e)}")
        raise