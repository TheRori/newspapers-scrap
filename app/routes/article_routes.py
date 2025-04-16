# routes/article_routes.py
import logging
import os
from pathlib import Path
from flask import jsonify, request, render_template

from . import article_bp
from services.correction import process_article_correction

logger = logging.getLogger(__name__)


@article_bp.route('/api/correct/<topic>/<filename>', methods=['POST'])
def correct_file(topic, filename):
    """
    Point d'accès API pour appliquer une correction orthographique à un fichier.

    Accepte la méthode de correction via JSON et traite l'article
    en utilisant le service de correction approprié.
    """
    file_path = os.path.join('data', 'by_topic', topic, filename)

    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        return jsonify({'error': 'Fichier introuvable'}), 404

    try:
        # Récupération de la méthode de correction depuis la requête
        data = request.json
        correction_method = data.get('correction_method', 'symspell')

        # Traitement de la correction via le service dédié
        success, error_message, result = process_article_correction(file_path, correction_method)

        if not success:
            return jsonify({'error': error_message}), 500

        return jsonify(result)

    except Exception as e:
        logger.error(f"Erreur lors de la correction du fichier {file_path}: {str(e)}")
        return jsonify({'error': str(e)}), 500