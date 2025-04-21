# token_scope.py
"""
Token-Aware Directory Explorer

A tool to analyze directory structures while being mindful of token limitations for LLMs.
"""
from fastmcp import FastMCP, Context
from typing import Any
import os
from datetime import datetime

# Import functionality from our file system module
from tokenscope.file_system import (
    scan_directory, 
    format_directory_tree,
    extract_file_content_utility,
    is_binary_file,
    estimate_tokens,
    format_size,
    find_files as _find_files,
    PathIgnoreFilter,
    prioritize_files,
    copy_file
)

# Global base path for security validation
def set_base_path(base_path: str):
    global BASE_PATH
    BASE_PATH = base_path
    

# Create an MCP server
mcp = FastMCP(
    "TokenScope",
    on_duplicate_tools="error",
    description="Explore directory structures with token awareness for LLMs",
    dependencies=["tiktoken"]
)

# Default ignore patterns for common directories and files
DEFAULT_IGNORE_PATTERNS = [
    ".git/",
    ".venv/",
    "venv/",
    "__pycache__/",
    "node_modules/",
    ".pytest_cache/",
    ".ipynb_checkpoints/",
    ".DS_Store",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.so",
    "*.dll",
    "*.class",
    "build/",
    "dist/",
    "*.egg-info/",
    ".tox/",
    ".coverage",
    ".idea/",
    ".vscode/",
    ".mypy_cache/",
]

# --- Tools ---

@mcp.tool()
async def scan_directory_structure(
    path: str, 
    depth: int = 3,
    max_tokens: int = 10000,
    ignore_patterns: list[str] | None = None,
    include_gitignore: bool = True,
    include_default_ignores: bool = True
) -> dict[str, Any]:
    """
    Scans a directory and returns its structure in a token-efficient way.
    
    This tool performs a recursive scan of the specified directory, creating a detailed
    representation of the directory structure including files, subdirectories, and their sizes.
    The resulting structure is optimized to stay within token limits while providing
    maximum useful information.
    
    Args:
        path: Directory path to scan
        depth: Maximum depth to traverse (default: 3)
        max_tokens: Maximum tokens for the structure output (default: 10000)
        ignore_patterns: List of patterns to ignore (gitignore syntax)
        include_gitignore: Whether to respect .gitignore files (default: True)
        include_default_ignores: Whether to use built-in default ignores (default: True)
    
    Returns:
        Dictionary with directory structure information, including:
        - Full directory tree object
        - Formatted text representation
        - Token count
        - File and directory statistics
        - Size information
    """
    # Resolve path
    explore_path = os.path.abspath(path)
    if not os.path.exists(explore_path):
        return {"error": f"Path not found: {explore_path}"}
    
    # Create ignore patterns list
    patterns = []
    if ignore_patterns:
        patterns.extend(ignore_patterns)
    if include_default_ignores:
        patterns.extend(DEFAULT_IGNORE_PATTERNS)
    
    # Create ignore filter
    ignore_filter = None
    if patterns or include_gitignore:
        gitignore_file = os.path.join(explore_path, '.gitignore') if include_gitignore else None
        ignore_filter = PathIgnoreFilter(patterns, gitignore_file)
    
    # Scan directory with base path validation
    directory_tree = scan_directory(explore_path, depth, ignore_filter=ignore_filter, base_path=BASE_PATH)
    
    # Format the tree as text
    tree_text, tree_tokens = format_directory_tree(
        directory_tree, max_tokens=max_tokens
    )
    
    return {
        "directory": directory_tree,
        "tree_text": "\n".join(tree_text),
        "token_count": tree_tokens,
        "total_files": directory_tree["total_file_count"],
        "total_directories": directory_tree["total_dir_count"],
        "total_size": format_size(directory_tree["size"]),
        "ignored_patterns": patterns if include_default_ignores else ignore_patterns,
        "gitignore_used": include_gitignore
    }


