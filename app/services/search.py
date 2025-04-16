# services/search.py
import logging
import os
import sys
from pathlib import Path
from threading import Thread
from queue import Empty

logger = logging.getLogger(__name__)


def create_search_tasks(query_data):
    """
    Crée les tâches de recherche basées sur les paramètres de la requête.

    Args:
        query_data: Dictionnaire contenant les paramètres de recherche

    Returns:
        Tuple contenant (liste de commandes de recherche, liste des périodes correspondantes)
    """
    search_tasks = []  # Liste pour stocker plusieurs tâches de recherche
    search_periods = []  # Stockage des périodes lisibles pour chaque tâche

    # Commande de base avec les paramètres communs
    base_cmd = [sys.executable, 'scripts/run_search.py', query_data['query']]

    # Ajout des paramètres communs
    if query_data.get('newspapers'):
        base_cmd.extend(['--newspapers'] + query_data['newspapers'].split())
    if query_data.get('cantons'):
        base_cmd.extend(['--cantons'] + query_data['cantons'].split())
    if query_data.get('searches') and query_data.get('searches') != 'all':
        base_cmd.extend(['--max_articles', str(query_data['searches'])])

    # Récupération du paramètre start_from (l'UI utilise une base 1, le code une base 0)
    start_from = query_data.get('start_from', '0')
    try:
        start_from_value = int(start_from)
    except ValueError:
        logger.warning(f"Valeur start_from invalide: {start_from}, retour à 0 par défaut")
        start_from_value = 0

    # Ajout des paramètres de correction
    correction_method = query_data.get('correction_method', 'none')
    if correction_method and correction_method != 'none':
        base_cmd.extend(['--correction', correction_method])
    else:
        base_cmd.extend(['--no-correction'])

    # Gestion de la recherche année par année
    start_year = query_data.get('start_year')
    end_year = query_data.get('end_year')

    if start_year and end_year:
        start_year = int(start_year)
        end_year = int(end_year)

        # Création d'une tâche pour chaque année
        for i, year in enumerate(range(start_year, end_year + 1)):
            year_cmd = base_cmd.copy()
            year_cmd.extend(['--date_range', f"{year}-{year}"])

            # Ajout du paramètre start_from uniquement à la première année/tâche
            if i == 0 and start_from_value > 0:
                year_cmd.extend(['--start_from', str(start_from_value - 1)])  # Conversion vers base 0

            search_tasks.append(year_cmd)
            search_periods.append(f"{year}")
    else:
        # Pour une recherche unique ou sur toute la période
        if start_from_value > 0:
            base_cmd.extend(['--start_from', str(start_from_value - 1)])  # Conversion vers base 0

        search_tasks.append(base_cmd)
        search_periods.append("Default")

    return search_tasks, search_periods


def emit_search_output(socketio, process_tracker):
    """
    Tâche d'arrière-plan pour émettre les progrès de recherche via Socket.IO

    Args:
        socketio: Instance SocketIO pour émettre des événements
        process_tracker: Instance de ProcessTracker pour suivre l'état de la recherche
    """
    while process_tracker.running:
        if process_tracker.process.poll() is not None:  # Vérification si le processus actuel a terminé
            process_tracker.current_task_index += 1

            # Si toutes les tâches sont terminées
            if process_tracker.current_task_index >= len(process_tracker.search_tasks):
                socketio.emit('search_complete', {'status': 'completed'})
                process_tracker.running = False
                socketio.sleep(0.1)
                break

            # Démarrage de la tâche suivante
            next_cmd = process_tracker.search_tasks[process_tracker.current_task_index]
            current_period = process_tracker.search_periods[process_tracker.current_task_index]

            # Émission d'informations sur la tâche suivante
            socketio.emit('task_change', {
                'current_task': process_tracker.current_task_index + 1,
                'total_tasks': len(process_tracker.search_tasks),
                'period': current_period
            })

            # Calcul de la progression globale (basé sur les tâches terminées)
            overall_progress = int((process_tracker.current_task_index / len(process_tracker.search_tasks)) * 100)

            # Démarrage du processus suivant en utilisant la méthode d'aide
            process_tracker.start_process(next_cmd, current_period)

            # Mise à jour de la progression avec la valeur de progression globale
            socketio.emit('overall_progress', {
                'value': overall_progress,
                'current_task': process_tracker.current_task_index + 1,
                'total_tasks': len(process_tracker.search_tasks)
            })

            # Poursuite du traitement de la sortie
            continue

        try:
            if process_tracker.output_queue:
                try:
                    line = process_tracker.output_queue.get(timeout=0.1)
                    if line:
                        socketio.emit('log_message', {'message': line})
                        socketio.sleep(0)
                except Empty:
                    socketio.sleep(0.1)
        except Exception as e:
            logger.error(f"Erreur dans emit_search_output: {str(e)}")
            socketio.sleep(0.1)


def start_search(socketio, process_tracker, query_data):
    """
    Démarre une recherche basée sur les données de la requête

    Args:
        socketio: Instance SocketIO pour émettre des événements
        process_tracker: Instance de ProcessTracker pour suivre l'état de la recherche
        query_data: Dictionnaire contenant les paramètres de recherche

    Returns:
        Dictionnaire contenant les informations de recherche
    """
    # Nettoyage de l'état précédent
    process_tracker.running = False
    if process_tracker.process and process_tracker.process.poll() is None:
        try:
            process_tracker.process.terminate()
        except:
            pass

    # Suppression du fichier de signal d'arrêt s'il existe
    if os.path.exists('stop_signal.txt'):
        try:
            os.remove('stop_signal.txt')
            logger.info("Fichier de signal d'arrêt existant supprimé")
        except Exception as e:
            logger.error(f"Erreur lors de la suppression du fichier de signal d'arrêt: {str(e)}")

    # Création des tâches de recherche
    search_tasks, search_periods = create_search_tasks(query_data)

    # Mise à jour du traceur de processus
    process_tracker.search_tasks = search_tasks
    process_tracker.search_periods = search_periods
    process_tracker.current_task_index = 0
    process_tracker.running = True

    # Envoi du nombre total de tâches au client
    socketio.emit('search_started', {
        'total_tasks': len(search_tasks),
        'periods': search_periods
    })

    # Démarrage de la première tâche
    cmd = search_tasks[0]
    current_period = search_periods[0]

    # Démarrage du processus en utilisant la méthode du traceur
    process_tracker.start_process(cmd, current_period)

    # Démarrage de la tâche d'arrière-plan pour émettre la sortie
    socketio.start_background_task(emit_search_output, socketio, process_tracker)

    return {
        'status': 'started',
        'tasks_count': len(search_tasks),
        'periods': search_periods
    }