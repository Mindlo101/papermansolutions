from app.utils.pdf_generator import generate_loan_agreement
from app.models.customer import Customer
from app.models.loan import Loan
from datetime import date
import os

# Create mock objects
class MockCustomer:
    first_name = "John"
    last_name = "Doe"
    id_number = "123456789"
    phone = "0712345678"

class MockLoan:
    id = 1
    customer_id = 1
    amount = 1000
    term_months = 3
    interest_rate = 30.0
    interest_amount = 300
    total_repayment = 1300
    monthly_installment = 433.33

# Test PDF generation
if __name__ == "__main__":
    print("Testing PDF generation...")
    customer = MockCustomer()
    loan = MockLoan()
    
    try:
        # Create uploads directory
        os.makedirs("app/static/uploads", exist_ok=True)
        
        # Generate PDF
        output_path = "app/static/uploads/test_agreement.pdf"
        generate_loan_agreement(loan, customer, output_path)
        
        # Check if file exists
        if os.path.exists(output_path):
            print(f"✅ PDF generated successfully at: {output_path}")
            print(f"File size: {os.path.getsize(output_path)} bytes")
        else:
            print("❌ PDF file was not created")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()