@mcp.tool()
async def extract_file_content(
    file_path: str, 
    max_tokens: int = 10000,
    sample_only: bool = False
) -> dict[str, Any]:
    """
    Extracts the content of a specific file, respecting token limits and format.
    
    This tool intelligently extracts file content while maintaining token awareness.
    It handles binary detection, provides token counts, and can generate file samples
    instead of full content when requested. Special handling is provided for common
    file formats like JSON.
    
    Args:
        file_path: Path to the file to extract content from
        max_tokens: Maximum tokens to return (default: 10000)
        sample_only: If True, return only a sample of the file (default: False)
    
    Returns:
        Dictionary with file content information, including:
        - File path and size
        - Binary detection status
        - Extracted content
        - Token count
        - File extension
    """
    # Resolve path
    file_path = os.path.abspath(file_path)
    
    # Check if file exists
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    # Check if it's a directory
    if os.path.isdir(file_path):
        return {"error": f"Path is a directory, not a file: {file_path}"}
    
    # Get file details
    try:
        file_size = os.path.getsize(file_path)
        file_binary = is_binary_file(file_path)
        
        # Extract content with base path validation
        content, token_count = extract_file_content_utility(file_path, max_tokens, sample_only, BASE_PATH)
        
        return {
            "path": file_path,
            "size": file_size,
            "size_formatted": format_size(file_size),
            "is_binary": file_binary,
            "content": content,
            "token_count": token_count,
            "extension": os.path.splitext(file_path)[1].lower()
        }
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}


@mcp.tool()
async def search_files_by_pattern(
    directory: str,
    patterns: list[str],
    max_depth: int = 5,
    include_content: bool = False,
    max_files: int = 100,
    max_tokens_per_file: int = 1000,
    sample_only: bool = False,
    ignore_patterns: list[str] | None = None,
    include_gitignore: bool = True,
    include_default_ignores: bool = True
) -> dict[str, Any]:
    """
    Searches for files matching specified patterns within a directory structure.
    
    This tool performs a pattern-based search across a directory structure to find matching
    files. It can optionally include file contents in the results and applies various
    filters to exclude irrelevant files. Pattern matching uses gitignore-style syntax.
    
    Args:
        directory: Base directory to search in
        patterns: List of patterns to match (e.g. ["*.py", "README*"])
        max_depth: Maximum directory depth to search (default: 5)
        include_content: Whether to include file contents (default: False)
        max_files: Maximum number of files to return (default: 100)
        max_tokens_per_file: Maximum tokens per file if including content (default: 1000)
        sample_only: Whether to show only a sample of each file (default: False)
        ignore_patterns: List of patterns to ignore (gitignore syntax)
        include_gitignore: Whether to respect .gitignore files (default: True)
        include_default_ignores: Whether to use built-in default ignores (default: True)
    
    Returns:
        Dictionary with matching files information, including:
        - List of matching file paths
        - Count statistics
        - Detailed information for each file
        - Content when requested
    """
    # Resolve path
    base_dir = os.path.abspath(directory)
    if not os.path.exists(base_dir):
        return {"error": f"Directory not found: {base_dir}"}
    
    # Create ignore patterns list
    all_patterns = []
    if ignore_patterns:
        all_patterns.extend(ignore_patterns)
    if include_default_ignores:
        all_patterns.extend(DEFAULT_IGNORE_PATTERNS)
    
    # Create ignore filter
    ignore_filter = None
    if all_patterns or include_gitignore:
        gitignore_file = os.path.join(base_dir, '.gitignore') if include_gitignore else None
        ignore_filter = PathIgnoreFilter(all_patterns, gitignore_file)
    
    # Scan directory with base path validation
    directory_tree = scan_directory(base_dir, max_depth, ignore_filter=ignore_filter, base_path=BASE_PATH)
    
    # Find files matching patterns
    matching_files = []
    for pattern in patterns:
        matches = _find_files(directory_tree, pattern)
        matching_files.extend(matches)
    
    # Remove duplicates while preserving order
    unique_files = []
    seen = set()
    for file in matching_files:
        if file not in seen:
            unique_files.append(file)
            seen.add(file)
    
    matching_files = unique_files[:max_files]
    
    # Prepare result
    result = {
        "matching_files": matching_files,
        "count": len(matching_files),
        "truncated": len(unique_files) > max_files,
        "files_info": [],
        "ignored_patterns": all_patterns if include_default_ignores else ignore_patterns,
        "gitignore_used": include_gitignore
    }
    
    # Add file information
    for file_path in matching_files:
        file_info = {
            "path": file_path,
            "size": os.path.getsize(file_path),
            "size_formatted": format_size(os.path.getsize(file_path)),
            "is_binary": is_binary_file(file_path)
        }
        
        # Include content if requested
        if include_content and not file_info["is_binary"]:
            content, tokens = extract_file_content_utility(file_path, max_tokens_per_file, sample_only=sample_only, base_path=BASE_PATH)
            file_info["content"] = content
            file_info["token_count"] = tokens
        
        result["files_info"].append(file_info)
    
    return result


