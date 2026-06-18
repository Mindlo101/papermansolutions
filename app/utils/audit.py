from sqlalchemy.orm import Session
from ..models.audit_log import AuditLog

def log_action(
    db: Session,
    user_id: int,
    username: str,
    action: str,
    table_name: str,
    record_id: int,
    old_value: str = None,
    new_value: str = None,
    ip_address: str = "0.0.0.0"
):
    log = AuditLog(
        user_id=user_id,
        username=username,
        action=action,
        table_name=table_name,
        record_id=record_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address
    )
    db.add(log)
    db.commit()