# TokenScope

TokenScope is a token-aware directory explorer for Large Language Models.

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server for token-aware directory exploration and analysis, designed for Large Language Models (LLMs).

## Overview

TokenScope provides intelligent directory structure analysis and token-aware file content exploration. It helps LLMs like Claude understand codebases and directory structures by:

1. Scanning directory structures with token-efficient summaries
2. Extracting and analyzing file contents with token awareness
3. Finding important files for codebase understanding
4. Generating reports with relevant information

## Features

- **Token-Aware Directory Scanning**
  - Explores directories recursively with configurable depth
  - Provides intelligent summaries for large directories
  - Respects .gitignore files and custom ignore patterns

- **File Content Analysis**
  - Smart extraction of file contents that respects token limits
  - Special handling for JSON and other structured files
  - File selection prioritization based on importance

- **Token Usage Statistics**
  - Estimates tokens required to process directories
  - Breaks down token usage by file extension
  - Identifies token-heavy files

- **Comprehensive Reporting**
  - Generates markdown reports with directory structure
  - Includes token usage statistics
  - Shows samples of important files

- **Security Features**
  - Path validation to restrict operations to a specified base directory
  - Prevents access to files outside the allowed base path

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended for easy dependency management)

### 1. Main Installation (PyPI)

This is the recommended method for most users who just want to use TokenScope:

```bash
# Install from PyPI using uv (recommended)
uv pip install tokenscope
```

#### Running TokenScope

The `--base-path` argument is mandatory for security reasons. It restricts all file operations to the specified directory.

```bash
# Run using the installed package
uv run --with tokenscope tokenscope --base-path /path/to/allowed/directory
```

#### Configuring in Claude Desktop

1. Locate Claude Desktop's configuration file (typically in `~/.config/claude/config.json`)

2. Add TokenScope to the `mcpServers` section:

   ```json
   "mcpServers": {
     "TokenScope": {
       "command": "uv",
       "args": [
         "run",
         "--with",
         "tokenscope",
         "tokenscope",
         "--base-path",
         "/your/secure/base/path"
       ]
     }
   }
   ```

3. Replace `/your/secure/base/path` with the directory you want to restrict operations to

4. Save the configuration file and restart Claude Desktop

### 2. Development Installation (from GitHub)

For contributors or users who want to modify the code:

```bash
# Clone the repository
git clone https://github.com/cdgaete/token-scope-mcp.git
cd token-scope-mcp

# Install development dependencies with uv
uv pip install -e ".[dev]"
```

#### Running in Development Mode

```bash
# Run the server directly with uv
uv run --with fastmcp --with tiktoken src/server.py --base-path /path/to/allowed/directory
```

#### Configuring Development Version in Claude Desktop

1. Locate Claude Desktop's configuration file

2. Add TokenScope to the `mcpServers` section with development paths:

   ```json
   "mcpServers": {
     "TokenScope (Dev)": {
       "command": "uv",
       "args": [
         "run",
         "--with",
         "fastmcp",
         "--with",
         "tiktoken",
         "/path/to/your/token-scope-mcp/src/server.py",
         "--base-path",
         "/your/secure/base/path"
       ]
     }
   }
   ```

3. Replace `/path/to/your/token-scope-mcp/src/server.py` with the actual path to the server.py file
4. Replace `/your/secure/base/path` with your secure directory

## Security Features

The `--base-path` argument is mandatory for security reasons:

- All file operations are validated to ensure they're within the specified directory
- Attempts to access or modify files outside the base path will be rejected
- The base path is set once when starting the server and cannot be changed without restart

## Example Prompts

Here are some examples of how to use TokenScope with Claude:

```text
Please scan my project directory at /path/to/project and tell me about its structure, focusing on the most important files.
```

```text
Analyze the token usage in my project directory at /path/to/project and tell me how many tokens would be needed to process the entire codebase with an LLM.
```

```text
Generate a comprehensive directory report about my project at /path/to/project, including structure, token statistics, and samples of the most important files.
```

## Available Tools

The server provides the following MCP tools:

### `scan_directory_structure`

Scans a directory and returns its structure in a token-efficient way.

```python
scan_directory_structure(
    path: str, 
    depth: int = 3,
    max_tokens: int = 10000,
    ignore_patterns: list[str] | None = None,
    include_gitignore: bool = True,
    include_default_ignores: bool = True
)
```

### `extract_file_content`

Extracts the content of a specific file, respecting token limits and format.

```python
extract_file_content(
    file_path: str, 
    max_tokens: int = 10000,
    sample_only: bool = False
)
```

### `search_files_by_pattern`

Searches for files matching specified patterns within a directory structure.

```python
search_files_by_pattern(
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
)
```

### `analyze_token_usage`

Analyzes token usage for a directory or file to estimate LLM processing requirements.

```python
analyze_token_usage(
    path: str,
    include_file_details: bool = False,
    ignore_patterns: list[str] | None = None,
    include_gitignore: bool = True,
    include_default_ignores: bool = True
)
```

### `generate_directory_report`

Generates a comprehensive markdown report about a directory with token statistics.

```python
generate_directory_report(
    directory: str, 
    depth: int = 3,
    include_file_content: bool = True,
    max_files_with_content: int = 5,
    max_tokens_per_file: int = 1000,
    sample_only: bool = False,
    ignore_patterns: list[str] | None = None,
    include_gitignore: bool = True,
    include_default_ignores: bool = True
)
```

### `copy_file_to_destination`

Copy a file from source path to destination path.

```python
copy_file_to_destination(
    source_path: str,
    destination_path: str
)
```

## Default Ignore Patterns

TokenScope automatically ignores common directories and files:

```python
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
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Uses [tiktoken](https://github.com/openai/tiktoken) for accurate token counting
- This same concept was implemented originally in [repoai](https://github.com/cdgaete/repoai)
- Inspired by the need to efficiently analyze codebases with LLMs
