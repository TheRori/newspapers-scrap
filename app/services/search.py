# services/search.py
import json
import logging
import os
import sys
import traceback
from threading import Thread
from queue import Empty
from flask import current_app, copy_current_request_context

logger = logging.getLogger(__name__)


def create_search_tasks(query_data):
    """
    Creates search tasks based on query parameters.

    Args:
        query_data: Dictionary containing search parameters

    Returns:
        Tuple containing (list of search commands, list of corresponding periods)
    """
    logger.info(f"Creating search tasks with query data: {query_data}")
    search_tasks = []  # List to store multiple search tasks
    search_periods = []  # Store human-readable periods for each task

    # Base command with common parameters
    base_cmd = [sys.executable, 'scripts/run_search.py', query_data['query']]
    logger.info(f"Base command: {base_cmd}")

    # Add common parameters
    if query_data.get('newspapers'):
        base_cmd.extend(['--newspapers'] + query_data['newspapers'].split())
    if query_data.get('cantons'):
        base_cmd.extend(['--cantons'] + query_data['cantons'].split())
    if query_data.get('searches') and query_data.get('searches') != 'all':
        base_cmd.extend(['--max_articles', str(query_data['searches'])])

    # Get start_from parameter value (UI value is 1-based, code uses 0-based)
    start_from = query_data.get('start_from', '0')
    try:
        start_from_value = int(start_from)
    except ValueError:
        logger.warning(f"Invalid start_from value: {start_from}, defaulting to 0")
        start_from_value = 0

    # Add correction parameters
    correction_method = query_data.get('correction_method', 'none')
    if correction_method and correction_method != 'none':
        base_cmd.extend(['--correction', correction_method])
    else:
        base_cmd.extend(['--no-correction'])

    # Handle year-by-year search
    start_year = query_data.get('start_year')
    end_year = query_data.get('end_year')

    if start_year and end_year:
        start_year = int(start_year)
        end_year = int(end_year)
        logger.info(f"Creating year-by-year search tasks from {start_year} to {end_year}")

        # Create a task for each year
        for i, year in enumerate(range(start_year, end_year + 1)):
            year_cmd = base_cmd.copy()
            year_cmd.extend(['--date_range', f"{year}-{year}"])

            # Only add start_from parameter to the first year/task
            if i == 0 and start_from_value > 0:
                year_cmd.extend(['--start_from', str(start_from_value - 1)])  # Convert to 0-based

            search_tasks.append(year_cmd)
            search_periods.append(f"{year}")
    else:
        logger.info("Creating single search task")
        # For single search or all-time search, include start_from if needed
        if start_from_value > 0:
            base_cmd.extend(['--start_from', str(start_from_value - 1)])  # Convert to 0-based

        search_tasks.append(base_cmd)
        search_periods.append("Default")

    logger.info(f"Created {len(search_tasks)} search tasks")
    return search_tasks, search_periods