@mcp.tool()
async def analyze_token_usage(
    path: str,
    include_file_details: bool = False,
    ignore_patterns: list[str] | None = None,
    include_gitignore: bool = True,
    include_default_ignores: bool = True
) -> dict[str, Any]:
    """
    Analyzes token usage for a directory or file to estimate LLM processing requirements.
    
    This tool provides a detailed analysis of token usage across files in a directory
    or for a single file. It helps estimate how many tokens would be required to process
    the content with an LLM. For directories, it provides breakdowns by file extension
    and can optionally include per-file details.
    
    Args:
        path: Path to directory or file to analyze
        include_file_details: Whether to include per-file token statistics (default: False)
        ignore_patterns: List of patterns to ignore (gitignore syntax)
        include_gitignore: Whether to respect .gitignore files (default: True)
        include_default_ignores: Whether to use built-in default ignores (default: True)
    
    Returns:
        Dictionary with token analysis information, including:
        - Total token count
        - File counts (text vs binary)
        - Size information
        - Extension breakdown with token statistics
        - Optional per-file details
    """
    # Resolve path
    target_path = os.path.abspath(path)
    if not os.path.exists(target_path):
        return {"error": f"Path not found: {target_path}"}
    
    result = {
        "path": target_path,
        "is_directory": os.path.isdir(target_path),
        "total_tokens": 0,
        "total_size": 0
    }
    
    # If it's a file, estimate tokens for it
    if not result["is_directory"]:
        if is_binary_file(target_path):
            result["is_binary"] = True
            result["total_tokens"] = 0
        else:
            try:
                with open(target_path, encoding='utf-8', errors='replace') as f:
                    content = f.read()
                token_count = estimate_tokens(content)
                result["total_tokens"] = token_count
                result["total_size"] = os.path.getsize(target_path)
                result["size_formatted"] = format_size(result["total_size"])
            except Exception as e:
                return {"error": f"Error reading file: {str(e)}"}
        return result
    
    # Create ignore patterns list
    all_patterns = []
    if ignore_patterns:
        all_patterns.extend(ignore_patterns)
    if include_default_ignores:
        all_patterns.extend(DEFAULT_IGNORE_PATTERNS)
    
    # Create ignore filter
    ignore_filter = None
    if all_patterns or include_gitignore:
        gitignore_file = os.path.join(target_path, '.gitignore') if include_gitignore else None
        ignore_filter = PathIgnoreFilter(all_patterns, gitignore_file)
    
    # For directories, scan and analyze all text files
    directory_tree = scan_directory(target_path, max_depth=10, ignore_filter=ignore_filter, base_path=BASE_PATH)
    
    # Add ignore info to result
    result["ignored_patterns"] = all_patterns if include_default_ignores else ignore_patterns
    result["gitignore_used"] = include_gitignore
    
    # Collect all text files
    all_files = []
    def collect_files(dir_node):
        for file in dir_node.get('files', []):
            all_files.append(file['path'])
        for subdir in dir_node.get('dirs', []):
            collect_files(subdir)
    
    collect_files(directory_tree)
    result["total_files"] = len(all_files)
    result["total_size"] = directory_tree["size"]
    result["size_formatted"] = format_size(directory_tree["size"])
    
    # Analyze text files for tokens
    text_files = []
    binary_files = []
    file_details = []
    total_tokens = 0
    
    for file_path in all_files:
        is_binary = is_binary_file(file_path)
        file_size = os.path.getsize(file_path)
        
        if is_binary:
            binary_files.append(file_path)
            if include_file_details:
                file_details.append({
                    "path": file_path,
                    "size": file_size,
                    "size_formatted": format_size(file_size),
                    "is_binary": True,
                    "tokens": 0
                })
        else:
            text_files.append(file_path)
            try:
                with open(file_path, encoding='utf-8', errors='replace') as f:
                    content = f.read()
                token_count = estimate_tokens(content)
                total_tokens += token_count
                
                if include_file_details:
                    file_details.append({
                        "path": file_path,
                        "size": file_size,
                        "size_formatted": format_size(file_size),
                        "is_binary": False,
                        "tokens": token_count
                    })
            except Exception:
                # Skip files with errors
                pass
    
    result["text_files"] = len(text_files)
    result["binary_files"] = len(binary_files)
    result["total_tokens"] = total_tokens
    result["average_tokens_per_file"] = total_tokens // len(text_files) if text_files else 0
    
    if include_file_details:
        # Sort by token count
        file_details.sort(key=lambda x: x.get("tokens", 0), reverse=True)
        result["file_details"] = file_details
    
    # Group by extension
    extensions = {}
    for file_path in text_files:
        ext = os.path.splitext(file_path)[1].lower() or "[no extension]"
        if ext not in extensions:
            extensions[ext] = {"count": 0, "tokens": 0, "size": 0}
        
        try:
            with open(file_path, encoding='utf-8', errors='replace') as f:
                content = f.read()
            token_count = estimate_tokens(content)
            file_size = os.path.getsize(file_path)
            
            extensions[ext]["count"] += 1
            extensions[ext]["tokens"] += token_count
            extensions[ext]["size"] += file_size
        except Exception:
            # Skip files with errors
            pass
    
    result["extensions"] = {ext: extensions[ext] for ext in sorted(extensions.keys())}
    
    return result


