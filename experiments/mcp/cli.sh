#!/bin/bash

# MEMG Core MCP Server - Safe CLI
# Safety-first approach with explicit flags and validation

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values (safe)
TARGET_PATH=""
REBUILD_SAFE=false
REBUILD_BACKUP=false
REBUILD_FORCE=false
START_ONLY=false
STOP_ONLY=false
RESTART_ONLY=false
RESET_DATABASE=false
RESTORE_BACKUP=""
SHOW_HELP=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --target-path)
            TARGET_PATH="$2"
            shift 2
            ;;
        --yaml-path)
            echo -e "${YELLOW}⚠️  --yaml-path is deprecated. Use --target-path instead${NC}"
            echo "  Example: $0 --target-path software_developer/"
            exit 1
            ;;
        --rebuild-safe)
            REBUILD_SAFE=true
            shift
            ;;
        --rebuild-backup)
            REBUILD_BACKUP=true
            shift
            ;;
        --rebuild-force)
            REBUILD_FORCE=true
            shift
            ;;
        --rebuild)
            echo -e "${YELLOW}⚠️  --rebuild is deprecated. Use:${NC}"
            echo "  --rebuild-safe    (only if no data exists)"
            echo "  --rebuild-backup  (backup first, then rebuild)"
            echo "  --rebuild-force   (dangerous, requires confirmation)"
            exit 1
            ;;
        --restore-backup)
            RESTORE_BACKUP="$2"
            shift 2
            ;;
        --start)
            START_ONLY=true
            shift
            ;;
        --stop)
            STOP_ONLY=true
            shift
            ;;
        --restart)
            RESTART_ONLY=true
            shift
            ;;
        --reset-database)
            RESET_DATABASE=true
            shift
            ;;
        -h|--help)
            SHOW_HELP=true
            shift
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Help function
show_help() {
    echo -e "${BLUE}🚀 MEMG Core MCP Server - Safe CLI${NC}"
    echo "=================================================="
    echo ""
    echo "USAGE:"
    echo "  $0 [OPTIONS]"
    echo ""
    echo "OPTIONS:"
echo "  --target-path PATH  Path to target directory containing .env and YAML files"
echo "  --rebuild-safe      Rebuild only if no data exists (safest)"
echo "  --rebuild-backup    Backup data first, then rebuild"
echo "  --rebuild-force     Force rebuild (DANGEROUS - requires confirmation)"
echo "  --start             Start existing container (if stopped)"
echo "  --stop              Stop container"
echo "  --restart           Restart container (preserve data)"
echo "  --reset-database    🚨 DELETE all database files (DANGEROUS)"
echo "  --restore-backup    Restore from backup file"
echo "  -h, --help          Show this help message"
    echo ""
    echo "SAFETY FEATURES:"
    echo "  ✅ Validates .env and YAML files before proceeding"
    echo "  ✅ Checks for port conflicts"
    echo "  ✅ Protects existing database files"
    echo "  ✅ No risky defaults"
    echo ""
    echo "EXAMPLES:"
echo "  # First time setup"
echo "  $0 --target-path software_developer/ --rebuild-safe"
echo ""
echo "  # Start existing setup"
echo "  $0 --target-path software_developer/ --start"
echo ""
echo "  # Safe rebuild (only if no data)"
echo "  $0 --target-path software_developer/ --rebuild-safe"
echo ""
echo "  # Rebuild with backup"
echo "  $0 --target-path software_developer/ --rebuild-backup"
echo ""
echo "  # Restore from backup"
echo "  $0 --target-path software_developer/ --restore-backup backups/backup_2024-08-30_13-45.tar.gz"
echo ""
echo "  # Clean restart (DANGEROUS - deletes data)"
echo "  $0 --target-path software_developer/ --reset-database --rebuild-safe"
    echo ""
}

# Validation functions
validate_target_path() {
    if [ -z "$TARGET_PATH" ]; then
        echo -e "${RED}❌ ERROR: --target-path is required${NC}"
        echo "Example: $0 --target-path software_developer/ --rebuild-safe"
        exit 1
    fi

    # Normalize target path (remove trailing slash for consistency)
    TARGET_DIR="${TARGET_PATH%/}"

    if [ ! -d "$TARGET_DIR" ]; then
        echo -e "${RED}❌ ERROR: Target directory not found: $TARGET_DIR${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ Target directory found: $TARGET_DIR${NC}"
}

