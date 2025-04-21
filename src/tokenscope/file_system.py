# file_system.py
"""
Token-Aware Directory Explorer

A tool to analyze directory structures while being mindful of token limitations for LLMs.
"""

import os
import sys
import json
import time
import argparse
import fnmatch
import tiktoken
import shutil
from typing import Any


def validate_path(path: str, base_path: str | None = None) -> dict[str, Any]:
    """Validate that a path is within the specified base path for security.
    
    Args:
        path: The path to validate
        base_path: The allowed base path (if None, no validation is performed)
        
    Returns:
        Dictionary with validation results containing:
        - is_valid: Whether the path is valid
        - resolved_path: The resolved absolute path
        - error: Error message if invalid
    """
    result = {
        "is_valid": True,
        "resolved_path": os.path.abspath(path),
        "original_path": path,
        "error": None
    }
    
    # If no base path specified, skip validation
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


def copy_file(source_path: str, destination_path: str, base_path: str | None = None) -> dict[str, Any]:
    """Copy a file from source path to destination path.
    
    Args:
        source_path: Path of the file to copy
        destination_path: Path where the file should be copied to
        base_path: Base directory for security validation; if provided, both
                  source and destination must be within this directory
        
    Returns:
        Dictionary with operation information including status, source and destination details
    """
    result = {
        "source": source_path,
        "destination": destination_path,
        "success": False,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    try:
        # Validate source path
        source_validation = validate_path(source_path, base_path)
        if not source_validation["is_valid"]:
            result["error"] = f"Invalid source path: {source_validation['error']}"
            return result
            
        # Validate destination path
        dest_validation = validate_path(destination_path, base_path)
        if not dest_validation["is_valid"]:
            result["error"] = f"Invalid destination path: {dest_validation['error']}"
            return result
            
        # Use validated paths
        validated_source = source_validation["resolved_path"]
        validated_dest = dest_validation["resolved_path"]
        
        # Check if source file exists
        if not os.path.exists(validated_source):
            result["error"] = f"Source file not found: {validated_source}"
            return result
            
        # Check if source is a file
        if not os.path.isfile(validated_source):
            result["error"] = f"Source is not a file: {validated_source}"
            return result
        
        # Create destination directory if it doesn't exist
        dest_dir = os.path.dirname(validated_dest)
        if dest_dir and not os.path.exists(dest_dir):
            # Validate that we can create this directory
            if base_path and not os.path.abspath(dest_dir).startswith(os.path.abspath(base_path)):
                result["error"] = f"Cannot create directory outside base path: {dest_dir}"
                return result
                
            os.makedirs(dest_dir, exist_ok=True)
            
        # Copy the file
        shutil.copy2(validated_source, validated_dest)
        
        # Get file information for the result
        source_size = os.path.getsize(validated_source)
        dest_size = os.path.getsize(validated_dest)
        
        result.update({
            "success": True,
            "source_size": source_size,
            "source_size_formatted": format_size(source_size),
            "destination_size": dest_size,
            "destination_size_formatted": format_size(dest_size),
            "is_binary": is_binary_file(validated_source)
        })
        
    except Exception as e:
        result["error"] = str(e)
        
    return result


def is_binary_file(file_path: str) -> bool:
    """Detect if a file is binary based on extension or content analysis."""
    # Check extension first
    binary_extensions = {
        '.exe', '.dll', '.so', '.dylib', '.bin', '.obj', '.o',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.tif', '.tiff',
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


def scan_directory(path, max_depth, current_depth=0, quick_scan=False, ignore_filter=None, base_path=None):
    """
    Scan a directory recursively up to max_depth.
    
    Args:
        path: Directory path to scan
        max_depth: Maximum depth to scan
        current_depth: Current depth in the recursion
        quick_scan: If True, only collect counts without details
        ignore_filter: PathIgnoreFilter to exclude files/directories
        base_path: Base directory for security validation
    """
    # Validate path if base_path is provided
    if base_path is not None:
        validation = validate_path(path, base_path)
        if not validation["is_valid"]:
            return {
                'name': os.path.basename(path) or path,
                'path': path,
                'is_dir': True,
                'error': validation["error"],
                'direct_file_count': 0,
                'direct_dir_count': 0,
                'total_file_count': 0,
                'total_dir_count': 0,
                'size': 0
            }
        path = validation["resolved_path"]
    # Check if this directory should be ignored
    if ignore_filter and ignore_filter.should_ignore(path, is_dir=True):
        return None
    
    if current_depth > max_depth and max_depth >= 0:
        return {
            'name': os.path.basename(path),
            'path': path,
            'is_dir': True,
            'truncated': True,
            'direct_file_count': 0,
            'direct_dir_count': 0,
            'total_file_count': 0,
            'total_dir_count': 0,
            'size': 0
        }

    result = {
        'name': os.path.basename(path) or path,  # Use path if root directory
        'path': path,
        'is_dir': True,
        'size': 0,
        'files': [],
        'dirs': [],
        'direct_file_count': 0,
        'direct_dir_count': 0,
        'total_file_count': 0,
        'total_dir_count': 0,
        'token_count': 0,
        'truncated': False
    }

    try:
        entries = list(os.scandir(path))
        
        # Process directories first
        for entry in [e for e in entries if e.is_dir()]:
            # Skip if this subdirectory should be ignored
            if ignore_filter and ignore_filter.should_ignore(entry.path, is_dir=True):
                continue
            subdir = scan_directory(entry.path, max_depth, current_depth + 1, quick_scan)
            if subdir:
                if not quick_scan:
                    result['dirs'].append(subdir)
                result['direct_dir_count'] += 1
                result['total_dir_count'] += 1 + subdir['total_dir_count']
                result['total_file_count'] += subdir['total_file_count']
                result['size'] += subdir['size']
        
        # Process files
        for entry in [e for e in entries if not e.is_dir()]:
            # Skip if this file should be ignored
            if ignore_filter and ignore_filter.should_ignore(entry.path):
                continue
            try:
                file_size = entry.stat().st_size
            except (PermissionError, FileNotFoundError):
                file_size = 0
                
            result['direct_file_count'] += 1
            result['total_file_count'] += 1
            result['size'] += file_size
            
            if not quick_scan:
                file_info = {
                    'name': entry.name,
                    'path': entry.path,
                    'is_dir': False,
                    'size': file_size,
                    'extension': os.path.splitext(entry.name)[1].lower(),
                    'is_binary': None  # Will be determined lazily if needed
                }
                result['files'].append(file_info)
                
    except PermissionError:
        result['error'] = "Permission denied"
    except Exception as e:
        result['error'] = str(e)

    return result


def collect_text_files(directory: dict[str, Any]) -> list[str]:
    """Collect all text files from the directory structure."""
    text_files = []
    
    # Process this directory's files
    for file in directory.get('files', []):
        if not is_binary_file(file['path']):
            text_files.append(file['path'])
    
    # Process subdirectories
    for subdir in directory.get('dirs', []):
        text_files.extend(collect_text_files(subdir))
    
    return text_files


def find_files(directory: dict[str, Any], pattern: str) -> list[str]:
    """Find files matching a pattern in the directory structure."""
    matching_files = []
    
    # Check if this directory matches
    if fnmatch.fnmatch(directory['path'], pattern):
        matching_files.append(directory['path'])
    
    # Check files in this directory
    for file in directory.get('files', []):
        if fnmatch.fnmatch(file['path'], pattern) or fnmatch.fnmatch(file['name'], pattern):
            matching_files.append(file['path'])
    
    # Check subdirectories
    for subdir in directory.get('dirs', []):
        matching_files.extend(find_files(subdir, pattern))
    
    return matching_files


def extract_file_content_utility(file_path: str, max_tokens: int = 50000, sample_only: bool = False, base_path: str | None = None) -> tuple[str, int]:
    """Extract content from a file, respecting token limits and optionally just taking a sample."""
    # Validate the path if base_path is provided
    if base_path is not None:
        validation = validate_path(file_path, base_path)
        if not validation["is_valid"]:
            return f"Error: {validation['error']}", 0
        file_path = validation["resolved_path"]
    if is_binary_file(file_path):
        return f"[Binary file: {os.path.basename(file_path)}]", 0
    
    try:
        # For JSON files, try to show a meaningful sample
        if file_path.lower().endswith('.json'):
            with open(file_path, encoding='utf-8', errors='replace') as f:
                try:
                    # Try to load as JSON to get structure
                    import json
                    
                    # Only read part of the file to check structure
                    sample = f.read(10000)
                    try:
                        data = json.loads(sample)
                        # If it's not a complete JSON object, read the full file
                        if not sample.strip().endswith('}') and not sample.strip().endswith(']'):
                            f.seek(0)
                            data = json.loads(f.read())
                    except json.JSONDecodeError:
                        # If partial read fails, try reading the whole file
                        f.seek(0)
                        data = json.loads(f.read())
                    
                    # For arrays, show the first few items
                    if isinstance(data, list):
                        sample_size = min(3, len(data))
                        if sample_only or len(data) > 10:
                            content = json.dumps(data[:sample_size], indent=2)
                            content += f"\n\n[...{len(data) - sample_size} more items...]"
                            if sample_size < len(data):
                                content += f"\n\n{json.dumps(data[-1], indent=2)}"
                        else:
                            content = json.dumps(data, indent=2)
                    # For objects, show a summary
                    elif isinstance(data, dict):
                        if sample_only or len(str(data)) > 1000:
                            # Show top-level keys and sample some values
                            summary = {k: str(v)[:100] + '...' if isinstance(v, (str, list, dict)) and len(str(v)) > 100 else v 
                                      for k, v in list(data.items())[:5]}
                            content = json.dumps(summary, indent=2)
                            if len(data) > 5:
                                content += f"\n\n[...{len(data) - 5} more keys...]"
                        else:
                            content = json.dumps(data, indent=2)
                    else:
                        content = json.dumps(data, indent=2)
                    
                    token_count = estimate_tokens(content)
                    return content, token_count
                except json.JSONDecodeError:
                    # If JSON parsing fails, fall back to regular text processing
                    f.seek(0)
                    pass
        
        # Normal text file handling
        if sample_only:
            with open(file_path, encoding='utf-8', errors='replace') as f:
                content = f.read(2000)  # Read just the first 2000 chars
                file_size = os.path.getsize(file_path)
                content += f"\n\n[...file continues for {format_size(file_size)}...]"
            token_count = estimate_tokens(content)
        else:
            # Read the entire file
            with open(file_path, encoding='utf-8', errors='replace') as f:
                content = f.read()
            
            token_count = estimate_tokens(content)
            if token_count > max_tokens:
                # Truncate content if it exceeds token limit
                encoding = tiktoken.get_encoding("cl100k_base")
                tokens = encoding.encode(content)
                truncated_tokens = tokens[:max_tokens-100]  # Leave room for message
                content = encoding.decode(truncated_tokens)
                content += f"\n\n[...{token_count - len(truncated_tokens)} more tokens...]"
                token_count = estimate_tokens(content)
        return content, token_count
    except Exception as e:
        return f"[Error reading file: {str(e)}]", 0

def format_directory_tree(directory: dict[str, Any], indent: int = 0, 
                         max_tokens: int = 50000, current_tokens: int = 0) -> tuple[list[str], int]:
    """Format directory tree as text with token tracking."""
    result = []
    prefix = "  " * indent
    
    # Format the directory header
    if directory.get('truncated', False):
        header = f"{prefix}{directory['name']}/ [Directory truncated at depth limit]"
    else:
        header = f"{prefix}{directory['name']}/ ({directory['total_file_count']} files, {directory['total_dir_count']} folders, {format_size(directory['size'])})"
    
    result.append(header)
    header_tokens = estimate_tokens(header)
    current_tokens += header_tokens
    
    if 'error' in directory:
        error_line = f"{prefix}  [Error: {directory['error']}]"
        result.append(error_line)
        error_tokens = estimate_tokens(error_line)
        current_tokens += error_tokens
    
    # Check if we need to do intelligent summarization
    if current_tokens > max_tokens * 0.1 and len(directory.get('files', [])) > 20:
        return summarize_directory_tree(directory, indent, max_tokens, current_tokens)
    
    # Add files
    files = sorted(directory.get('files', []), key=lambda x: x['name'].lower())
    for file in files:
        file_line = f"{prefix}  {file['name']} ({format_size(file['size'])})"
        tokens_needed = estimate_tokens(file_line)
        
        if current_tokens + tokens_needed > max_tokens:
            remaining = len(files) - len(result) + 1
            summary = f"{prefix}  [Token limit reached, {remaining} more files not shown]"
            result.append(summary)
            current_tokens += estimate_tokens(summary)
            break
            
        result.append(file_line)
        current_tokens += tokens_needed
    
    # Add subdirectories
    dirs = sorted(directory.get('dirs', []), key=lambda x: x['name'].lower())
    for subdir in dirs:
        # Allocate token budget for this subdirectory
        subdir_budget = (max_tokens - current_tokens) // (len(dirs) - dirs.index(subdir) or 1)
        
        subdir_result, subdir_tokens = format_directory_tree(
            subdir, indent + 1, subdir_budget, 0
        )
        
        if current_tokens + subdir_tokens > max_tokens:
            remaining = len(dirs) - dirs.index(subdir)
            summary = f"{prefix}  [Token limit reached, {remaining} more directories not shown]"
            result.append(summary)
            current_tokens += estimate_tokens(summary)
            break
            
        result.extend(subdir_result)
        current_tokens += subdir_tokens
    
    return result, current_tokens


def summarize_directory_tree(directory: dict[str, Any], indent: int, 
                            max_tokens: int, current_tokens: int) -> tuple[list[str], int]:
    """Create a summarized version of the directory tree when full listing would be too large."""
    result = []
    prefix = "  " * indent
    
    # Group files by extension
    extensions = {}
    for file in directory.get('files', []):
        ext = file['extension'] or '[no extension]'
        if ext not in extensions:
            extensions[ext] = []
        extensions[ext].append(file)
    
    # Format extension groups
    for ext, files in sorted(extensions.items()):
        if len(files) <= 3:  # Show all files if there are just a few
            for file in sorted(files, key=lambda x: x['name']):
                file_line = f"{prefix}  {file['name']} ({format_size(file['size'])})"
                result.append(file_line)
                current_tokens += estimate_tokens(file_line)
        else:
            # Show summary with examples
            total_size = sum(f['size'] for f in files)
            examples = sorted([f['name'] for f in files], key=lambda x: x.lower())[:3]
            examples_str = ", ".join(examples)
            
            summary = f"{prefix}  {ext} files: {len(files)} files, {format_size(total_size)} total (e.g., {examples_str})"
            result.append(summary)
            current_tokens += estimate_tokens(summary)
    
    # Summarize subdirectories
    dirs = directory.get('dirs', [])
    
    if len(dirs) <= 5:  # Show all subdirectories if there are just a few
        for subdir in sorted(dirs, key=lambda x: x['name'].lower()):
            # Recursively summarize each subdirectory
            subdir_summary, subdir_tokens = summarize_directory_tree(
                subdir, indent + 1, max_tokens - current_tokens, 0
            )
            
            if current_tokens + subdir_tokens > max_tokens:
                remaining = len(dirs) - dirs.index(subdir)
                summary = f"{prefix}  [Token limit reached, {remaining} more directories not shown]"
                result.append(summary)
                current_tokens += estimate_tokens(summary)
                break
                
            result.extend(subdir_summary)
            current_tokens += subdir_tokens
    else:
        # Show summary with a few examples
        examples = sorted([d['name'] for d in dirs], key=lambda x: x.lower())[:5]
        examples_str = ", ".join(examples)
        
        summary = f"{prefix}  [Contains {len(dirs)} subdirectories, including: {examples_str}]"
        result.append(summary)
        current_tokens += estimate_tokens(summary)
        
        # Show the largest subdirectories
        largest_dirs = sorted(dirs, key=lambda x: x['total_file_count'], reverse=True)[:3]
        for subdir in largest_dirs:
            subdir_header = f"{prefix}  {subdir['name']}/ ({subdir['total_file_count']} files, {subdir['total_dir_count']} folders)"
            result.append(subdir_header)
            current_tokens += estimate_tokens(subdir_header)
    
    return result, current_tokens


def get_directory_from_path(directory_tree: dict[str, Any], path: str) -> dict[str, Any] | None:
    """Retrieve a specific subdirectory from the directory tree."""
    # If path is the root directory
    if path == directory_tree['path']:
        return directory_tree
    
    # Check if the path is a direct subdirectory
    for subdir in directory_tree.get('dirs', []):
        if subdir['path'] == path:
            return subdir
        
        # Recursively check deeper directories
        if path.startswith(subdir['path']):
            result = get_directory_from_path(subdir, path)
            if result:
                return result
                
    return None


class PathIgnoreFilter:
    """Filter paths based on gitignore-style patterns."""
    
    def __init__(self, patterns=None, gitignore_file=None):
        """
        Initialize with patterns or a gitignore file.
        
        Args:
            patterns: List of gitignore-style patterns
            gitignore_file: Path to a gitignore file
        """
        self.patterns = patterns or []
        
        # Load patterns from gitignore file if specified
        if gitignore_file and os.path.isfile(gitignore_file):
            with open(gitignore_file, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith('#'):
                        self.patterns.append(line)
    
    def should_ignore(self, path, is_dir=False):
        """Check if a path should be ignored based on the patterns."""
        # Normalize path for consistent matching
        rel_path = os.path.normpath(path)
        
        # Track if path should be included or excluded
        should_exclude = False
        
        for pattern in self.patterns:
            # Handle negation patterns (those starting with !)
            is_negation = pattern.startswith('!')
            if is_negation:
                pattern = pattern[1:].strip()
            
            # Skip empty patterns
            if not pattern:
                continue
            
            # Match the pattern against the path
            if self._match_pattern(pattern, rel_path, is_dir):
                # If it's a negation pattern, mark for inclusion
                should_exclude = not is_negation
        
        return should_exclude
    
    def _match_pattern(self, pattern, path, is_dir):
        """Match a single pattern against a path."""
        # Normalize pattern
        pattern = pattern.rstrip('/')
        
        # Handle directory-only patterns (ending with '/')
        if pattern.endswith('/') and not is_dir:
            return False
        
        # Handle patterns that start with '/'
        if pattern.startswith('/'):
            # Remove the leading '/' for absolute pattern matching
            pattern = pattern[1:]
            return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, f"*/{pattern}")
        else:
            # For normal patterns, match against the basename or any path part
            basename = os.path.basename(path)
            return (fnmatch.fnmatch(basename, pattern) or 
                   fnmatch.fnmatch(path, pattern) or 
                   fnmatch.fnmatch(path, f"*/{pattern}"))


class TokenBudgetManager:
    """Manages token allocation between structure and content."""
    
    def __init__(self, structure_tokens: int, content_tokens: int, total_tokens: int):
        self.structure_tokens = structure_tokens
        self.content_tokens = content_tokens
        self.total_tokens = total_tokens
        self.structure_used = 0
        self.content_used = 0
    
    def adjust_budgets(self, directory_complexity: float):
        """Adjust token allocation based on directory complexity."""
        # More complex directory = more tokens for structure
        if directory_complexity > 0.7:
            # Allocate more to structure
            self.structure_tokens = int(self.total_tokens * 0.7)
            self.content_tokens = self.total_tokens - self.structure_tokens
        elif directory_complexity < 0.3:
            # Allocate more to content
            self.content_tokens = int(self.total_tokens * 0.7)
            self.structure_tokens = self.total_tokens - self.content_tokens
    
    def get_structure_budget(self) -> int:
        """Get remaining token budget for structure."""
        return self.structure_tokens - self.structure_used
    
    def get_content_budget(self) -> int:
        """Get remaining token budget for content."""
        return self.content_tokens - self.content_used
    
    def update_structure_usage(self, tokens: int):
        """Update the structure token usage."""
        self.structure_used += tokens
    
    def update_content_usage(self, tokens: int):
        """Update the content token usage."""
        self.content_used += tokens


def calculate_directory_complexity(directory: dict[str, Any]) -> float:
    """Calculate directory complexity as a value from 0 to 1."""
    total_files = directory['total_file_count']
    total_dirs = directory['total_dir_count']
    
    # Calculate max depth
    def get_max_depth(dir_node, current_depth=0):
        if not dir_node.get('dirs'):
            return current_depth
        
        subdepths = [get_max_depth(subdir, current_depth + 1) 
                    for subdir in dir_node.get('dirs', [])]
        return max(subdepths) if subdepths else current_depth
    
    max_depth = get_max_depth(directory)
    
    # Count unique file extensions
    extensions = set()
    def collect_extensions(dir_node):
        for file in dir_node.get('files', []):
            extensions.add(file.get('extension', ''))
        
        for subdir in dir_node.get('dirs', []):
            collect_extensions(subdir)
    
    collect_extensions(directory)
    extension_variety = len(extensions)
    
    # Calculate complexity score (0 to 1)
    file_factor = min(1.0, total_files / 1000)  # Normalize file count
    dir_factor = min(1.0, total_dirs / 100)     # Normalize directory count
    depth_factor = min(1.0, max_depth / 10)     # Normalize depth
    variety_factor = min(1.0, extension_variety / 20)  # Normalize extension variety
    
    # Weighted average of factors
    complexity = (file_factor * 0.4 + 
                  dir_factor * 0.3 + 
                  depth_factor * 0.2 + 
                  variety_factor * 0.1)
    
    return complexity


def prioritize_files(files: list[str], max_tokens: int) -> list[str]:
    """Intelligently select important files when not all can fit in token limits."""
    # Define importance score for common files
    def importance_score(filename):
        basename = os.path.basename(filename).lower()
        
        if 'readme' in basename:
            return 100
        if basename in ('requirements.txt', 'package.json', 'setup.py'):
            return 90
        if basename in ('config.json', '.env.example', 'dockerfile'):
            return 80
        if basename.startswith('main.') or basename.startswith('index.'):
            return 70
        if basename == 'license':
            return 60
        
        # Prioritize certain extensions
        ext = os.path.splitext(basename)[1].lower()
        if ext in ('.py', '.js', '.java', '.c', '.cpp', '.go', '.rs'):
            return 50
        if ext in ('.md', '.txt', '.json', '.yaml', '.yml', '.toml'):
            return 40
        
        return 10  # Default importance
    
    # Sort files by importance
    sorted_files = sorted(files, key=importance_score, reverse=True)
    
    # Group files by extension to ensure variety
    extension_groups = {}
    for file in sorted_files:
        ext = os.path.splitext(file)[1].lower() or '[no extension]'
        if ext not in extension_groups:
            extension_groups[ext] = []
        extension_groups[ext].append(file)
    
    # Interleave files from different extension groups
    prioritized_files = []
    while extension_groups:
        for ext in list(extension_groups.keys()):
            if extension_groups[ext]:
                prioritized_files.append(extension_groups[ext].pop(0))
                if not extension_groups[ext]:
                    del extension_groups[ext]
            
            # Check if we've reached capacity
            token_estimate = 0
            for path in prioritized_files:
                # Get file size as proxy for tokens
                try:
                    size = os.path.getsize(path)
                    # Very rough estimate: 1 token ≈ 4 bytes
                    token_estimate += min(size // 4, 1000)  # Cap per-file estimate
                    # Add overhead for file headers
                    token_estimate += 50
                except:
                    token_estimate += 100  # Default estimate
            
            if token_estimate >= max_tokens:
                return prioritized_files
    
    return prioritized_files


def main():
    """Main entry point for the Token-Aware Directory Explorer."""
    parser = argparse.ArgumentParser(description="Token-Aware Directory Explorer")
    parser.add_argument("path", nargs='?', default=".", help="Directory path to explore")
    parser.add_argument("--depth", type=int, default=3, help="Maximum exploration depth (default: 3)")
    parser.add_argument("--structure-tokens", type=int, default=10000, help="Maximum tokens for directory structure (default: 10,000)")
    parser.add_argument("--content-tokens", type=int, default=50000, help="Maximum tokens for file contents (default: 50,000)")
    parser.add_argument("--content", action="store_true", help="Include file contents in the report")
    parser.add_argument("--files", nargs="+", help="Specific files to include content for")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")
    parser.add_argument("--subdir", help="Focus on a specific subdirectory")
    parser.add_argument("--auto-budget", action="store_true", help="Automatically adjust token allocation")
    parser.add_argument("--omit", nargs="+", help="Patterns of files/directories to ignore (gitignore syntax)")
    parser.add_argument("--gitignore", action="store_true", help="Use .gitignore file in the target directory")
    parser.add_argument("--sample", action="store_true", help="Show samples of files instead of full content")
    
    args = parser.parse_args()
    
    # Resolve path
    explore_path = os.path.abspath(args.path)
    if not os.path.exists(explore_path):
        print(f"Error: Path not found: {explore_path}")
        return 1
    
    # Create ignore filter
    ignore_filter = None
    if args.omit or args.gitignore:
        gitignore_file = os.path.join(explore_path, '.gitignore') if args.gitignore else None
        ignore_filter = PathIgnoreFilter(args.omit, gitignore_file)
    
    print(f"Scanning directory: {explore_path}")
    start_time = time.time()
    
    # Perform a single comprehensive scan
    print("Scanning directory structure...")
    directory_tree = scan_directory(explore_path, args.depth, ignore_filter=ignore_filter)
    
    # Calculate complexity based on the scan results
    complexity = calculate_directory_complexity(directory_tree)
    print(f"Directory complexity: {complexity:.2f} (0-1 scale)")
    
    # Initialize token budget manager
    budget_manager = TokenBudgetManager(args.structure_tokens, args.content_tokens, 
                                       args.structure_tokens + args.content_tokens)
    
    # Adjust budgets if auto-budgeting is enabled
    if args.auto_budget:
        budget_manager.adjust_budgets(complexity)
        print(f"Adjusted token allocation: {budget_manager.structure_tokens} for structure, "
              f"{budget_manager.content_tokens} for content")
    
    print(f"Scan completed in {time.time() - start_time:.2f} seconds")
    print(f"Found {directory_tree['total_file_count']} files in {directory_tree['total_dir_count']} directories")
    
    # Focus on subdirectory if specified
    if args.subdir:
        target_path = os.path.abspath(args.subdir)
        target_dir = get_directory_from_path(directory_tree, target_path)
        if target_dir:
            directory_tree = target_dir
            print(f"Focusing on subdirectory: {target_path}")
        else:
            print(f"Warning: Subdirectory not found: {target_path}")
    
    # Generate and display directory structure
    if args.json:
        # Remove 'token_count' field from JSON output to simplify it
        def clean_for_json(dir_node):
            if 'token_count' in dir_node:
                del dir_node['token_count']
            
            for subdir in dir_node.get('dirs', []):
                clean_for_json(subdir)
            
            return dir_node
        
        clean_tree = clean_for_json(directory_tree)
        print(json.dumps(clean_tree, indent=2))
    else:
        print("\nDIRECTORY STRUCTURE:", explore_path)
        print("=" * 80)
        tree_text, tree_tokens = format_directory_tree(
            directory_tree, max_tokens=budget_manager.structure_tokens
        )
        print("\n".join(tree_text))
        print(f"\nStructure used approximately {tree_tokens} tokens")
        budget_manager.update_structure_usage(tree_tokens)
        
        # Extract and display file contents if requested
        if args.content or args.files:
            print("\nFILE CONTENTS")
            print("=" * 80)
            
            files_to_process = []
            if args.files:
                # Process specific files
                for file_pattern in args.files:
                    matching_files = find_files(directory_tree, file_pattern)
                    files_to_process.extend(matching_files)
                print(f"Found {len(files_to_process)} files matching specified patterns")
            else:
                # Process all text files up to the token limit
                all_text_files = collect_text_files(directory_tree)
                
                # With sample mode, include more files
                if args.sample:
                    max_sample_files = 20  # Show samples from up to 20 files
                    # Sort by different file extensions to get variety
                    by_ext = {}
                    for f in all_text_files:
                        ext = os.path.splitext(f)[1].lower() or '[no extension]'
                        if ext not in by_ext:
                            by_ext[ext] = []
                        by_ext[ext].append(f)
                    
                    # Get one from each extension first
                    samples = []
                    for ext_files in by_ext.values():
                        if ext_files:
                            samples.append(ext_files[0])
                    
                    files_to_process = samples[:max_sample_files]
                    print(f"Showing samples from {len(files_to_process)} files")
                else:
                    files_to_process = prioritize_files(all_text_files, budget_manager.content_tokens)
                    print(f"Selected {len(files_to_process)} files from {len(all_text_files)} text files")
            
            total_content_tokens = 0
            files_processed = 0
            
            for file_path in files_to_process:
                remaining_tokens = budget_manager.content_tokens - total_content_tokens
                if remaining_tokens <= 100:  # Keep some tokens for the summary
                    print(f"\n[Token limit reached. Showing {files_processed} of {len(files_to_process)} files]")
                    break
                
                print(f"\nFILE: {file_path}")
                print("-" * 80)
                
                # JSON file special handling
                if file_path.lower().endswith('.json'):
                    try:
                        with open(file_path, encoding='utf-8', errors='replace') as f:
                            # Sample just the beginning to determine structure
                            sample = f.read(10000)
                            try:
                                data = json.loads(sample)
                                # If sample isn't complete JSON, read the whole file
                                if not sample.strip().endswith('}') and not sample.strip().endswith(']'):
                                    f.seek(0)
                                    data = json.loads(f.read())
                            except json.JSONDecodeError:
                                # If sample isn't valid JSON, read the whole file
                                f.seek(0)
                                data = json.loads(f.read())
                        
                        # For arrays, show first few and last item
                        if isinstance(data, list):
                            if len(data) > 5 or args.sample:
                                sample_size = min(3, len(data))
                                content = json.dumps(data[:sample_size], indent=2)
                                if len(data) > sample_size:
                                    content += f"\n\n[...{len(data) - sample_size - 1} more items...]"
                                    content += f"\n\n{json.dumps(data[-1], indent=2)}"
                                print(content)
                                total_content_tokens += estimate_tokens(content)
                                files_processed += 1
                                continue
                        # For large objects in sample mode, summarize
                        elif isinstance(data, dict) and (len(data) > 10 or args.sample):
                            keys_to_show = min(5, len(data))
                            sample_dict = {k: data[k] for k in list(data.keys())[:keys_to_show]}
                            content = json.dumps(sample_dict, indent=2)
                            if len(data) > keys_to_show:
                                content += f"\n\n[...{len(data) - keys_to_show} more keys...]"
                            print(content)
                            total_content_tokens += estimate_tokens(content)
                            files_processed += 1
                            continue
                    except Exception:
                        # Fall back to normal processing if JSON handling fails
                        pass
                
                # Normal processing (no chunking)
                content, tokens = extract_file_content_utility(
                    file_path, 
                    remaining_tokens, 
                    sample_only=args.sample or (file_path.lower().endswith('.json') and os.path.getsize(file_path) > 10000)
                )
                print(content)
                total_content_tokens += tokens
                files_processed += 1
            
            print(f"\nContent used approximately {total_content_tokens} tokens")
            budget_manager.update_content_usage(total_content_tokens)
            
            # Final summary
            print("\nTOKEN USAGE SUMMARY")
            print("=" * 80)
            print(f"Structure tokens: {budget_manager.structure_used} of {budget_manager.structure_tokens}")
            print(f"Content tokens:   {budget_manager.content_used} of {budget_manager.content_tokens}")
            print(f"Total tokens:     {budget_manager.structure_used + budget_manager.content_used} of {budget_manager.total_tokens}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())