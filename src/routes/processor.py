from flask import Blueprint, request, jsonify, current_app
import os
import json
import subprocess
import sys
import glob
from pathlib import Path
import logging
import threading
import time

# Import functions from the processor script
from src.tv_movie_processor import (
    search_for_vo_and_es_files,
    process_file_pair,
    ensure_mkv_format,
    transfer_audio_track,
    validate_and_cleanup,
)

MEDIA_ROOT = '/mnt/nfs/media/test_downloads'

processor_bp = Blueprint('processor', __name__)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Store active jobs and their status
active_jobs = {}

def is_path_allowed(path):
    """
    Check if the path is within the allowed media root directory.
    
    Args:
        path (str): Path to check
        
    Returns:
        bool: True if path is allowed, False otherwise
    """
    # Normalize paths for comparison
    norm_path = os.path.normpath(path)
    norm_media_root = os.path.normpath(MEDIA_ROOT)
    
    # Check if path is the media root or a subdirectory
    return norm_path == norm_media_root or norm_path.startswith(norm_media_root + os.sep)

@processor_bp.route('/api/list-directories', methods=['GET'])
def list_directories():
    """List available directories for selection"""
    # Default to media root if no path provided or path is not allowed
    requested_path = request.args.get('path', MEDIA_ROOT)
    
    # Ensure the media root exists
    if not os.path.exists(MEDIA_ROOT):
        try:
            os.makedirs(MEDIA_ROOT, exist_ok=True)
            logger.info(f"Created media root directory: {MEDIA_ROOT}")
        except Exception as e:
            logger.error(f"Failed to create media root directory: {e}")
            return jsonify({
                'error': f"Failed to create media root directory: {str(e)}",
                'current_path': MEDIA_ROOT,
                'parent_path': MEDIA_ROOT,
                'items': []
            }), 500
    
    # If requested path is not allowed, default to media root
    if not is_path_allowed(requested_path):
        logger.warning(f"Attempted to access restricted path: {requested_path}")
        requested_path = MEDIA_ROOT
    
    try:
        # Ensure the path exists and is a directory
        if not os.path.isdir(requested_path):
            return jsonify({
                'error': 'Invalid directory path',
                'current_path': MEDIA_ROOT,
                'parent_path': MEDIA_ROOT,
                'items': []
            }), 400
        
        # Get directories and files
        items = []
        for item in os.listdir(requested_path):
            full_path = os.path.join(requested_path, item)
            item_type = 'directory' if os.path.isdir(full_path) else 'file'
            
            # Only include video files
            if item_type == 'file' and not item.lower().endswith(('.mkv', '.mp4', '.avi')):
                continue
                
            items.append({
                'name': item,
                'path': full_path,
                'type': item_type
            })
        
        # Sort directories first, then files
        items.sort(key=lambda x: (0 if x['type'] == 'directory' else 1, x['name']))
        
        # Determine parent path, but don't allow going above media root
        parent_path = os.path.dirname(requested_path)
        if not is_path_allowed(parent_path):
            parent_path = requested_path
        
        return jsonify({
            'current_path': requested_path,
            'parent_path': parent_path,
            'items': items,
            'media_root': MEDIA_ROOT
        })
    except Exception as e:
        logger.error(f"Error listing directories: {e}")
        return jsonify({
            'error': str(e),
            'current_path': MEDIA_ROOT,
            'parent_path': MEDIA_ROOT,
            'items': [],
            'media_root': MEDIA_ROOT
        }), 500

@processor_bp.route('/api/search-files', methods=['POST'])
def search_files():
    """Search for VO and ES files based on criteria"""
    data = request.json
    series = data.get('series')
    season = data.get('season')
    if season and season.isdigit():
        season = int(season)
    else:
        season = None
    
    search_paths = data.get('paths', [])
    
    # Validate search paths
    valid_paths = []
    for path in search_paths:
        if is_path_allowed(path):
            valid_paths.append(path)
        else:
            logger.warning(f"Skipping restricted path: {path}")
    
    if not valid_paths:
        return jsonify({
            'error': 'No valid search paths provided. All paths must be within the media root directory.',
            'media_root': MEDIA_ROOT
        }), 400
    
    try:
        matched_files = search_for_vo_and_es_files(series, season, valid_paths)
        
        # Convert to a format suitable for the frontend
        result = []
        for key, files in matched_files.items():
            result.append({
                'key': key,
                'vo_file': files['vo'],
                'es_file': files['es']
            })
        
        return jsonify({
            'matches': result,
            'count': len(result),
            'media_root': MEDIA_ROOT
        })
    except Exception as e:
        logger.error(f"Error searching for files: {e}")
        return jsonify({
            'error': str(e),
            'media_root': MEDIA_ROOT
        }), 500

