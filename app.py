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

logger = logging.getLogger(__name__)
current_process = None
current_scraper = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'newspaper-search-secret'
app.config['DEBUG'] = True
app.config['TEMPLATES_AUTO_RELOAD'] = False
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


class ProcessTracker:
    def __init__(self):
        self.process = None
        self.current_task_index = 0
        self.search_tasks = []
        self.search_periods = []
        self.output_queue = None
        self.running = False

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
                    socketio.emit('search_scope', {
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
                    socketio.emit('year_progress', {
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
                    socketio.emit('period_update', {'period': current_period})

                # Check if line contains information about total results found
                results_found_match = results_found_pattern.search(line)
                if results_found_match:
                    total_results = int(results_found_match.group(1))
                    max_articles = int(results_found_match.group(2))
                    queue.put(f"Found {total_results} total results, processing up to {max_articles}")

                    # Emit results count information
                    socketio.emit('results_count', {
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
                    socketio.emit('article_saved', {
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
                    socketio.emit('progress', {
                        'value': task_progress,
                        'saved': current_article,
                        'total': total_articles,
                        'period': current_period
                    })

                    # Update overall progress
                    socketio.emit('overall_progress', {
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
                    socketio.emit('overall_progress', {
                        'value': task_complete_progress,
                        'current_task': self.current_task_index + 1,
                        'total_tasks': len(self.search_tasks)
                    })

        finally:
            process.stdout.close()
            queue.put("Search process completed")

process_tracker = ProcessTracker()


@app.route('/api/search', methods=['POST'])
def search():
    global process_tracker

    # Clear the previous state
    process_tracker.running = False
    if process_tracker.process and process_tracker.process.poll() is None:
        try:
            process_tracker.process.terminate()
        except:
            pass

    # Remove the stop signal file if it exists
    if os.path.exists('stop_signal.txt'):
        try:
            os.remove('stop_signal.txt')
            logger.info("Removed existing stop signal file")
        except Exception as e:
            logger.error(f"Error removing stop signal file: {str(e)}")

    data = request.json
    search_tasks = []  # List to store multiple search tasks
    search_periods = []  # Store human-readable periods for each task

    # Base command with common parameters
    base_cmd = [sys.executable, 'scripts/run_search.py', data['query']]

    # Add common parameters
    if data.get('newspapers'):
        base_cmd.extend(['--newspapers'] + data['newspapers'].split())
    if data.get('cantons'):
        base_cmd.extend(['--cantons'] + data['cantons'].split())
    if data.get('searches') and data.get('searches') != 'all':
        base_cmd.extend(['--max_articles', str(data['searches'])])
    logger.debug(f"start_from: {data.get('start_from')}")

    # Get start_from parameter value (UI value is 1-based, code uses 0-based)
    start_from = data.get('start_from', '0')
    try:
        start_from_value = int(start_from)
    except ValueError:
        logger.warning(f"Invalid start_from value: {start_from}, defaulting to 0")
        start_from_value = 0

    # Add correction parameters
    correction_method = data.get('correction_method', 'none')
    if correction_method and correction_method != 'none':
        base_cmd.extend(['--correction', correction_method])
    else:
        base_cmd.extend(['--no-correction'])

    # Handle year-by-year search
    start_year = data.get('start_year')
    end_year = data.get('end_year')

    if start_year and end_year:
        start_year = int(start_year)
        end_year = int(end_year)

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
        # For single search or all-time search, include start_from if needed
        if start_from_value > 0:
            base_cmd.extend(['--start_from', str(start_from_value - 1)])  # Convert to 0-based

        search_tasks.append(base_cmd)
        search_periods.append("Default")

    # Update the process tracker
    process_tracker.search_tasks = search_tasks
    process_tracker.search_periods = search_periods
    process_tracker.current_task_index = 0
    process_tracker.running = True

    # Send the total number of tasks to the client
    socketio.emit('search_started', {
        'total_tasks': len(search_tasks),
        'periods': search_periods
    })

    # Start the first task
    cmd = search_tasks[0]
    current_period = search_periods[0]

    # Start process using the tracker's method
    process_tracker.start_process(cmd, current_period)

    socketio.start_background_task(emit_output)

    return jsonify({
        'status': 'started',
        'tasks_count': len(search_tasks),
        'periods': search_periods
    })


def emit_output():
    global process_tracker

    while process_tracker.running:
        if process_tracker.process.poll() is not None:  # Check if the current process has finished
            process_tracker.current_task_index += 1

            # If all tasks are completed
            if process_tracker.current_task_index >= len(process_tracker.search_tasks):
                socketio.emit('search_complete', {'status': 'completed'})
                process_tracker.running = False
                socketio.sleep(0.1)
                break

            # Start the next task
            next_cmd = process_tracker.search_tasks[process_tracker.current_task_index]
            current_period = process_tracker.search_periods[process_tracker.current_task_index]

            # Emit information about the next task
            socketio.emit('task_change', {
                'current_task': process_tracker.current_task_index + 1,
                'total_tasks': len(process_tracker.search_tasks),
                'period': current_period
            })

            # Calculate overall progress (based on completed tasks)
            overall_progress = int((process_tracker.current_task_index / len(process_tracker.search_tasks)) * 100)

            # Start the next process using the helper method
            process_tracker.start_process(next_cmd, current_period)

            # Update progress with overall progress value
            socketio.emit('overall_progress', {
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
                        socketio.emit('log_message', {'message': line})
                        socketio.sleep(0)
                except Empty:
                    socketio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in emit_output: {str(e)}")
            socketio.sleep(0.1)


import os
from flask import send_from_directory, abort


@app.route('/api/correct/<topic>/<filename>', methods=['POST'])
def correct_file(topic, filename):
    """API endpoint to apply spelling correction to a file."""
    file_path = os.path.join('data', 'by_topic', topic, filename)

    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        return jsonify({'error': 'File not found'}), 404

    try:
        # Read the correction method from the request
        data = request.json
        correction_method = data.get('correction_method', 'symspell')

        # Load the article data
        with open(file_path, 'r', encoding='utf-8') as f:
            article_data = json.load(f)

        # Ensure original content is stored
        if 'original_content' not in article_data and 'content' in article_data:
            article_data['original_content'] = article_data['content']

        original_content = article_data.get('original_content', '')
        if not original_content:
            return jsonify({'error': 'No content available for correction'}), 400

        # Apply the selected correction method
        if correction_method == 'symspell':
            from newspapers_scrap.data_manager.ocr_cleaner.symspell_checker import SpellCorrector
            corrector = SpellCorrector(language='fr')
            corrected_text = corrector.correct_text_sym(original_content)
            article_data.update({
                'content': corrected_text,
                'spell_corrected': True,
                'correction_method': 'symspell'
            })
        elif correction_method == 'mistral':
            from newspapers_scrap.data_manager.ocr_cleaner.mistral_checker import correct_text_ai
            import tempfile

            # Use temporary files for Mistral correction
            with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as temp_in:
                temp_in.write(original_content)
                input_path = temp_in.name

            output_path = input_path + '_corrected'
            if correct_text_ai(input_path, output_path):
                with open(output_path, 'r', encoding='utf-8') as f:
                    corrected_text = f.read()
                article_data.update({
                    'content': corrected_text,
                    'spell_corrected': True,
                    'correction_method': 'mistral'
                })
                os.unlink(output_path)  # Clean up
            else:
                return jsonify({'error': 'Mistral correction failed'}), 500

            os.unlink(input_path)  # Clean up
        else:
            return jsonify({'error': 'Invalid correction method'}), 400

        # Update word count
        article_data['word_count'] = len(article_data['content'].split())

        # Save the updated file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(article_data, f, ensure_ascii=False, indent=4)

        # Create a new version of the article
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

        return jsonify({
            'success': True,
            'word_count': article_data['word_count'],
            'correction_method': correction_method
        })

    except Exception as e:
        logger.error(f"Error correcting file {file_path}: {str(e)}")
        return jsonify({'error': str(e)}), 500


# Add this route to browse topics and files
@app.route('/browse')
def browse_topics():
    """Display the topics directory structure with rich metadata and filtering"""
    topics_dir = Path('data') / 'by_topic'

    # Get filter parameters
    filter_word = request.args.get('filter_word', '').strip().lower()
    filter_date_from = request.args.get('date_from', '')
    filter_date_to = request.args.get('date_to', '')
    filter_canton = request.args.get('canton', '').strip()
    filter_newspaper = request.args.get('newspaper', '').strip().lower()

    # Get word count filter parameters
    min_words = request.args.get('min_words', '')
    max_words = request.args.get('max_words', '')

    # Get pagination parameters
    limit_per_topic = 5  # Default number of articles to show per topic
    show_all_topic = request.args.get('show_all_topic', '')  # Topic name to show all results

    # Convert to integers if present
    min_words = int(min_words) if min_words and min_words.isdigit() else None
    max_words = int(max_words) if max_words and max_words.isdigit() else None

    if not os.path.exists(topics_dir):
        return render_template('browse.html', error=f'Topics directory {topics_dir} not found', topics=[])

    topics = []
    for topic in sorted(os.listdir(topics_dir)):
        topic_path = os.path.join(topics_dir, topic)
        if os.path.isdir(topic_path):
            topic_info = {
                'name': topic,
                'files': [],
                'total_files': 0,
                'showing_all': topic == show_all_topic
            }

            matching_files = []
            for file in sorted(os.listdir(topic_path)):
                if file.endswith('.json'):
                    file_path = os.path.join(topic_path, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            file_data = json.load(f)

                            # Check if file matches the filter criteria
                            include_file = True

                            # Word filter (in title or content)
                            if filter_word:
                                title = file_data.get('title', '').lower()
                                content = file_data.get('content', '').lower()
                                if filter_word not in title and filter_word not in content:
                                    include_file = False

                            # Date range filter
                            if include_file and (filter_date_from or filter_date_to):
                                file_date = file_data.get('date', '')
                                if filter_date_from and file_date < filter_date_from:
                                    include_file = False
                                if filter_date_to and file_date > filter_date_to:
                                    include_file = False

                            # Word count filter
                            if include_file and (min_words is not None or max_words is not None):
                                word_count = file_data.get('word_count', 0)
                                if min_words is not None and word_count < min_words:
                                    include_file = False
                                if max_words is not None and word_count > max_words:
                                    include_file = False

                            # Canton filter
                            if include_file and filter_canton:
                                article_canton = file_data.get('canton', '')
                                if not article_canton or filter_canton.lower() != article_canton.lower():
                                    include_file = False

                            # Newspaper filter
                            if include_file and filter_newspaper:
                                article_newspaper = file_data.get('newspaper', '').lower()
                                if not article_newspaper or filter_newspaper not in article_newspaper:
                                    include_file = False

                            if include_file:
                                file_info = {
                                    'filename': file,
                                    'title': file_data.get('title', 'No title'),
                                    'date': file_data.get('date', 'Unknown date'),
                                    'word_count': file_data.get('word_count', 0),
                                    'newspaper': file_data.get('newspaper', 'Unknown source'),
                                    'canton': file_data.get('canton', None)
                                }
                                matching_files.append(file_info)
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {str(e)}")
                        if not filter_word and not filter_date_from and not filter_date_to and min_words is None and max_words is None:
                            # Only add error files if no filters are active
                            matching_files.append({
                                'filename': file,
                                'title': 'Error reading file',
                                'error': str(e)
                            })

            # Set total count of matching files
            topic_info['total_files'] = len(matching_files)

            # Apply limit unless showing all for this topic
            if topic == show_all_topic or len(matching_files) <= limit_per_topic:
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


@app.route('/topic/<topic_name>')
def topic_results(topic_name):
    """Display all articles for a specific topic with filtering"""
    topic_path = Path('data') / 'by_topic' / topic_name

    # Get filter parameters
    filter_word = request.args.get('filter_word', '').strip().lower()
    filter_date_from = request.args.get('date_from', '')
    filter_date_to = request.args.get('date_to', '')
    filter_canton = request.args.get('canton', '').strip()
    filter_newspaper = request.args.get('newspaper', '').strip().lower()
    min_words = request.args.get('min_words', '')
    max_words = request.args.get('max_words', '')

    # Convert to integers if present
    min_words = int(min_words) if min_words and min_words.isdigit() else None
    max_words = int(max_words) if max_words and max_words.isdigit() else None

    if not topic_path.exists() or not topic_path.is_dir():
        return render_template('topic_results.html', error=f'Topic {topic_name} not found',
                               topic_name=topic_name, files=[])

    files = []
    for file in sorted(os.listdir(topic_path)):
        if file.endswith('.json'):
            file_path = os.path.join(topic_path, file)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_data = json.load(f)

                    # Check if file matches the filter criteria
                    include_file = True

                    # Word filter (in title or content)
                    if filter_word:
                        title = file_data.get('title', '').lower()
                        content = file_data.get('content', '').lower()
                        if filter_word not in title and filter_word not in content:
                            include_file = False

                    # Date range filter
                    if include_file and (filter_date_from or filter_date_to):
                        file_date = file_data.get('date', '')
                        if filter_date_from and file_date < filter_date_from:
                            include_file = False
                        if filter_date_to and file_date > filter_date_to:
                            include_file = False

                    # Word count filter
                    if include_file and (min_words is not None or max_words is not None):
                        word_count = file_data.get('word_count', 0)
                        if min_words is not None and word_count < min_words:
                            include_file = False
                        if max_words is not None and word_count > max_words:
                            include_file = False

                    # Canton filter
                    if include_file and filter_canton:
                        article_canton = file_data.get('canton', '')
                        if not article_canton or filter_canton.lower() != article_canton.lower():
                            include_file = False

                    # Newspaper filter
                    if include_file and filter_newspaper:
                        article_newspaper = file_data.get('newspaper', '').lower()
                        if not article_newspaper or filter_newspaper not in article_newspaper:
                            include_file = False

                    if include_file:
                        file_info = {
                            'filename': file,
                            'title': file_data.get('title', 'No title'),
                            'date': file_data.get('date', 'Unknown date'),
                            'word_count': file_data.get('word_count', 0),
                            'newspaper': file_data.get('newspaper', 'Unknown source'),
                            'canton': file_data.get('canton', None)
                        }
                        files.append(file_info)
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {str(e)}")
                if not filter_word and not filter_date_from and not filter_date_to and min_words is None and max_words is None:
                    # Only add error files if no filters are active
                    files.append({
                        'filename': file,
                        'title': 'Error reading file',
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


@app.route('/browse/<topic>/<filename>')
def view_file(topic, filename):
    """View a specific JSON file with complete metadata and versions"""
    file_path = os.path.join('data', 'by_topic', topic, filename)

    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        abort(404)

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_content = json.load(f)

            # Get base_id to find all versions
            base_id = full_content.get('base_id')
            current_version_id = full_content.get('id')

            # Get all versions of this article
            versions = []
            if base_id:
                versions = get_article_versions(base_id)

            # Get original content if spell corrections were made
            original_content = full_content.get('original_content')
            content = full_content.get('content', '')
            spell_corrected = full_content.get('spell_corrected', False)

            # Generate diff HTML if there are spell corrections
            diff_html = None
            show_diff = False
            if spell_corrected and original_content:
                from newspapers_scrap.utils import generate_html_diff
                diff_html = generate_html_diff(original_content, content)
                show_diff = True

            # Extract metadata for template
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
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return render_template('view_file.html', error=str(e), filename=filename, topic=topic)


@app.route('/version/<version_id>')
def view_version(version_id):
    """View a specific version of an article"""
    logger.debug(f"Requested version_id: {version_id}")

    # Check if this exact version_id exists anywhere
    versions_dir = Path('data') / 'processed' / 'versions'
    version_file = None
    base_dir = None

    # First, try to find the version file directly
    for base_dir_path in versions_dir.glob('article_*'):
        potential_file = base_dir_path / f"{version_id}.json"
        if potential_file.exists():
            version_file = potential_file
            base_dir = base_dir_path
            break

    # If not found, try to extract base_id parts from version_id
    if not version_file:
        # Extract date and newspaper from version_id
        parts = version_id.split('_')
        if len(parts) >= 3:
            date_part = parts[1]  # Should be YYYYMMDD
            newspaper_part = parts[2]  # Newspaper identifier

            # Look for matching base directories
            potential_dirs = list(versions_dir.glob(f"article_{date_part}_{newspaper_part}*"))
            if potential_dirs:
                base_dir = potential_dirs[0]
                version_file = base_dir / f"{version_id}.json"

                # If exact file doesn't exist, try to find any file with this version_id
                if not version_file.exists():
                    matching_files = list(base_dir.glob(f"*{version_id}*.json"))
                    if matching_files:
                        version_file = matching_files[0]

    if not version_file or not version_file.exists():
        logger.error(f"Could not find version file for: {version_id}")
        abort(404)

    base_id = base_dir.name if base_dir else None
    logger.debug(f"Found base_id: {base_id}")
    logger.debug(f"Using version file: {version_file}")

    try:
        with open(version_file, 'r', encoding='utf-8') as f:
            full_content = json.load(f)

        # Get the base_id from the content if available
        if 'base_id' in full_content:
            base_id = full_content['base_id']
            logger.debug(f"Updated base_id from file content: {base_id}")

        # Get all versions of this article
        versions = get_article_versions(base_id)

        # Get the raw text (original uncorrected content) from the raw file
        raw_path = full_content.get('raw_path')
        original_content = None

        if raw_path and os.path.exists(raw_path):
            try:
                with open(raw_path, 'r', encoding='utf-8') as f:
                    original_content = f.read()
                    logger.info(f"Loaded original content from raw file: {raw_path}")
            except Exception as e:
                logger.error(f"Failed to load original content from {raw_path}: {str(e)}")

        # If raw_path doesn't exist or couldn't be read, try to get from the file itself
        if not original_content:
            original_content = full_content.get('original_content')

        content = full_content.get('content', '')
        spell_corrected = full_content.get('spell_corrected', False)
        correction_method = full_content.get('correction_method', 'none')

        # Generate diff HTML if there are spell corrections
        diff_html = None
        show_diff = False

        if spell_corrected and original_content and correction_method != 'none':
            from newspapers_scrap.utils import generate_html_diff
            diff_html = generate_html_diff(original_content, content)
            show_diff = True
            logger.info("Generated diff HTML for version view")

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
            'correction_method': correction_method,
            'language': full_content.get('language', 'fr'),
            'diff_html': diff_html,
            'show_diff': show_diff,
            'versions': versions,
            'current_version_id': version_id,
            'base_id': base_id,
            'is_version_view': True
        }

        # Determine which topic this article belongs to
        topic = "unknown"
        topics_dir = Path('data') / 'by_topic'
        if topics_dir.exists():
            for topic_dir in topics_dir.iterdir():
                if topic_dir.is_dir():
                    for file_path in topic_dir.glob('*.json'):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                file_data = json.load(f)
                                if file_data.get('base_id') == base_id:
                                    topic = topic_dir.name
                                    break
                        except:
                            continue
                    if topic != "unknown":
                        break

        return render_template('view_file.html', filename=f"{version_id}.json", topic=topic, **metadata)

    except Exception as e:
        logger.error(f"Error reading version file {version_file}: {str(e)}")
        return render_template('view_file.html', error=str(e), filename=f"{version_id}.json", topic="unknown")


@app.route('/api/file/<topic>/<filename>')
def get_file_content(topic, filename):
    """API endpoint to get file content as JSON"""
    file_path = os.path.join('data', 'by_topic', topic, filename)

    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        return jsonify({'error': 'File not found'}), 404

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_content = json.load(f)
            # Extract only title and content
            result = {
                'title': full_content.get('title', ''),
                'content': full_content.get('content', '')
            }
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/')
def index():
    return render_template('index.html')


def get_article_versions(base_id):
    """
    Retrieve all versions of an article.

    Args:
        base_id: The base ID of the article.

    Returns:
        A list of dictionaries containing version metadata.
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
            logger.warning(f"Error reading version file {version_file}: {str(e)}")

    # Sort versions by creation date (newest first)
    versions.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return versions


if __name__ == '__main__':
    socketio.run(app, debug=True, use_reloader=False)
