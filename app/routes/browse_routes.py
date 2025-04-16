# routes/browse_routes.py
import logging
import json
import os
from pathlib import Path
from flask import render_template, jsonify, abort, request
from utils.file import find_files, read_json_file

from . import browse_bp

logger = logging.getLogger(__name__)

@browse_bp.route('/browse')
def browse_topics():
    """Affiche la structure des répertoires de sujets avec métadonnées et filtrage"""
    topics_dir = Path('data') / 'by_topic'

    # Récupération des paramètres de filtrage
    filter_word = request.args.get('filter_word', '').strip().lower()
    filter_date_from = request.args.get('date_from', '')
    filter_date_to = request.args.get('date_to', '')
    filter_canton = request.args.get('canton', '').strip()
    filter_newspaper = request.args.get('newspaper', '').strip().lower()

    # Récupération des paramètres de filtrage par nombre de mots
    min_words = request.args.get('min_words', '')
    max_words = request.args.get('max_words', '')

    # Paramètres de pagination
    limit_per_topic = 5  # Nombre par défaut d'articles à afficher par sujet
    show_all_topic = request.args.get('show_all_topic', '')  # Nom du sujet pour lequel afficher tous les résultats

    # Conversion en entiers si présents
    min_words = int(min_words) if min_words and min_words.isdigit() else None
    max_words = int(max_words) if max_words and max_words.isdigit() else None

    if not topics_dir.exists():
        return render_template('browse.html', error=f'Répertoire de sujets {topics_dir} introuvable', topics=[])

    topics = []
    for topic in sorted(topics_dir.iterdir()):
        if topic.is_dir():
            topic_info = {
                'name': topic.name,
                'files': [],
                'total_files': 0,
                'showing_all': topic.name == show_all_topic
            }

            matching_files = []
            # Utilisation de find_files pour trouver les JSON
            json_files = find_files(topic, "*.json")

            for file_path in sorted(json_files):
                try:
                    # Utilisation de read_json_file pour lire les fichiers
                    file_data = read_json_file(file_path)

                    # Vérification si le fichier correspond aux critères de filtrage
                    include_file = True

                    # Filtre par mot (dans le titre ou le contenu)
                    if filter_word:
                        title = file_data.get('title', '').lower()
                        content = file_data.get('content', '').lower()
                        if filter_word not in title and filter_word not in content:
                            include_file = False

                    # Filtre par plage de dates
                    if include_file and (filter_date_from or filter_date_to):
                        file_date = file_data.get('date', '')
                        if filter_date_from and file_date < filter_date_from:
                            include_file = False
                        if filter_date_to and file_date > filter_date_to:
                            include_file = False

                    # Filtre par nombre de mots
                    if include_file and (min_words is not None or max_words is not None):
                        word_count = file_data.get('word_count', 0)
                        if min_words is not None and word_count < min_words:
                            include_file = False
                        if max_words is not None and word_count > max_words:
                            include_file = False

                    # Filtre par canton
                    if include_file and filter_canton:
                        article_canton = file_data.get('canton', '')
                        if not article_canton or filter_canton.lower() != article_canton.lower():
                            include_file = False

                    # Filtre par journal
                    if include_file and filter_newspaper:
                        article_newspaper = file_data.get('newspaper', '').lower()
                        if not article_newspaper or filter_newspaper not in article_newspaper:
                            include_file = False

                    if include_file:
                        file_info = {
                            'filename': file_path.name,
                            'title': file_data.get('title', 'Sans titre'),
                            'date': file_data.get('date', 'Date inconnue'),
                            'word_count': file_data.get('word_count', 0),
                            'newspaper': file_data.get('newspaper', 'Source inconnue'),
                            'canton': file_data.get('canton', None)
                        }
                        matching_files.append(file_info)
                except Exception as e:
                    logger.error(f"Erreur de lecture du fichier {file_path}: {str(e)}")
                    if not filter_word and not filter_date_from and not filter_date_to and min_words is None and max_words is None:
                        # Ajouter les fichiers en erreur seulement si aucun filtre n'est actif
                        matching_files.append({
                            'filename': file_path.name,
                            'title': 'Erreur de lecture du fichier',
                            'error': str(e)
                        })

            # Définir le nombre total de fichiers correspondants
            topic_info['total_files'] = len(matching_files)

            # Appliquer la limite sauf si on affiche tout pour ce sujet
            if topic.name == show_all_topic or len(matching_files) <= limit_per_topic:
                topic_info['files'] = matching_files
            else:
                topic_info['files'] = matching_files[:limit_per_topic]
                topic_info['has_more'] = True

            topics.append(topic_info)

    return render_template(
        'browse.html',
        topics=topics,
        filter_word=filter_word,
        date_from=filter_date_from,
        date_to=filter_date_to,
        min_words=min_words or '',
        max_words=max_words or '',
        canton=filter_canton,
        newspaper=filter_newspaper,
        limit_per_topic=limit_per_topic
    )


