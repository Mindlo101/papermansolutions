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
        """Check if customer can afford the loan - recommends max amount based on 30% of income"""
        flags = []
        risk_score = 0
        
        # If no income recorded, flag it
        if not customer.monthly_income or customer.monthly_income <= 0:
            flags.append({
                "type": "no_income",
                "severity": "high",
                "message": "No income recorded for this customer. Please verify income details before approving."
            })
            risk_score += 40
            return {
                "flags": flags,
                "risk_score": min(risk_score, 100)
            }
        
        monthly_income = customer.monthly_income
        
        # ==========================================
        # CALCULATE MAX AFFORDABLE LOAN
        # 30% of income is the safe repayment capacity
        # Total repayment = Loan × 1.3 (30% interest)
        # So: Loan × 1.3 = Income × 30%
        # Therefore: Loan = (Income × 30%) / 1.3
        # ==========================================
        max_repayment_capacity = monthly_income * 0.30
        max_affordable_loan = max_repayment_capacity / 1.3
        total_repayment = loan_amount * 1.3
        
        # ==========================================
        # CHECK 1: Does the loan exceed the safe limit?
        # ==========================================
        if loan_amount > max_affordable_loan:
            excess_percentage = ((loan_amount - max_affordable_loan) / max_affordable_loan) * 100
            
            # ALWAYS add a flag if loan exceeds recommendation
            if excess_percentage > 100:
                flags.append({
                    "type": "loan_exceeds_capacity_critical",
                    "severity": "critical",
                    "message": f"🔴 CRITICAL: Loan of R{loan_amount:,.2f} is {excess_percentage:.0f}% ABOVE the recommended amount of R{max_affordable_loan:,.2f}. Customer earns R{monthly_income:,.2f} per month."
                })
                risk_score += 45
            elif excess_percentage > 50:
                flags.append({
                    "type": "loan_exceeds_capacity_high",
                    "severity": "high",
                    "message": f"🔴 HIGH RISK: Loan of R{loan_amount:,.2f} is {excess_percentage:.0f}% ABOVE the recommended amount of R{max_affordable_loan:,.2f}. Customer earns R{monthly_income:,.2f} per month."
                })
                risk_score += 35
            elif excess_percentage > 20:
                flags.append({
                    "type": "loan_exceeds_capacity_medium",
                    "severity": "medium",
                    "message": f"🟡 MEDIUM RISK: Loan of R{loan_amount:,.2f} is {excess_percentage:.0f}% ABOVE the recommended amount of R{max_affordable_loan:,.2f}. Review required."
                })
                risk_score += 20
            else:
                flags.append({
                    "type": "loan_exceeds_capacity_low",
                    "severity": "low",
                    "message": f"🟢 Loan of R{loan_amount:,.2f} slightly exceeds the recommended amount of R{max_affordable_loan:,.2f} by {excess_percentage:.0f}%. Review recommended."
                })
                risk_score += 8
        else:
            flags.append({
                "type": "loan_affordable",
                "severity": "info",
                "message": f"✅ Loan of R{loan_amount:,.2f} is WITHIN the recommended amount of R{max_affordable_loan:,.2f}. Customer earns R{monthly_income:,.2f} per month."
            })
        
        # ==========================================
        # CHECK 2: Total repayment vs monthly income
        # ==========================================
        repayment_ratio = (total_repayment / monthly_income) * 100
        
        if repayment_ratio > 70:
            flags.append({
                "type": "critical_repayment_ratio",
                "severity": "critical",
                "message": f"🔴 Total repayment of R{total_repayment:,.2f} is {repayment_ratio:.1f}% of monthly income. This is EXTREMELY HIGH."
            })
            risk_score += 20
        elif repayment_ratio > 50:
            flags.append({
                "type": "high_repayment_ratio",
                "severity": "high",
                "message": f"⚠️ Total repayment of R{total_repayment:,.2f} is {repayment_ratio:.1f}% of monthly income. This is very high."
            })
            risk_score += 15
        elif repayment_ratio > 30:
            flags.append({
                "type": "medium_repayment_ratio",
                "severity": "medium",
                "message": f"⚠️ Total repayment of R{total_repayment:,.2f} is {repayment_ratio:.1f}% of monthly income. This exceeds the recommended 30%."
            })
            risk_score += 10
        
        # ==========================================
        # CHECK 3: Loan to income ratio
        # ==========================================
        loan_to_income = loan_amount / monthly_income
        
        if loan_to_income > 3:
            flags.append({
                "type": "loan_to_income_critical",
                "severity": "critical",
                "message": f"🔴 Loan is {loan_to_income:.1f}x monthly income. This is DANGEROUSLY HIGH."
            })
            risk_score += 15
        elif loan_to_income > 2:
            flags.append({
                "type": "loan_to_income_high",
                "severity": "high",
                "message": f"⚠️ Loan is {loan_to_income:.1f}x monthly income. This is very high."
            })
            risk_score += 10
        elif loan_to_income > 1:
            flags.append({
                "type": "loan_to_income_medium",
                "severity": "medium",
                "message": f"⚠️ Loan is {loan_to_income:.1f}x monthly income. Review recommended."
            })
            risk_score += 5
        
        # ==========================================
        # CHECK 4: Affordability Summary (Always included)
        # ==========================================
        flags.append({
            "type": "affordability_summary",
            "severity": "info",
            "message": f"📊 SUMMARY: Income R{monthly_income:,.2f} | Safe repayment (30%) = R{max_repayment_capacity:,.2f} | Max recommended loan = R{max_affordable_loan:,.2f} | Requested = R{loan_amount:,.2f}"
        })
        
        return {
            "flags": flags,
            "risk_score": min(risk_score, 100)
        }
    
    def detect_fraud(self, customer: Customer, loan_amount: float = 0, term_months: int = 1) -> dict:
        """
        Run all fraud detection checks and return comprehensive risk assessment
        """
        all_flags = []
        total_score = 0
        risk_level = "LOW"
        
        # Run all checks
        identity_check = self.check_identity_fraud(customer)
        pattern_check = self.check_loan_application_pattern(customer.id)
        
        # Pass loan_amount explicitly
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
        return True
    elif user_role == "manager":
        if risk_level in ["LOW", "MEDIUM"]:
            return True
        return False
    else:
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