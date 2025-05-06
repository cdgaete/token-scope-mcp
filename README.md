# TokenScope

Token-Aware Directory Explorer for Large Language Models (LLMs).

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that helps LLMs efficiently explore and understand codebases and directory structures.

## Overview

TokenScope provides intelligent directory structure analysis and token-aware file content exploration designed for LLMs like Claude. It helps LLMs understand codebases by:

1. Exploring directory structures with token-aware summarization
2. Viewing file contents with token limitations in mind
3. Generating comprehensive reports about directories

## Key Features

### Token-Aware Directory Exploration

- **Automatic summarization** for large directories while showing small directories in full
- **Respect for token limits** to maximize useful information within constraints
- **Built-in security** with base path validation
- **Smart filtering** with default patterns and .gitignore support
- **Accurate directory statistics** for even the largest directories

### Simple, Intuitive Tools

TokenScope provides just three core tools:

1. `explore_directory` - Scan and understand directory structures
2. `view_content` - Access file contents with token awareness
3. `generate_report` - Create comprehensive reports (with option to save to file)

## Installation

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) (recommended for dependency management)

### Installation (PyPI)

This is the recommended method for most users who just want to use TokenScope:

```bash
# Install from PyPI using uv (recommended)
uv pip install tokenscope
```

## Running TokenScope

The `--base-path` argument is mandatory for security reasons. It restricts all file operations to the specified directory.

```bash
# Run using the installed package
uv run --with tokenscope tokenscope --base-path /path/to/allowed/directory
```

### Configuring in Claude Desktop

1. Locate Claude Desktop's configuration file (typically `~/.config/claude/config.json`)

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


## Usage

### Running TokenScope Server

The `--base-path` argument is required for security (it restricts file operations to the specified directory):

```bash
tokenscope --base-path /path/to/allowed/directory
```

### Testing Tools Directly

TokenScope includes a test mode for trying out tools directly:

```bash
# Test directory exploration
tokenscope --base-path /path/to/allowed/directory --test "explore:/path/to/directory"

# Test with custom ignore patterns
tokenscope --base-path /path/to/allowed/directory --test "explore:/path/to/directory?ignore=cache,*.log,tmp/&gitignore=false"

# Test file viewing
tokenscope --base-path /path/to/allowed/directory --test "view:/path/to/file"

# Test report generation
tokenscope --base-path /path/to/allowed/directory --test "report:/path/to/directory"

# Test report generation with file output and custom ignore patterns
tokenscope --base-path /path/to/allowed/directory --test "report:/path/to/directory?ignore=*.bak,temp/ > /path/to/output.md"
```

## Example Prompts

Here are some examples of how to use TokenScope with Claude:

```text
Could you explore my project directory at /path/to/project and tell me about its structure?
```

```text
Can you show me the content of the file at /path/to/file.py?
```

```text
Please generate a comprehensive report about my project at /path/to/project and save it to /path/to/report.md
```

## Accurate Directory Statistics

TokenScope now provides two levels of directory information:

1. **Quick Scan Statistics**: Information about files and directories visible in the tree view
2. **Full Directory Statistics**: Complete counts of ALL files and directories, even in very large repositories

This dual approach ensures that even for massive directories (with thousands or millions of files), you'll get accurate information about the total number of files, directories, and disk usage. This is especially valuable when working with large codebases where a complete directory listing would exceed token limits.

### Example Output

```txt
QUICK SCAN STATISTICS (files visible in tree):
Files shown in tree: 47
Directories shown in tree: 16
Size shown in tree: 185.9 MB

FULL DIRECTORY STATISTICS (all files):
Total files: 16,059
Total directories: 8
Total disk size: 2.1 GB
```

## Smart Filtering with Ignore Patterns

TokenScope automatically filters out common directories and files that typically don't contribute to understanding a codebase:

- **Default ignored patterns**: `.git/`, `.venv/`, `venv/`, `__pycache__/`, `node_modules/`, `build/`, `dist/`, etc.
- **Custom ignore patterns**: You can specify additional patterns to ignore via the `ignore_patterns` parameter
- **.gitignore support**: TokenScope can automatically respect .gitignore files in the directories it scans

This functionality helps prevent token waste on irrelevant files and directories like:

- Dependency directories (e.g., `node_modules`, virtual environments)
- Build artifacts and cache directories
- Version control metadata
- IDE configuration files

### Using Ignore Patterns in CLI Test Mode

```bash
# Ignore specific patterns
tokenscope --base-path /path --test "explore:/code?ignore=*.log,temp/"

# Disable .gitignore processing
tokenscope --base-path /path --test "explore:/code?gitignore=false"

# Both together
tokenscope --base-path /path --test "explore:/code?ignore=*.tmp&gitignore=false"
```

## Security Features

TokenScope includes important security features:

- All file operations are validated to ensure they're within the specified base directory
- Attempts to access files outside the base path are rejected
- The base path is set once when starting the server and cannot be changed without restart

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [FastMCP](https://github.com/jlowin/fastmcp)
- Uses [tiktoken](https://github.com/openai/tiktoken) for accurate token counting