validate_env_file() {
    local env_file="$TARGET_DIR/.env"

    if [ ! -f "$env_file" ]; then
        echo -e "${RED}❌ ERROR: .env file not found at $env_file${NC}"
        echo "Please create .env file with required variables:"
        echo "  MEMORY_SYSTEM_MCP_PORT=8008"
        echo "  MEMG_YAML_SCHEMA=your_schema.yaml"
        echo "  BASE_MEMORY_PATH=local_memory_data"
        exit 1
    fi

    # Load environment variables from target directory
    eval $(grep -E '^(MEMORY_SYSTEM_MCP_PORT|MEMG_YAML_SCHEMA|BASE_MEMORY_PATH)=' "$env_file" | sed 's/^/export /')

    # Validate required variables
    if [ -z "$MEMORY_SYSTEM_MCP_PORT" ]; then
        echo -e "${RED}❌ ERROR: MEMORY_SYSTEM_MCP_PORT not set in $env_file${NC}"
        exit 1
    fi

    if [ -z "$MEMG_YAML_SCHEMA" ]; then
        echo -e "${RED}❌ ERROR: MEMG_YAML_SCHEMA not set in $env_file${NC}"
        exit 1
    fi

    # Validate YAML file exists in target directory
    local yaml_file="$TARGET_DIR/$MEMG_YAML_SCHEMA"
    if [ ! -f "$yaml_file" ]; then
        echo -e "${RED}❌ ERROR: YAML file not found: $yaml_file${NC}"
        echo "Make sure $MEMG_YAML_SCHEMA exists in $TARGET_DIR"
        exit 1
    fi

    echo -e "${GREEN}✅ .env file validated${NC}"
    echo "  Port: $MEMORY_SYSTEM_MCP_PORT"
    echo "  YAML: $MEMG_YAML_SCHEMA"
    echo "  YAML Path: $yaml_file"
    echo "  Data Path: ${BASE_MEMORY_PATH:-local_memory_data}"
}

check_port_conflict() {
    local port=$1

    # Check if port is in use
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo -e "${RED}❌ ERROR: Port $port is already in use${NC}"
        echo ""
        echo "🛑 SAFETY STOP: Cannot proceed with port conflict"
        echo ""
        echo "Options:"
        echo "1. Change MEMORY_SYSTEM_MCP_PORT in .env to a different port"
        echo "2. Stop the service using port $port:"
        echo "   lsof -Pi :$port -sTCP:LISTEN"
        echo "3. If it's a previous MEMG container, stop it:"
        echo "   docker-compose --project-name memg-mcp-$port down"
        exit 1
    fi
    echo -e "${GREEN}✅ Port $port is available${NC}"
}

check_data_exists() {
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    if [ -d "$data_path" ]; then
        # Check if there's actual data (not just empty directories)
        if [ -n "$(find "$data_path" -name "*.sqlite" -o -name "memg" -o -name "*.wal" 2>/dev/null)" ]; then
            echo -e "${YELLOW}⚠️  Existing database found at: $data_path${NC}"
            return 0  # Data exists
        fi
    fi
    return 1  # No data
}

create_backup() {
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    if ! check_data_exists; then
        echo -e "${BLUE}ℹ️  No data to backup${NC}"
        return 0
    fi

    # Create backups directory in target directory
    mkdir -p "$TARGET_DIR/backups"

    # Create timestamped backup
    local timestamp=$(date +"%Y-%m-%d_%H-%M-%S")
    local backup_file="$TARGET_DIR/backups/backup_${timestamp}.tar.gz"

    echo -e "${BLUE}💾 Creating backup: $backup_file${NC}"

    if tar -czf "$backup_file" -C "$(dirname "$data_path")" "$(basename "$data_path")" 2>/dev/null; then
        echo -e "${GREEN}✅ Backup created successfully${NC}"
        echo "  File: $backup_file"
        echo "  Size: $(du -h "$backup_file" | cut -f1)"
        return 0
    else
        echo -e "${RED}❌ Failed to create backup${NC}"
        exit 1
    fi
}