@mcp.tool()
async def generate_directory_report(
    directory: str, 
    depth: int = 3,
    include_file_content: bool = True,
    max_files_with_content: int = 5,
    max_tokens_per_file: int = 1000,
    sample_only: bool = False,
    ignore_patterns: list[str] | None = None,
    include_gitignore: bool = True,
    include_default_ignores: bool = True,
    ctx: Context = None
) -> str:
    """
    Generates a comprehensive markdown report about a directory with token statistics.
    
    This tool creates a detailed markdown report about a directory structure, combining
    information about directory structure, token usage statistics, and file contents.
    The report is designed to provide a comprehensive understanding of a codebase or
    directory while maintaining token awareness.
    
    The report includes:
    - Filtering settings (gitignore, ignored patterns)
    - Summary statistics (files, directories, sizes, token counts)
    - Directory structure visualization
    - File extension breakdown with token statistics
    - Contents of the most important files
    
    Args:
        directory: Directory to analyze and report on
        depth: Maximum depth to scan in the directory (default: 3)
        include_file_content: Whether to include file contents in the report (default: True)
        max_files_with_content: Maximum number of files to include content for (default: 5)
        max_tokens_per_file: Maximum tokens per file (default: 1000)
        sample_only: Whether to show only a sample of each file (default: False)
        ignore_patterns: List of patterns to ignore (gitignore syntax)
        include_gitignore: Whether to respect .gitignore files (default: True)
        include_default_ignores: Whether to use built-in default ignores (default: True)
        ctx: MCP context for progress reporting
    
    Returns:
        Formatted markdown report as a string
    """
    if ctx:
        await ctx.info(f"Starting analysis of {directory}")
        await ctx.report_progress(0, 5)
    
    # Resolve path
    dir_path = os.path.abspath(directory)
    if not os.path.exists(dir_path):
        return f"Error: Directory not found: {dir_path}"
    
    # Create ignore patterns list
    all_patterns = []
    if ignore_patterns:
        all_patterns.extend(ignore_patterns)
    if include_default_ignores:
        all_patterns.extend(DEFAULT_IGNORE_PATTERNS)
    
    # Create ignore filter
    ignore_filter = None
    if all_patterns or include_gitignore:
        gitignore_file = os.path.join(dir_path, '.gitignore') if include_gitignore else None
        ignore_filter = PathIgnoreFilter(all_patterns, gitignore_file)
    
    # 1. Scan directory
    if ctx:
        await ctx.info("Scanning directory structure...")
        await ctx.report_progress(1, 5)
    
    directory_tree = scan_directory(dir_path, depth, ignore_filter=ignore_filter, base_path=BASE_PATH)
    tree_text, tree_tokens = format_directory_tree(directory_tree)
    
    # 2. Analyze tokens
    if ctx:
        await ctx.info("Analyzing token usage...")
        await ctx.report_progress(2, 5)
    
    token_analysis_result = await analyze_token_usage(
        dir_path, 
        ignore_patterns=ignore_patterns,
        include_gitignore=include_gitignore,
        include_default_ignores=include_default_ignores
    )
    
    # 3. Find important files
    if ctx:
        await ctx.info("Finding important files...")
        await ctx.report_progress(3, 5)
    
    all_text_files = []
    def collect_text_files(dir_node):
        for file in dir_node.get('files', []):
            if not is_binary_file(file['path']):
                all_text_files.append(file['path'])
        for subdir in dir_node.get('dirs', []):
            collect_text_files(subdir)
    
    collect_text_files(directory_tree)
    
    # 4. Select files to include in report
    important_files = prioritize_files(all_text_files, max_tokens_per_file * max_files_with_content)
    important_files = important_files[:max_files_with_content]
    
    # 5. Generate report
    if ctx:
        await ctx.info("Generating report...")
        await ctx.report_progress(4, 5)
    
    report = []
    report.append(f"# Directory Report: {dir_path}")
    report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Filtering information
    report.append("## Filtering Settings")
    if include_gitignore:
        report.append("- Using .gitignore: Yes")
    if include_default_ignores or ignore_patterns:
        report.append("- Ignored patterns:")
        if include_default_ignores:
            report.append("  - Default ignore patterns: " + ", ".join(DEFAULT_IGNORE_PATTERNS[:5]) + "...")
        if ignore_patterns:
            report.append("  - Custom ignore patterns: " + ", ".join(ignore_patterns))
    report.append("")
    
    # Summary section
    report.append("## Summary")
    report.append(f"- Total files: {directory_tree['total_file_count']}")
    report.append(f"- Total directories: {directory_tree['total_dir_count']}")
    report.append(f"- Total size: {format_size(directory_tree['size'])}")
    report.append(f"- Text files: {token_analysis_result.get('text_files', 0)}")
    report.append(f"- Binary files: {token_analysis_result.get('binary_files', 0)}")
    report.append(f"- Estimated total tokens: {token_analysis_result.get('total_tokens', 0):,}")
    report.append("")
    
    # Directory structure
    report.append("## Directory Structure")
    report.append("```")
    report.append("\n".join(tree_text))
    report.append("```")
    report.append("")
    
    # Extension breakdown
    if token_analysis_result.get('extensions'):
        report.append("## File Extensions")
        extensions = token_analysis_result['extensions']
        report.append("| Extension | Count | Size | Tokens |")
        report.append("|-----------|-------|------|--------|")
        
        for ext, data in extensions.items():
            report.append(f"| {ext} | {data['count']} | {format_size(data['size'])} | {data['tokens']:,} |")
        
        report.append("")
    
    # File contents
    if include_file_content and important_files:
        report.append("## Important File Contents")
        
        for file_path in important_files:
            rel_path = os.path.relpath(file_path, dir_path)
            report.append(f"### {rel_path}")
            content, tokens = extract_file_content_utility(file_path, max_tokens_per_file, sample_only=sample_only, base_path=BASE_PATH)
            report.append(f"Size: {format_size(os.path.getsize(file_path))}, Tokens: {tokens:,}")
            report.append("```" + os.path.splitext(file_path)[1].lstrip('.'))
            report.append(content)
            report.append("```")
            report.append("")
    
    if ctx:
        await ctx.report_progress(5, 5)
        await ctx.info("Report generation complete")
    
    return "\n".join(report)


