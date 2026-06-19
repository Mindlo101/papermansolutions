from datetime import date, timedelta

def calculate_loan(amount: float, term_months: int = 1, annual_interest_rate: float = 30.0):
    """
    Flat rate interest calculation.
    Default term is 1 month.
    Returns dict with interest_amount, total_repayment, monthly_installment, schedule.
    """
    interest = amount * (annual_interest_rate / 100)
    total = amount + interest
    monthly = total / term_months

    schedule = []
    start_date = date.today()
    for i in range(term_months):
        due_date = start_date + timedelta(days=30 * (i + 1))
        schedule.append({
            "installment_number": i + 1,
            "due_date": due_date,
            "amount_due": round(monthly, 2)
        })

    return {
        "interest_amount": round(interest, 2),
        "total_repayment": round(total, 2),
        "monthly_installment": round(monthly, 2),
        "schedule": schedule
    }