@browse_bp.route('/topic/<topic_name>')
def topic_results(topic_name):
    """Affiche tous les articles pour un sujet spécifique avec filtrage"""
    topic_path = Path('data') / 'by_topic' / topic_name

    # Récupération des paramètres de filtrage
    filter_word = request.args.get('filter_word', '').strip().lower()
    filter_date_from = request.args.get('date_from', '')
    filter_date_to = request.args.get('date_to', '')
    filter_canton = request.args.get('canton', '').strip()
    filter_newspaper = request.args.get('newspaper', '').strip().lower()
    min_words = request.args.get('min_words', '')
    max_words = request.args.get('max_words', '')

    # Conversion en entiers si présents
    min_words = int(min_words) if min_words and min_words.isdigit() else None
    max_words = int(max_words) if max_words and max_words.isdigit() else None

    if not topic_path.exists() or not topic_path.is_dir():
        return render_template('topic_results.html', error=f'Sujet {topic_name} introuvable',
                               topic_name=topic_name, files=[])

    files = []
    for file in sorted(os.listdir(topic_path)):
        if file.endswith('.json'):
            file_path = os.path.join(topic_path, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)

                    # Vérification si le fichier correspond aux critères de filtrage
                    include_file = True

                    # Filtre par mot (dans le titre ou le contenu)
                    if filter_word:
                        title = file_data.get('title', '').lower()
                        content = file_data.get('content', '').lower()
                        if filter_word not in title and filter_word not in content:
                            include_file = False

                    # Filtre par plage de dates
                    if include_file and (filter_date_from or filter_date_to):
                        file_date = file_data.get('date', '')
                        if filter_date_from and file_date < filter_date_from:
                            include_file = False
                        if filter_date_to and file_date > filter_date_to:
                            include_file = False

                    # Filtre par nombre de mots
                    if include_file and (min_words is not None or max_words is not None):
                        word_count = file_data.get('word_count', 0)
                        if min_words is not None and word_count < min_words:
                            include_file = False
                        if max_words is not None and word_count > max_words:
                            include_file = False

                    # Filtre par canton
                    if include_file and filter_canton:
                        article_canton = file_data.get('canton', '')
                        if not article_canton or filter_canton.lower() != article_canton.lower():
                            include_file = False

                    # Filtre par journal
                    if include_file and filter_newspaper:
                        article_newspaper = file_data.get('newspaper', '').lower()
                        if not article_newspaper or filter_newspaper not in article_newspaper:
                            include_file = False

                    if include_file:
                        file_info = {
                            'filename': file,
                            'title': file_data.get('title', 'Sans titre'),
                            'date': file_data.get('date', 'Date inconnue'),
                            'word_count': file_data.get('word_count', 0),
                            'newspaper': file_data.get('newspaper', 'Source inconnue'),
                            'canton': file_data.get('canton', None)
                        }
                        files.append(file_info)
            except Exception as e:
                logger.error(f"Erreur de lecture du fichier {file_path}: {str(e)}")
                if not filter_word and not filter_date_from and not filter_date_to and min_words is None and max_words is None:
                    # Ajouter les fichiers en erreur seulement si aucun filtre n'est actif
                    files.append({
                        'filename': file,
                        'title': 'Erreur de lecture du fichier',
                        'error': str(e)
                    })

    return render_template(
        'topic_results.html',
        topic_name=topic_name,
        files=files,
        filter_word=filter_word,
        date_from=filter_date_from,
        date_to=filter_date_to,
        min_words=min_words or '',
        max_words=max_words or '',
        canton=filter_canton,
        newspaper=filter_newspaper,
        total_files=len(files)
    )


@browse_bp.route('/browse/<topic>/<filename>')
def view_file(topic, filename):
    """Affiche un fichier JSON spécifique avec métadonnées complètes et versions"""
    file_path = os.path.join('data', 'by_topic', topic, filename)

    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        abort(404)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_content = json.load(f)

            # Récupération du base_id pour trouver toutes les versions
            base_id = full_content.get('base_id')
            current_version_id = full_content.get('id')

            # Récupération de toutes les versions de cet article
            versions = []
            if base_id:
                from services.correction import get_article_versions
                versions = get_article_versions(base_id)

            # Récupération du contenu original si des corrections orthographiques ont été faites
            original_content = full_content.get('original_content')
            content = full_content.get('content', '')
            spell_corrected = full_content.get('spell_corrected', False)

            # Génération du HTML de différence si des corrections orthographiques sont présentes
            diff_html = None
            show_diff = False
            if spell_corrected and original_content:
                from newspapers_scrap.utils import generate_html_diff
                diff_html = generate_html_diff(original_content, content)
                show_diff = True

            # Extraction des métadonnées pour le template
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
                'correction_method': full_content.get('correction_method', 'none'),
                'language': full_content.get('language', 'fr'),
                'diff_html': diff_html,
                'show_diff': show_diff,
                'versions': versions,
                'current_version_id': current_version_id,
                'base_id': base_id
            }

        return render_template('view_file.html', filename=filename, topic=topic, **metadata)
    except Exception as e:
        logger.error(f"Erreur de lecture du fichier {file_path}: {str(e)}")
        return render_template('view_file.html', error=str(e), filename=filename, topic=topic)


@browse_bp.route('/api/file/<topic>/<filename>')
def get_file_content(topic, filename):
    """Point d'accès API pour obtenir le contenu du fichier au format JSON"""
    file_path = os.path.join('data', 'by_topic', topic, filename)

    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        return jsonify({'error': 'Fichier introuvable'}), 404

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_content = json.load(f)
            # Extraction du titre et du contenu uniquement
            result = {
                'title': full_content.get('title', ''),
                'content': full_content.get('content', '')
            }
        return jsonify(result)
    except Exception as e:
        logger.error(f"Erreur de lecture du fichier {file_path}: {str(e)}")
        return jsonify({'error': str(e)}), 500