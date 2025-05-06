"""
TokenScope MCP Server

Main entry point for running the Model Context Protocol server for TokenScope.
"""

import os
import sys
import argparse
from datetime import datetime
from typing import Any

from fastmcp import FastMCP, Context

from tokenscope.core import (
    scan_directory,
    extract_file_content,
    generate_directory_tree,
    validate_path,
    calculate_recursive_files,
    calculate_recursive_dirs,
    calculate_recursive_tokens,
    get_total_directory_stats
)


# Global base path for security validation
BASE_PATH = None

def set_base_path(base_path: str):
    """Set the global base path for security validation."""
    global BASE_PATH
    BASE_PATH = base_path

# Create an MCP server
mcp = FastMCP(
    "TokenScope",
    description="Explore directory structures efficiently with token awareness for LLMs",
    dependencies=["tiktoken"]
)

@mcp.tool()
async def explore_directory(
    path: str, 
    max_tokens: int = 5000,
    ignore_patterns: list[str] | None = None,
    use_gitignore: bool = True,
    ctx: Context = None
) -> dict[str, Any]:
    """
    Scan and explore a directory with token-aware summarization.
    
    This tool intelligently scans a directory structure and provides a summary
    that respects token limits. Large directories are automatically summarized
    while small directories are shown in full detail.
    
    Args:
        path: Directory path to explore
        max_tokens: Maximum tokens to use for the directory structure (default: 10000)
        ignore_patterns: list of file/directory patterns to ignore (like '.git/', '*.pyc')
        use_gitignore: Whether to use .gitignore file in the directory (default: True)
        
    Returns:
        Detailed information about the directory structure with token usage statistics
    """
    if ctx:
        await ctx.info(f"Exploring directory: {path}")
    
    # Scan directory with base path validation
    directory = scan_directory(
        path, 
        max_tokens, 
        BASE_PATH,
        ignore_patterns=ignore_patterns,
        use_gitignore=use_gitignore
    )
    
    total_files = calculate_recursive_files(directory)
    total_dirs = calculate_recursive_dirs(directory)
    total_tokens = calculate_recursive_tokens(directory)
    
    # Generate tree representation with recursive totals
    tree_lines = generate_directory_tree(directory, calculate_totals=True)
    
    # Get accurate directory statistics using full scan
    stats = get_total_directory_stats(path, ignore_patterns, use_gitignore)
    
    # Build result with both structured data and human-readable format
    result = {
        "directory": directory,
        "tree_text": "\n".join(tree_lines),
        "structure_tokens": directory.get("tokens_used", 0),
        "content_tokens": total_tokens,
        "total_tokens": directory.get("tokens_used", 0) + total_tokens,
        "total_files": total_files,
        "total_dirs": total_dirs,
        "total_size": directory.get("size", 0),
        "size_formatted": directory.get("size_formatted", ""),
        "is_summarized": directory.get("is_summarized", False),
        # Actual full directory statistics
        "full_file_count": stats["total_files"],
        "full_dir_count": stats["total_dirs"],
        "full_size": stats["total_size"],
        "full_size_formatted": stats["size_formatted"]
    }
    
    if ctx:
        await ctx.info(f"Exploration complete: {result['total_files']} files, {result['size_formatted']}")
    
    return result


@mcp.tool()
async def view_content(
    file_path: str,
    max_tokens: int = 15000,
    sample_only: bool = False,
    ctx: Context = None
) -> dict[str, Any]:
    """
    View the content of a file with token awareness.
    
    This tool extracts the content of a file while respecting token limits.
    Binary files are detected automatically, and large text files can be
    sampled or truncated to stay within token limits.
    
    Args:
        file_path: Path to the file to view
        max_tokens: Maximum tokens to return (default: 15000)
        sample_only: If True, return only a sample of large files
        
    Returns:
        File content and metadata including token count
    """
    if ctx:
        await ctx.info(f"Viewing file: {file_path}")
    
    # Extract file content with base path validation
    result = extract_file_content(file_path, max_tokens, sample_only, BASE_PATH)
    
    if ctx:
        if "error" in result:
            await ctx.info(f"Error viewing file: {result['error']}")
        else:
            token_info = f", {result.get('token_count', 0)} tokens"
            sample_info = " (sample)" if result.get("is_sample", False) else ""
            truncated_info = " (truncated)" if result.get("is_truncated", False) else ""
            await ctx.info(f"File viewed: {result.get('size_formatted', '')}{token_info}{sample_info}{truncated_info}")
    
    return result


