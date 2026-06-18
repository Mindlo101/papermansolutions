import shutil
import os
from datetime import datetime

print("📋 Available backups:")
backup_dir = "backups"

if not os.path.exists(backup_dir):
    print("❌ No backups directory found!")
    exit()

backups = sorted([f for f in os.listdir(backup_dir) if f.endswith('.db')])
if not backups:
    print("❌ No backup files found!")
    exit()

for i, b in enumerate(backups, 1):
    b_path = os.path.join(backup_dir, b)
    b_size = os.path.getsize(b_path)
    print(f"   {i}. {b} ({b_size / 1024:.2f} KB)")

print("\nEnter the number of the backup to restore (or 0 to cancel):")
choice = input("> ")

try:
    choice_num = int(choice)
    if choice_num == 0:
        print("❌ Restore cancelled.")
        exit()
    if choice_num < 1 or choice_num > len(backups):
        print("❌ Invalid selection!")
        exit()
    
    selected = backups[choice_num - 1]
    backup_path = os.path.join(backup_dir, selected)
    
    # Create a backup of current database before restoring
    if os.path.exists("papermansolutions.db"):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        pre_restore_backup = f"backups/pre_restore_backup_{timestamp}.db"
        shutil.copy2("papermansolutions.db", pre_restore_backup)
        print(f"✅ Current database backed up to: {pre_restore_backup}")
    
    # Restore the selected backup
    shutil.copy2(backup_path, "papermansolutions.db")
    print(f"✅ Database restored from: {selected}")
    print(f"📏 File size: {os.path.getsize('papermansolutions.db') / 1024:.2f} KB")
    
except ValueError:
    print("❌ Invalid input!")