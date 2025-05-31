# TV Show and Movie Processor

This script automates the processing of TV shows and movies downloaded in two versions: original version (VO) and Spanish dubbed version (ES). It retains only the original video file while adding the Spanish audio track as an additional track, and then deletes the dubbed version.

## Features

- Modular design with standalone functions for flexible execution
- Support for multiple video container formats (.mkv, .mp4, .avi, etc.)
- Automatic conversion to .mkv format to support multiple audio tracks
- Filename normalization and cleaning
- Direct audio transfer without re-encoding
- Automatic file cleanup after successful processing
- Comprehensive logging and error handling

## Requirements

- Python 3.6+
- ffmpeg (installed automatically by the script if missing)

## Usage

The script can be run in different modes:

### Full Process Mode

Process all matching files in the specified paths:

```bash
./tv_movie_processor.py full --series "Series Name" --season 1 --paths /path/to/tv /path/to/downloads
```

### Individual Step Modes

Search for matching VO and ES files:

```bash
./tv_movie_processor.py search --series "Series Name" --season 1 --paths /path/to/tv /path/to/downloads
```

Normalize filenames:

```bash
./tv_movie_processor.py normalize --files /path/to/file1.mkv /path/to/file2.mp4
```

Convert files to MKV format:

```bash
./tv_movie_processor.py convert --files /path/to/file1.mp4 /path/to/file2.avi
```

Merge ES audio into VO file:

```bash
./tv_movie_processor.py merge --vo /path/to/original.mkv --es /path/to/spanish.mkv
```

Validate and cleanup files:

```bash
./tv_movie_processor.py cleanup --files /path/to/processed.mkv
```

## Output Format

The script produces files with the following naming pattern:

```
Series.Name.S01E01.1080p.details.en.es.mkv
```

## How It Works

1. The script searches for matching VO and ES files based on the provided series name and season.
2. It ensures all files are in MKV format, converting if necessary.
3. It transfers the Spanish audio track from the ES file to the VO file without re-encoding.
4. It validates the output file to ensure it has both audio tracks.
5. It cleans up by deleting the ES file and any temporary files.

## Notes

- The script works directly on files in the /tv or /movies folders, which are typically hard links created by Sonarr or Radarr.
- It preserves the original video quality by avoiding re-encoding.
- Language metadata is properly set for both audio tracks (eng and spa).
