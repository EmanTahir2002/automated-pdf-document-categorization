"""
metadata_extractor.py
---------------------
Extract category-specific structured fields from PDF text using regex.

Each category has its own extractor function. Common fields (emails, dates,
currency amounts) are pulled by a shared helper. Unknown fields gracefully
return None rather than raising.

In a production AWS pipeline, this module would be the second Lambda
function in the chain (or a step inside a single Lambda after classification).
For more complex / variable layouts, this is the layer you would later
swap out for an LLM call (Bedrock) or Amazon Textract Queries.
"""

import re
from typing import Optional


# ---------------------------------------------------------------------
# Generic patterns (compiled once)
# ---------------------------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s\(\)]{7,}\d")
DATE_RE = re.compile(
    r"\b(20\d{2}-\d{2}-\d{2}|\d{2}/\d{2}/20\d{2}|\d{1,2}\s+"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+20\d{2})\b",
    re.IGNORECASE,
)
CURRENCY_RE = re.compile(r"\$\s?[\d,]+(?:\.\d{2})?")


def _first(pattern, text, group=0, flags=0) -> Optional[str]:
    """Return the first regex match or None."""
    m = re.search(pattern, text, flags=flags)
    if not m:
        return None
    try:
        return m.group(group).strip()
    except IndexError:
        return m.group(0).strip()


def _money_to_float(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    cleaned = s.replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------
# Per-category extractors
# ---------------------------------------------------------------------
def extract_invoice_fields(text: str) -> dict:
    invoice_no = _first(
        r"Invoice\s*(?:Number|No\.?|#)\s*[:\-]?\s*([A-Z0-9\-]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    invoice_date = _first(
        r"Invoice\s*Date\s*[:\-]?\s*([0-9A-Za-z\-/\s]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    due_date = _first(
        r"Due\s*Date\s*[:\-]?\s*([0-9A-Za-z\-/\s]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    total_due = _first(
        r"Total\s+Amount\s+Due[:\s]*\$?\s*([\d,]+\.\d{2})",
        text, group=1, flags=re.IGNORECASE,
    )
    subtotal = _first(
        r"Subtotal[:\s]*\$?\s*([\d,]+\.\d{2})",
        text, group=1, flags=re.IGNORECASE,
    )
    tax = _first(
        r"Tax\s*\([^)]*\)[:\s]*\$?\s*([\d,]+\.\d{2})",
        text, group=1, flags=re.IGNORECASE,
    )
    # Bill-to: the line after "Bill To:" is typically the customer name
    bill_to = _first(
        r"Bill\s*To:\s*\n?\s*([A-Za-z0-9&\.,\- ]+?)\s*\n",
        text, group=1, flags=re.IGNORECASE,
    )
    email = _first(EMAIL_RE, text)

    return {
        "invoice_number": invoice_no,
        "invoice_date": (invoice_date or "").split("\n")[0].strip() or None,
        "due_date": (due_date or "").split("\n")[0].strip() or None,
        "bill_to": bill_to,
        "customer_email": email,
        "subtotal": _money_to_float(subtotal),
        "tax": _money_to_float(tax),
        "total_amount_due": _money_to_float(total_due),
        "currency": "USD" if "$" in text else None,
    }


def extract_sales_report_fields(text: str) -> dict:
    period = _first(
        r"Reporting\s*Period\s*[:\-]?\s*([^\n]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    region = _first(
        r"Region\s*[:\-]?\s*([^\n]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    report_date = _first(
        r"Report\s*Generated\s*[:\-]?\s*([0-9\-/]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    # Total revenue line at bottom of breakdown table
    total_revenue = _first(
        r"TOTAL\s+\$?\s*([\d,]+\.\d{2})\s*100",
        text, group=1, flags=re.IGNORECASE,
    )
    if not total_revenue:
        # Fallback: largest dollar amount in the doc
        amounts = CURRENCY_RE.findall(text)
        nums = [_money_to_float(a) for a in amounts]
        nums = [n for n in nums if n is not None]
        total_revenue = max(nums) if nums else None
    else:
        total_revenue = _money_to_float(total_revenue)

    quarter = _first(r"\b(Q[1-4]\s*20\d{2})\b", text, group=1, flags=re.IGNORECASE)

    return {
        "reporting_period": period,
        "quarter": quarter,
        "region": region,
        "report_generated": report_date,
        "total_revenue": total_revenue,
        "currency": "USD" if "$" in text else None,
    }


def extract_customer_application_fields(text: str) -> dict:
    app_id = _first(
        r"Application\s*ID\s*[:\-]?\s*([A-Z0-9\-]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    app_date = _first(
        r"Date\s*of\s*Application\s*[:\-]?\s*([0-9\-/]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    account_type = _first(
        r"Account\s*Type(?:\s*Requested)?\s*[:\-]?\s*([^\n]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    full_name = _first(
        r"Full\s*Name:\s*([A-Za-z][A-Za-z\.\-' ]+?)\s*\n",
        text, group=1, flags=re.IGNORECASE,
    )
    dob = _first(
        r"Date\s*of\s*Birth:\s*([0-9\-/]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    ssn = _first(
        r"(?:National\s*ID|SSN|Social\s*Security)[^:]*:\s*([A-Z0-9\-]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    email = _first(EMAIL_RE, text)
    phone = _first(
        r"Phone\s*Number:\s*(\+?[\d\-\s\(\)]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    employer = _first(
        r"Employer:\s*([^\n]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    job_title = _first(
        r"Job\s*Title:\s*([^\n]+)",
        text, group=1, flags=re.IGNORECASE,
    )
    income = _first(
        r"Annual\s*Income:\s*([^\n]+)",
        text, group=1, flags=re.IGNORECASE,
    )

    return {
        "application_id": app_id,
        "application_date": app_date,
        "account_type": (account_type or "").strip() or None,
        "applicant_name": full_name,
        "date_of_birth": dob,
        "national_id": ssn,
        "email": email,
        "phone": (phone or "").strip() or None,
        "employer": (employer or "").strip() or None,
        "job_title": (job_title or "").strip() or None,
        "annual_income": (income or "").strip() or None,
    }


# ---------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------
EXTRACTORS = {
    "Invoice": extract_invoice_fields,
    "Sales Report": extract_sales_report_fields,
    "Customer Application": extract_customer_application_fields,
}


def extract_metadata(category: str, text: str) -> dict:
    """Route to the correct extractor based on classifier output."""
    extractor = EXTRACTORS.get(category)
    if extractor is None:
        return {"warning": f"No extractor registered for category '{category}'."}
    return extractor(text)


if __name__ == "__main__":
    import sys, json
    from text_extractor import extract_text_from_pdf
    from classifier import DocumentClassifier
    from generic_field_extractor import extract_generic_fields

    if len(sys.argv) < 2:
        print("Usage: python metadata_extractor.py <pdf_path>")
        sys.exit(1)

    doc = extract_text_from_pdf(sys.argv[1])
    clf = DocumentClassifier()
    cat = clf.classify(doc["text"])["category"]
    meta = extract_metadata(cat, doc["text"])
    generic = extract_generic_fields(doc["text"])
    print(f"Category: {cat}")
    print("\nCategory-specific metadata:")
    print(json.dumps(meta, indent=2))
    print("\nGeneric keyword fields:")
    print(json.dumps(generic["fields"], indent=2))
    print("\nMatched keyword evidence:")
    print(json.dumps(generic["matches"], indent=2))
