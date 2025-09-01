# CLI Usage Guide

## 🚀 **Commands**

```bash
./cli.sh <target-path> [options]
```

### **Smart Start (Default)**
```bash
./cli.sh software_developer/
```
- **Running?** → Shows "already running"
- **Stopped?** → Starts existing container
- **Missing?** → Builds and starts new container
- **Never destroys data**

### **Fresh Start**
```bash
./cli.sh software_developer/ --fresh
```
1. Auto-backup to `target/backups/`
2. Stop container
3. Delete database files
4. Rebuild container
5. Start with empty database

### **Other Commands**
```bash
./cli.sh project/ --stop     # Stop server
./cli.sh project/ --backup   # Manual backup
./cli.sh --help             # Show help
```

## 🛡️ **Safety Features**

- **Auto-backup** before `--fresh` operations
- **Confirmation required** for destructive operations (type "DELETE")
- **5 backup retention** with automatic cleanup
- **Port conflict detection** with fix suggestions

## 🔄 **Backup & Restore**

### **Restore Process**
```bash
# 1. Stop server
./cli.sh project/ --stop

# 2. Extract backup
cd project/
tar -xzf backups/backup_2024-01-15_14-30.tar.gz

# 3. Restart
cd ../experiments/mcp/
./cli.sh project/
```

### **Check Backups**
```bash
ls -la project/backups/
```

## 🐛 **Troubleshooting**

**Port in use:** `./cli.sh project/ --stop`
**Won't start:** `./cli.sh project/ --fresh`
**Check logs:** `docker-compose --project-name memg-mcp-{PORT} logs`