@mcp.tool()
async def generate_report(
    directory: str,
    output_path: str | None = None,
    max_tokens: int = 50000,
    include_file_contents: bool = True,
    max_files_with_content: int = 100,
    max_tokens_per_file: int = 10000,
    ignore_patterns: list[str] | None = None,
    use_gitignore: bool = True,
    ctx: Context = None
) -> str:
    """
    Generate a comprehensive report about a directory.
    
    This tool creates a detailed markdown report about a directory structure, including
    token usage statistics and optionally file contents. The report can be saved to a
    file if an output path is provided.
    
    Args:
        directory: Directory to analyze and report on
        output_path: Optional path to save the report to a file (default: None)
        max_tokens: Maximum tokens for directory scanning (default: 50000)
        include_file_contents: Whether to include file contents (default: True)
        max_files_with_content: Maximum number of files to show content for (default: 100)
        max_tokens_per_file: Maximum tokens per file content (default: 10000)
        ignore_patterns: list of file/directory patterns to ignore (like '.git/', '*.pyc')
        use_gitignore: Whether to use .gitignore file in the directory (default: True)
        
    Returns:
        Formatted markdown report
    """
    if ctx:
        await ctx.info(f"Generating report for: {directory}")
        await ctx.report_progress(0, 3)
    
    # Validate directory
    validation = validate_path(directory, BASE_PATH)
    if not validation["is_valid"]:
        return f"Error: {validation['error']}"
    
    dir_path = validation["resolved_path"]
    
    # 1. Scan directory
    if ctx:
        await ctx.info("Scanning directory structure...")
        await ctx.report_progress(1, 3)
    
    dir_result = await explore_directory(
        dir_path, 
        max_tokens,
        ignore_patterns=ignore_patterns,
        use_gitignore=use_gitignore,
        ctx=ctx
    )
    directory_data = dir_result["directory"]
    
    # 2. Generate report
    if ctx:
        await ctx.info("Generating report...")
        await ctx.report_progress(2, 3)
    
    report = []
    report.append(f"# Directory Report: {dir_path}")
    report.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append("")
    
    # Summary section
    report.append("## Summary")
    # First show stats from quick scan
    report.append("### Quick Scan")
    report.append(f"- Files shown in tree: {dir_result['total_files']}")
    report.append(f"- Size shown in tree: {dir_result['size_formatted']}")
    report.append(f"- Estimated tokens for structure: {dir_result['structure_tokens']}")
    report.append(f"- Estimated tokens for visible content: {dir_result['content_tokens']:,}")
    report.append(f"- Total tokens (structure + visible content): {dir_result['total_tokens']:,}")
    report.append("")
    
    # Then show full directory stats
    report.append("### Full Directory Statistics")
    report.append(f"- Total files: {dir_result['full_file_count']:,}")
    report.append(f"- Total disk size: {dir_result['full_size_formatted']}")
    report.append("- Note: These statistics include ALL files, even ones not shown in the tree view.")
    report.append("")
    
    # Directory structure
    report.append("## Directory Structure")
    report.append("```")
    report.append(dir_result["tree_text"])
    report.append("```")
    report.append("")
    
    # File contents (if requested)
    if include_file_contents:
        report.append("## File Contents")
        
        # Collect files to show (prioritize top-level files)
        files_to_show = []
        
        # Function to collect files from directory structure
        def collect_files(dir_data, current_depth=0, max_depth=2):
            if current_depth > max_depth:
                return
            
            # Add files at this level
            for file in dir_data.get("files", []):
                if not file.get("is_binary", False):
                    files_to_show.append(file["path"])
                    if len(files_to_show) >= max_files_with_content:
                        return
            
            # Recurse into subdirectories
            for subdir in dir_data.get("directories", []):
                collect_files(subdir, current_depth + 1, max_depth)
                if len(files_to_show) >= max_files_with_content:
                    return
        
        # Collect files
        collect_files(directory_data)
        
        # Get content for each file
        for file_path in files_to_show:
            file_result = await view_content(
                file_path, 
                max_tokens=max_tokens_per_file,
                sample_only=True,
                ctx=ctx
            )
            
            if "error" in file_result:
                continue
            
            rel_path = os.path.relpath(file_path, dir_path)
            report.append(f"### {rel_path}")
            
            size_info = file_result.get("size_formatted", "")
            token_info = file_result.get("token_count", 0)
            
            report.append(f"Size: {size_info}, Tokens: {token_info}")
            report.append("```" + os.path.splitext(file_path)[1].lstrip('.'))
            report.append(file_result.get("content", ""))
            report.append("```")
            report.append("")
    
    # Join report lines
    report_text = "\n".join(report)
    
    # Save to file if output path is provided
    if output_path:
        output_validation = validate_path(output_path, BASE_PATH)
        if not output_validation["is_valid"]:
            return f"Error saving report: {output_validation['error']}\n\n{report_text}"
        
        try:
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_validation["resolved_path"]), exist_ok=True)
            
            # Write report to file
            with open(output_validation["resolved_path"], 'w', encoding='utf-8') as f:
                f.write(report_text)
                
            if ctx:
                await ctx.info(f"Report saved to: {output_path}")
        except Exception as e:
            return f"Error saving report: {str(e)}\n\n{report_text}"
    
    if ctx:
        await ctx.report_progress(3, 3)
        await ctx.info("Report generation complete")
    
    return report_text