# --- Resources ---

@mcp.resource("directory://{path}")
async def get_directory_info(path: str) -> dict[str, Any]:
    """
    Get information about a directory structure.
    
    Args:
        path: Directory path
    
    Returns:
        Dictionary with directory information
    """
    # Resolve path
    dir_path = os.path.abspath(path)
    if not os.path.exists(dir_path):
        return {"error": f"Path not found: {dir_path}"}
    
    if not os.path.isdir(dir_path):
        return {"error": f"Path is not a directory: {dir_path}"}
    
    # Create ignore filter with default patterns
    ignore_filter = PathIgnoreFilter(DEFAULT_IGNORE_PATTERNS, 
                                    os.path.join(dir_path, '.gitignore'))
    
    # Scan directory with default depth and base path validation
    directory_tree = scan_directory(dir_path, max_depth=3, ignore_filter=ignore_filter, base_path=BASE_PATH)
    
    return {
        "path": dir_path,
        "name": os.path.basename(dir_path) or dir_path,
        "total_files": directory_tree["total_file_count"],
        "total_dirs": directory_tree["total_dir_count"],
        "size": directory_tree["size"],
        "size_formatted": format_size(directory_tree["size"]),
        "direct_files": directory_tree["direct_file_count"],
        "direct_dirs": directory_tree["direct_dir_count"],
        "ignored_patterns": DEFAULT_IGNORE_PATTERNS,
        "gitignore_used": True
    }


