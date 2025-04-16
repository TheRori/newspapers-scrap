# routes/article_routes.py
import logging
import os
import glob
import json
import yaml
from pathlib import Path
from flask import jsonify, request, render_template, current_app
from pymongo import MongoClient

from . import article_bp
from services.correction import process_article_correction

logger = logging.getLogger(__name__)


@article_bp.route('/api/correct/<topic>/<filename>', methods=['POST'])
def correct_file(topic, filename):
    """
    Point d'accès API pour appliquer une correction orthographique à un fichier.

    Accepte la méthode de correction via JSON et traite l'article
    en utilisant le service de correction approprié.
    """
    file_path = os.path.join('data', 'by_topic', topic, filename)

    # Vérification de l'existence du fichier
    if not os.path.exists(file_path) or not file_path.endswith('.json'):
        return jsonify({'error': 'Fichier introuvable'}), 404

    try:
        # Récupération de la méthode de correction depuis la requête
        data = request.json
        correction_method = data.get('correction_method', 'symspell')

        # Traitement de la correction via le service dédié
        success, error_message, result = process_article_correction(file_path, correction_method)

        if not success:
            return jsonify({'error': error_message}), 500

        return jsonify(result)

    except Exception as e:
        logger.error(f"Erreur lors de la correction du fichier {file_path}: {str(e)}")
        return jsonify({'error': str(e)}), 500


# MongoDB related routes
def get_mongo_config():
    """Load MongoDB configuration from secrets.yaml"""
    yaml_path = Path(__file__).resolve().parent.parent.parent / "newspapers_scrap" / "config" / "secrets.yaml"
    with open(yaml_path, 'r') as f:
        secrets = yaml.safe_load(f)
    
    return secrets.get("mongodb", {})

@article_bp.route('/mongodb')
def mongodb_page():
    """Render the MongoDB operations page"""
    return render_template('mongodb.html')

@article_bp.route('/api/mongodb/push', methods=['POST'])
def push_to_mongodb():
    """Push processed articles to MongoDB"""
    # Get request parameters
    data = request.get_json(silent=True) or {}
    only_new = data.get('onlyNew', False)
    
    # Get MongoDB configuration
    mongo_conf = get_mongo_config()
    
    # MongoDB connection
    client = MongoClient(mongo_conf.get("uri"))
    db = client[mongo_conf.get("database", "articles")]
    collection = db[mongo_conf.get("collection", "press_processed")]
    
    # Directory with processed articles
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "processed"
    
    # Find all JSON files in processed directory
    json_files = glob.glob(str(data_dir / "*.json"))
    total_files = len(json_files)
    
    # Initialize counters
    inserted = 0
    skipped = 0
    
    # If only pushing new articles, first get all existing article IDs from MongoDB
    existing_ids = set()
    if only_new:
        # Emit status update
        current_app.socketio.emit('mongodb_progress', {
            'status': 'Fetching existing article IDs from MongoDB...',
            'current': 0,
            'total': total_files,
            'percentage': 0,
            'inserted': 0,
            'skipped': 0
        })
        
        # Get all existing article IDs (this is much faster than checking one by one)
        existing_cursor = collection.find({}, {'id': 1, '_id': 0})
        for doc in existing_cursor:
            if 'id' in doc:
                existing_ids.add(doc['id'])
        
        # Emit status update
        current_app.socketio.emit('mongodb_progress', {
            'status': f'Found {len(existing_ids)} existing articles in MongoDB',
            'current': 0,
            'total': total_files,
            'percentage': 0,
            'inserted': 0,
            'skipped': 0
        })
    
    # Process each file
    for i, file_path in enumerate(json_files):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                article = json.load(f)
                article_id = article['id']
                
                # Check if article exists in MongoDB
                if only_new and article_id in existing_ids:
                    skipped += 1
                else:
                    # Insert into MongoDB (upsert by 'id' if needed)
                    collection.update_one({'id': article_id}, {'$set': article}, upsert=True)
                    inserted += 1
                
                # Update progress every 10 files or at the end
                if i % 10 == 0 or i == total_files - 1:
                    progress = {
                        'status': 'Processing articles...',
                        'current': i + 1,
                        'total': total_files,
                        'percentage': round((i + 1) / total_files * 100, 1),
                        'inserted': inserted,
                        'skipped': skipped
                    }
                    current_app.socketio.emit('mongodb_progress', progress)
        except Exception as e:
            current_app.logger.error(f"Error processing file {file_path}: {str(e)}")
    
    # Return final result
    result = {
        'success': True,
        'message': f"Processed {total_files} articles: {inserted} inserted/updated, {skipped} skipped",
        'inserted': inserted,
        'skipped': skipped,
        'total': total_files
    }
    
    return jsonify(result)

@article_bp.route('/api/mongodb/status', methods=['GET'])
def mongodb_status():
    """Get MongoDB connection status"""
    try:
        # Get MongoDB configuration
        mongo_conf = get_mongo_config()
        
        # Test MongoDB connection
        client = MongoClient(mongo_conf.get("uri"), serverSelectionTimeoutMS=5000)
        client.admin.command('ping')
        
        # Get database and collection info
        db_name = mongo_conf.get("database", "articles")
        collection_name = mongo_conf.get("collection", "press_processed")
        
        # Count documents if connected
        db = client[db_name]
        collection = db[collection_name]
        count = collection.count_documents({})
        
        return jsonify({
            'connected': True,
            'database': db_name,
            'collection': collection_name,
            'document_count': count
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'error': str(e)
        })