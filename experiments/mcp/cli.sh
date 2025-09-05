#!/bin/bash

# MEMG Core MCP Server - Simplified CLI
# Usage: ./cli.sh path/to/schema.yaml [options]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Parse arguments
YAML_FILE=""
PORT=""
DATABASE_PATH=""
FRESH=false
STOP_ONLY=false
BACKUP_ONLY=false
SHOW_HELP=false
FORCE=false
NO_MOUNT=false

if [[ $# -gt 0 && ! "$1" =~ ^-- ]]; then
    YAML_FILE="$1"
    shift
fi

while [[ $# -gt 0 ]]; do
    case $1 in
        --fresh) FRESH=true; shift ;;
        --stop) STOP_ONLY=true; shift ;;
        --backup) BACKUP_ONLY=true; shift ;;
        --force) FORCE=true; shift ;;
        --no-mount) NO_MOUNT=true; shift ;;
        --port|-p) PORT="$2"; shift 2 ;;
        --database-path) DATABASE_PATH="$2"; shift 2 ;;
        -h|--help) SHOW_HELP=true; shift ;;
        *) echo -e "${RED}❌ Unknown option: $1${NC}"; exit 1 ;;
    esac
done

show_help() {
    cat << EOF
🚀 MEMG Core MCP Server - Simplified CLI

USAGE: $0 <yaml-file> [options]

OPTIONS:
  --fresh          Fresh start (auto-backup + clean rebuild) - requires confirmation
  --force          Skip safety confirmations (use with --fresh)
  --no-mount       Copy YAML into container (no runtime mount) - ephemeral data
  --port, -p       Override port (default: 8888, or from .env if exists)
  --database-path  Override database storage location (default: same as YAML file)
  --stop           Stop container
  --backup         Create manual backup
  --help           Show help

EXAMPLES:
  $0 path/to/myschema.yaml                              # Smart start (default port 8888)
  $0 path/to/myschema.yaml --port 8228                  # Use specific port
  $0 myschema.yaml --database-path ~/my_memories        # Store in ~/my_memories/myschema_8888/
  $0 path/to/myschema.yaml --fresh                      # Fresh rebuild (with confirmation)
  $0 path/to/myschema.yaml --no-mount                   # Self-contained (ephemeral)
  $0 path/to/myschema.yaml --stop                       # Stop server
EOF
}