@mcp.resource("file://{path}")
async def get_file_info(path: str) -> dict[str, Any]:
    """
    Get information about a file.
    
    Args:
        path: File path
    
    Returns:
        Dictionary with file information
    """
    # Resolve path
    file_path = os.path.abspath(path)
    if not os.path.exists(file_path):
        return {"error": f"File not found: {file_path}"}
    
    if os.path.isdir(file_path):
        return {"error": f"Path is a directory, not a file: {file_path}"}
    
    try:
        file_size = os.path.getsize(file_path)
        file_binary = is_binary_file(file_path)
        
        result = {
            "path": file_path,
            "name": os.path.basename(file_path),
            "size": file_size,
            "size_formatted": format_size(file_size),
            "is_binary": file_binary,
            "extension": os.path.splitext(file_path)[1].lower()
        }
        
        # If it's a text file, estimate tokens
        if not file_binary:
            try:
                with open(file_path, encoding='utf-8', errors='replace') as f:
                    # Only read first 10KB to estimate
                    sample = f.read(10240)
                sample_tokens = estimate_tokens(sample)
                
                # Extrapolate to full file
                full_tokens = int(sample_tokens * (file_size / len(sample) if len(sample) > 0 else 1))
                result["estimated_tokens"] = full_tokens
            except Exception:
                # Skip token estimation if it fails
                pass
        
        return result
    except Exception as e:
        return {"error": f"Error reading file: {str(e)}"}


@mcp.resource("tokens://{path}")
async def get_token_info(path: str) -> dict[str, Any]:
    """
    Get token usage information for a path.
    
    Args:
        path: Path to analyze (file or directory)
    
    Returns:
        Token usage information
    """
    return await analyze_token_usage(path, include_file_details=False, include_default_ignores=True)


@mcp.tool()
async def copy_file_to_destination(
    source_path: str,
    destination_path: str
) -> dict[str, Any]:
    """
    Copy a file from source path to destination path.
    
    This tool copies a file from one location to another, preserving file metadata
    such as timestamps. It will create destination directories if they don't exist,
    and provides detailed information about the copy operation including file sizes
    and success status.
    
    For security, all file operations are restricted to the configured base directory
    if one has been specified when starting the server.
    
    Args:
        source_path: Path of the file to copy
        destination_path: Path where the file should be copied to
    
    Returns:
        Dictionary with detailed operation information including:
        - Success status
        - Source and destination file details
        - File sizes and timestamps
        - Any errors that occurred
    """
    # Call the implementation with global base path for validation
    result = copy_file(source_path, destination_path, BASE_PATH)
    
    return result


# --- Prompts ---

@mcp.prompt()
def explore_prompt() -> str:
    """Standard prompt for exploring a directory."""
    return """
I need you to help me analyze a directory structure with the Token-Aware Directory Explorer tool.
Please explore the directory I provide, tell me about its structure, and identify key files that would be important to understand the project.
Focus on providing a clear overview while being mindful of token usage.

By default, the tool will ignore common directories and files like:
- .git/, .venv/, venv/, __pycache__/, node_modules/
- Build artifacts and IDE-specific directories
- Binary and compiled files

This helps focus on the relevant source code and documentation.
    """


@mcp.prompt()
def token_analysis_prompt() -> str:
    """Standard prompt for token analysis of a codebase."""
    return """
I need you to analyze the token usage of a project directory to understand how many tokens would be needed to process it with an LLM.
Please use the Token-Aware Directory Explorer to:
1. Show me the total token count for the codebase
2. Break down token usage by file extensions
3. Identify the largest files in terms of token usage
4. Suggest which files are most important to understand the project

Note that the tool will automatically filter out common non-source directories like .git, node_modules, __pycache__, etc.
    """

# Run the server if this script is executed directly
if __name__ == "__main__":
    mcp.run()
