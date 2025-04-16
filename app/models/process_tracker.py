import logging
import os
import re
import subprocess
from queue import Queue, Empty
from threading import Thread
import json
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

class ProcessTracker:
    def __init__(self,socketio=None):
        self.process = None
        self.current_task_index = 0
        self.search_tasks = []
        self.search_periods = []
        self.output_queue = None
        self.running = False
        self.socketio = socketio

    def start_process(self, cmd, current_period=None):
        """Start a new process with the given command"""
        # Add environment variable to use a different log file for subprocesses
        env = os.environ.copy()
        env['SUBPROCESS_LOG'] = '1'

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace',
            env=env  # Pass the modified environment
        )

        self.process = process
        self.output_queue = Queue()

        thread = Thread(target=self.stream_process, args=(process, self.output_queue))
        thread.daemon = True
        thread.start()

        return process

    def stream_process(self, process, queue):
        article_found_pattern = re.compile(r'Processing article (\d+)/(\d+)')
        total_pattern = re.compile(r'Processing complete\. (\d+) articles processed')
        processed_pattern = re.compile(r'Version saved to: (.*?)\.json')
        results_found_pattern = re.compile(r'Found (\d+) total results for query .*, processing up to (\d+)')
        date_range_pattern = re.compile(r'Searching for period: (\d{4})-(\d{4}|\d{4})')
        scope_pattern = re.compile(r'SEARCH_SCOPE: total_years=(\d+)')
        year_progress_pattern = re.compile(r'YEAR_PROGRESS: current_year=(\d+) total_years=(\d+)')
        total_years = 1
        current_year = 0

        try:
            # Get current period directly from self
            current_period = self.search_periods[self.current_task_index] if self.search_periods else "Default"

            # Calculate base progress percentage for completed tasks
            base_progress = (self.current_task_index / len(self.search_tasks)) * 100 if self.search_tasks else 0
            # Calculate how much this task contributes to the total progress
            task_weight = 1 / len(self.search_tasks) * 100 if self.search_tasks else 100

            for line in iter(process.stdout.readline, ''):
                scope_match = scope_pattern.search(line)
                if scope_match:
                    total_years = int(scope_match.group(1))
                    self.socketio.emit('search_scope', {
                        'total_years': total_years
                    })
                    continue
                if isinstance(line, bytes):
                    line = line.decode('utf-8')
                line = line.strip()
                try:
                    print(line)  # Show logs in the Flask terminal
                except UnicodeEncodeError:
                    print(line.encode('utf-8', errors='replace').decode('ascii',
                                                                        errors='replace'))  # Safely encode problematic characters
                year_match = year_progress_pattern.search(line)
                if year_match:
                    current_year = int(year_match.group(1))
                    total_years = int(year_match.group(2))

                    # Emit cumulative progress information
                    self.socketio.emit('year_progress', {
                        'current_year': current_year,
                        'total_years': total_years,
                        'percentage': int((current_year / total_years) * 100)
                    })
                    continue
                # Check if line contains information about the date range being searched
                date_range_match = date_range_pattern.search(line)
                if date_range_match:
                    current_period = f"{date_range_match.group(1)}-{date_range_match.group(2)}"
                    queue.put(f"Searching period: {current_period}")
                    self.socketio.emit('period_update', {'period': current_period})

                # Check if line contains information about total results found
                results_found_match = results_found_pattern.search(line)
                if results_found_match:
                    total_results = int(results_found_match.group(1))
                    max_articles = int(results_found_match.group(2))
                    queue.put(f"Found {total_results} total results, processing up to {max_articles}")

                    # Emit results count information
                    self.socketio.emit('results_count', {
                        'total': total_results,
                        'max_articles': max_articles,
                        'period': current_period
                    })

                # When an article is saved, extract path and add to queue
                processed_match = processed_pattern.search(line)
                if processed_match:
                    json_path = processed_match.group(1) + '.json'
                    # Send this message to queue to display in web app
                    queue.put(f"Article saved to: {json_path}")

                    # Also emit using socketio for immediate display
                    self.socketio.emit('article_saved', {
                        'path': json_path,
                        'period': current_period
                    })

                    try:
                        with open(json_path, 'r', encoding='utf-8') as f:
                            article_data = json.load(f)
                            queue.put(f"Article: {article_data.get('title', 'No title')}")
                            queue.put(
                                f"Source: {article_data.get('newspaper', 'Unknown')} ({article_data.get('date', 'Unknown')})")
                            queue.put(f"URL: {article_data.get('url', 'No URL')}")
                            queue.put("---")
                    except Exception as e:
                        queue.put(f"Error reading article data: {str(e)}")

                # Process progress information
                progress_match = article_found_pattern.search(line)
                if progress_match:
                    current_article = int(progress_match.group(1))
                    total_articles = int(progress_match.group(2))

                    # Task-specific progress (for current year/period)
                    task_progress = int((current_article / total_articles) * 100)

                    # Calculate overall progress (base progress + weighted current task progress)
                    current_task_contribution = (task_progress / 100) * task_weight
                    overall_progress = int(base_progress + current_task_contribution)

                    # Add to queue for display in logs
                    queue.put(f"Processing: {current_article}/{total_articles} articles ({task_progress}%)")

                    # Update task progress through socketio
                    self.socketio.emit('progress', {
                        'value': task_progress,
                        'saved': current_article,
                        'total': total_articles,
                        'period': current_period
                    })

                    # Update overall progress
                    self.socketio.emit('overall_progress', {
                        'value': overall_progress,
                        'current_task': self.current_task_index + 1,
                        'total_tasks': len(self.search_tasks)
                    })

                complete_match = total_pattern.search(line)
                if complete_match:
                    saved_articles = int(complete_match.group(1))
                    queue.put(f"Completed processing {saved_articles} articles for period {current_period}")

                    # When a task is complete, emit the updated overall progress
                    task_complete_progress = int(base_progress + task_weight)
                    self.socketio.emit('overall_progress', {
                        'value': task_complete_progress,
                        'current_task': self.current_task_index + 1,
                        'total_tasks': len(self.search_tasks)
                    })

        finally:
            process.stdout.close()
            queue.put("Search process completed")