# Validation
validate_setup() {
    [ -z "$YAML_FILE" ] && { echo -e "${RED}❌ YAML file path required${NC}"; show_help; exit 1; }
    [ ! -f "$YAML_FILE" ] && { echo -e "${RED}❌ YAML file not found: $YAML_FILE${NC}"; exit 1; }

    # Determine port (priority: --port > .env > default)
    MEMORY_SYSTEM_MCP_PORT="8888"  # Default

    # Override with .env if exists
    if [ -f ".env" ]; then
        ENV_PORT=$(grep -E '^MEMORY_SYSTEM_MCP_PORT=' .env 2>/dev/null | cut -d'=' -f2 | tr -d '"')
        [ -n "$ENV_PORT" ] && MEMORY_SYSTEM_MCP_PORT="$ENV_PORT"
        echo -e "${BLUE}ℹ️  Found .env file, using port from .env${NC}"
    else
        echo -e "${BLUE}ℹ️  No .env file found, using default port${NC}"
    fi

    # Override with CLI --port if provided
    if [ -n "$PORT" ]; then
        MEMORY_SYSTEM_MCP_PORT="$PORT"
        echo -e "${BLUE}ℹ️  Using port from --port argument${NC}"
    fi

    # Validate port is numeric
    if ! [[ "$MEMORY_SYSTEM_MCP_PORT" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}❌ Invalid port: $MEMORY_SYSTEM_MCP_PORT${NC}"
        exit 1
    fi

    # Extract schema name from file path (without extension)
    SCHEMA_NAME=$(basename "$YAML_FILE" .yaml)
    SCHEMA_NAME=$(basename "$SCHEMA_NAME" .yml)

    # Database path: use --database-path if provided, otherwise same directory as YAML file
    if [ -z "$DATABASE_PATH" ]; then
        # Default to YAML file directory (convert to absolute path)
        DATABASE_PATH=$(cd "$(dirname "$YAML_FILE")" && pwd)
        echo -e "${BLUE}ℹ️  Using default database path (same as YAML file): $DATABASE_PATH${NC}"
    else
        # Convert custom database path to absolute path
        DATABASE_PATH=$(cd "$DATABASE_PATH" && pwd)
        echo -e "${BLUE}ℹ️  Using custom database path: $DATABASE_PATH${NC}"
    fi

    # Set environment variables for docker-compose
    export YAML_FILE
    export SCHEMA_NAME
    export MEMORY_SYSTEM_MCP_PORT
    export DATABASE_PATH

    # Create database directories if not in no-mount mode
    if [ "$NO_MOUNT" != true ] && [ "$STOP_ONLY" = false ] && [ "$BACKUP_ONLY" = false ]; then
        local data_path="${DATABASE_PATH}/${SCHEMA_NAME}_${MEMORY_SYSTEM_MCP_PORT}"
        mkdir -p "${data_path}/qdrant" "${data_path}/kuzu"
        echo -e "${BLUE}ℹ️  Created database directories: $data_path${NC}"
    fi

    # Check port conflict (skip for stop/backup operations)
    if [ "$STOP_ONLY" = false ] && [ "$BACKUP_ONLY" = false ]; then
        if lsof -Pi :$MEMORY_SYSTEM_MCP_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo -e "${RED}❌ Port $MEMORY_SYSTEM_MCP_PORT in use${NC}"
            echo "Stop first: $0 $YAML_FILE --stop"
            exit 1
        fi
    fi

    # Check MCP files
    local files=("Dockerfile" "docker-compose.yml" "server.py" "requirements_mcp.txt")
    for file in "${files[@]}"; do
        [ ! -f "$file" ] && { echo -e "${RED}❌ $file missing (run from experiments/mcp/)${NC}"; exit 1; }
    done

    # Validate no-mount files exist
    if [ "$NO_MOUNT" = true ]; then
        if [ ! -f "Dockerfile.no-mount" ] || [ ! -f "docker-compose.no-mount.yml" ]; then
            echo -e "${RED}❌ No-mount Docker files missing (Dockerfile.no-mount, docker-compose.no-mount.yml)${NC}"
            exit 1
        fi
        echo -e "${BLUE}✅ Using no-mount mode (ephemeral data)${NC}"
    else
        echo -e "${BLUE}✅ Using mount mode (persistent data in ${SCHEMA_NAME}_${MEMORY_SYSTEM_MCP_PORT}/)${NC}"
    fi

    echo -e "${GREEN}✅ Setup validated - Port: $MEMORY_SYSTEM_MCP_PORT, Schema: $SCHEMA_NAME${NC}"
}

# Container status: 0=running, 1=stopped, 2=missing
check_container() {
    local project="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"
    local info=$(timeout 5 docker-compose --project-name "$project" ps 2>/dev/null || echo "")

    [ -z "$info" ] && return 2
    [ $(echo "$info" | tail -n +2 | wc -l) -eq 0 ] && return 2
    echo "$info" | grep -q "Up" && return 0 || return 1
}

# Backup functions (only for mount mode)
has_data() {
    [ "$NO_MOUNT" = true ] && return 1  # No-mount mode has no persistent data
    local data_path="${DATABASE_PATH}/${SCHEMA_NAME}_${MEMORY_SYSTEM_MCP_PORT}"
    [ -d "$data_path" ] && [ -n "$(find "$data_path" -name "*.sqlite" -o -name "memg" 2>/dev/null)" ]
}

create_backup() {
    if ! has_data; then
        echo -e "${BLUE}ℹ️  No data to backup${NC}"
        return 0
    fi

    mkdir -p "backups"
    local data_path="${DATABASE_PATH}/${SCHEMA_NAME}_${MEMORY_SYSTEM_MCP_PORT}"
    local backup_file="backups/${SCHEMA_NAME}_backup_$(date +%Y-%m-%d_%H-%M-%S).tar.gz"

    if tar -czf "$backup_file" "$data_path" 2>/dev/null; then
        echo -e "${GREEN}✅ Backup created: $(basename "$backup_file")${NC}"
        # Keep last 5 backups
        ls -t backups/${SCHEMA_NAME}_backup_*.tar.gz 2>/dev/null | tail -n +6 | xargs -r rm -f
    else
        echo -e "${RED}❌ Backup failed${NC}"; exit 1
    fi
}

# Safety confirmation for destructive operations
confirm_destructive_action() {
    local action="$1"
    echo -e "${RED}⚠️  WARNING: This will DELETE all existing data!${NC}"
    echo -e "${YELLOW}Action: $action${NC}"
    echo -e "${YELLOW}Data path: ${SCHEMA_NAME}_${MEMORY_SYSTEM_MCP_PORT}${NC}"
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
    local data_path="${DATABASE_PATH}/${SCHEMA_NAME}_${MEMORY_SYSTEM_MCP_PORT}"
    local compose_file=""

    # Set compose file based on mount option
    if [ "$NO_MOUNT" = true ]; then
        compose_file="-f docker-compose.no-mount.yml"
        echo -e "${BLUE}🔄 Fresh start (no-mount mode)${NC}"
    else
        echo -e "${BLUE}🔄 Fresh start${NC}"
        # Safety confirmation if data exists
        if has_data; then
            if [ "$FORCE" = false ]; then
                confirm_destructive_action "Fresh start (delete database + rebuild)"
            else
                echo -e "${YELLOW}⚠️  FORCE mode: Skipping confirmation but creating backup...${NC}"
            fi
        fi
    fi

    create_backup
    docker-compose $compose_file --project-name "$project" down 2>/dev/null || true

    # Only create/clean directories if not in no-mount mode
    if [ "$NO_MOUNT" != true ]; then
        [ -d "$data_path" ] && rm -rf "$data_path"
        mkdir -p "${data_path}/qdrant" "${data_path}/kuzu"
    fi

    docker-compose $compose_file --project-name "$project" build --no-cache
    docker-compose $compose_file --project-name "$project" up -d
}

smart_start() {
    local project="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"
    local data_path="${DATABASE_PATH}/${SCHEMA_NAME}_${MEMORY_SYSTEM_MCP_PORT}"
    local compose_file=""

    # Set compose file based on mount option
    if [ "$NO_MOUNT" = true ]; then
        compose_file="-f docker-compose.no-mount.yml"
        echo -e "${BLUE}🧠 Smart start (no-mount mode - forcing rebuild)${NC}"
        # No-mount mode always requires rebuild since YAML is copied into image
        # No directory creation needed - everything is self-contained in container
        docker-compose $compose_file --project-name "$project" build --no-cache
        docker-compose $compose_file --project-name "$project" up -d
        return
    fi

    set +e  # Temporarily disable exit on error
    check_container
    local status=$?
    set -e  # Re-enable exit on error

    case $status in
        0) echo -e "${GREEN}✅ Already running${NC}" ;;
        1) echo -e "${BLUE}▶️  Starting...${NC}"; docker-compose $compose_file --project-name "$project" up -d ;;
        2) echo -e "${BLUE}🔨 Building...${NC}"
           # Only create directories for regular (non-no-mount) mode
           if [ "$NO_MOUNT" != true ]; then
               mkdir -p "${data_path}/qdrant" "${data_path}/kuzu"
           fi
           docker-compose $compose_file --project-name "$project" build --no-cache
           docker-compose $compose_file --project-name "$project" up -d ;;
    esac
}

wait_for_health() {
    echo -e "${BLUE}⏳ Starting...${NC}"
    sleep 3

    for i in {1..8}; do
        if curl -sf "http://localhost:$MEMORY_SYSTEM_MCP_PORT/health" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ Server ready: http://localhost:$MEMORY_SYSTEM_MCP_PORT${NC}"
            echo -e "${GREEN}✅ Schema: $(basename "$YAML_FILE")${NC}"
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

    # Set compose file for operations
    local compose_file=""
    if [ "$NO_MOUNT" = true ]; then
        compose_file="-f docker-compose.no-mount.yml"
    fi

    if [ "$STOP_ONLY" = true ]; then
        docker-compose $compose_file --project-name "$PROJECT_NAME" down || echo -e "${YELLOW}⚠️  Nothing to stop${NC}"
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
