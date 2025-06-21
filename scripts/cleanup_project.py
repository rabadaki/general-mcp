#!/usr/bin/env python3
"""
Comprehensive Project Cleanup Script

This script will:
1. Create proper directory structure
2. Move files to appropriate locations
3. Remove duplicate/unnecessary files
4. Clean up debug logs and temporary files
"""

import os
import shutil
import glob
from pathlib import Path

def create_directory_structure():
    """Create organized directory structure"""
    directories = [
        "src",
        "tests", 
        "docs",
        "config",
        "scripts",
        "backup",
        "logs"
    ]
    
    for dir_name in directories:
        os.makedirs(dir_name, exist_ok=True)
        print(f"✅ Created directory: {dir_name}")

def move_test_files():
    """Move all test files to tests directory"""
    test_files = glob.glob("test_*.py")
    
    for test_file in test_files:
        try:
            shutil.move(test_file, f"tests/{test_file}")
            print(f"📁 Moved {test_file} to tests/")
        except Exception as e:
            print(f"❌ Error moving {test_file}: {e}")

def move_documentation():
    """Move documentation files to docs directory"""
    doc_files = [
        "*.md",
        "FORCE_REBUILD*"
    ]
    
    for pattern in doc_files:
        for doc_file in glob.glob(pattern):
            if doc_file != "README.md":  # Keep README in root
                try:
                    shutil.move(doc_file, f"docs/{doc_file}")
                    print(f"📚 Moved {doc_file} to docs/")
                except Exception as e:
                    print(f"❌ Error moving {doc_file}: {e}")

def move_scripts():
    """Move shell scripts to scripts directory"""
    script_files = glob.glob("*.sh")
    
    for script_file in script_files:
        try:
            shutil.move(script_file, f"scripts/{script_file}")
            print(f"🔧 Moved {script_file} to scripts/")
        except Exception as e:
            print(f"❌ Error moving {script_file}: {e}")

def move_config_files():
    """Move configuration files to config directory"""
    config_files = [
        "requirements.txt",
        "mcp_requirements.txt", 
        "*.json",
        "mcp_*.py"
    ]
    
    for pattern in config_files:
        for config_file in glob.glob(pattern):
            # Skip main server files
            if config_file not in ["mcp_stdio_server.py"]:
                try:
                    shutil.move(config_file, f"config/{config_file}")
                    print(f"⚙️  Moved {config_file} to config/")
                except Exception as e:
                    print(f"❌ Error moving {config_file}: {e}")

def move_source_files():
    """Move main source files to src directory"""
    source_files = [
        "mcp_stdio_server.py",
        "server.py"
    ]
    
    for src_file in source_files:
        if os.path.exists(src_file):
            try:
                shutil.copy2(src_file, f"src/{src_file}")
                print(f"💻 Copied {src_file} to src/")
            except Exception as e:
                print(f"❌ Error copying {src_file}: {e}")

def backup_old_files():
    """Move backup and old files to backup directory"""
    backup_patterns = [
        "*_backup.py",
        "backup_*",
        "old_*"
    ]
    
    for pattern in backup_patterns:
        for backup_file in glob.glob(pattern):
            try:
                shutil.move(backup_file, f"backup/{backup_file}")
                print(f"💾 Moved {backup_file} to backup/")
            except Exception as e:
                print(f"❌ Error moving {backup_file}: {e}")

def clean_logs_and_temp():
    """Clean up log files and temporary files"""
    # Move logs
    log_files = ["*.log"]
    for pattern in log_files:
        for log_file in glob.glob(pattern):
            try:
                shutil.move(log_file, f"logs/{log_file}")
                print(f"📋 Moved {log_file} to logs/")
            except Exception as e:
                print(f"❌ Error moving {log_file}: {e}")
    
    # Remove temporary files
    temp_patterns = [
        "__pycache__",
        "*.pyc", 
        ".DS_Store",
        "*.tmp"
    ]
    
    for pattern in temp_patterns:
        for temp_item in glob.glob(pattern):
            try:
                if os.path.isdir(temp_item):
                    shutil.rmtree(temp_item)
                else:
                    os.remove(temp_item)
                print(f"🗑️  Removed {temp_item}")
            except Exception as e:
                print(f"❌ Error removing {temp_item}: {e}")

def remove_duplicate_venvs():
    """Remove duplicate virtual environments, keep only venv"""
    venv_dirs = ["mcp_env"]
    
    for venv_dir in venv_dirs:
        if os.path.exists(venv_dir):
            try:
                shutil.rmtree(venv_dir)
                print(f"🗑️  Removed duplicate venv: {venv_dir}")
            except Exception as e:
                print(f"❌ Error removing {venv_dir}: {e}")

def create_gitignore():
    """Create/update .gitignore file"""
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
venv/
env/
ENV/
mcp_env/

# IDE
.vscode/
.cursor/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
*.log
logs/

# Temporary files
*.tmp
*.temp

# API keys and secrets
.env
secrets.json

# Test artifacts
.pytest_cache/
.coverage
htmlcov/
"""
    
    with open(".gitignore", "w") as f:
        f.write(gitignore_content)
    print("📝 Updated .gitignore")

def main():
    """Run the complete cleanup"""
    print("🧹 Starting comprehensive project cleanup...\n")
    
    # Create directory structure
    create_directory_structure()
    print()
    
    # Move files to appropriate directories
    move_test_files()
    move_documentation() 
    move_scripts()
    move_config_files()
    move_source_files()
    backup_old_files()
    print()
    
    # Clean up temporary files and logs
    clean_logs_and_temp()
    remove_duplicate_venvs()
    print()
    
    # Create .gitignore
    create_gitignore()
    print()
    
    print("✅ Project cleanup completed!")
    print("\n📁 New directory structure:")
    print("├── src/           # Main source code")
    print("├── tests/         # All test files") 
    print("├── docs/          # Documentation")
    print("├── config/        # Configuration files")
    print("├── scripts/       # Shell scripts")
    print("├── backup/        # Backup files")
    print("├── logs/          # Log files")
    print("└── venv/          # Virtual environment")

if __name__ == "__main__":
    main() 