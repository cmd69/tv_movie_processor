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

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
    
    logger.info(f"Searching for files in: {', '.join(search_paths)}")
    
    # Patterns to identify VO and ES files
    vo_patterns = [r'\.en\.', r'\.eng\.', r'\.english\.', r'VOSE', r'VO']
    es_patterns = [r'\.es\.', r'\.esp\.', r'\.spanish\.', r'ESPAÑOL', r'ESP']
    
    # Compile season pattern if season is provided
    season_pattern = None
    if season is not None:
        season_pattern = re.compile(rf'S0*{season}|Season\s*{season}', re.IGNORECASE)
    
    # Compile series pattern if series is provided
    series_pattern = None
    if series is not None:
        # Escape special characters in series name and make it case insensitive
        series_escaped = re.escape(series)
        series_pattern = re.compile(rf'{series_escaped}', re.IGNORECASE)
    
    # Dictionary to store matched files
    matched_files = {}
    
    # Search for files in all provided paths
    for search_path in search_paths:
        for root, _, files in os.walk(search_path):
            for file in files:
                # Check if file is a video file
                if not file.lower().endswith(('.mkv', '.mp4', '.avi')):
                    continue
                
                full_path = os.path.join(root, file)
                
                # Filter by series if provided
                if series_pattern and not series_pattern.search(file):
                    continue
                
                # Filter by season if provided
                if season_pattern and not season_pattern.search(file):
                    continue
                
                # Check if file is VO or ES
                is_vo = any(re.search(pattern, file, re.IGNORECASE) for pattern in vo_patterns)
                is_es = any(re.search(pattern, file, re.IGNORECASE) for pattern in es_patterns)
                
                # If neither VO nor ES pattern is found, assume it's VO
                if not is_vo and not is_es:
                    is_vo = True
                
                # Extract episode information
                episode_match = re.search(r'S(\d+)E(\d+)', file, re.IGNORECASE)
                if episode_match:
                    season_num = int(episode_match.group(1))
                    episode_num = int(episode_match.group(2))
                    key = f"S{season_num:02d}E{episode_num:02d}"
                    
                    if key not in matched_files:
                        matched_files[key] = {'vo': None, 'es': None}
                    
                    if is_vo:
                        matched_files[key]['vo'] = full_path
                    elif is_es:
                        matched_files[key]['es'] = full_path
                else:
                    # For movies or files without standard episode naming
                    # Use filename as key
                    key = os.path.splitext(file)[0]
                    
                    if key not in matched_files:
                        matched_files[key] = {'vo': None, 'es': None}
                    
                    if is_vo:
                        matched_files[key]['vo'] = full_path
                    elif is_es:
                        matched_files[key]['es'] = full_path
    
    # Filter out entries that don't have both VO and ES files
    complete_matches = {k: v for k, v in matched_files.items() if v['vo'] and v['es']}
    
    logger.info(f"Found {len(complete_matches)} complete matches (both VO and ES)")
    
    return complete_matches

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

def transfer_audio_track(vo_file, es_file):
    """
    Transfer the Spanish audio track from the ES file to the VO file.
    
    Args:
        vo_file (str): Path to the original version file
        es_file (str): Path to the Spanish dubbed file
    
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
    # TODO Change output
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

def process_file_pair(vo_file, es_file):
    """
    Process a pair of VO and ES files.
    
    Args:
        vo_file (str): Path to the original version file
        es_file (str): Path to the Spanish dubbed file
    
    Returns:
        bool: True if processing succeeded, False otherwise
    """
    logger.info(f"Processing file pair: VO={vo_file}, ES={es_file}")
    
    # Ensure VO file is in MKV format
    vo_mkv = ensure_mkv_format(vo_file)
    if not vo_mkv:
        return False
    
    # Transfer audio track
    output_file = transfer_audio_track(vo_mkv, es_file)
    if not output_file:
        return False
    
    # Validate and cleanup
    return validate_and_cleanup(output_file, es_file, vo_file if vo_file != vo_mkv else None)

def main():
    """
    Main function to run the script.
    """
    # Check dependencies
    if not check_dependencies():
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
            if process_file_pair(files['vo'], files['es']):
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
        output_file = transfer_audio_track(args.vo, args.es)
        if output_file:
            print(f"Merged audio tracks: {output_file}")
    
    elif args.mode == 'cleanup':
        # Validate and cleanup files
        for file in args.files:
            if validate_and_cleanup(file, file + ".es.original"):
                print(f"Validated and cleaned up: {file}")

if __name__ == "__main__":
    main()
