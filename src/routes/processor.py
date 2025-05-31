#!/usr/bin/env python3
"""
TV Show and Movie Processor

This script automates the processing of TV shows and movies downloaded in two versions:
original version (VO) and Spanish dubbed version (ES). It retains only the original video file
while adding the Spanish audio track as an additional track, and then deletes the dubbed version.

Requirements:
- ffmpeg must be installed
"""

import os
import sys
import re
import subprocess
import logging
import argparse
from pathlib import Path
import shutil
import glob
import difflib
from collections import defaultdict
from flask import current_app

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def get_media_root():
    """
    Get the media root directory from the Flask app config.
    
    Returns:
        str: Path to the media root directory
    """
    try:
        # Get from Flask app config
        from flask import current_app
        if current_app:
            return current_app.config.get('MEDIA_ROOT')
    except (ImportError, RuntimeError):
        # Not in Flask context or Flask not available
        pass
    
    # Fall back to environment variable for CLI usage
    return os.environ.get('MEDIA_ROOT', '/mnt/nfs/media')

def setup_argument_parser():
    """
    Set up command line argument parser for the script.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description='Process TV shows and movies to combine original and Spanish audio tracks.'
    )
    
    # Add subparsers for different modes
    subparsers = parser.add_subparsers(dest='mode', help='Operation mode')
    
    # Full process mode
    full_parser = subparsers.add_parser('full', help='Run the full process')
    full_parser.add_argument('--series', help='Series name')
    full_parser.add_argument('--season', type=int, help='Season number')
    full_parser.add_argument('--paths', nargs='+', required=True, help='Search paths for media files')
    full_parser.add_argument('--destination', help='Destination path for output files (default: same as input)')
    
    # Individual step modes
    search_parser = subparsers.add_parser('search', help='Search for VO and ES files')
    search_parser.add_argument('--series', help='Series name')
    search_parser.add_argument('--season', type=int, help='Season number')
    search_parser.add_argument('--paths', nargs='+', required=True, help='Search paths for media files')
    
    normalize_parser = subparsers.add_parser('normalize', help='Normalize and clean filenames')
    normalize_parser.add_argument('--files', nargs='+', required=True, help='Files to normalize')
    
    convert_parser = subparsers.add_parser('convert', help='Convert files to MKV format')
    convert_parser.add_argument('--files', nargs='+', required=True, help='Files to convert')
    
    merge_parser = subparsers.add_parser('merge', help='Merge ES audio into VO file')
    merge_parser.add_argument('--vo', required=True, help='Original version file')
    merge_parser.add_argument('--es', required=True, help='Spanish dubbed file')
    merge_parser.add_argument('--destination', help='Destination path for output file (default: same as input)')
    
    cleanup_parser = subparsers.add_parser('cleanup', help='Validate and cleanup files')
    cleanup_parser.add_argument('--files', nargs='+', required=True, help='Files to validate and cleanup')
    
    return parser

def gather_user_inputs():
    """
    Parse command line arguments and gather user inputs.
    
    Returns:
        argparse.Namespace: Parsed command line arguments
    """
    parser = setup_argument_parser()
    args = parser.parse_args()
    
    if not args.mode:
        parser.print_help()
        sys.exit(1)
    
    logger.info(f"Running in {args.mode} mode")
    return args

def check_dependencies():
    """
    Check if required dependencies are installed.
    
    Returns:
        bool: True if all dependencies are installed, False otherwise
    """
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        logger.info("ffmpeg is installed")
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("ffmpeg is not installed. Please install it before running this script.")
        return False

def normalize_filename(filename):
    """
    Normalize and clean a filename, replacing spaces and special characters with periods.
    
    Args:
        filename (str): Original filename
    
    Returns:
        str: Normalized filename
    """
    # Extract base name without extension
    base_name = os.path.splitext(os.path.basename(filename))[0]
    extension = os.path.splitext(filename)[1].lower()
    
    # Replace spaces, dashes, and underscores with periods
    normalized = re.sub(r'[ _-]+', '.', base_name)
    
    # Remove other special characters
    normalized = re.sub(r'[^\w.]', '', normalized)
    
    # Replace multiple consecutive periods with a single period
    normalized = re.sub(r'\.+', '.', normalized)
    
    # Remove leading and trailing periods
    normalized = normalized.strip('.')
    
    return normalized + extension

def extract_episode_info(filename):
    """
    Extract episode information from filename using multiple patterns.
    
    Args:
        filename (str): Filename to extract information from
        
    Returns:
        tuple: (series_name, season_num, episode_num, quality, language) or None if not found
    """
    # Initialize default values
    series_name = None
    season_num = None
    episode_num = None
    quality = None
    language = None
    
    # Extract base name without path and extension
    base_name = os.path.splitext(os.path.basename(filename))[0]
    
    # Try standard pattern: SeriesName.S01E01.Quality
    standard_match = re.search(r'(.+?)\.S(\d+)E(\d+)(?:\.|\s|-)(.+)', base_name, re.IGNORECASE)
    if standard_match:
        series_name = standard_match.group(1).replace('.', ' ')
        season_num = int(standard_match.group(2))
        episode_num = int(standard_match.group(3))
        quality = standard_match.group(4)
    
    # Try alternative pattern: SeriesName.1x01.Quality
    if not season_num:
        alt_match = re.search(r'(.+?)\.(\d+)x(\d+)(?:\.|\s|-)(.+)', base_name, re.IGNORECASE)
        if alt_match:
            series_name = alt_match.group(1).replace('.', ' ')
            season_num = int(alt_match.group(2))
            episode_num = int(alt_match.group(3))
            quality = alt_match.group(4)
    
    # Try season folder pattern: Season X/Episode Y
    if not season_num:
        season_folder_match = re.search(r'Season\s*(\d+).*?(?:Episode|Ep|E)\s*(\d+)', filename, re.IGNORECASE)
        if season_folder_match:
            season_num = int(season_folder_match.group(1))
            episode_num = int(season_folder_match.group(2))
            # Try to extract series name from path
            path_parts = Path(filename).parts
            if len(path_parts) > 2:
                series_name = path_parts[-3]
    
    # Try to extract language information
    if '.en.' in filename.lower() or '.eng.' in filename.lower() or '.english.' in filename.lower():
        language = 'en'
    elif '.es.' in filename.lower() or '.esp.' in filename.lower() or '.spanish.' in filename.lower():
        language = 'es'
    elif 'VOSE' in filename or 'VO' in filename:
        language = 'en'
    elif 'ESPAÑOL' in filename or 'ESP' in filename:
        language = 'es'
    
    # If we have at least season and episode, return the information
    if season_num is not None and episode_num is not None:
        return (series_name, season_num, episode_num, quality, language)
    
    return None

def get_file_similarity(file1, file2):
    """
    Calculate similarity between two filenames.
    
    Args:
        file1 (str): First filename
        file2 (str): Second filename
        
    Returns:
        float: Similarity score between 0 and 1
    """
    # Extract base names without extensions
    base1 = os.path.splitext(os.path.basename(file1))[0]
    base2 = os.path.splitext(os.path.basename(file2))[0]
    
    # Calculate similarity using difflib
    return difflib.SequenceMatcher(None, base1, base2).ratio()

def is_path_allowed(path):
    """
    Check if the path is within the allowed media root directory.
    
    Args:
        path (str): Path to check
        
    Returns:
        bool: True if path is allowed, False otherwise
    """
    # Get media root
    media_root = get_media_root()
    
    # Normalize paths for comparison
    norm_path = os.path.normpath(path)
    norm_media_root = os.path.normpath(media_root)
    
    # Check if path is the media root or a subdirectory
    return norm_path == norm_media_root or norm_path.startswith(norm_media_root + os.sep)

def search_for_vo_and_es_files(series=None, season=None, search_paths=None):
    """
    Search for original (VO) and Spanish dubbed (ES) files in the given paths.
    
    Args:
        series (str, optional): Series name to filter by
        season (int, optional): Season number to filter by
        search_paths (list, optional): List of paths to search in
    
    Returns:
        dict: Dictionary with matched VO and ES files
    """
    if not search_paths:
        logger.error("No search paths provided")
        return {}
    
    # Get media root
    media_root = get_media_root()
    
    # Ensure all search paths are within the media root
    valid_search_paths = []
    for path in search_paths:
        if not is_path_allowed(path):
            logger.warning(f"Path {path} is outside the media root and will be ignored")
            continue
        valid_search_paths.append(path)
    
    if not valid_search_paths:
        logger.error("No valid search paths within the media root")
        return {}
    
    logger.info(f"Searching for files in: {', '.join(valid_search_paths)}")
    
    # Patterns to identify VO and ES files
    vo_patterns = [r'\.en\.', r'\.eng\.', r'\.english\.', r'VOSE', r'VO']
    es_patterns = [r'\.es\.', r'\.esp\.', r'\.spanish\.', r'ESPAÑOL', r'ESP']
    
    # Compile season pattern if season is provided
    season_pattern = None
    if season is not None:
        season_pattern = re.compile(rf'S0*{season}|Season\s*{season}|{season}x\d+', re.IGNORECASE)
    
    # Compile series pattern if series is provided
    series_pattern = None
    if series is not None:
        # Escape special characters in series name and make it case insensitive
        series_escaped = re.escape(series)
        series_pattern = re.compile(rf'{series_escaped}', re.IGNORECASE)
    
    # Lists to store VO and ES files
    vo_files = []
    es_files = []
    
    # Search for files in all provided paths
    for search_path in valid_search_paths:
        for root, _, files in os.walk(search_path):
            for file in files:
                # Check if file is a video file
                if not file.lower().endswith(('.mkv', '.mp4', '.avi')):
                    continue
                
                full_path = os.path.join(root, file)
                
                # Filter by series if provided
                if series_pattern and not series_pattern.search(file) and not series_pattern.search(root):
                    continue
                
                # Filter by season if provided
                if season_pattern and not season_pattern.search(file) and not season_pattern.search(root):
                    continue
                
                # Check if file is VO or ES
                is_vo = any(re.search(pattern, file, re.IGNORECASE) for pattern in vo_patterns)
                is_es = any(re.search(pattern, file, re.IGNORECASE) for pattern in es_patterns)
                
                # If neither VO nor ES pattern is found, try to determine from folder structure
                if not is_vo and not is_es:
                    if 'english' in root.lower() or 'vo' in root.lower() or 'original' in root.lower():
                        is_vo = True
                    elif 'spanish' in root.lower() or 'es' in root.lower() or 'español' in root.lower():
                        is_es = True
                    else:
                        # Default to VO if we can't determine
                        is_vo = True
                
                # Add file to appropriate list
                if is_vo:
                    vo_files.append(full_path)
                elif is_es:
                    es_files.append(full_path)
    
    logger.info(f"Found {len(vo_files)} VO files and {len(es_files)} ES files")
    
    # Dictionary to store matched files
    matched_files = {}
    
    # First, try to match using episode information
    vo_info = {}
    es_info = {}
    
    # Extract episode information from VO files
    for vo_file in vo_files:
        info = extract_episode_info(vo_file)
        if info:
            series_name, season_num, episode_num, quality, _ = info
            key = f"S{season_num:02d}E{episode_num:02d}"
            vo_info[key] = vo_file
    
    # Extract episode information from ES files
    for es_file in es_files:
        info = extract_episode_info(es_file)
        if info:
            series_name, season_num, episode_num, quality, _ = info
            key = f"S{season_num:02d}E{episode_num:02d}"
            es_info[key] = es_file
    
    # Match files based on episode information
    for key in vo_info:
        if key in es_info:
            matched_files[key] = {'vo': vo_info[key], 'es': es_info[key]}
    
    # For remaining unmatched files, try similarity matching
    remaining_vo = [f for f in vo_files if not any(f == matched_files[k]['vo'] for k in matched_files)]
    remaining_es = [f for f in es_files if not any(f == matched_files[k]['es'] for k in matched_files)]
    
    # Group files by potential series/movie
    vo_groups = defaultdict(list)
    es_groups = defaultdict(list)
    
    # Group VO files
    for vo_file in remaining_vo:
        base_name = os.path.basename(vo_file)
        # Try to extract series name or movie title
        match = re.search(r'^(.+?)(?:\.S\d+|\.E\d+|\.\d+x\d+)', base_name)
        if match:
            group_key = match.group(1).lower()
        else:
            # Use first part of filename before first dot
            group_key = base_name.split('.')[0].lower()
        vo_groups[group_key].append(vo_file)
    
    # Group ES files
    for es_file in remaining_es:
        base_name = os.path.basename(es_file)
        # Try to extract series name or movie title
        match = re.search(r'^(.+?)(?:\.S\d+|\.E\d+|\.\d+x\d+)', base_name)
        if match:
            group_key = match.group(1).lower()
        else:
            # Use first part of filename before first dot
            group_key = base_name.split('.')[0].lower()
        es_groups[group_key].append(es_file)
    
    # Match files within groups based on similarity
    for group_key in vo_groups:
        # Find closest matching group in ES files
        best_es_group = None
        best_similarity = 0
        
        for es_group in es_groups:
            similarity = difflib.SequenceMatcher(None, group_key, es_group).ratio()
            if similarity > best_similarity and similarity > 0.6:  # Threshold for group matching
                best_similarity = similarity
                best_es_group = es_group
        
        if best_es_group:
            # Match files within these groups
            for vo_file in vo_groups[group_key]:
                best_es_file = None
                best_file_similarity = 0
                
                for es_file in es_groups[best_es_group]:
                    similarity = get_file_similarity(vo_file, es_file)
                    if similarity > best_file_similarity and similarity > 0.5:  # Threshold for file matching
                        best_file_similarity = similarity
                        best_es_file = es_file
                
                if best_es_file:
                    # Create a key based on filename if we can't extract episode info
                    key = os.path.splitext(os.path.basename(vo_file))[0]
                    matched_files[key] = {'vo': vo_file, 'es': best_es_file}
                    # Remove the matched ES file to avoid duplicate matches
                    es_groups[best_es_group].remove(best_es_file)
    
    logger.info(f"Found {len(matched_files)} complete matches (both VO and ES)")
    
    return matched_files

def ensure_mkv_format(file_path):
    """
    Ensure the file is in MKV format, converting if necessary.
    
    Args:
        file_path (str): Path to the file
    
    Returns:
        str: Path to the MKV file
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return None
    
    # Check if file is already MKV
    if file_path.lower().endswith('.mkv'):
        logger.info(f"File is already in MKV format: {file_path}")
        return file_path
    
    # Create output path with .mkv extension
    output_path = os.path.splitext(file_path)[0] + '.mkv'
    
    # Convert to MKV using ffmpeg (copy streams without re-encoding)
    logger.info(f"Converting {file_path} to MKV format")
    try:
        cmd = [
            'ffmpeg',
            '-i', file_path,
            '-c', 'copy',
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Verify the output file exists and has a non-zero size
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"Successfully converted to MKV: {output_path}")
            return output_path
        else:
            logger.error(f"Conversion failed: Output file is missing or empty")
            return None
    except subprocess.SubprocessError as e:
        logger.error(f"Error converting file to MKV: {e}")
        return None

