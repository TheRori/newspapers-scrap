# app.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import logging_config
import json
import os
import re
import logging
from threading import Thread
from queue import Queue, Empty

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from models.process_tracker import ProcessTracker

# Configure logging
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'newspaper-search-secret'
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = False

# Initialize Flask-SocketIO with our Flask app
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode="threading"
)

# Initialize the process tracker
process_tracker = ProcessTracker()
process_tracker.set_app(app)  # Pass the Flask app reference

# Make process_tracker and socketio available as app attributes
app.process_tracker = process_tracker
app.socketio = socketio

# Add Socket.IO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info(f"Client connected")
    socketio.emit('connection_response', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"Client disconnected")

def emit_output():
    """Thread function to handle process output and emit events to the client"""
    # Create a copy of the app for this thread
    app_for_thread = app._get_current_object()
    
    # Create application context for this thread
    with app_for_thread.app_context():
        logger.info("Started emit_output thread with application context")
        
        while process_tracker.running:
            if process_tracker.process and process_tracker.process.poll() is not None:  # Check if current process has finished
                process_tracker.current_task_index += 1
                logger.info(f"Process completed, moving to task {process_tracker.current_task_index}")

                # If all tasks are completed
                if process_tracker.current_task_index >= len(process_tracker.search_tasks):
                    process_tracker.emit_socketio_event('search_complete', {'status': 'completed'})
                    logger.info("All search tasks completed")
                    process_tracker.running = False
                    socketio.sleep(0.1)
                    break

                # Start the next task
                next_cmd = process_tracker.search_tasks[process_tracker.current_task_index]
                current_period = process_tracker.search_periods[process_tracker.current_task_index]
                logger.info(f"Starting next task: {next_cmd}")

                # Emit info about the next task
                process_tracker.emit_socketio_event('task_change', {
                    'current_task': process_tracker.current_task_index + 1,
                    'total_tasks': len(process_tracker.search_tasks),
                    'period': current_period
                })

                # Calculate overall progress
                overall_progress = int((process_tracker.current_task_index / len(process_tracker.search_tasks)) * 100)

                # Start the next process
                process_tracker.start_process(next_cmd, current_period)
                logger.info(f"Started process for task {process_tracker.current_task_index}")

                # Update progress
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
                            process_tracker.emit_socketio_event('log_message', {'message': line})
                            socketio.sleep(0)
                    except Empty:
                        socketio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in emit_output: {str(e)}")
                socketio.sleep(0.1)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    from routes import register_blueprints
    register_blueprints(app)

    # Start the Flask server with SocketIO
    socketio.run(app, host='127.0.0.1', port=8008, debug=True, use_reloader=False)