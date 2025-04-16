# routes/version_routes.py
import logging
import json
import os
from pathlib import Path
from flask import render_template, jsonify, abort, request
from . import version_bp
from services.correction import get_article_versions

logger = logging.getLogger(__name__)

@version_bp.route('/version/<version_id>')
def view_version(version_id):
    """Vue d'une version spécifique d'un article"""
    logger.debug(f"Version demandée: {version_id}")

    # Vérification si cet identifiant de version existe
    versions_dir = Path('data') / 'processed' / 'versions'
    version_file = None
    base_dir = None

    # D'abord, tenter de trouver le fichier de version directement
    for base_dir_path in versions_dir.glob('article_*'):
        potential_file = base_dir_path / f"{version_id}.json"
        if potential_file.exists():
            version_file = potential_file
            base_dir = base_dir_path
            break

    # Si non trouvé, essayer d'extraire les parties du base_id du version_id
    if not version_file:
        # Extraire la date et le journal du version_id
        parts = version_id.split('_')
        if len(parts) >= 3:
            date_part = parts[1]  # Format YYYYMMDD
            newspaper_part = parts[2]  # Identifiant du journal

            # Rechercher les répertoires de base correspondants
            potential_dirs = list(versions_dir.glob(f"article_{date_part}_{newspaper_part}*"))
            if potential_dirs:
                base_dir = potential_dirs[0]
                version_file = base_dir / f"{version_id}.json"

                # Si le fichier exact n'existe pas, chercher tout fichier avec ce version_id
                if not version_file.exists():
                    matching_files = list(base_dir.glob(f"*{version_id}*.json"))
                    if matching_files:
                        version_file = matching_files[0]

    if not version_file or not version_file.exists():
        logger.error(f"Impossible de trouver le fichier de version pour: {version_id}")
        abort(404)

    base_id = base_dir.name if base_dir else None
    logger.debug(f"base_id trouvé: {base_id}")
    logger.debug(f"Fichier de version utilisé: {version_file}")

    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            full_content = json.load(f)

        # Récupérer le base_id du contenu si disponible
        if 'base_id' in full_content:
            base_id = full_content['base_id']
            logger.debug(f"base_id mis à jour depuis le contenu du fichier: {base_id}")

        # Récupérer toutes les versions de cet article
        versions = get_article_versions(base_id)

        # Récupérer le texte brut (contenu original non corrigé) depuis le fichier brut
        raw_path = full_content.get('raw_path')
        original_content = None

        if raw_path and os.path.exists(raw_path):
            try:
                with open(raw_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                    logger.info(f"Contenu original chargé depuis le fichier brut: {raw_path}")
            except Exception as e:
                logger.error(f"Impossible de charger le contenu original depuis {raw_path}: {str(e)}")

        # Si raw_path n'existe pas ou n'a pas pu être lu, essayer de récupérer depuis le fichier lui-même
        if not original_content:
            original_content = full_content.get('original_content')

        content = full_content.get('content', '')
        spell_corrected = full_content.get('spell_corrected', False)
        correction_method = full_content.get('correction_method', 'none')

        # Générer le HTML de différence s'il y a des corrections orthographiques
        diff_html = None
        show_diff = False

        if spell_corrected and original_content and correction_method != 'none':
            from newspapers_scrap.utils import generate_html_diff
            diff_html = generate_html_diff(original_content, content)
            show_diff = True
            logger.info("HTML de différence généré pour la vue de version")

        metadata = {
            'title': full_content.get('title', ''),
            'content': content,
            'original_content': original_content,
            'date': full_content.get('date', ''),
            'newspaper': full_content.get('newspaper', ''),
            'canton': full_content.get('canton', ''),
            'word_count': full_content.get('word_count', 0),
            'url': full_content.get('url', ''),
            'spell_corrected': spell_corrected,
            'correction_method': correction_method,
            'language': full_content.get('language', 'fr'),
            'diff_html': diff_html,
            'show_diff': show_diff,
            'versions': versions,
            'current_version_id': version_id,
            'base_id': base_id,
            'is_version_view': True
        }

        # Déterminer à quel sujet appartient cet article
        topic = "unknown"
        topics_dir = Path('data') / 'by_topic'
        if topics_dir.exists():
            for topic_dir in topics_dir.iterdir():
                if topic_dir.is_dir():
                    for file_path in topic_dir.glob('*.json'):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                                if file_data.get('base_id') == base_id:
                                    topic = topic_dir.name
                                    break
                        except:
                            continue
                    if topic != "unknown":
                        break

        return render_template('view_file.html', filename=f"{version_id}.json", topic=topic, **metadata)

    except Exception as e:
        logger.error(f"Erreur de lecture du fichier de version {version_file}: {str(e)}")
        return render_template('view_file.html', error=str(e), filename=f"{version_id}.json", topic="unknown")