# routes/search_routes.py
import logging
import os
import sys
import json
from pathlib import Path
from flask import jsonify, request, current_app
from threading import Thread

from . import search_bp
from services.search import start_search

logger = logging.getLogger(__name__)

# We'll get process_tracker and socketio from current_app instead of importing directly
# to avoid circular imports

def get_process_tracker():
    logger.info("Getting process_tracker from current_app")
    if hasattr(current_app, 'process_tracker'):
        return current_app.process_tracker
    else:
        logger.error("process_tracker not found in current_app")
        return None

def get_socketio():
    logger.info("Getting socketio from current_app")
    if hasattr(current_app, 'socketio'):
        return current_app.socketio
    else:
        logger.error("socketio not found in current_app")
        return None

def emit_output(data):
    socketio = get_socketio()
    if socketio:
        socketio.emit('output', data)
    else:
        logger.error("Cannot emit output: socketio not available")


@search_bp.route('/api/search', methods=['POST'])
def search():
    """
    API endpoint to start an article search.
    Accepts search parameters in JSON and starts the search process.
    """
    logger.info("Search API endpoint called")
    
    # Get process_tracker from current_app
    process_tracker = get_process_tracker()
    if not process_tracker:
        logger.error("Cannot start search: process_tracker not available")
        return jsonify({
            'status': 'error',
            'error': 'Process tracker not available'
        }), 500
        
    data = request.json
    logger.info(f"Search request data: {data}")

    try:
        # Start the search with the provided parameters
        logger.info("Starting search with process_tracker")
        result = start_search(process_tracker, data)
        logger.info(f"Search started, result: {result}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Error starting search: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


@search_bp.route('/api/search/stop', methods=['POST'])
def stop_search():
    """
    Arrête le processus de recherche en cours
    """
    try:
        # Créer un fichier de signal d'arrêt pour le processus de recherche
        with open('stop_signal.txt', 'w') as f:
            f.write('stop')

        # Marquer le traceur de processus comme non actif
        get_process_tracker().running = False

        # Tenter de terminer le processus en cours
        if get_process_tracker().process and get_process_tracker().process.poll() is None:
            try:
                get_process_tracker().process.terminate()
                logger.info("Processus de recherche terminé")

                # Informer les clients via le socket
                get_socketio().emit('search_stopped', {'message': 'Recherche arrêtée manuellement'})
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
    # We don't need to import process_tracker again, it's already imported at the top of the file

    status = {
        'running': get_process_tracker().running,
        'current_task': get_process_tracker().current_task_index + 1 if get_process_tracker().running else 0,
        'total_tasks': len(get_process_tracker().search_tasks) if get_process_tracker().search_tasks else 0,
        'current_period': get_process_tracker().search_periods[get_process_tracker().current_task_index]
        if get_process_tracker().running and get_process_tracker().search_periods else "Aucune"
    }

    # Calculer la progression globale
    if status['total_tasks'] > 0:
        status['overall_progress'] = int((get_process_tracker().current_task_index / status['total_tasks']) * 100)
    else:
        status['overall_progress'] = 0

    return jsonify(status)