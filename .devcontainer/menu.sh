#!/bin/bash

# Colors for better readability
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Function to display the header
show_header() {
    clear
    echo -e "${BLUE}${BOLD}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}${BOLD}║                                                                ║${NC}"
    echo -e "${BLUE}${BOLD}║         🏠 Unraid Management Agent - Dev Container 🏠          ║${NC}"
    echo -e "${BLUE}${BOLD}║                                                                ║${NC}"
    echo -e "${BLUE}${BOLD}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Home Assistant Custom Integration for Unraid Server Management${NC}"
    echo -e "${GREEN}Monitor and control your Unraid servers from Home Assistant${NC}"
    echo ""
    
    # Show HA status
    if [ -f ".ha-pid" ]; then
        PID=$(cat .ha-pid)
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "${GREEN}✓ Home Assistant is RUNNING (PID: $PID)${NC}"
            echo -e "${GREEN}  Access at: ${BOLD}http://localhost:8123${NC}"
        else
            echo -e "${YELLOW}⚠ Home Assistant is STOPPED (stale PID file)${NC}"
        fi
    else
        echo -e "${YELLOW}⚠ Home Assistant is STOPPED${NC}"
    fi
    echo ""
}

# Function to display the menu
show_menu() {
    echo -e "${BOLD}Available Commands:${NC}"
    echo ""
    echo -e "  ${YELLOW}1${NC}) ${BOLD}start${NC}     - Start Home Assistant in background"
    echo -e "  ${YELLOW}2${NC}) ${BOLD}stop${NC}      - Stop Home Assistant"
    echo -e "  ${YELLOW}3${NC}) ${BOLD}restart${NC}   - Restart Home Assistant"
    echo -e "  ${YELLOW}4${NC}) ${BOLD}develop${NC}   - Run Home Assistant in foreground (debug mode)"
    echo -e "  ${YELLOW}5${NC}) ${BOLD}lint${NC}      - Run code quality checks (ruff format & check)"
    echo -e "  ${YELLOW}6${NC}) ${BOLD}test${NC}      - Run pytest tests with coverage"
    echo -e "  ${YELLOW}7${NC}) ${BOLD}logs${NC}      - View Home Assistant logs"
    echo -e "  ${YELLOW}8${NC}) ${BOLD}setup${NC}     - Sync dependencies (uv sync --extra dev)"
    echo -e "  ${YELLOW}9${NC}) ${BOLD}status${NC}    - Show detailed status"
    echo ""
    echo -e "  ${RED}q${NC}) ${BOLD}quit${NC}      - Exit menu (services continue running)"
    echo ""
}

# Function to show detailed status
show_status() {
    echo ""
    echo -e "${BOLD}=== System Status ===${NC}"
    echo ""
    
    # HA Process
    echo -e "${BOLD}Home Assistant:${NC}"
    if [ -f ".ha-pid" ]; then
        PID=$(cat .ha-pid)
        if ps -p "$PID" > /dev/null 2>&1; then
            echo -e "  Status: ${GREEN}RUNNING${NC} (PID: $PID)"
            echo -e "  URL: ${BOLD}http://localhost:8123${NC}"
            echo -e "  Uptime: $(ps -o etime= -p "$PID" | xargs)"
        else
            echo -e "  Status: ${RED}STOPPED${NC} (stale PID file)"
        fi
    else
        echo -e "  Status: ${RED}STOPPED${NC}"
    fi
    echo ""
    
    # Python Environment
    echo -e "${BOLD}Python Environment:${NC}"
    if [ -d ".venv" ]; then
        echo -e "  Virtual Env: ${GREEN}Active${NC} (.venv)"
        echo -e "  Python: $(uv run python --version 2>&1)"
        echo -e "  Packages: $(uv pip list 2>/dev/null | wc -l | xargs) installed"
    else
        echo -e "  Virtual Env: ${RED}Not found${NC} (run 'setup' to create)"
    fi
    echo ""
    
    # Tools
    echo -e "${BOLD}Development Tools:${NC}"
    echo -e "  UV: $(uv --version 2>&1)"
    echo -e "  Node.js: $(node --version 2>&1)"
    echo -e "  GitHub CLI: $(gh --version 2>&1 | head -1)"
    echo -e "  Copilot CLI: $(which github-copilot-cli >/dev/null 2>&1 && echo 'Installed' || echo 'Not found')"
    echo ""
    
    # Log file info
    if [ -f "config/home-assistant.log" ]; then
        LOG_SIZE=$(du -h config/home-assistant.log | cut -f1)
        LOG_LINES=$(wc -l < config/home-assistant.log)
        echo -e "${BOLD}Log File:${NC}"
        echo -e "  Size: $LOG_SIZE ($LOG_LINES lines)"
        echo -e "  Location: config/home-assistant.log"
        echo ""
    fi
}

# Function to view logs
view_logs() {
    echo ""
    if [ -f "config/home-assistant.log" ]; then
        echo -e "${BOLD}Showing last 50 lines (Press Ctrl+C to exit)...${NC}"
        echo ""
        sleep 1
        tail -f -n 50 config/home-assistant.log
    else
        echo -e "${RED}No log file found. Start Home Assistant first.${NC}"
        sleep 2
    fi
}

# Function to run a command
run_command() {
    local cmd=$1
    local script="./scripts/$cmd"
    
    echo ""
    if [ -f "$script" ]; then
        echo -e "${BOLD}Running: $script${NC}"
        echo ""
        "$script"
        local exit_code=$?
        echo ""
        if [ $exit_code -eq 0 ]; then
            echo -e "${GREEN}✓ Command completed successfully${NC}"
        else
            echo -e "${RED}✗ Command failed with exit code: $exit_code${NC}"
        fi
    else
        echo -e "${RED}Script not found: $script${NC}"
    fi
    echo ""
    echo -e "Press Enter to continue..."
    read
}

# Function to run tests
run_tests() {
    echo ""
    echo -e "${BOLD}Running tests with coverage...${NC}"
    echo ""
    uv run pytest --cov=custom_components.unraid_management_agent --cov-report=term-missing tests/
    local exit_code=$?
    echo ""
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ Tests passed${NC}"
    else
        echo -e "${RED}✗ Tests failed${NC}"
    fi
    echo ""
    echo -e "Press Enter to continue..."
    read
}

# Main loop
main() {
    while true; do
        show_header
        show_menu
        
        echo -ne "${BOLD}Select option [1-9, q]:${NC} "
        read -r choice
        
        case $choice in
            1|start)
                run_command "start"
                ;;
            2|stop)
                run_command "stop"
                ;;
            3|restart)
                run_command "restart"
                ;;
            4|develop)
                echo ""
                echo -e "${BOLD}Starting Home Assistant in development mode...${NC}"
                echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
                echo ""
                sleep 1
                ./scripts/develop
                echo ""
                echo -e "Press Enter to continue..."
                read
                ;;
            5|lint)
                run_command "lint"
                ;;
            6|test)
                run_tests
                ;;
            7|logs)
                view_logs
                ;;
            8|setup)
                run_command "setup"
                ;;
            9|status)
                show_status
                echo -e "Press Enter to continue..."
                read
                ;;
            q|quit|exit)
                echo ""
                echo -e "${GREEN}Exiting menu. Services will continue running in background.${NC}"
                echo -e "${GREEN}Run './scripts/menu' to return to this menu.${NC}"
                echo ""
                exit 0
                ;;
            *)
                echo ""
                echo -e "${RED}Invalid option. Please select 1-9 or q.${NC}"
                sleep 1
                ;;
        esac
    done
}

# Run the menu
main
