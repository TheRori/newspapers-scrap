# app.py
from pathlib import Path

import logging_config
import json
import os
import re
import psutil
import signal
from datetime import datetime
import sys
import logging
import subprocess
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from queue import Queue, Empty
from threading import Thread

from models.process_tracker import ProcessTracker
from routes import register_blueprints

logger = logging.getLogger(__name__)
current_process = None
current_scraper = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'newspaper-search-secret'
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = False
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Enregistrement des blueprints pour organiser le code
register_blueprints(app)

# Initialisation du traceur de processus
process_tracker = ProcessTracker(socketio=socketio)


def emit_output():
    global process_tracker

    while process_tracker.running:
        if process_tracker.process.poll() is not None:  # Check if current process has finished
            process_tracker.current_task_index += 1

            # If all tasks are done
            if process_tracker.current_task_index >= len(process_tracker.search_tasks):
                socketio.emit('search_complete', {'status': 'completed'})
                process_tracker.running = False
                socketio.sleep(0.1)
                break

            # Start next task
            next_cmd = process_tracker.search_tasks[process_tracker.current_task_index]
            current_period = process_tracker.search_periods[process_tracker.current_task_index]

            # Emit info about next task
            socketio.emit('task_change', {
                'current_task': process_tracker.current_task_index + 1,
                'total_tasks': len(process_tracker.search_tasks),
                'period': current_period
            })

            # Calculate overall progress (based on completed tasks)
            overall_progress = int((process_tracker.current_task_index / len(process_tracker.search_tasks)) * 100)

            # Start next process using the helper method
            process_tracker.start_process(next_cmd, current_period)

            # Update progress with the overall progress value
            socketio.emit('overall_progress', {
                'value': overall_progress,
                'current_task': process_tracker.current_task_index + 1,
                'total_tasks': len(process_tracker.search_tasks)
            })

            # Continue to process output
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
            logger.error(f"Error in emit_output: {str(e)}")
            socketio.sleep(0.1)


@app.route('/')
def index():
    return render_template('index.html')


if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False, port=8080)