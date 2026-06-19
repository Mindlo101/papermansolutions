"""
Cron job to permanently delete customers that have been in trash for more than 30 days.
Run this daily using a scheduler.
"""

from datetime import datetime, timedelta
import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.database import SessionLocal
from app.models.customer import Customer

def cleanup_deleted_customers():
    """Permanently delete customers that were deleted more than 30 days ago"""
    db = SessionLocal()
    try:
        thirty_days_ago = datetime.now() - timedelta(days=30)
        
        # Find customers deleted more than 30 days ago
        old_deleted = db.query(Customer).filter(
            Customer.deleted_at.isnot(None),
            Customer.deleted_at < thirty_days_ago
        ).all()
        
        count = len(old_deleted)
        for customer in old_deleted:
            db.delete(customer)
        
        db.commit()
        print(f"✅ Cleaned up {count} customers from trash (older than 30 days)")
        return count
    except Exception as e:
        print(f"❌ Error cleaning up trash: {e}")
        db.rollback()
        return 0
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_deleted_customers()