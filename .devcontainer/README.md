# DevContainer Guide

## Getting Started

1. **Open in VS Code**: Open this project in VS Code with the Dev Containers extension installed
2. **Reopen in Container**: Click the notification or run "Dev Containers: Reopen in Container"
3. **Wait for Setup**: The container will build and dependencies will be installed automatically
4. **Interactive Menu**: An interactive menu will launch automatically showing all available commands
5. **Home Assistant Auto-starts**: Once setup completes, Home Assistant starts automatically in the background
6. **Access Home Assistant**: Open http://localhost:8123 in your browser

## Interactive Menu

When the devcontainer loads, you'll see an interactive menu with all available commands:

```
╔════════════════════════════════════════════════════════════════╗
║                                                                ║
║         🏠 Unraid Management Agent - Dev Container 🏠          ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝

Home Assistant Custom Integration for Unraid Server Management
Monitor and control your Unraid servers from Home Assistant

✓ Home Assistant is RUNNING (PID: 123)
  Access at: http://localhost:8123

Available Commands:

  1) start     - Start Home Assistant in background
  2) stop      - Stop Home Assistant
  3) restart   - Restart Home Assistant
  4) develop   - Run Home Assistant in foreground (debug mode)
  5) lint      - Run code quality checks (ruff format & check)
  6) test      - Run pytest tests with coverage
  7) logs      - View Home Assistant logs
  8) setup     - Sync dependencies (uv sync --extra dev)
  9) status    - Show detailed status

  q) quit      - Exit menu (services continue running)
```

### Menu Features

- **Real-time Status**: Shows if Home Assistant is running
- **Interactive Navigation**: Simple numbered options
- **Command Descriptions**: Clear explanations of what each command does
- **Background Operations**: Services continue running when you exit the menu
- **Relaunchable**: Run `./scripts/menu` anytime to return to the menu

## Available Scripts
- **Logs**: Run VS Code task "Home Assistant: View Logs" or `tail -f config/home-assistant.log`

## VS Code Tasks (Ctrl/Cmd+Shift+P → "Run Task")

- **Home Assistant: Start** - Start HA in background
- **Home Assistant: Stop** - Stop HA
- **Home Assistant: Restart** - Restart HA (use after code changes)
- **Home Assistant: View Logs** - Live tail of logs
- **Lint** - Run code linting and formatting
- **Run Tests** - Execute pytest test suite

## Scripts

Available in `./scripts/` directory:

- `./scripts/menu` - **Launch interactive menu** (recommended - shows all commands)
- `./scripts/start` - Start Home Assistant in background
- `./scripts/stop` - Stop Home Assistant
- `./scripts/restart` - Restart Home Assistant
- `./scripts/develop` - Run Home Assistant in foreground (for debugging)
- `./scripts/lint` - Run linting and auto-fix issues
- `./scripts/setup` - Install/sync dependencies

## Development Workflow

1. Make code changes to the integration
2. Run "Home Assistant: Restart" task or `./scripts/restart`
3. Test changes in Home Assistant at http://localhost:8123
4. Run `./scripts/lint` before committing

## Installed Tools

- **UV**: Fast Python package manager (replaces pip)
- **GitHub CLI** (`gh`): GitHub command-line tool
- **GitHub Copilot CLI**: AI-powered terminal assistance
- **Node.js 22**: For Copilot CLI and other tools
- **Python 3.13**: Latest Python version
- **ffmpeg, libpcap, libturbojpeg**: Required by Home Assistant

## VS Code Extensions (Auto-installed)

- Claude Code (Anthropic)
- Ruff (Python linting/formatting)
- Prettier (Code formatter)
- GitHub Copilot & Copilot Chat
- GitHub Actions & Pull Requests
- Python, Pylance
- Coverage Gutters

## VS Code Extensions

The devcontainer automatically installs the following extensions optimized for Home Assistant integration development:

### Core Development Extensions
- **Python** (`ms-python.python`) - Python language support with IntelliSense
- **Pylance** (`ms-python.vscode-pylance`) - Advanced Python static type analysis
- **Ruff** (`astral-sh.ruff` & `charliermarsh.ruff`) - Fast Python linter and formatter
- **Prettier** (`esbenp.prettier-vscode`) - Code formatter for JSON, YAML, Markdown

### Home Assistant Development
- **YAML Support** (`redhat.vscode-yaml`) - YAML syntax highlighting and validation
- **Python Indent** (`kevinrose.vsc-python-indent`) - Correct Python indentation

### Code Quality & Organization
- **Indent Rainbow** (`oderwat.indent-rainbow`) - Colorize indentation levels
- **Material Icons** (`PKief.material-icon-theme`) - Beautiful file explorer icons
- **Coverage Gutters** (`ryanluker.vscode-coverage-gutters`) - Test coverage visualization

### GitHub & AI Integration
- **GitHub Copilot** (`github.copilot`) - AI-powered code suggestions
- **Copilot Chat** (`github.copilot-chat`) - AI chat interface in VS Code
- **GitHub Actions** (`github.vscode-github-actions`) - GitHub Actions workflow support
- **Pull Requests** (`github.vscode-pull-request-github`) - Manage pull requests from VS Code
- **Claude** (`anthropic.claude-dev`) - Anthropic Claude AI integration

## Command-Line Tools

The devcontainer includes all essential command-line tools:

- **UV** (0.9.17) - Fast Python package manager and installer
- **Python** (3.13.9) - Latest Python version with Home Assistant support
- **GitHub CLI** (latest) - Manage GitHub repositories from terminal
- **GitHub Copilot CLI** (latest) - AI assistance in the terminal
- **Node.js** (22 LTS) - For GitHub Copilot CLI support
- **Git** - Version control
- **FFmpeg** - Media processing (required by Home Assistant)

## Extension Settings

The devcontainer configures these extensions automatically:

```json
{
  "files.eol": "\n",
  "editor.tabSize": 4,
  "editor.formatOnPaste": true,
  "editor.formatOnSave": true,
  "editor.formatOnType": false,
  "files.trimTrailingWhitespace": true,
  "python.analysis.typeCheckingMode": "basic",
  "python.analysis.autoImportCompletions": true,
  "python.defaultInterpreterPath": "${containerWorkspaceFolder}/.venv/bin/python"
}
```

## Troubleshooting

### Home Assistant won't start
- Check logs: `tail -50 config/home-assistant.log`
- Verify dependencies: `uv sync --extra dev --frozen`
- Restart container: Close and reopen in container

### Port 8123 already in use
- Stop existing HA instance: `./scripts/stop`
- Check for other processes: `lsof -i :8123`

### Dependencies issues
- Recreate venv: `rm -rf .venv && uv sync --extra dev --frozen`
- Rebuild container: Dev Containers: Rebuild Container

## Notes

- The `.venv` directory is recreated on container start to ensure proper paths
- All dependencies are managed via `pyproject.toml` and `uv.lock`
- Home Assistant runs in debug mode by default for better development experience
