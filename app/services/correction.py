# services/correction.py
import json
import logging
import os
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def correct_article_content(article_data, correction_method):
    """
    Applique une correction orthographique au contenu d'un article.

    Args:
        article_data: Dictionnaire contenant les données de l'article
        correction_method: Méthode de correction à utiliser ('symspell' ou 'mistral')

    Returns:
        Tuple contenant (texte corrigé, booléen de succès)
    """
    # S'assurer que le contenu original est disponible
    if 'original_content' not in article_data and 'content' in article_data:
        article_data['original_content'] = article_data['content']

    original_content = article_data.get('original_content', '')
    if not original_content:
        logger.error("Aucun contenu disponible pour la correction")
        return None, False

    corrected_text = None
    success = False

    try:
        # Appliquer la méthode de correction sélectionnée
        if correction_method == 'symspell':
            from newspapers_scrap.data_manager.ocr_cleaner.symspell_checker import SpellCorrector
            corrector = SpellCorrector(language='fr')
            corrected_text = corrector.correct_text_sym(original_content)
            success = True
            logger.info("Correction SymSpell appliquée avec succès")

        elif correction_method == 'mistral':
            from newspapers_scrap.data_manager.ocr_cleaner.mistral_checker import correct_text_ai

            # Utiliser des fichiers temporaires pour la correction Mistral
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_in:
                temp_in.write(original_content)
                input_path = temp_in.name

            output_path = input_path + '_corrected'
            if correct_text_ai(input_path, output_path):
                with open(output_path, 'r', encoding='utf-8') as f:
                    corrected_text = f.read()
                success = True
                logger.info("Correction Mistral appliquée avec succès")
                os.unlink(output_path)  # Nettoyage
            else:
                logger.error("La correction Mistral a échoué")
                success = False

            os.unlink(input_path)  # Nettoyage
        else:
            logger.error(f"Méthode de correction non valide: {correction_method}")
            success = False
    except Exception as e:
        logger.error(f"Erreur lors de la correction du texte: {str(e)}")
        success = False

    return corrected_text, success


def save_corrected_article(file_path, article_data, corrected_text, correction_method):
    """
    Sauvegarde l'article corrigé et crée une nouvelle version.

    Args:
        file_path: Chemin du fichier de l'article
        article_data: Dictionnaire contenant les données de l'article
        corrected_text: Texte corrigé à sauvegarder
        correction_method: Méthode de correction utilisée

    Returns:
        Tuple contenant (booléen de succès, nombre de mots, dictionnaire de la version)
    """
    try:
        # Mettre à jour les données de l'article
        article_data.update({
            'content': corrected_text,
            'spell_corrected': True,
            'correction_method': correction_method,
            'word_count': len(corrected_text.split())
        })

        # Sauvegarder le fichier mis à jour
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(article_data, f, ensure_ascii=False, indent=4)

        # Créer une nouvelle version de l'article
        version_id = f"{article_data['id']}_{correction_method}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        base_id = article_data.get('base_id') or article_data.get('id')
        versions_dir = Path('data') / 'processed' / 'versions' / base_id
        versions_dir.mkdir(exist_ok=True, parents=True)

        version_data = article_data.copy()
        version_data.update({
            'id': version_id,
            'base_id': base_id,
            'created_at': datetime.now().isoformat()
        })

        version_path = versions_dir / f"{version_id}.json"
        with open(version_path, 'w', encoding='utf-8') as f:
            json.dump(version_data, f, ensure_ascii=False, indent=4)

        logger.info(f"Version sauvegardée: {version_path}")

        return True, article_data['word_count'], version_data

    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde de l'article corrigé: {str(e)}")
        return False, 0, None


def get_article_versions(base_id):
    """
    Récupère toutes les versions d'un article.

    Args:
        base_id: L'identifiant de base de l'article

    Returns:
        Liste de dictionnaires contenant les métadonnées des versions
    """
    versions_dir = Path('data') / 'processed' / 'versions' / base_id
    if not versions_dir.exists():
        return []

    versions = []
    for version_file in versions_dir.glob('*.json'):
        try:
            with open(version_file, 'r', encoding='utf-8') as f:
                version_data = json.load(f)
                versions.append({
                    'id': version_data['id'],
                    'correction_method': version_data.get('correction_method', 'none'),
                    'language': version_data.get('language', 'fr'),
                    'word_count': version_data.get('word_count', 0),
                    'created_at': version_data.get('created_at', ''),
                    'path': str(version_file)
                })
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Erreur lors de la lecture du fichier de version {version_file}: {str(e)}")

    # Trier les versions par date de création (plus récentes en premier)
    versions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return versions


def process_article_correction(file_path, correction_method):
    """
    Traite une demande de correction d'article complète.

    Args:
        file_path: Chemin du fichier de l'article
        correction_method: Méthode de correction à utiliser

    Returns:
        Tuple contenant (succès, message d'erreur, données de résultat)
    """
    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        return False, "Fichier non trouvé", None

    try:
        # Charger les données de l'article
        with open(file_path, 'r', encoding='utf-8') as f:
            article_data = json.load(f)

        # Appliquer la correction
        corrected_text, success = correct_article_content(article_data, correction_method)
        if not success:
            return False, f"La correction {correction_method} a échoué", None

        # Sauvegarder l'article corrigé
        success, word_count, version_data = save_corrected_article(
            file_path, article_data, corrected_text, correction_method
        )

        if not success:
            return False, "Échec de la sauvegarde de l'article corrigé", None

        return True, None, {
            'success': True,
            'word_count': word_count,
            'correction_method': correction_method
        }

    except Exception as e:
        logger.error(f"Erreur lors de la correction du fichier {file_path}: {str(e)}")
        return False, str(e), None