def process_files_task(job_id, mode, file_pairs):
    """Background task to process files"""
    active_jobs[job_id]['status'] = 'processing'
    active_jobs[job_id]['progress'] = 0
    active_jobs[job_id]['processed'] = 0
    active_jobs[job_id]['total'] = len(file_pairs)
    active_jobs[job_id]['results'] = []
    
    try:
        for i, pair in enumerate(file_pairs):
            vo_file = pair.get('vo_file')
            es_file = pair.get('es_file')
            
            # Validate paths
            if not vo_file or not es_file:
                active_jobs[job_id]['results'].append({
                    'vo_file': vo_file,
                    'es_file': es_file,
                    'success': False,
                    'message': 'Missing VO or ES file'
                })
                continue
            
            if not is_path_allowed(vo_file) or not is_path_allowed(es_file):
                active_jobs[job_id]['results'].append({
                    'vo_file': vo_file,
                    'es_file': es_file,
                    'success': False,
                    'message': 'Files must be within the media root directory'
                })
                continue
            
            # Process the file pair
            success = process_file_pair(vo_file, es_file)
            
            active_jobs[job_id]['processed'] += 1
            active_jobs[job_id]['progress'] = (active_jobs[job_id]['processed'] / active_jobs[job_id]['total']) * 100
            
            active_jobs[job_id]['results'].append({
                'vo_file': vo_file,
                'es_file': es_file,
                'success': success,
                'message': 'Successfully processed' if success else 'Failed to process'
            })
    except Exception as e:
        logger.error(f"Error in processing task: {e}")
        active_jobs[job_id]['error'] = str(e)
    
    active_jobs[job_id]['status'] = 'completed'
    active_jobs[job_id]['end_time'] = time.time()

@processor_bp.route('/api/process-files', methods=['POST'])
def process_files():
    """Process selected files"""
    data = request.json
    mode = data.get('mode', 'movie')  # 'movie' or 'tv'
    file_pairs = data.get('file_pairs', [])
    
    if not file_pairs:
        return jsonify({'error': 'No file pairs provided'}), 400
    
    # Validate all file paths
    for pair in file_pairs:
        vo_file = pair.get('vo_file')
        es_file = pair.get('es_file')
        
        if not vo_file or not es_file:
            return jsonify({'error': 'Missing VO or ES file in one or more pairs'}), 400
        
        if not is_path_allowed(vo_file) or not is_path_allowed(es_file):
            return jsonify({
                'error': 'All files must be within the media root directory',
                'media_root': MEDIA_ROOT
            }), 400
    
    # Create a job ID
    job_id = str(int(time.time()))
    
    # Initialize job status
    active_jobs[job_id] = {
        'id': job_id,
        'mode': mode,
        'status': 'starting',
        'start_time': time.time(),
        'file_count': len(file_pairs),
        'progress': 0
    }
    
    # Start processing in a background thread
    thread = threading.Thread(
        target=process_files_task,
        args=(job_id, mode, file_pairs)
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'job_id': job_id,
        'status': 'started',
        'message': f'Processing {len(file_pairs)} file pairs'
    })

@processor_bp.route('/api/job-status/<job_id>', methods=['GET'])
def job_status(job_id):
    """Get the status of a processing job"""
    if job_id not in active_jobs:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify(active_jobs[job_id])

@processor_bp.route('/api/active-jobs', methods=['GET'])
def list_jobs():
    """List all active jobs"""
    return jsonify({
        'jobs': list(active_jobs.values()),
        'media_root': MEDIA_ROOT
    })

@processor_bp.route('/api/media-root', methods=['GET'])
def get_media_root():
    """Get the media root directory"""
    # Check if media root exists
    exists = os.path.exists(MEDIA_ROOT)
    writable = os.access(MEDIA_ROOT, os.W_OK) if exists else False
    
    return jsonify({
        'media_root': MEDIA_ROOT,
        'exists': exists,
        'writable': writable
    })
