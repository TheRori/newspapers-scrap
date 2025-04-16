# routes/search_routes.py
import logging
import os
import sys
from pathlib import Path
from flask import jsonify, request
from flask_socketio import SocketIO

from . import search_bp
from services.search import start_search

logger = logging.getLogger(__name__)


@search_bp.route('/api/search', methods=['POST'])
def search():
    """
    Point d'entrée API pour lancer une recherche d'articles.
    Accepte les paramètres de recherche en JSON et démarre le processus de recherche.
    """
    from app import process_tracker, socketio

    data = request.json

    try:
        # Démarrer la recherche avec les paramètres fournis
        result = start_search(socketio, process_tracker, data)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Erreur lors du démarrage de la recherche: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@search_bp.route('/api/search/stop', methods=['POST'])
def stop_search():
    """
    Arrête le processus de recherche en cours
    """
    from app import process_tracker

    try:
        # Créer un fichier de signal d'arrêt pour le processus de recherche
        with open('stop_signal.txt', 'w') as f:
            f.write('stop')

        # Marquer le traceur de processus comme non actif
        process_tracker.running = False

        # Tenter de terminer le processus en cours
        if process_tracker.process and process_tracker.process.poll() is None:
            try:
                process_tracker.process.terminate()
                logger.info("Processus de recherche terminé")
            except Exception as e:
                logger.error(f"Erreur lors de la terminaison du processus: {str(e)}")

        return jsonify({
            'status': 'stopped',
            'message': 'Recherche arrêtée avec succès'
        })

    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt de la recherche: {str(e)}")
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@search_bp.route('/api/search/status', methods=['GET'])
def search_status():
    """
    Renvoie l'état actuel du processus de recherche
    """
    from app import process_tracker

    status = {
        'running': process_tracker.running,
        'current_task': process_tracker.current_task_index + 1 if process_tracker.running else 0,
        'total_tasks': len(process_tracker.search_tasks) if process_tracker.search_tasks else 0,
        'current_period': process_tracker.search_periods[process_tracker.current_task_index]
        if process_tracker.running and process_tracker.search_periods else "Aucune"
    }

    # Calculer la progression globale
    if status['total_tasks'] > 0:
        status['overall_progress'] = int((process_tracker.current_task_index / status['total_tasks']) * 100)
    else:
        status['overall_progress'] = 0

    return jsonify(status)