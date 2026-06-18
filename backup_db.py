import shutil
import os
from datetime import datetime

# Source and destination paths
source = "papermansolutions.db"
backup_dir = "backups"

# Create backup directory if it doesn't exist
if not os.path.exists(backup_dir):
    os.makedirs(backup_dir)
    print(f"📁 Created backup directory: {backup_dir}")

# Create backup filename with timestamp
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
backup_file = f"{backup_dir}/papermansolutions_backup_{timestamp}.db"

# Copy the database
if os.path.exists(source):
    # Get file size before backup
    file_size = os.path.getsize(source)
    shutil.copy2(source, backup_file)
    print(f"✅ Database backed up successfully!")
    print(f"📁 Location: {backup_file}")
    print(f"📏 File size: {file_size} bytes ({file_size / 1024:.2f} KB)")
    
    # List all backups
    print("\n📋 All backups:")
    backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
    for i, b in enumerate(backups, 1):
        b_path = os.path.join(backup_dir, b)
        b_size = os.path.getsize(b_path)
        print(f"   {i}. {b} ({b_size / 1024:.2f} KB)")
else:
    print("❌ Database file 'papermansolutions.db' not found!")
    print("   Make sure you're in the correct directory.")