# app.py
from pathlib import Path

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
                        queue.put(f"Article: {article_data.get('title', 'No title')}")
                        queue.put(
                            f"Source: {article_data.get('newspaper', 'Unknown')} ({article_data.get('date', 'Unknown')})")
                        queue.put(f"URL: {article_data.get('url', 'No URL')}")
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

    finally:
        process.stdout.close()
        queue.put("Search process completed")


import os
from flask import send_from_directory, abort


# Add this route to browse topics and files
@app.route('/browse')
def browse_topics():
    """Display the topics directory structure with rich metadata and filtering"""
    topics_dir = Path('data') / 'by_topic'

    # Get filter parameters
    filter_word = request.args.get('filter_word', '').strip().lower()
    filter_date_from = request.args.get('date_from', '')
    filter_date_to = request.args.get('date_to', '')

    # Get word count filter parameters
    min_words = request.args.get('min_words', '')
    max_words = request.args.get('max_words', '')

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
                'files': []
            }

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

                            if include_file:
                                file_info = {
                                    'filename': file,
                                    'title': file_data.get('title', 'No title'),
                                    'date': file_data.get('date', 'Unknown date'),
                                    'word_count': file_data.get('word_count', 0),
                                    'newspaper': file_data.get('newspaper', 'Unknown source'),
                                    'canton': file_data.get('canton', None)
                                }
                                topic_info['files'].append(file_info)
                    except Exception as e:
                        logger.error(f"Error reading file {file_path}: {str(e)}")
                        if not filter_word and not filter_date_from and not filter_date_to and min_words is None and max_words is None:
                            # Only add error files if no filters are active
                            topic_info['files'].append({
                                'filename': file,
                                'title': 'Error reading file',
                                'error': str(e)
                            })
            topics.append(topic_info)

    return render_template(
        'browse.html',
        topics=topics,
        filter_word=filter_word,
        date_from=filter_date_from,
        date_to=filter_date_to,
        min_words=min_words or '',
        max_words=max_words or ''
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
                from newspapers_scrap.utils.diff_generator import generate_html_diff
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
    # Extract base_id more reliably using pattern matching
    # The pattern for base_id is "article_YYYYMMDD_newspapername"
    match = re.match(r'(article_\d{8}_[^_]+)(_.*)?', version_id)

    if not match:
        logger.error(f"Invalid version_id format: {version_id}")
        abort(404)

    base_id = match.group(1)
    logger.debug(f"base_id: {base_id}")

    # First check if this exact base_id exists
    version_path = Path('data') / 'processed' / 'versions' / base_id / f"{version_id}.json"

    # If not found, try to find the actual directory by pattern
    if not version_path.exists():
        versions_dir = Path('data') / 'processed' / 'versions'
        possible_dirs = list(versions_dir.glob(f"article_*_{version_id.split('_')[2]}*"))

        if possible_dirs:
            # Use the first matching directory
            base_id = possible_dirs[0].name
            version_path = possible_dirs[0] / f"{version_id}.json"
        else:
            abort(404)

    if not version_path.exists():
        abort(404)

    try:
        with open(version_path, 'r', encoding='utf-8') as f:
            full_content = json.load(f)

        # The correct base_id should be in the JSON file itself
        if 'base_id' in full_content:
            base_id = full_content['base_id']

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
            from newspapers_scrap.utils.diff_generator import generate_html_diff
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
        for root, dirs, files in os.walk(Path('data') / 'by_topic'):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_data = json.load(f)
                        if file_data.get('base_id') == base_id:
                            topic = os.path.basename(root)
                            break
                except:
                    continue
            if topic != "unknown":
                break

        return render_template('view_file.html', filename=f"{version_id}.json", topic=topic, **metadata)

    except Exception as e:
        logger.error(f"Error reading version file {version_path}: {str(e)}")
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


@app.route('/api/search', methods=['POST'])
@app.route('/api/search', methods=['POST'])
def search():
    data = request.json

    logger.debug(f"Received search request: {data}")

    # Build command arguments
    cmd = [sys.executable, 'scripts/run_search.py', data['query']]

    if data.get('newspapers'):
        cmd.extend(['--newspapers'] + data['newspapers'].split())
    if data.get('cantons'):
        cmd.extend(['--cantons'] + data['cantons'].split())
    if data.get('searches'):
        cmd.extend(['--sch', str(data['searches'])])
    if data.get('deq'):
        cmd.extend(['--deq', data['deq']])
    if data.get('yeq'):
        cmd.extend(['--yeq', data['yeq']])

    # Add spell correction parameters
    correction_method = data.get('correction_method', 'none')
    if correction_method and correction_method != 'none':
        cmd.extend(['--correction', correction_method])
        # Add language parameter if spell correction is enabled
        language = data.get('language', 'fr')
        cmd.extend(['--language', language])
    else:
        cmd.extend(['--no-correction'])  # Explicitly disable correction

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
    socketio.run(app, debug=True)
