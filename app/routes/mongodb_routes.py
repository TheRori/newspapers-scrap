import os
import glob
import json
import yaml
from pathlib import Path
from flask import Blueprint, jsonify, current_app, request, render_template
from pymongo import MongoClient
from flask_socketio import emit

mongodb_bp = Blueprint('mongodb', __name__)

def get_mongo_config():
    """Load MongoDB configuration from secrets.yaml"""
    yaml_path = Path(__file__).resolve().parent.parent.parent / "newspapers_scrap" / "config" / "secrets.yaml"
    with open(yaml_path, 'r') as f:
        secrets = yaml.safe_load(f)
    
    return secrets.get("mongodb", {})

@mongodb_bp.route('/mongodb')
def mongodb_page():
    """Render the MongoDB operations page"""
    return render_template('mongodb.html')

@mongodb_bp.route('/api/mongodb/push', methods=['POST'])
def push_to_mongodb():
    """Push processed articles to MongoDB"""
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
    
    # Process each file
    for i, file_path in enumerate(json_files):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                article = json.load(f)
                # Insert into MongoDB (upsert by 'id' if needed)
                collection.update_one({'id': article['id']}, {'$set': article}, upsert=True)
                inserted += 1
                
                # Update progress every 10 files or at the end
                if i % 10 == 0 or i == total_files - 1:
                    progress = {
                        'current': i + 1,
                        'total': total_files,
                        'percentage': round((i + 1) / total_files * 100, 1),
                        'inserted': inserted
                    }
                    current_app.socketio.emit('mongodb_progress', progress)
            except Exception as e:
                current_app.logger.error(f"Error processing file {file_path}: {str(e)}")
    
    # Return final result
    result = {
        'success': True,
        'message': f"Inserted or updated {inserted} articles into MongoDB",
        'inserted': inserted,
        'total': total_files
    }
    
    return jsonify(result)

@mongodb_bp.route('/api/mongodb/status', methods=['GET'])
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
