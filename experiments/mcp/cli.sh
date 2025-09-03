#!/bin/bash

# MEMG Core MCP Server - Clean CLI
# Smart defaults with automatic backups

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
TARGET_PATH=""
FRESH=false
STOP_ONLY=false
BACKUP_ONLY=false
SHOW_HELP=false
FORCE=false

if [[ $# -gt 0 && ! "$1" =~ ^-- ]]; then
    TARGET_PATH="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --fresh) FRESH=true; shift ;;
        --stop) STOP_ONLY=true; shift ;;
        --backup) BACKUP_ONLY=true; shift ;;
        --force) FORCE=true; shift ;;
        -h|--help) SHOW_HELP=true; shift ;;
        *) echo -e "${RED}❌ Unknown option: $1${NC}"; exit 1 ;;
    esac
done

show_help() {
    cat << EOF
🚀 MEMG Core MCP Server - Clean CLI

USAGE: $0 <target-path> [options]

OPTIONS:
  --fresh    Fresh start (auto-backup + clean rebuild) - requires confirmation
  --force    Skip safety confirmations (use with --fresh)
  --stop     Stop container
  --backup   Create manual backup
  --help     Show help

EXAMPLES:
  $0 software_developer/                    # Smart start
  $0 software_developer/ --fresh            # Fresh rebuild (with confirmation)
  $0 software_developer/ --fresh --force    # Fresh rebuild (no confirmation)
  $0 software_developer/ --stop             # Stop server
EOF
}

# Validation
validate_setup() {
    [ -z "$TARGET_PATH" ] && { echo -e "${RED}❌ Target path required${NC}"; exit 1; }

    TARGET_DIR="${TARGET_PATH%/}"
    [ ! -d "$TARGET_DIR" ] && { echo -e "${RED}❌ Directory not found: $TARGET_DIR${NC}"; exit 1; }

    local env_file="$TARGET_DIR/.env"
    [ ! -f "$env_file" ] && { echo -e "${RED}❌ .env file missing${NC}"; exit 1; }

    # Load environment
    eval $(grep -E '^(MEMORY_SYSTEM_MCP_PORT|MEMG_YAML_SCHEMA|BASE_MEMORY_PATH)=' "$env_file" | sed 's/^/export /')

    [ -z "$MEMORY_SYSTEM_MCP_PORT" ] && { echo -e "${RED}❌ MEMORY_SYSTEM_MCP_PORT missing${NC}"; exit 1; }
    [ -z "$MEMG_YAML_SCHEMA" ] && { echo -e "${RED}❌ MEMG_YAML_SCHEMA missing${NC}"; exit 1; }
    [ ! -f "$TARGET_DIR/$MEMG_YAML_SCHEMA" ] && { echo -e "${RED}❌ YAML file missing: $MEMG_YAML_SCHEMA${NC}"; exit 1; }

    # Check port conflict (skip for stop/backup operations)
    if [ "$STOP_ONLY" = false ] && [ "$BACKUP_ONLY" = false ]; then
        if lsof -Pi :$MEMORY_SYSTEM_MCP_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo -e "${RED}❌ Port $MEMORY_SYSTEM_MCP_PORT in use${NC}"
            echo "Stop first: $0 $TARGET_PATH --stop"
            exit 1
        fi
    fi

    # Check MCP files
    local files=("Dockerfile" "docker-compose.yml" "mcp_server.py" "requirements_mcp.txt")
    for file in "${files[@]}"; do
        [ ! -f "$file" ] && { echo -e "${RED}❌ $file missing (run from experiments/mcp/)${NC}"; exit 1; }
    done

    echo -e "${GREEN}✅ Setup validated - Port: $MEMORY_SYSTEM_MCP_PORT${NC}"
}

# Container status: 0=running, 1=stopped, 2=missing
check_container() {
    local project="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"
    local info=$(timeout 5 docker-compose --project-name "$project" ps 2>/dev/null || echo "")

    [ -z "$info" ] && return 2
    [ $(echo "$info" | tail -n +2 | wc -l) -eq 0 ] && return 2
    echo "$info" | grep -q "Up" && return 0 || return 1
}

# Backup functions
has_data() {
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"
    [ -d "$data_path" ] && [ -n "$(find "$data_path" -name "*.sqlite" -o -name "memg" 2>/dev/null)" ]
}

