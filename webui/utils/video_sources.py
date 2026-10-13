"""Resolve and discover video sources without copying or uploading files."""

import os
from pathlib import Path


VIDEO_UPLOAD_TYPES = ["mp4", "mov", "avi", "flv", "mkv", "mpeg4"]


def resolve_video_source_directory(default_directory, configured_directory=""):
    directory = (
        os.environ.get("NARRATO_VIDEO_SOURCE_DIR", "").strip()
        or str(configured_directory).strip()
        or str(default_directory)
    )
    return str(Path(directory).expanduser().resolve())


def list_video_source_files(directory):
    root = Path(directory)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    extensions = {f".{suffix}" for suffix in VIDEO_UPLOAD_TYPES}
    video_files = []

    def raise_walk_error(error):
        raise error

    for current_directory, _, filenames in os.walk(root, onerror=raise_walk_error):
        for filename in filenames:
            candidate = Path(current_directory) / filename
            if candidate.suffix.lower() in extensions and candidate.is_file():
                video_files.append(str(candidate))
    return sorted(video_files, key=lambda filename: filename.casefold())