def emit_search_output(process_tracker, app):
    """
    Background task to emit search progress via socketio

    Args:
        process_tracker: ProcessTracker instance to track search state
        app: Flask app instance for creating application context
    """
    logger.info("Starting emit_search_output thread")
    
    # Create application context for this thread
    with app.app_context():
        try:
            socketio = current_app.socketio
            logger.info(f"Got socketio from current_app: {socketio}")
        except Exception as e:
            logger.error(f"Error getting socketio from current_app: {str(e)}")
            socketio = None
        
        while process_tracker.running:
            try:
                if process_tracker.process and process_tracker.process.poll() is not None:  # Check if the current process is finished
                    logger.info(f"Process completed with return code: {process_tracker.process.returncode}")
                    process_tracker.current_task_index += 1
                    logger.info(f"Moving to next task: {process_tracker.current_task_index}")

                    # If all tasks are finished
                    if process_tracker.current_task_index >= len(process_tracker.search_tasks):
                        logger.info("All search tasks completed")
                        process_tracker.emit_socketio_event('search_complete', {
                            'status': 'completed'
                        })
                        process_tracker.running = False
                        continue

                    # Start the next task
                    next_cmd = process_tracker.search_tasks[process_tracker.current_task_index]
                    current_period = process_tracker.search_periods[process_tracker.current_task_index]
                    logger.info(f"Starting next task with command: {next_cmd}")

                    # Emit information about the next task
                    process_tracker.emit_socketio_event('task_change', {
                        'current_task': process_tracker.current_task_index + 1,
                        'total_tasks': len(process_tracker.search_tasks),
                        'period': current_period
                    })

                    # Calculate overall progress (based on finished tasks)
                    overall_progress = int((process_tracker.current_task_index / len(process_tracker.search_tasks)) * 100)

                    # Start the next process using the tracker's method
                    process_tracker.start_process(next_cmd, current_period)
                    logger.info(f"Started process for task {process_tracker.current_task_index}")

                    # Update progress with the overall progress value
                    process_tracker.emit_socketio_event('overall_progress', {
                        'value': overall_progress,
                        'current_task': process_tracker.current_task_index + 1,
                        'total_tasks': len(process_tracker.search_tasks)
                    })

                    # Continue processing output
                    continue

                try:
                    if process_tracker.output_queue:
                        try:
                            line = process_tracker.output_queue.get(timeout=0.1)
                            if line:
                                logger.debug(f"Output line: {line}")
                                process_tracker.emit_socketio_event('log_message', {
                                    'message': line
                                })
                        except Empty:
                            pass
                except Exception as e:
                    logger.error(f"Error processing output queue: {str(e)}")
            except Exception as e:
                logger.error(f"Error in emit_search_output main loop: {str(e)}")
                logger.error(traceback.format_exc())


def start_search(process_tracker, query_data):
    """
    Starts a search based on query data

    Args:
        process_tracker: ProcessTracker instance to track search state
        query_data: Dictionary containing search parameters

    Returns:
        Dictionary containing search information
    """
    logger.info(f"Starting search with process_tracker: {process_tracker}")
    
    # Get Flask app instance
    app = current_app._get_current_object()
    
    # Clean previous state
    process_tracker.running = False
    if process_tracker.process and process_tracker.process.poll() is None:
        try:
            process_tracker.process.terminate()
            logger.info("Terminated existing process")
        except Exception as e:
            logger.error(f"Error terminating existing process: {str(e)}")

    # Remove the stop signal file if it exists
    if os.path.exists('stop_signal.txt'):
        try:
            os.remove('stop_signal.txt')
            logger.info("Removed existing stop signal file")
        except Exception as e:
            logger.error(f"Error removing stop signal file: {str(e)}")

    # Create search tasks
    search_tasks, search_periods = create_search_tasks(query_data)

    # Update the process tracker
    process_tracker.search_tasks = search_tasks
    process_tracker.search_periods = search_periods
    process_tracker.current_task_index = 0
    process_tracker.running = True
    logger.info(f"Updated process tracker with {len(search_tasks)} tasks")

    # Send the total number of tasks to the client
    process_tracker.emit_socketio_event('search_started', {
        'total_tasks': len(search_tasks),
        'periods': search_periods
    })

    # Start the first task
    cmd = search_tasks[0]
    current_period = search_periods[0]
    logger.info(f"Starting first task with command: {cmd}")

    try:
        # Start process using the tracker's method
        process = process_tracker.start_process(cmd, current_period)
        logger.info(f"Started process with PID: {process.pid if process else 'Unknown'}")
    except Exception as e:
        logger.error(f"Error starting process: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'status': 'error',
            'error': f"Failed to start search process: {str(e)}"
        }

    # Start the background task to emit output
    try:
        # Use emit_output from app.py if available
        if hasattr(current_app, 'emit_output'):
            output_thread = Thread(target=current_app.emit_output)
            output_thread.daemon = True
            output_thread.start()
            logger.info("Started emit_output thread from current_app")
        else:
            # Fallback to local emit_search_output function
            output_thread = Thread(target=emit_search_output, args=(process_tracker, app))
            output_thread.daemon = True
            output_thread.start()
            logger.info("Started local emit_search_output thread")
    except Exception as e:
        logger.error(f"Error starting output thread: {str(e)}")
        logger.error(traceback.format_exc())

    return {
        'status': 'started',
        'tasks_count': len(search_tasks),
        'periods': search_periods
    }