def main():
    """Main entry point for the TokenScope server."""
    parser = argparse.ArgumentParser(
        description="TokenScope: Token-Aware Directory Explorer for LLMs"
    )
    parser.add_argument(
        "--base-path", 
        type=str, 
        help="Base directory for security validation. All file operations will be restricted to this directory."
    )
    parser.add_argument(
        "--test",
        type=str,
        help="Test mode: Run a tool and print the output. Format: 'tool_name:/path/to/directory'"
    )
    args = parser.parse_args()
    
    # Validate base path
    if args.base_path is None:
        print("Error: Base path is required.")
        print("Usage: tokenscope --base-path /path/to/allowed/directory")
        return 1
        
    if not os.path.exists(args.base_path) or not os.path.isdir(args.base_path):
        print(f"Error: Base path does not exist or is not a directory: {args.base_path}")
        return 1
        
    # Use absolute path
    base_path = os.path.abspath(args.base_path)
    
    # Set the base path for the MCP server
    set_base_path(base_path)
    print(f"Security: All file operations restricted to {base_path}")
    
    # Test mode
    if args.test:
        print(f"Test mode: {args.test}")
        try:
            if args.test.startswith("explore:"):
                path = args.test.split(":", 1)[1]
                import asyncio
                # Check for ignore options
                ignore_patterns = None
                use_gitignore = True
                
                # Parse parameters if provided as key=value&key=value format
                if "?" in path:
                    path, params = path.split("?", 1)
                    param_list = params.split("&")
                    for param in param_list:
                        if "=" in param:
                            key, value = param.split("=", 1)
                            if key == "ignore":
                                ignore_patterns = value.split(",")
                            elif key == "gitignore" and value.lower() == "false":
                                use_gitignore = False
                
                result = asyncio.run(explore_directory(path, ignore_patterns=ignore_patterns, use_gitignore=use_gitignore))
                print("\nDIRECTORY STRUCTURE:")
                print("=" * 80)
                print(result["tree_text"])
                
                # Show two levels of information
                print("\nQUICK SCAN STATISTICS (files visible in tree):")
                print(f"Files shown in tree: {result['total_files']}")
                print(f"Size shown in tree: {result['size_formatted']}")
                
                print("\nFULL DIRECTORY STATISTICS (all files):")
                print(f"Total files: {result['full_file_count']:,}")
                print(f"Total disk size: {result['full_size_formatted']}")
                
                print("\nTOKEN COUNTS:")
                print(f"  Structure tokens: {result['structure_tokens']:,}")
                print(f"  Visible content tokens: {result['content_tokens']:,}")
                print(f"  Total tokens: {result['total_tokens']:,}")
                return 0
                
            elif args.test.startswith("view:"):
                path = args.test.split(":", 1)[1]
                import asyncio
                result = asyncio.run(view_content(path))
                print(f"\nFILE: {result.get('path', '')}")
                print("=" * 80)
                print(f"Size: {result.get('size_formatted', '')}")
                print(f"Tokens: {result.get('token_count', 0)}")
                print("=" * 80)
                print(result.get("content", ""))
                return 0
                
            elif args.test.startswith("report:"):
                path = args.test.split(":", 1)[1]
                output_path = None
                ignore_patterns = None
                use_gitignore = True
                
                # Check if an output path is specified
                if ">" in path:
                    path, output_path = path.split(">", 1)
                    path = path.strip()
                    output_path = output_path.strip()
                
                # Parse parameters if provided
                if "?" in path:
                    path, params = path.split("?", 1)
                    param_list = params.split("&")
                    for param in param_list:
                        if "=" in param:
                            key, value = param.split("=", 1)
                            if key == "ignore":
                                ignore_patterns = value.split(",")
                            elif key == "gitignore" and value.lower() == "false":
                                use_gitignore = False
                
                import asyncio
                report = asyncio.run(generate_report(
                    path, 
                    output_path, 
                    ignore_patterns=ignore_patterns,
                    use_gitignore=use_gitignore
                ))
                print(report)
                if output_path:
                    print(f"\nReport saved to: {output_path}")
                return 0
            
            else:
                print("Unknown test command. Available commands:")
                print("  explore:/path/to/directory")
                print("  view:/path/to/file")
                print("  report:/path/to/directory > /optional/output/path.md")
                return 1
                
        except Exception as e:
            print(f"Error in test mode: {str(e)}")
            return 1
    
    # Run the MCP server
    try:
        print("Starting TokenScope MCP server...")
        mcp.run()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