def transfer_audio_track(vo_file, es_file, destination_path=None):
    """
    Transfer the Spanish audio track from the ES file to the VO file.
    
    Args:
        vo_file (str): Path to the original version file
        es_file (str): Path to the Spanish dubbed file
        destination_path (str, optional): Path to save the output file (default: same directory as vo_file)
    
    Returns:
        str: Path to the output file with both audio tracks
    """
    if not os.path.exists(vo_file) or not os.path.exists(es_file):
        logger.error(f"One or both input files not found: VO={vo_file}, ES={es_file}")
        return None
    
    # Ensure both files are in MKV format
    vo_mkv = ensure_mkv_format(vo_file)
    es_mkv = ensure_mkv_format(es_file)
    
    if not vo_mkv or not es_mkv:
        logger.error("Failed to ensure MKV format for input files")
        return None
    
    # Create output filename with language tags
    if destination_path:
        # Ensure destination path exists
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)
        
        # Use destination path but keep the filename from vo_mkv
        output_base = os.path.splitext(os.path.basename(vo_mkv))[0]
        output_dir = destination_path
    else:
        output_dir = os.path.dirname(vo_mkv)
        output_base = os.path.splitext(os.path.basename(vo_mkv))[0]
    
    # Add language tags if not already present
    if '.en.es.' not in output_base.lower():
        # Remove any existing language tags
        output_base = re.sub(r'\.(en|eng|english|es|esp|spanish)\.',
                            '.', output_base, flags=re.IGNORECASE)
        output_base = output_base.rstrip('.')
        output_base += '.en.es'
    
    output_file = os.path.join(output_dir, f"{output_base}.mkv")
    
    # Use ffmpeg to merge the audio track without re-encoding
    logger.info(f"Transferring Spanish audio from {es_mkv} to {vo_mkv}")
    try:
        cmd = [
            'ffmpeg',
            '-i', vo_mkv,  # Original video with English audio
            '-i', es_mkv,  # Spanish dubbed version
            '-map', '0:v',  # Map video from first input
            '-map', '0:a',  # Map audio from first input (English)
            '-map', '1:a',  # Map audio from second input (Spanish)
            '-c', 'copy',   # Copy all streams without re-encoding
            '-metadata:s:a:0', 'language=eng',  # Set language metadata for first audio
            '-metadata:s:a:1', 'language=spa',  # Set language metadata for second audio
            output_file
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Verify the output file exists and has a non-zero size
        if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
            logger.info(f"Successfully created output file with both audio tracks: {output_file}")
            return output_file
        else:
            logger.error(f"Audio transfer failed: Output file is missing or empty")
            return None
    except subprocess.SubprocessError as e:
        logger.error(f"Error transferring audio track: {e}")
        return None

def validate_and_cleanup(output_file, es_file, vo_file=None):
    """
    Validate the output file and clean up temporary files.
    
    Args:
        output_file (str): Path to the output file
        es_file (str): Path to the Spanish dubbed file to delete
        vo_file (str, optional): Path to the original file to delete if different from output
    
    Returns:
        bool: True if validation and cleanup succeeded, False otherwise
    """
    if not os.path.exists(output_file):
        logger.error(f"Output file not found: {output_file}")
        return False
    
    # Validate the output file has both audio tracks
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type', '-of', 'csv=p=0', output_file]
        result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Count audio streams
        audio_streams = result.stdout.strip().split('\n').count('audio')
        
        if audio_streams < 2:
            logger.error(f"Validation failed: Output file has only {audio_streams} audio streams")
            return False
        
        logger.info(f"Validation successful: Output file has {audio_streams} audio streams")
        
        # Delete the Spanish dubbed file
        if os.path.exists(es_file):
            os.remove(es_file)
            logger.info(f"Deleted Spanish dubbed file: {es_file}")
        
        # Delete the original VO file if it's different from the output file
        if vo_file and vo_file != output_file and os.path.exists(vo_file):
            os.remove(vo_file)
            logger.info(f"Deleted original VO file: {vo_file}")
        
        return True
    except subprocess.SubprocessError as e:
        logger.error(f"Error validating output file: {e}")
        return False

def process_file_pair(vo_file, es_file, destination_path=None):
    """
    Process a pair of VO and ES files.
    
    Args:
        vo_file (str): Path to the original version file
        es_file (str): Path to the Spanish dubbed file
        destination_path (str, optional): Path to save the output file (default: same directory as vo_file)
    
    Returns:
        tuple: (success, output_file) - Whether processing succeeded and path to output file
    """
    logger.info(f"Processing file pair: VO={vo_file}, ES={es_file}")
    
    # Ensure VO file is in MKV format
    vo_mkv = ensure_mkv_format(vo_file)
    if not vo_mkv:
        return False, None
    
    # Transfer audio track
    output_file = transfer_audio_track(vo_mkv, es_file, destination_path)
    if not output_file:
        return False, None
    
    # Validate and cleanup
    success = validate_and_cleanup(output_file, es_file, vo_file if vo_file != vo_mkv else None)
    return success, output_file

def main():
    """
    Main function to run the script.
    """
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Ensure media root exists
    media_root = get_media_root()
    if not os.path.exists(media_root):
        logger.warning(f"Media root directory {media_root} does not exist. Attempting to create it.")
        try:
            os.makedirs(media_root, exist_ok=True)
            logger.info(f"Created media root directory: {media_root}")
        except Exception as e:
            logger.error(f"Failed to create media root directory: {e}")
            sys.exit(1)
    
    # Gather user inputs
    args = gather_user_inputs()
    
    if args.mode == 'full':
        # Run the full process
        matched_files = search_for_vo_and_es_files(args.series, args.season, args.paths)
        
        if not matched_files:
            logger.error("No matching file pairs found")
            sys.exit(1)
        
        success_count = 0
        for key, files in matched_files.items():
            logger.info(f"Processing {key}")
            success, _ = process_file_pair(files['vo'], files['es'], args.destination)
            if success:
                success_count += 1
        
        logger.info(f"Successfully processed {success_count} out of {len(matched_files)} file pairs")
    
    elif args.mode == 'search':
        # Just search for files
        matched_files = search_for_vo_and_es_files(args.series, args.season, args.paths)
        
        if not matched_files:
            logger.error("No matching file pairs found")
            sys.exit(1)
        
        for key, files in matched_files.items():
            print(f"{key}:")
            print(f"  VO: {files['vo']}")
            print(f"  ES: {files['es']}")
    
    elif args.mode == 'normalize':
        # Normalize filenames
        for file in args.files:
            normalized = normalize_filename(file)
            print(f"{file} -> {normalized}")
    
    elif args.mode == 'convert':
        # Convert files to MKV
        for file in args.files:
            mkv_file = ensure_mkv_format(file)
            if mkv_file:
                print(f"Converted: {mkv_file}")
    
    elif args.mode == 'merge':
        # Merge ES audio into VO file
        success, output_file = process_file_pair(args.vo, args.es, args.destination)
        if success:
            print(f"Merged audio tracks: {output_file}")
    
    elif args.mode == 'cleanup':
        # Validate and cleanup files
        for file in args.files:
            if validate_and_cleanup(file, file + ".es.original"):
                print(f"Validated and cleaned up: {file}")

if __name__ == "__main__":
    main()