create_backup() {
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    if ! has_data; then
        echo -e "${BLUE}ℹ️  No data to backup${NC}"
        return 0
    fi

    mkdir -p "$TARGET_DIR/backups"
    local backup_file="$TARGET_DIR/backups/backup_$(date +%Y-%m-%d_%H-%M-%S).tar.gz"

    if tar -czf "$backup_file" -C "$(dirname "$data_path")" "$(basename "$data_path")" 2>/dev/null; then
        echo -e "${GREEN}✅ Backup created: $(basename "$backup_file")${NC}"
        # Keep last 5 backups
        ls -t "$TARGET_DIR/backups"/backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
    else
        echo -e "${RED}❌ Backup failed${NC}"; exit 1
    fi
}

# Safety confirmation for destructive operations
confirm_destructive_action() {
    local action="$1"
    echo -e "${RED}⚠️  WARNING: This will DELETE all existing data!${NC}"
    echo -e "${YELLOW}Action: $action${NC}"
    echo -e "${YELLOW}Data path: $TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}${NC}"
    echo ""
    echo -e "${BLUE}A backup will be created automatically before deletion.${NC}"
    echo ""
    echo -e "${RED}Type 'DELETE' to confirm (case-sensitive):${NC}"
    read -r confirmation

    if [ "$confirmation" != "DELETE" ]; then
        echo -e "${GREEN}✅ Operation cancelled - no data was deleted${NC}"
        exit 0
    fi
    echo -e "${YELLOW}⚠️  Proceeding with destructive operation...${NC}"
}

# Main operations
fresh_start() {
    local project="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    # Safety confirmation if data exists
    if has_data; then
        if [ "$FORCE" = false ]; then
            confirm_destructive_action "Fresh start (delete database + rebuild)"
        else
            echo -e "${YELLOW}⚠️  FORCE mode: Skipping confirmation but creating backup...${NC}"
        fi
    fi

    echo -e "${BLUE}🔄 Fresh start${NC}"
    create_backup
    docker-compose --project-name "$project" down 2>/dev/null || true
    [ -d "$data_path" ] && rm -rf "$data_path"
    mkdir -p "${data_path}/qdrant" "${data_path}/kuzu"
    docker-compose --project-name "$project" build --no-cache
    docker-compose --project-name "$project" up -d
}

smart_start() {
    local project="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    set +e  # Temporarily disable exit on error
    check_container
    local status=$?
    set -e  # Re-enable exit on error

    case $status in
        0) echo -e "${GREEN}✅ Already running${NC}" ;;
        1) echo -e "${BLUE}▶️  Starting...${NC}"; docker-compose --project-name "$project" up -d ;;
        2) echo -e "${BLUE}🔨 Building...${NC}"
           mkdir -p "${data_path}/qdrant" "${data_path}/kuzu"
           docker-compose --project-name "$project" build --no-cache
           docker-compose --project-name "$project" up -d ;;
    esac
}

wait_for_health() {
    echo -e "${BLUE}⏳ Starting...${NC}"
    sleep 3

    for i in {1..8}; do
        if curl -sf "http://localhost:$MEMORY_SYSTEM_MCP_PORT/health" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Server ready: http://localhost:$MEMORY_SYSTEM_MCP_PORT${NC}"
            return 0
        fi
        [ $i -lt 8 ] && sleep 2
    done

    echo -e "${RED}❌ Health check failed${NC}"
    echo "Check logs: docker-compose --project-name memg-mcp-$MEMORY_SYSTEM_MCP_PORT logs"
    exit 1
}

# Main execution
main() {
    [ "$SHOW_HELP" = true ] && { show_help; exit 0; }

    validate_setup
    PROJECT_NAME="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"

    # Set TARGET_PATH for docker-compose
    export TARGET_PATH="$([[ "$TARGET_DIR" == /* ]] && echo "$TARGET_DIR" || echo "./$TARGET_DIR")"

    if [ "$STOP_ONLY" = true ]; then
        docker-compose --project-name "$PROJECT_NAME" down || echo -e "${YELLOW}⚠️  Nothing to stop${NC}"
    elif [ "$BACKUP_ONLY" = true ]; then
        create_backup
    elif [ "$FRESH" = true ]; then
        fresh_start
        wait_for_health
    else
        echo -e "${BLUE}🧠 Smart start${NC}"
        smart_start
        wait_for_health
    fi
}

main "$@"
