"""
Generate realistic, digitally-native sample PDFs for testing the pipeline.
Creates 3 categories: Invoice, Sales Report, Customer Application.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_pdfs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

styles = getSampleStyleSheet()
h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=20, alignment=TA_CENTER)
h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=14)
body = styles["BodyText"]


# ----------------- INVOICE -----------------
def make_invoice(filename, invoice_no, customer, date, items, tax_rate=0.17):
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=A4, title=f"Invoice {invoice_no}")
    story = []

    story.append(Paragraph("<b>INVOICE</b>", h1))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph(f"<b>Invoice Number:</b> {invoice_no}", body))
    story.append(Paragraph(f"<b>Invoice Date:</b> {date}", body))
    story.append(Paragraph(f"<b>Due Date:</b> {date}", body))
    story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph("<b>Bill To:</b>", body))
    story.append(Paragraph(customer["name"], body))
    story.append(Paragraph(customer["address"], body))
    story.append(Paragraph(f"Email: {customer['email']}", body))
    story.append(Spacer(1, 0.25 * inch))

    # Items table
    data = [["Description", "Qty", "Unit Price", "Total"]]
    subtotal = 0.0
    for it in items:
        line_total = it["qty"] * it["price"]
        subtotal += line_total
        data.append([it["desc"], str(it["qty"]),
                     f"${it['price']:.2f}", f"${line_total:.2f}"])

    tax = subtotal * tax_rate
    grand_total = subtotal + tax
    data.append(["", "", "Subtotal:", f"${subtotal:.2f}"])
    data.append(["", "", f"Tax ({tax_rate*100:.0f}%):", f"${tax:.2f}"])
    data.append(["", "", "Total Amount Due:", f"${grand_total:.2f}"])

    t = Table(data, colWidths=[3 * inch, 0.8 * inch, 1.2 * inch, 1.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E4053")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -4), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (-2, -3), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph(
        "Payment Terms: Net 30 days. Please remit payment by the due date "
        "to avoid late fees. Thank you for your business.", body))

    doc.build(story)
    print(f"  Created: {filename}")


# ----------------- SALES REPORT -----------------
def make_sales_report(filename, period, region, total_revenue, breakdown):
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=A4, title=f"Sales Report {period}")
    story = []

    story.append(Paragraph("<b>QUARTERLY SALES REPORT</b>", h1))
    story.append(Spacer(1, 0.15 * inch))

    story.append(Paragraph(f"<b>Reporting Period:</b> {period}", body))
    story.append(Paragraph(f"<b>Region:</b> {region}", body))
    story.append(Paragraph(f"<b>Report Generated:</b> {datetime.now().strftime('%Y-%m-%d')}", body))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("<b>Executive Summary</b>", h2))
    story.append(Paragraph(
        f"This report summarizes the sales performance for {region} during {period}. "
        f"Total revenue reached ${total_revenue:,.2f}, representing strong year-over-year growth. "
        "Performance is broken down by product line below. Key drivers include increased "
        "enterprise contract sizes and improved retention rates. Overall, the quarter exceeded "
        "internal targets and provides a strong foundation for the next reporting period.", body))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("<b>Revenue Breakdown by Product Line</b>", h2))
    data = [["Product Line", "Units Sold", "Revenue", "% of Total"]]
    for line, vals in breakdown.items():
        pct = (vals["revenue"] / total_revenue) * 100
        data.append([line, str(vals["units"]),
                     f"${vals['revenue']:,.2f}", f"{pct:.1f}%"])
    data.append(["TOTAL", "", f"${total_revenue:,.2f}", "100.0%"])

    t = Table(data, colWidths=[2.2 * inch, 1.2 * inch, 1.5 * inch, 1.2 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1A5276")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#D5DBDB")),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph("<b>Key Observations</b>", h2))
    story.append(Paragraph(
        "The sales team achieved record performance this quarter. Customer acquisition "
        "increased by 22 percent compared to the prior period. Recommendations for next "
        "quarter include expanding the enterprise account team and increasing marketing "
        "spend on digital channels. Forecast for the next quarter projects continued growth "
        "with revenue targets set at 15 percent above this period.", body))

    doc.build(story)
    print(f"  Created: {filename}")


# ----------------- CUSTOMER APPLICATION -----------------
def make_customer_application(filename, app_id, applicant, account_type):
    path = os.path.join(OUTPUT_DIR, filename)
    doc = SimpleDocTemplate(path, pagesize=A4, title=f"Application {app_id}")
    story = []

    story.append(Paragraph("<b>CUSTOMER APPLICATION FORM</b>", h1))
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph(f"<b>Application ID:</b> {app_id}", body))
    story.append(Paragraph(f"<b>Date of Application:</b> {applicant['date']}", body))
    story.append(Paragraph(f"<b>Account Type Requested:</b> {account_type}", body))
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph("<b>Personal Information</b>", h2))
    info = [
        ["Full Name:", applicant["name"]],
        ["Date of Birth:", applicant["dob"]],
        ["National ID / SSN:", applicant["ssn"]],
        ["Email Address:", applicant["email"]],
        ["Phone Number:", applicant["phone"]],
        ["Residential Address:", applicant["address"]],
    ]
    t = Table(info, colWidths=[2.0 * inch, 4.0 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * inch))

    story.append(Paragraph("<b>Employment Information</b>", h2))
    emp = [
        ["Employer:", applicant["employer"]],
        ["Job Title:", applicant["job_title"]],
        ["Annual Income:", applicant["income"]],
        ["Years Employed:", applicant["years_employed"]],
    ]
    t2 = Table(emp, colWidths=[2.0 * inch, 4.0 * inch])
    t2.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t2)
    story.append(Spacer(1, 0.25 * inch))

    story.append(Paragraph(
        "I hereby certify that the information provided in this application is "
        "true and complete to the best of my knowledge. I authorize the verification "
        "of the information provided and consent to a credit check if applicable. "
        "I understand that providing false information may result in the rejection "
        "of this application and potential legal consequences.", body))
    story.append(Spacer(1, 0.3 * inch))

    story.append(Paragraph(f"<b>Signature:</b> {applicant['name']}", body))
    story.append(Paragraph(f"<b>Date:</b> {applicant['date']}", body))

    doc.build(story)
    print(f"  Created: {filename}")


if __name__ == "__main__":
    print("Generating sample PDFs...\n")
    print("Invoices:")
    make_invoice(
        "invoice_001.pdf",
        invoice_no="INV-2025-0042",
        customer={"name": "Acme Corporation",
                  "address": "123 Business Park, Karachi, Pakistan",
                  "email": "billing@acme-corp.com"},
        date="2025-09-15",
        items=[
            {"desc": "Cloud Hosting (Monthly)", "qty": 1, "price": 450.00},
            {"desc": "Premium Support Plan", "qty": 1, "price": 200.00},
            {"desc": "Data Backup Storage (TB)", "qty": 3, "price": 75.00},
        ],
    )
    make_invoice(
        "invoice_002.pdf",
        invoice_no="INV-2025-0089",
        customer={"name": "Globex Industries",
                  "address": "456 Industrial Road, Lahore, Pakistan",
                  "email": "accounts@globex.io"},
        date="2025-10-02",
        items=[
            {"desc": "Software License Annual", "qty": 5, "price": 1200.00},
            {"desc": "Onboarding Services", "qty": 1, "price": 800.00},
        ],
    )

    print("\nSales Reports:")
    make_sales_report(
        "sales_report_q3_2025.pdf",
        period="Q3 2025 (July - September)",
        region="South Asia",
        total_revenue=482350.00,
        breakdown={
            "Enterprise Software":  {"units": 45,  "revenue": 215000.00},
            "Cloud Services":       {"units": 320, "revenue": 156800.00},
            "Professional Services":{"units": 22,  "revenue": 88000.00},
            "Hardware Accessories": {"units": 410, "revenue": 22550.00},
        },
    )
    make_sales_report(
        "sales_report_q2_2025.pdf",
        period="Q2 2025 (April - June)",
        region="Middle East",
        total_revenue=298100.00,
        breakdown={
            "Enterprise Software":  {"units": 28, "revenue": 142000.00},
            "Cloud Services":       {"units": 215,"revenue": 98900.00},
            "Professional Services":{"units": 18, "revenue": 57200.00},
        },
    )

    print("\nCustomer Applications:")
    make_customer_application(
        "customer_application_001.pdf",
        app_id="APP-2025-77321",
        applicant={
            "name": "Maaz Ahmed",
            "dob": "1998-05-12",
            "ssn": "35202-1234567-8",
            "email": "maaz.ahmed@example.com",
            "phone": "+92-300-1234567",
            "address": "House 12, Street 4, Defence Phase II, Karachi",
            "employer": "R2V Private Limited",
            "job_title": "Data Scientist",
            "income": "$45,000",
            "years_employed": "2",
            "date": "2025-10-10",
        },
        account_type="Premium Savings Account",
    )
    make_customer_application(
        "customer_application_002.pdf",
        app_id="APP-2025-77498",
        applicant={
            "name": "Sara Khan",
            "dob": "1995-11-23",
            "ssn": "42101-9876543-2",
            "email": "sara.khan@example.org",
            "phone": "+92-321-7654321",
            "address": "Apartment 8B, Gulberg III, Lahore",
            "employer": "Tech Innovate Ltd",
            "job_title": "Software Engineer",
            "income": "$52,000",
            "years_employed": "3",
            "date": "2025-10-11",
        },
        account_type="Business Checking Account",
    )
    print("\nAll sample PDFs generated successfully.")
