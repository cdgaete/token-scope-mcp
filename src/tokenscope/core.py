"""
Core functionality for TokenScope - token-aware directory explorer.

This module contains the essential file system operations and token estimation
functions used throughout TokenScope.
"""

import os
import fnmatch
from typing import Any
import tiktoken


def validate_path(path: str, base_path: str | None = None) -> dict[str, Any]:
    """Validate that a path is within the allowed base path for security.
    
    Args:
        path: The path to validate
        base_path: The allowed base path (if None, no validation is performed)
        
    Returns:
        dictionary with validation results
    """
    result = {
        "is_valid": True,
        "resolved_path": os.path.abspath(path),
        "error": None
    }
    
    # Skip validation if no base path specified
    if base_path is None:
        return result
        
    # Resolve base path
    resolved_base = os.path.abspath(base_path)
    
    # Check if the path is within the base path
    if not result["resolved_path"].startswith(resolved_base):
        result["is_valid"] = False
        result["error"] = f"Path is outside of the allowed base directory: {resolved_base}"
    
    return result


def format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0 or unit == 'TB':
            return f"{size_bytes:.1f} {unit}" if unit != 'B' else f"{size_bytes} {unit}"
        size_bytes /= 1024.0


def estimate_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Estimate number of tokens in the text using tiktoken."""
    try:
        encoding = tiktoken.get_encoding(encoding_name)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to approximate counting if tiktoken fails
        return len(text) // 4  # Rough approximation: 4 chars per token


def is_binary_file(file_path: str) -> bool:
    """Detect if a file is binary based on extension or content analysis."""
    # Check extension first
    binary_extensions = {
        '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.tiff',
        '.zip', '.tar', '.gz', '.bz2', '.xz', '.rar', '.7z',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.mp3', '.mp4', '.avi', '.mov', '.flv', '.wav', '.ogg'
    }
    
    ext = os.path.splitext(file_path)[1].lower()
    if ext in binary_extensions:
        return True
    
    # If extension check is inconclusive, check the content
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            # Check for null bytes which indicate binary content
            if b'\x00' in chunk:
                return True
            # If more than 30% of the characters are non-ASCII, consider it binary
            non_ascii = sum(1 for b in chunk if b > 127)
            if non_ascii > len(chunk) * 0.3:
                return True
    except Exception:
        # If we can't read the file, assume it's binary to be safe
        return True
    
    return False


class PathFilter:
    """Filter paths based on gitignore-style patterns."""
    
    # Default patterns to ignore common non-source directories and files
    DEFAULT_PATTERNS = [
        ".git/", ".venv/", "venv/", "__pycache__/", "node_modules/",
        "build/", "dist/", "*.egg-info/", ".tox/", ".idea/", ".vscode/"
    ]
    
    def __init__(self, patterns: list[str] | None = None, gitignore_file: str | None = None):
        """Initialize with patterns and optionally a gitignore file."""
        self.patterns = list(self.DEFAULT_PATTERNS)
        
        # Add custom patterns if specified
        if patterns:
            self.patterns.extend(patterns)
        
        # Load patterns from gitignore file if specified
        if gitignore_file and os.path.isfile(gitignore_file):
            with open(gitignore_file, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        self.patterns.append(line)
    
    def should_ignore(self, path: str, is_dir: bool = False) -> bool:
        """Check if a path should be ignored based on the patterns."""
        # Use basename for path-only checks
        basename = os.path.basename(path)
        
        for pattern in self.patterns:
            # Handle directory-only patterns
            if pattern.endswith('/') and not is_dir:
                continue
                
            # Remove trailing slash for matching
            pattern = pattern.rstrip('/')
            
            # Simple glob matching
            if fnmatch.fnmatch(basename, pattern) or fnmatch.fnmatch(path, pattern):
                return True
                
            # Check for pattern matches within subdirectories
            if fnmatch.fnmatch(path, f"*/{pattern}"):
                return True
        
        return False


def create_path_filter(path: str, ignore_patterns: list[str] | None, use_gitignore: bool) -> PathFilter:
    """Create a path filter with the given settings.
    
    Args:
        path: Base directory path for finding .gitignore
        ignore_patterns: list of patterns to ignore
        use_gitignore: Whether to use .gitignore file
        
    Returns:
        Configured PathFilter
    """
    gitignore_file = os.path.join(path, '.gitignore') if use_gitignore else None
    return PathFilter(patterns=ignore_patterns, gitignore_file=gitignore_file)


def count_directory_entries(path: str, path_filter: PathFilter) -> tuple[int, int]:
    """Count total files and directories after filtering.
    
    Args:
        path: Directory path
        path_filter: Filter for paths
        
    Returns:
        tuple of (file_count, dir_count)
    """
    try:
        entries = list(os.scandir(path))
        total_files = sum(1 for e in entries if e.is_file() and not path_filter.should_ignore(e.path))
        total_dirs = sum(1 for e in entries if e.is_dir() and not path_filter.should_ignore(e.path, is_dir=True))
        return total_files, total_dirs
    except (PermissionError, FileNotFoundError):
        return 0, 0


def estimate_file_tokens(file_path: str, file_size: int) -> int:
    """Estimate tokens in a text file, using sampling for large files.
    
    Args:
        file_path: Path to the file
        file_size: Size of the file in bytes
        
    Returns:
        Estimated token count
    """
    try:
        # For very large files, use sampling
        if file_size > 100000:  # Over 100KB
            with open(file_path, encoding='utf-8', errors='replace') as f:
                # Read samples from beginning, middle, and end
                begin = f.read(4096)
                
                # Seek to middle
                f.seek(file_size // 2)
                f.readline()  # Skip to next line boundary
                middle = f.read(4096)
                
                # Seek to near end
                f.seek(max(0, file_size - 8192))
                end = f.read(4096)
                
                # Combine samples
                sample = begin + middle + end
                
                # Estimate tokens and extrapolate
                token_density = estimate_tokens(sample) / len(sample.encode('utf-8'))
                token_estimate = int(token_density * file_size)
        else:
            # For smaller files, read the whole content
            with open(file_path, encoding='utf-8', errors='replace') as f:
                content = f.read()
                token_estimate = estimate_tokens(content)
                
        return token_estimate
    except Exception:
        # If error reading, make a rough estimate
        return file_size // 4  # Rough approximation


def process_file_entry(entry, path_filter: PathFilter) -> dict[str, Any] | None:
    """Process a single file entry.
    
    Args:
        entry: File entry from os.scandir
        path_filter: Filter for paths
        
    Returns:
        dictionary with file information or None if file should be ignored
    """
    # Skip ignored files
    if path_filter.should_ignore(entry.path):
        return None
        
    try:
        file_size = entry.stat().st_size
        is_binary = is_binary_file(entry.path)
        
        file_info = {
            "name": entry.name,
            "path": entry.path,
            "size": file_size,
            "size_formatted": format_size(file_size),
            "extension": os.path.splitext(entry.name)[1].lower(),
            "is_binary": is_binary
        }
        
        # Estimate tokens if it's a text file
        if not is_binary:
            file_info["estimated_tokens"] = estimate_file_tokens(entry.path, file_size)
        
        return file_info
    except Exception:
        # Skip files we can't access
        return None


def process_files(entries, path_filter: PathFilter, summarize: bool, total_files: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], int, int, bool]:
    """Process file entries in a directory.
    
    Args:
        entries: Directory entries from os.scandir
        path_filter: Filter for paths
        summarize: Whether to use summary mode
        total_files: Total number of files (used for truncation info)
        
    Returns:
        tuple of (file_list, extensions_info, total_size, tokens_used, is_truncated)
    """
    files = [e for e in entries if e.is_file() and not path_filter.should_ignore(e.path)]
    
    # If summarizing, limit the number of files we process
    is_truncated = False
    if summarize and len(files) > 10:
        files = files[:10]  # Just show the first 10 files
        is_truncated = True
    
    file_list = []
    total_size = 0
    tokens_used = 0
    extensions = {}
    
    for entry in files:
        file_info = process_file_entry(entry, path_filter)
        if file_info:
            file_list.append(file_info)
            total_size += file_info["size"]
            tokens_used += 50  # Approx 50 tokens per file entry
            
            # Track extensions for summary mode
            if summarize:
                ext = file_info["extension"] or "[no extension]"
                if ext not in extensions:
                    extensions[ext] = {
                        "count": 0,
                        "size": 0,
                        "size_formatted": ""
                    }
                
                extensions[ext]["count"] += 1
                extensions[ext]["size"] += file_info["size"]
    
    # Format extension sizes
    if summarize:
        for ext in extensions:
            extensions[ext]["size_formatted"] = format_size(extensions[ext]["size"])
    
    return file_list, extensions, total_size, tokens_used, is_truncated


def process_subdirectory(entry, path_filter: PathFilter, max_tokens: int, base_path: str | None, summary_threshold: int) -> tuple[dict[str, Any], int]:
    """Process a subdirectory entry.
    
    Args:
        entry: Directory entry from os.scandir
        path_filter: Filter for paths
        max_tokens: Maximum tokens for this subdirectory
        base_path: Base directory for security validation
        summary_threshold: Number of items for summary mode
        
    Returns:
        tuple of (subdirectory_info, tokens_used)
    """
    if path_filter.should_ignore(entry.path, is_dir=True):
        return None, 0
        
    subdir = scan_directory(
        entry.path,
        max_tokens,
        base_path,
        summary_threshold,
        path_filter=path_filter
    )
    
    # Return tokens used
    return subdir, subdir.get("tokens_used", 0)


def process_subdirectories(entries, path_filter: PathFilter, max_tokens: int, base_path: str | None, summary_threshold: int) -> tuple[list[dict[str, Any]], int, int]:
    """Process subdirectory entries.
    
    Args:
        entries: Directory entries from os.scandir
        path_filter: Filter for paths
        max_tokens: Maximum tokens for all subdirectories
        base_path: Base directory for security validation
        summary_threshold: Number of items for summary mode
        
    Returns:
        tuple of (subdirectory_list, total_size, tokens_used)
    """
    directories = [e for e in entries if e.is_dir() and not path_filter.should_ignore(e.path, is_dir=True)]
    
    # Allocate tokens proportionally for subdirectories
    if directories:
        tokens_per_dir = max_tokens // (len(directories) + 1)  # +1 for files
    else:
        tokens_per_dir = 0
    
    subdirectory_list = []
    total_size = 0
    tokens_used = 0
    
    for entry in directories:
        subdir, subdir_tokens = process_subdirectory(
            entry, 
            path_filter, 
            tokens_per_dir, 
            base_path, 
            summary_threshold
        )
        
        if subdir:
            subdirectory_list.append(subdir)
            total_size += subdir.get("size", 0)
            tokens_used += subdir_tokens
    
    return subdirectory_list, total_size, tokens_used


def scan_directory(
    path: str, 
    max_tokens: int = 10000, 
    base_path: str | None = None,
    summary_threshold: int = 100,  # Number of items that triggers summary mode
    ignore_patterns: list[str] | None = None,
    use_gitignore: bool = True,
    path_filter: PathFilter | None = None
) -> dict[str, Any]:
    """
    Scan a directory with token-aware summarization.
    
    Args:
        path: Directory path to scan
        max_tokens: Maximum tokens to use for the directory structure
        base_path: Base directory for security validation
        summary_threshold: Number of items that triggers directory summarization
        ignore_patterns: list of patterns to ignore
        use_gitignore: Whether to use .gitignore file
        path_filter: Optional pre-configured path filter
        
    Returns:
        dictionary with directory structure information
    """
    # Validate path if base_path is provided
    if base_path:
        validation = validate_path(path, base_path)
        if not validation["is_valid"]:
            return {
                "error": validation["error"],
                "path": path,
                "is_valid": False
            }
        path = validation["resolved_path"]
    
    # Create path filter if not provided
    if path_filter is None:
        path_filter = create_path_filter(path, ignore_patterns, use_gitignore)
    
    # Start token counting
    tokens_used = 0
    
    # Initialize directory structure result
    result = {
        "name": os.path.basename(path) or path,
        "path": path,
        "size": 0,
        "files": [],
        "directories": [],
        "file_count": 0,
        "dir_count": 0,
        "tokens_used": 0,
        "is_summarized": False
    }
    
    try:
        # Get directory entries
        entries = list(os.scandir(path))
        
        # Count total items after filtering
        total_files, total_dirs = count_directory_entries(path, path_filter)
        
        # Determine if we need summary mode
        summarize = (total_files + total_dirs) > summary_threshold
        result["is_summarized"] = summarize
        
        # Process subdirectories
        subdirectories, subdir_size, subdir_tokens = process_subdirectories(
            entries, 
            path_filter, 
            max_tokens, 
            base_path, 
            summary_threshold
        )
        
        result["directories"] = subdirectories
        result["dir_count"] = len(subdirectories)
        result["size"] += subdir_size
        tokens_used += subdir_tokens
        
        # Process files
        files, extensions, file_size, file_tokens, is_truncated = process_files(
            entries, 
            path_filter, 
            summarize, 
            total_files
        )
        
        result["files"] = files
        result["file_count"] = len(files)
        result["size"] += file_size
        tokens_used += file_tokens
        
        # Add truncation info if necessary
        if is_truncated:
            result["files_truncated"] = True
            result["total_files"] = total_files
        
        # Add extension summary if in summary mode
        if summarize:
            result["extensions"] = extensions
        
        # Update token usage and size
        result["tokens_used"] = tokens_used
        result["size_formatted"] = format_size(result["size"])
        
    except PermissionError:
        result["error"] = "Permission denied"
    except Exception as e:
        result["error"] = str(e)
    
    return result


def extract_file_content(
    file_path: str, 
    max_tokens: int = 5000,
    sample_only: bool = False,
    base_path: str | None = None
) -> dict[str, Any]:
    """
    Extract content from a file with token awareness.
    
    Args:
        file_path: Path to the file
        max_tokens: Maximum tokens to return
        sample_only: Whether to return just a sample of large files
        base_path: Base directory for security validation
        
    Returns:
        dictionary with file content and metadata
    """
    # Validate path if base_path is provided
    if base_path:
        validation = validate_path(file_path, base_path)
        if not validation["is_valid"]:
            return {
                "error": validation["error"],
                "path": file_path,
                "is_valid": False
            }
        file_path = validation["resolved_path"]
    
    result = {
        "path": file_path,
        "name": os.path.basename(file_path),
        "is_valid": True
    }
    
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            result["error"] = "File not found"
            return result
            
        # Check if it's a directory
        if os.path.isdir(file_path):
            result["error"] = "Path is a directory, not a file"
            return result
            
        # Get file size
        file_size = os.path.getsize(file_path)
        result["size"] = file_size
        result["size_formatted"] = format_size(file_size)
        
        # Check if it's a binary file
        is_binary = is_binary_file(file_path)
        result["is_binary"] = is_binary
        
        if is_binary:
            result["content"] = f"[Binary file: {os.path.basename(file_path)}]"
            result["token_count"] = len(result["content"]) // 4
            return result
        
        # Get file extension
        ext = os.path.splitext(file_path)[1].lower()
        result["extension"] = ext
        
        # Read file content with token awareness
        with open(file_path, encoding='utf-8', errors='replace') as f:
            if sample_only or file_size > 100000:  # Over 100KB, take a sample
                content = f.read(8192)  # Read ~8KB
                result["content"] = content
                result["is_sample"] = True
                result["token_count"] = estimate_tokens(content)
                
                if file_size > 8192:
                    result["content"] += f"\n\n[...file continues, {format_size(file_size - 8192)} remaining...]"
                    
            else:
                # Read the whole file but limit by tokens
                content = f.read()
                token_count = estimate_tokens(content)
                
                if token_count <= max_tokens:
                    result["content"] = content
                    result["token_count"] = token_count
                else:
                    # Truncate to max_tokens
                    encoding = tiktoken.get_encoding("cl100k_base")
                    tokens = encoding.encode(content)
                    truncated = tokens[:max_tokens-100]  # Leave room for message
                    result["content"] = encoding.decode(truncated)
                    result["content"] += f"\n\n[...file truncated, {token_count - len(truncated)} tokens remaining...]"
                    result["token_count"] = max_tokens
                    result["is_truncated"] = True
    
    except Exception as e:
        result["error"] = str(e)
    
    return result


def calculate_recursive_files(directory: dict[str, Any]) -> int:
    """Calculate total number of files in a directory and all its subdirectories."""
    total = directory.get("file_count", 0)
    
    for subdir in directory.get("directories", []):
        total += calculate_recursive_files(subdir)
        
    return total


def calculate_recursive_dirs(directory: dict[str, Any]) -> int:
    """Calculate total number of directories in a directory and all its subdirectories."""
    # Count directories at this level
    total = directory.get("dir_count", 0)
    
    # Add count of subdirectories themselves
    total += len(directory.get("directories", []))
    
    # Add counts from within subdirectories
    for subdir in directory.get("directories", []):
        total += calculate_recursive_dirs(subdir)
        
    return total


def calculate_recursive_tokens(directory: dict[str, Any]) -> int:
    """Calculate total estimated tokens for all text files in a directory and subdirectories."""
    total = 0
    
    # Add tokens from files in this directory
    for file in directory.get("files", []):
        if not file.get("is_binary", True):
            total += file.get("estimated_tokens", 0)
    
    # Add tokens from subdirectories
    for subdir in directory.get("directories", []):
        total += calculate_recursive_tokens(subdir)
        
    return total


def generate_directory_tree(
    directory: dict[str, Any], 
    indent: int = 0,
    max_lines: int = 200,
    calculate_totals: bool = True
) -> list[str]:
    """
    Generate a text representation of a directory tree.
    
    Args:
        directory: Directory structure from scan_directory
        indent: Current indentation level
        max_lines: Maximum number of lines to generate
        
    Returns:
        list of lines representing the directory tree
    """
    if not directory:
        return []
        
    result = []
    prefix = "  " * indent
    
    # Add directory header
    name = directory.get("name", "Unknown")
    size = directory.get("size_formatted", "")
    
    # Calculate total files and directories in this subtree if requested
    if calculate_totals:
        # Use our recursive calculation functions
        total_files = calculate_recursive_files(directory)
        total_dirs = calculate_recursive_dirs(directory)
        header = f"{prefix}{name}/ ({total_files} files, {total_dirs} directories, {size})"
    else:
        # Use direct counts as before
        file_count = directory.get("file_count", 0)
        dir_count = directory.get("dir_count", 0)
        header = f"{prefix}{name}/ ({file_count} files, {dir_count} directories, {size})"
    result.append(header)
    
    # Check for errors
    if "error" in directory:
        result.append(f"{prefix}  [Error: {directory['error']}]")
        return result
    
    # Add files
    for file in directory.get("files", [])[:max_lines//2]:  # Limit files to half the max lines
        file_line = f"{prefix}  {file['name']} ({file.get('size_formatted', '')})"
        result.append(file_line)
    
    # Check if files were truncated
    if directory.get("files_truncated", False):
        total = directory.get("total_files", 0)
        shown = len(directory.get("files", []))
        result.append(f"{prefix}  [...{total - shown} more files...]")
    
    # Add extension summary if available
    if "extensions" in directory:
        result.append(f"{prefix}  File extensions:")
        for ext, info in directory["extensions"].items():
            result.append(f"{prefix}    {ext}: {info['count']} files, {info['size_formatted']}")
    
    # Add subdirectories (recursively)
    for subdir in directory.get("directories", []):
        # Calculate remaining lines
        remaining_lines = max_lines - len(result)
        if remaining_lines <= 0:
            result.append(f"{prefix}  [Tree truncated due to size limits]")
            break
            
        # Generate subdirectory tree with proportional line allocation
        lines_per_dir = remaining_lines // (len(directory["directories"]) - directory["directories"].index(subdir))
        subdir_lines = generate_directory_tree(subdir, indent + 1, lines_per_dir)
        result.extend(subdir_lines)
    
    return result


def get_total_directory_stats(
    path: str, 
    ignore_patterns: list[str] | None = None,
    use_gitignore: bool = True
) -> dict:
    """
    Get comprehensive directory statistics including accurate total file count and disk usage.
    
    This function performs a full directory scan to count ALL files and accurately calculate
    total disk usage. It's designed to provide accurate numbers for very large directories.
    
    Args:
        path: Directory path to scan
        ignore_patterns: list of patterns to ignore (gitignore syntax)
        use_gitignore: Whether to respect .gitignore files
        
    Returns:
        dictionary with total file count, directory count, and disk usage
    """
    # Use the PathFilter class for consistency
    path_filter = create_path_filter(path, ignore_patterns, use_gitignore)
    
    # Initialize counters
    total_files = 0
    total_dirs = 0
    total_size = 0
    
    # Walk through the directory
    for root, dirs, files in os.walk(path):
        # Get relative path for pattern matching
        rel_root = os.path.relpath(root, path)
        if rel_root == '.':
            rel_root = ''
            
        # Filter out ignored directories
        dirs[:] = [d for d in dirs if not path_filter.should_ignore(os.path.join(rel_root, d), is_dir=True)]
        
        # Count directories (excluding the root)
        if rel_root:
            total_dirs += 1
            
        # Process files in this directory
        for file in files:
            file_path = os.path.join(rel_root, file)
            
            # Skip ignored files
            if path_filter.should_ignore(file_path):
                continue
                
            # Count file and size
            total_files += 1
            try:
                total_size += os.path.getsize(os.path.join(root, file))
            except (OSError, PermissionError):
                # Skip files we can't access
                pass
    
    return {
        "total_files": total_files,
        "total_dirs": total_dirs,
        "total_size": total_size,
        "size_formatted": format_size(total_size)
    }