restore_backup() {
    local backup_file="$1"

    # Handle relative backup paths
    if [[ "$backup_file" != /* ]]; then
        backup_file="$TARGET_DIR/$backup_file"
    fi

    if [ ! -f "$backup_file" ]; then
        echo -e "${RED}❌ ERROR: Backup file not found: $backup_file${NC}"
        exit 1
    fi

    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    echo -e "${BLUE}📥 Restoring from backup: $backup_file${NC}"
    echo -e "${YELLOW}⚠️  This will overwrite existing data${NC}"

    read -p "Type 'RESTORE' to confirm: " confirmation
    if [ "$confirmation" != "RESTORE" ]; then
        echo -e "${BLUE}ℹ️  Restore cancelled${NC}"
        exit 0
    fi

    # Remove existing data
    if [ -d "$data_path" ]; then
        rm -rf "$data_path"
    fi

    # Extract backup
    if tar -xzf "$backup_file" -C "$(dirname "$data_path")" 2>/dev/null; then
        echo -e "${GREEN}✅ Backup restored successfully${NC}"
        echo "  Data restored to: $data_path"
    else
        echo -e "${RED}❌ Failed to restore backup${NC}"
        exit 1
    fi
}

validate_mcp_files() {
    echo -e "${BLUE}📋 Validating MCP files in current directory...${NC}"

    # Check required files exist in current directory (mcp/)
    local files=("Dockerfile" "docker-compose.yml" "mcp_server.py" "requirements_mcp.txt" "yaml_docstring_helper.py")

    for file in "${files[@]}"; do
        if [ ! -f "$file" ]; then
            echo -e "${RED}❌ ERROR: $file not found in current directory${NC}"
            echo "Make sure you're running this script from the experiments/mcp/ directory"
            exit 1
        fi
    done

    echo -e "${GREEN}✅ All MCP files found${NC}"
}

reset_database() {
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    if [ -d "$data_path" ]; then
        echo -e "${RED}🚨 WARNING: This will DELETE ALL database files in $data_path${NC}"
        echo -e "${RED}This action cannot be undone!${NC}"
        echo ""
        read -p "Type 'DELETE' to confirm: " confirmation

        if [ "$confirmation" = "DELETE" ]; then
            echo -e "${YELLOW}🗑️  Deleting database files...${NC}"
            rm -rf "$data_path"
            echo -e "${GREEN}✅ Database files deleted${NC}"
        else
            echo -e "${BLUE}ℹ️  Database deletion cancelled${NC}"
            exit 0
        fi
    else
        echo -e "${BLUE}ℹ️  No database files found at $data_path${NC}"
    fi
}

create_data_directories() {
    local data_path="$TARGET_DIR/${BASE_MEMORY_PATH:-local_memory_data}_${MEMORY_SYSTEM_MCP_PORT}"

    echo -e "${BLUE}📁 Creating data directories...${NC}"
    mkdir -p "${data_path}/qdrant" "${data_path}/kuzu"
    chmod -R 755 "$data_path"
    echo -e "${GREEN}✅ Data directories ready: $data_path${NC}"
}

# Main execution
main() {
    echo -e "${BLUE}🚀 MEMG Core MCP Server - Safe CLI${NC}"
    echo "=================================================="

    # Show help if requested
    if [ "$SHOW_HELP" = true ]; then
        show_help
        exit 0
    fi

    # Validate target path first (required for all operations except help)
    validate_target_path

    # Handle restore backup first
    if [ -n "$RESTORE_BACKUP" ]; then
        validate_env_file
        restore_backup "$RESTORE_BACKUP"
        exit 0
    fi

    # If no arguments provided, show safe default behavior
    if [ "$REBUILD_SAFE" = false ] && [ "$REBUILD_BACKUP" = false ] && [ "$REBUILD_FORCE" = false ] && [ "$START_ONLY" = false ] && [ "$STOP_ONLY" = false ] && [ "$RESTART_ONLY" = false ] && [ "$RESET_DATABASE" = false ]; then
        echo -e "${YELLOW}⚠️  No action specified. This is safe mode.${NC}"
        echo ""
        echo "Target directory contents ($TARGET_DIR):"
        ls -la "$TARGET_DIR" | grep -E "\.(env|yaml|yml)$" || echo "  No relevant files found"
        echo ""
        echo "Suggestions:"
        if [ ! -f "$TARGET_DIR/.env" ]; then
            echo "  1. Create .env file in $TARGET_DIR"
        fi
        if [ -f "$TARGET_DIR/.env" ]; then
            echo "  2. Run: $0 --target-path $TARGET_PATH --rebuild-safe  (first time setup)"
            echo "  3. Run: $0 --target-path $TARGET_PATH --start  (start existing setup)"
        fi
        echo ""
        echo "Use --help for full options"
        exit 0
    fi

    # Validate environment
    validate_env_file

    # Handle stop-only case (no port check needed)
    if [ "$STOP_ONLY" = true ]; then
        echo -e "${BLUE}🛑 Stopping MCP server...${NC}"
        PROJECT_NAME="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"
        docker-compose --project-name "$PROJECT_NAME" down || echo -e "${YELLOW}⚠️  No container to stop${NC}"
        exit 0
    fi

    # Check port availability (except for stop)
    check_port_conflict "$MEMORY_SYSTEM_MCP_PORT"

    # Handle database reset if requested
    if [ "$RESET_DATABASE" = true ]; then
        reset_database
    fi

    # Validate MCP files in current directory
    validate_mcp_files

    # Stay in MCP directory for Docker operations (no need to change directory)
    echo -e "${BLUE}📂 Working from MCP directory: $(pwd)${NC}"
    echo -e "${BLUE}📂 Target directory: $TARGET_DIR${NC}"

    # Create data directories
    create_data_directories

    PROJECT_NAME="memg-mcp-${MEMORY_SYSTEM_MCP_PORT}"

    # Export TARGET_PATH for docker-compose (ensure it's a relative path with ./ prefix)
    if [[ "$TARGET_DIR" == /* ]]; then
        # Absolute path - use as is
        export TARGET_PATH="$TARGET_DIR"
    else
        # Relative path - ensure it starts with ./
        export TARGET_PATH="./$TARGET_DIR"
    fi

    # Handle different actions
    if [ "$START_ONLY" = true ]; then
        echo -e "${BLUE}▶️  Starting MCP server...${NC}"
        docker-compose --project-name "$PROJECT_NAME" up -d

    elif [ "$RESTART_ONLY" = true ]; then
        echo -e "${BLUE}🔄 Restarting MCP server...${NC}"
        docker-compose --project-name "$PROJECT_NAME" restart

    elif [ "$REBUILD_SAFE" = true ]; then
        if check_data_exists; then
            echo -e "${RED}❌ ERROR: Existing data found${NC}"
            echo -e "${YELLOW}⚠️  --rebuild-safe only works when no data exists${NC}"
            echo ""
            echo "Options:"
            echo "  1. Use --rebuild-backup to backup first"
            echo "  2. Use --rebuild-force (dangerous)"
            echo "  3. Use --reset-database first (deletes data)"
            exit 1
        fi
        echo -e "${BLUE}🔨 Safe rebuilding MCP server (no data exists)...${NC}"
        docker-compose --project-name "$PROJECT_NAME" down || true
        docker-compose --project-name "$PROJECT_NAME" build --no-cache
        docker-compose --project-name "$PROJECT_NAME" up -d

    elif [ "$REBUILD_BACKUP" = true ]; then
        create_backup
        echo -e "${BLUE}🔨 Rebuilding MCP server (backup created)...${NC}"
        docker-compose --project-name "$PROJECT_NAME" down || true
        docker-compose --project-name "$PROJECT_NAME" build --no-cache
        docker-compose --project-name "$PROJECT_NAME" up -d

    elif [ "$REBUILD_FORCE" = true ]; then
        if check_data_exists; then
            echo -e "${RED}🚨 WARNING: This will rebuild with existing data${NC}"
            echo -e "${RED}This may cause data corruption or inconsistency!${NC}"
            echo ""
            read -p "Type 'FORCE' to confirm dangerous rebuild: " confirmation
            if [ "$confirmation" != "FORCE" ]; then
                echo -e "${BLUE}ℹ️  Rebuild cancelled${NC}"
                exit 0
            fi
        fi
        echo -e "${BLUE}🔨 Force rebuilding MCP server...${NC}"
        docker-compose --project-name "$PROJECT_NAME" down || true
        docker-compose --project-name "$PROJECT_NAME" build --no-cache
        docker-compose --project-name "$PROJECT_NAME" up -d
    fi

    # Wait and test
    if [ "$START_ONLY" = true ] || [ "$REBUILD_SAFE" = true ] || [ "$REBUILD_BACKUP" = true ] || [ "$REBUILD_FORCE" = true ] || [ "$RESTART_ONLY" = true ]; then
        echo -e "${BLUE}⏳ Waiting for server startup...${NC}"
        sleep 5

        # Test health endpoint
        for i in {1..10}; do
            if curl -f "http://localhost:$MEMORY_SYSTEM_MCP_PORT/health" > /dev/null 2>&1; then
                echo -e "${GREEN}✅ MCP Server is running successfully!${NC}"
                echo ""
                echo -e "${BLUE}🌐 Server URLs:${NC}"
                echo "  Health: http://localhost:$MEMORY_SYSTEM_MCP_PORT/health"
                echo "  Root:   http://localhost:$MEMORY_SYSTEM_MCP_PORT/"
                echo ""
                echo -e "${BLUE}🔧 Management:${NC}"
                echo "  Stop:        $0 --stop"
                echo "  Restart:     $0 --restart"
                echo "  Rebuild:     $0 --rebuild-backup"
                echo "  Safe Build:  $0 --rebuild-safe"
                break
            elif [ $i -eq 10 ]; then
                echo -e "${RED}❌ Health check failed after 10 attempts${NC}"
                echo ""
                echo "Check logs:"
                echo "  docker-compose --project-name $PROJECT_NAME logs"
                exit 1
            else
                echo "  Attempt $i/10..."
                sleep 2
            fi
        done
    fi
}

# Run main function
main "$@"
