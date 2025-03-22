# app.py
import logging_config
import json
import os
import re
import sys
import logging
import subprocess
from logging.handlers import RotatingFileHandler

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from queue import Queue, Empty
from threading import Thread



logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'newspaper-search-secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


def stream_process(process, queue):
    article_found_pattern = re.compile(r'Processing article (\d+)/(\d+)')
    total_pattern = re.compile(r'Processing complete\. (\d+) articles processed')
    processed_pattern = re.compile(r'Processed content saved to: (.*?)\.json')

    try:
        for line in iter(process.stdout.readline, ''):
            if isinstance(line, bytes):
                line = line.decode('utf-8')
            line = line.strip()
            try:
                print(line)  # Show logs in the Flask terminal
            except UnicodeEncodeError:
                print(line.encode('utf-8', errors='replace').decode('ascii',
                                                                    errors='replace'))  # Safely encode problematic characters
            processed_match = processed_pattern.search(line)
            if processed_match:
                json_path = processed_match.group(1) + '.json'
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        article_data = json.load(f)
                        queue.put(f"Article: {article_data['title']}")
                        queue.put(f"Source: {article_data['newspaper']} ({article_data['date']})")
                        queue.put(f"URL: {article_data['url']}")
                        queue.put("---")
                except Exception as e:
                    queue.put(f"Error reading article data: {str(e)}")

            progress_match = article_found_pattern.search(line)
            if progress_match:
                current_article = int(progress_match.group(1))
                total_articles = int(progress_match.group(2))
                progress = int((current_article / total_articles) * 100)
                socketio.emit('progress', {
                    'value': progress,
                    'saved': current_article,
                    'total': total_articles
                })
                queue.put(f"Processing: {current_article}/{total_articles} articles ({progress}%)")

            complete_match = total_pattern.search(line)
            if complete_match:
                saved_articles = int(complete_match.group(1))
                queue.put(f"Completed: {saved_articles} articles processed")

    finally:
        process.stdout.close()
        queue.put("Search process completed")



@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/search', methods=['POST'])
def search():
    data = request.json

    # Build command arguments
    cmd = [sys.executable, 'scripts/run_search.py', data['query']]

    if data.get('newspapers'):
        cmd.extend(['--newspapers'] + data['newspapers'].split())
    if data.get('cantons'):
        cmd.extend(['--cantons'] + data['cantons'].split())
    if data.get('pages'):
        cmd.extend(['--pages', str(data['pages'])])
    if data.get('deq'):
        cmd.extend(['--deq', data['deq']])
    if data.get('yeq'):
        cmd.extend(['--yeq', data['yeq']])

    logger.info(f"Running command: {' '.join(cmd)}")

    # Create process with non-buffered output
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,  # Line buffered
        universal_newlines=True,
        encoding='utf-8',
        errors='replace'
    )

    # Create queue for output
    output_queue = Queue()

    # Start thread to read output
    thread = Thread(target=stream_process, args=(process, output_queue))
    thread.daemon = True
    thread.start()

    def emit_output():
        while True:
            # Check if process is still running
            if process.poll() is not None and output_queue.empty():
                logger.info("Process completed, emitting search_complete")
                socketio.emit('search_complete', {'status': 'completed'})
                socketio.sleep(0.1)  # Give some time for the last messages
                break

            # Get output from queue
            try:
                # Set a short timeout so we can check process status frequently
                line = output_queue.get(timeout=0.1)
                if line:
                    logger.debug(f"Emitting log message: {line}")
                    socketio.emit('log_message', {'message': line})
                    socketio.sleep(0)  # Yield to allow event to be sent immediately
            except Empty:
                socketio.sleep(0.1)  # Small delay when no output to avoid CPU spinning
                continue
            except Exception as e:
                logger.error(f"Error in emit_output: {str(e)}")
                socketio.sleep(0.1)
                continue

    socketio.start_background_task(emit_output)
    return jsonify({'status': 'started'})


if __name__ == '__main__':
    socketio.run(app, debug=True)
