import os
from datetime import datetime, timedelta
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from ..config import settings

# Try to register a font for better appearance
try:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    FONT_NAME = 'Helvetica'
    FONT_BOLD = 'Helvetica-Bold'
except:
    FONT_NAME = 'Helvetica'
    FONT_BOLD = 'Helvetica-Bold'


def generate_loan_agreement(loan, customer, output_path: str):
    """
    Generate a professional bank/fintech style loan agreement PDF.
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=18*mm,
        leftMargin=18*mm,
        topMargin=18*mm,
        bottomMargin=18*mm
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles with unique names to avoid conflicts
    styles.add(ParagraphStyle(
        name='CustomHeaderTitle',
        fontName=FONT_BOLD,
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=4,
        textColor=colors.HexColor('#1a365d')
    ))
    
    styles.add(ParagraphStyle(
        name='CustomHeaderSubtitle',
        fontName=FONT_NAME,
        fontSize=10,
        alignment=TA_CENTER,
        spaceAfter=16,
        textColor=colors.HexColor('#4a5568')
    ))
    
    styles.add(ParagraphStyle(
        name='CustomSectionTitle',
        fontName=FONT_BOLD,
        fontSize=13,
        spaceAfter=8,
        spaceBefore=12,
        textColor=colors.HexColor('#1a365d')
    ))
    
    styles.add(ParagraphStyle(
        name='CustomBodyText',
        fontName=FONT_NAME,
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=4,
        leading=14
    ))
    
    styles.add(ParagraphStyle(
        name='CustomBodyTextSmall',
        fontName=FONT_NAME,
        fontSize=9,
        alignment=TA_LEFT,
        spaceAfter=3,
        leading=12,
        textColor=colors.HexColor('#4a5568')
    ))
    
    styles.add(ParagraphStyle(
        name='CustomSignatureText',
        fontName=FONT_NAME,
        fontSize=10,
        alignment=TA_LEFT,
        spaceAfter=2
    ))
    
    styles.add(ParagraphStyle(
        name='CustomDisclaimer',
        fontName=FONT_NAME,
        fontSize=8,
        alignment=TA_CENTER,
        spaceAfter=2,
        textColor=colors.HexColor('#718096')
    ))

    story = []

    # ==========================================
    # HEADER SECTION
    # ==========================================
    
    # Company Name
    story.append(Paragraph(settings.COMPANY_NAME, styles['CustomHeaderTitle']))
    story.append(Paragraph("Financial Services", styles['CustomHeaderSubtitle']))
    
    # Company Contact Details
    contact_info = f"{settings.COMPANY_ADDRESS} | Tel: {settings.COMPANY_PHONE} | Email: {settings.COMPANY_EMAIL}"
    story.append(Paragraph(contact_info, styles['CustomBodyTextSmall']))
    
    # Divider line
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph("_" * 80, styles['CustomBodyText']))
    story.append(Spacer(1, 4*mm))
    
    # Document Title
    story.append(Paragraph("LOAN AGREEMENT", styles['CustomSectionTitle']))
    story.append(Spacer(1, 2*mm))
    
    # Agreement Number and Date
    agreement_date = datetime.now().strftime("%d %B %Y")
    story.append(Paragraph("Agreement Number: PS-LOAN-" + str(loan.id).zfill(6), styles['CustomBodyText']))
    story.append(Paragraph("Date: " + agreement_date, styles['CustomBodyText']))
    story.append(Spacer(1, 6*mm))

    # ==========================================
    # PARTIES SECTION
    # ==========================================
    
    story.append(Paragraph("1. PARTIES TO THE AGREEMENT", styles['CustomSectionTitle']))
    story.append(Spacer(1, 1*mm))
    
    parties_data = [
        ["Lender:", settings.COMPANY_NAME],
        ["Address:", settings.COMPANY_ADDRESS],
        ["Phone:", settings.COMPANY_PHONE],
        ["Email:", settings.COMPANY_EMAIL],
        ["", ""],
        ["Borrower:", customer.first_name + " " + customer.last_name],
        ["ID Number:", customer.id_number],
        ["Residential Address:", customer.address or "Not Provided"],
        ["Contact:", "Phone: " + customer.phone + " | Email: " + (customer.email or "Not Provided")],
    ]
    
    parties_table = Table(parties_data, colWidths=[40*mm, 100*mm])
    parties_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#1a365d')),
        ('FONTNAME', (0,0), (0,-1), FONT_BOLD),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 4*mm))

    # ==========================================
    # LOAN TERMS SECTION
    # ==========================================
    
    story.append(Paragraph("2. LOAN TERMS AND CONDITIONS", styles['CustomSectionTitle']))
    story.append(Spacer(1, 1*mm))
    
    # Loan Summary Table
    loan_data = [
        ["Principal Amount:", "R " + format(loan.amount, ",.2f")],
        ["Interest Rate:", str(loan.interest_rate) + "% Flat"],
        ["Interest Amount:", "R " + format(loan.interest_amount, ",.2f")],
        ["Total Repayment:", "R " + format(loan.total_repayment, ",.2f")],
        ["Term:", str(loan.term_months) + " Months"],
        ["Monthly Installment:", "R " + format(loan.monthly_installment, ",.2f")],
    ]
    
    loan_table = Table(loan_data, colWidths=[50*mm, 90*mm])
    loan_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#f7fafc')),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('FONTNAME', (0,0), (0,-1), FONT_BOLD),
    ]))
    story.append(loan_table)
    story.append(Spacer(1, 4*mm))

    # ==========================================
    # REPAYMENT SCHEDULE
    # ==========================================
    
    story.append(Paragraph("3. REPAYMENT SCHEDULE", styles['CustomSectionTitle']))
    story.append(Paragraph(
        "The Borrower agrees to repay the loan in equal monthly installments as per the schedule below:",
        styles['CustomBodyText']
    ))
    story.append(Spacer(1, 2*mm))
    
    # Build schedule
    schedule_data = [["#", "Due Date", "Amount Due"]]
    first_due = datetime.now().date() + timedelta(days=30)
    
    # Show all installments
    for i in range(loan.term_months):
        due_date = first_due + timedelta(days=30*i)
        schedule_data.append([
            str(i+1),
            due_date.strftime("%d %B %Y"),
            "R " + format(loan.monthly_installment, ",.2f")
        ])
    
    schedule_table = Table(schedule_data, colWidths=[20*mm, 60*mm, 60*mm])
    schedule_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a365d')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(schedule_table)
    story.append(Spacer(1, 4*mm))

    # ==========================================
    # TERMS AND CONDITIONS
    # ==========================================
    
    story.append(Paragraph("4. TERMS AND CONDITIONS", styles['CustomSectionTitle']))
    story.append(Spacer(1, 1*mm))
    
    terms = [
        "4.1 The Borrower agrees to repay the total loan amount in monthly installments as per the schedule above.",
        "4.2 All payments must be made by the due date to avoid penalties and interest charges.",
        "4.3 Late payments will incur a penalty of " + str(settings.LATE_FEE_PERCENT) + "% of the outstanding amount per week after a " + str(settings.GRACE_PERIOD_DAYS) + "-day grace period.",
        "4.4 The Borrower has the right to settle the loan early without penalty.",
        "4.5 The Lender reserves the right to take legal action in the event of default.",
        "4.6 This agreement is governed by the laws of the Republic of South Africa.",
        "4.7 For any queries regarding this agreement, please contact: " + settings.COMPANY_PHONE + " or " + settings.COMPANY_EMAIL,
    ]
    
    for term in terms:
        story.append(Paragraph(term, styles['CustomBodyText']))
    story.append(Spacer(1, 4*mm))

    # ==========================================
    # DECLARATION
    # ==========================================
    
    story.append(Paragraph("5. DECLARATION", styles['CustomSectionTitle']))
    story.append(Spacer(1, 1*mm))
    
    declaration = (
        "I, the undersigned, acknowledge that I have read, understood, and agree to all the terms and "
        "conditions of this loan agreement. I confirm that all information provided is true and correct, "
        "and I understand that failure to repay this loan may result in legal action being taken against me."
    )
    story.append(Paragraph(declaration, styles['CustomBodyText']))
    story.append(Spacer(1, 6*mm))

    # ==========================================
    # SIGNATURES
    # ==========================================
    
    # Create signature table
    sig_data = [
        ["", ""],
        ["BORROWER", "LENDER REPRESENTATIVE"],
        ["", ""],
        ["", ""],
        ["_________________________", "_________________________"],
        ["Signature", "Signature"],
        ["", ""],
        ["_________________________", "_________________________"],
        ["Date", "Date"],
    ]
    
    sig_table = Table(sig_data, colWidths=[70*mm, 70*mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('FONTNAME', (0,0), (-1,-1), FONT_NAME),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (1,0), (1,-1), 'CENTER'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('FONTNAME', (1,0), (1,-1), FONT_BOLD),
        ('FONTNAME', (0,0), (0,-1), FONT_BOLD),
    ]))
    story.append(sig_table)
    story.append(Spacer(1, 4*mm))

    # ==========================================
    # FOOTER / DISCLAIMER
    # ==========================================
    
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph("_" * 80, styles['CustomBodyText']))
    story.append(Spacer(1, 2*mm))
    
    disclaimer = (
        "This is a legally binding document. Please ensure you fully understand all terms and conditions. "
        + settings.COMPANY_NAME + " is a registered credit provider under the National Credit Act (NCA)."
    )
    story.append(Paragraph(disclaimer, styles['CustomDisclaimer']))
    
    story.append(Paragraph(
        "Document ID: PS-LOAN-" + str(loan.id).zfill(6) + " | Generated: " + datetime.now().strftime('%Y-%m-%d %H:%M') + " | Page 1 of 1",
        styles['CustomDisclaimer']
    ))

    # ==========================================
    # BUILD PDF
    # ==========================================
    
    try:
        doc.build(story)
        print("✅ Professional PDF generated at: " + output_path)
        return output_path
    except Exception as e:
        print("❌ PDF build error: " + str(e))
        raise