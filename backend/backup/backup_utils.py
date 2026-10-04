import os
import glob
import shutil
import hashlib
from pathlib import Path
from typing import Optional, Tuple, List, Union
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import logging

from core.config import settings
from backup.backup_models import RetentionClass

logger = logging.getLogger(__name__)


def resolve_mongodump_path() -> Optional[str]:
    """
    Resolves the absolute path to the mongodump binary.
    1. Checks settings.MONGODUMP_PATH if set.
    2. Checks system PATH via shutil.which('mongodump').
    3. Searches standard Windows installation directories.
    """
    if getattr(settings, "MONGODUMP_PATH", None) and os.path.exists(settings.MONGODUMP_PATH):
        return settings.MONGODUMP_PATH

    which_path = shutil.which("mongodump")
    if which_path:
        return which_path

    # Common Windows installation directories
    candidate_patterns = [
        r"C:\Program Files\MongoDB\Server\*\bin\mongodump.exe",
        r"C:\Program Files\MongoDB\Tools\*\bin\mongodump.exe",
        r"C:\Program Files (x86)\MongoDB\Server\*\bin\mongodump.exe",
        r"C:\mongodb\bin\mongodump.exe",
        r"C:\ProgramData\chocolatey\bin\mongodump.exe",
    ]
    for pattern in candidate_patterns:
        matches = glob.glob(pattern)
        if matches:
            # Sort descending to prefer newer versions (e.g. 7.0 over 5.0)
            matches.sort(reverse=True)
            return matches[0]

    return None


def resolve_mongorestore_path() -> Optional[str]:
    """
    Resolves the absolute path to the mongorestore binary.
    1. Checks settings.MONGORESTORE_PATH if set.
    2. Checks system PATH via shutil.which('mongorestore').
    3. Searches standard Windows installation directories.
    """
    if getattr(settings, "MONGORESTORE_PATH", None) and os.path.exists(settings.MONGORESTORE_PATH):
        return settings.MONGORESTORE_PATH

    which_path = shutil.which("mongorestore")
    if which_path:
        return which_path

    candidate_patterns = [
        r"C:\Program Files\MongoDB\Server\*\bin\mongorestore.exe",
        r"C:\Program Files\MongoDB\Tools\*\bin\mongorestore.exe",
        r"C:\Program Files (x86)\MongoDB\Server\*\bin\mongorestore.exe",
        r"C:\mongodb\bin\mongorestore.exe",
        r"C:\ProgramData\chocolatey\bin\mongorestore.exe",
    ]
    for pattern in candidate_patterns:
        matches = glob.glob(pattern)
        if matches:
            matches.sort(reverse=True)
            return matches[0]

    return None


def calculate_sha256(filepath: Union[str, Path]) -> str:
    """
    Calculates the SHA-256 hexadecimal hash of a file using 64KB chunk streaming.
    """
    sha256 = hashlib.sha256()
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"File not found for checksum calculation: {filepath}")

    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_checksum(filepath: Union[str, Path], expected_checksum: str) -> bool:
    """
    Verifies that the file matches the expected SHA-256 checksum.
    Returns False if file does not exist or checksum does not match.
    """
    try:
        actual = calculate_sha256(filepath)
        return actual.lower() == expected_checksum.lower()
    except Exception as e:
        logger.warning(f"[BackupUtils] Checksum verification failed with error: {e}")
        return False


def validate_backup_path(filepath: Union[str, Path], base_directory: Union[str, Path]) -> Path:
    """
    Path Traversal Guard:
    Resolves both paths to strict canonical form and ensures that the requested file
    is strictly within the base backup directory.
    Raises ValueError on attempted traversal.
    """
    resolved_base = Path(base_directory).resolve()
    resolved_file = Path(filepath).resolve()

    try:
        resolved_file.relative_to(resolved_base)
    except ValueError:
        raise ValueError(
            f"Path traversal detected: '{filepath}' is outside base directory '{base_directory}'"
        )
    return resolved_file


def sanitize_connection_args(
    mongo_url: str,
    target_db: Optional[str] = None
) -> Tuple[List[str], str]:
    """
    Extracts connection parameters from MONGO_URL into safe CLI arguments for mongodump/mongorestore.
    Returns:
      - args: list of arguments to pass to subprocess
      - sanitized_uri: safe representation for logging (passwords masked)
    """
    parsed = urlparse(mongo_url)
    args: List[str] = []

    # Build sanitized URI for logging
    if parsed.password:
        sanitized_netloc = f"{parsed.username}:***@{parsed.hostname}"
        if parsed.port:
            sanitized_netloc += f":{parsed.port}"
    else:
        sanitized_netloc = parsed.netloc

    sanitized_uri = f"{parsed.scheme}://{sanitized_netloc}{parsed.path}"

    # In modern mongodump / mongorestore, passing --uri is the safest and most robust approach.
    # Note: subprocess.run with a list of args (shell=False) passes the argument directly
    # to the process without shell interpretation.
    args.append(f"--uri={mongo_url}")

    if target_db:
        args.append(f"--db={target_db}")

    return args, sanitized_uri


def determine_retention_class(created_at: datetime) -> RetentionClass:
    """
    Classifies a backup into a retention tier based on creation date:
    - 1st of month -> MONTHLY
    - Sunday (weekday == 6) -> WEEKLY
    - Otherwise -> DAILY
    """
    if created_at.day == 1:
        return RetentionClass.MONTHLY
    elif created_at.weekday() == 6:
        return RetentionClass.WEEKLY
    else:
        return RetentionClass.DAILY
