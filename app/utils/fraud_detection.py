"""
AI Fraud Detection Engine for PapermanSolutions LMS
Provides risk scoring and fraud flagging for loan applications
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..models.customer import Customer
from ..models.loan import Loan
from ..models.fraud_alert import FraudAlert
from ..models.blacklist import Blacklist


class FraudDetector:
    """AI Fraud Detection Engine"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def check_identity_fraud(self, customer: Customer) -> dict:
        """Check for identity-related fraud"""
        flags = []
        risk_score = 0
        
        # Check 1: Duplicate ID with different name
        existing_customers = self.db.query(Customer).filter(
            Customer.id_number == customer.id_number,
            Customer.id != customer.id
        ).all()
        
        for existing in existing_customers:
            if existing.first_name != customer.first_name or existing.last_name != customer.last_name:
                flags.append({
                    "type": "identity_mismatch",
                    "severity": "high",
                    "message": f"ID number matches existing customer with different name: {existing.first_name} {existing.last_name}"
                })
                risk_score += 25
        
        # Check 2: ID on blacklist
        blacklisted = self.db.query(Blacklist).filter(Blacklist.customer_id == customer.id).first()
        if blacklisted:
            flags.append({
                "type": "blacklisted",
                "severity": "critical",
                "message": f"Customer is blacklisted. Reason: {blacklisted.reason}"
            })
            risk_score += 40
        
        # Check 3: Suspicious ID format (basic check)
        if len(customer.id_number) < 6:
            flags.append({
                "type": "invalid_id_format",
                "severity": "medium",
                "message": "ID number format appears invalid (too short)"
            })
            risk_score += 10
        
        return {
            "flags": flags,
            "risk_score": min(risk_score, 100)
        }
    
    def check_loan_application_pattern(self, customer_id: int) -> dict:
        """Check for suspicious application patterns"""
        flags = []
        risk_score = 0
        
        # Check 1: Application frequency (last 30 days)
        thirty_days_ago = datetime.now().date() - timedelta(days=30)
        recent_applications = self.db.query(Loan).filter(
            Loan.customer_id == customer_id,
            Loan.created_at >= thirty_days_ago
        ).count()
        
        if recent_applications >= 5:
            flags.append({
                "type": "high_frequency",
                "severity": "high",
                "message": f"{recent_applications} applications in last 30 days (exceeds limit of 5)"
            })
            risk_score += 20
        elif recent_applications >= 3:
            flags.append({
                "type": "medium_frequency",
                "severity": "medium",
                "message": f"{recent_applications} applications in last 30 days (review recommended)"
            })
            risk_score += 10
        
        # Check 2: Active loans
        active_loans = self.db.query(Loan).filter(
            Loan.customer_id == customer_id,
            Loan.status.in_(["PENDING", "APPROVED", "DISBURSED", "ACTIVE"])
        ).count()
        
        if active_loans > 0:
            flags.append({
                "type": "active_loans",
                "severity": "medium",
                "message": f"Customer has {active_loans} active loan(s)"
            })
            risk_score += 15
        
        # Check 3: Increasing loan amounts pattern
        previous_loans = self.db.query(Loan).filter(
            Loan.customer_id == customer_id,
            Loan.status.in_(["APPROVED", "DISBURSED", "ACTIVE", "COMPLETED"])
        ).order_by(Loan.id.desc()).limit(3).all()
        
        if len(previous_loans) >= 2:
            amounts = [l.amount for l in previous_loans]
            if all(amounts[i] < amounts[i-1] for i in range(1, len(amounts))):
                flags.append({
                    "type": "increasing_amounts",
                    "severity": "medium",
                    "message": "Pattern of increasing loan amounts detected"
                })
                risk_score += 15
        
        return {
            "flags": flags,
            "risk_score": min(risk_score, 100)
        }
    
    def check_affordability(self, customer: Customer, loan_amount: float, term_months: int) -> dict:
        """Check if customer can afford the loan"""
        flags = []
        risk_score = 0
        
        # Check 1: Income vs Loan amount (Annual perspective)
        annual_income = customer.monthly_income * 12
        total_repayment = loan_amount * 1.3  # 30% interest
        
        if annual_income > 0:
            debt_to_income = (total_repayment / annual_income) * 100
            
            if debt_to_income > 50:
                flags.append({
                    "type": "high_debt_to_income",
                    "severity": "high",
                    "message": f"Debt-to-income ratio is {debt_to_income:.1f}% (exceeds 50%)"
                })
                risk_score += 30
            elif debt_to_income > 30:
                flags.append({
                    "type": "medium_debt_to_income",
                    "severity": "medium",
                    "message": f"Debt-to-income ratio is {debt_to_income:.1f}% (exceeds 30%)"
                })
                risk_score += 15
        
        # Check 2: Monthly installment vs monthly income (Monthly perspective)
        # FIXED: This is the important check that catches high installment ratios
        monthly_installment = total_repayment / term_months
        if customer.monthly_income > 0:
            installment_ratio = (monthly_installment / customer.monthly_income) * 100
            
            if installment_ratio > 50:
                flags.append({
                    "type": "high_installment_ratio",
                    "severity": "high",
                    "message": f"Monthly installment is {installment_ratio:.1f}% of income (exceeds 50%)"
                })
                risk_score += 35
            elif installment_ratio > 35:
                flags.append({
                    "type": "medium_installment_ratio",
                    "severity": "medium",
                    "message": f"Monthly installment is {installment_ratio:.1f}% of income (exceeds 35%)"
                })
                risk_score += 20
            elif installment_ratio > 25:
                flags.append({
                    "type": "low_installment_ratio",
                    "severity": "low",
                    "message": f"Monthly installment is {installment_ratio:.1f}% of income (exceeds 25%)"
                })
                risk_score += 8
        
        # Check 3: No income recorded
        if customer.monthly_income <= 0:
            flags.append({
                "type": "no_income",
                "severity": "high",
                "message": "No income recorded for this customer"
            })
            risk_score += 20
        
        # Check 4: Loan amount vs monthly income (how many months to repay)
        if customer.monthly_income > 0:
            months_to_repay = loan_amount / customer.monthly_income
            if months_to_repay > 12:
                flags.append({
                    "type": "loan_too_high_vs_income",
                    "severity": "medium",
                    "message": f"Loan amount is {months_to_repay:.1f} times monthly income (exceeds 12 months)"
                })
                risk_score += 15
            elif months_to_repay > 6:
                flags.append({
                    "type": "loan_moderate_vs_income",
                    "severity": "low",
                    "message": f"Loan amount is {months_to_repay:.1f} times monthly income (exceeds 6 months)"
                })
                risk_score += 8
        
        return {
            "flags": flags,
            "risk_score": min(risk_score, 100)
        }
    
    def detect_fraud(self, customer: Customer, loan_amount: float = 0, term_months: int = 0) -> dict:
        """
        Run all fraud detection checks and return comprehensive risk assessment
        """
        all_flags = []
        total_score = 0
        risk_level = "LOW"
        
        # Run all checks
        identity_check = self.check_identity_fraud(customer)
        pattern_check = self.check_loan_application_pattern(customer.id)
        affordability_check = self.check_affordability(customer, loan_amount, term_months)
        
        # Combine flags
        all_flags.extend(identity_check.get("flags", []))
        all_flags.extend(pattern_check.get("flags", []))
        all_flags.extend(affordability_check.get("flags", []))
        
        # Calculate total score
        scores = [
            identity_check.get("risk_score", 0),
            pattern_check.get("risk_score", 0),
            affordability_check.get("risk_score", 0)
        ]
        total_score = min(sum(scores), 100)
        
        # Determine risk level
        if total_score >= 70:
            risk_level = "HIGH"
        elif total_score >= 40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"
        
        # Determine AI decision
        if risk_level == "HIGH":
            ai_decision = "BLOCK"
        elif risk_level == "MEDIUM":
            ai_decision = "REVIEW"
        else:
            ai_decision = "APPROVE"
        
        return {
            "risk_score": total_score,
            "risk_level": risk_level,
            "ai_decision": ai_decision,
            "flags": all_flags,
            "flag_count": len(all_flags)
        }


def can_override_ai_decision(user_role: str, risk_level: str) -> bool:
    """
    Check if a user can override AI decision based on their role
    """
    if user_role == "admin":
        # Admin can override ANY AI decision
        return True
    elif user_role == "manager":
        # Manager can override LOW and MEDIUM risk only (not HIGH)
        if risk_level in ["LOW", "MEDIUM"]:
            return True
        return False
    else:
        # Loan Officer cannot override anything
        return False


def get_override_message(risk_level: str) -> str:
    """
    Get appropriate message for AI override
    """
    messages = {
        "LOW": "This loan was auto-approved by AI. Are you sure you want to reject it?",
        "MEDIUM": "This loan was flagged for review by AI. Are you sure you want to approve it?",
        "HIGH": "⚠️ This loan was BLOCKED by AI fraud detection. Only Admin can override this decision."
    }
    return messages.get(risk_level, "AI fraud detection override")