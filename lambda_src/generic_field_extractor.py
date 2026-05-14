"""
generic_field_extractor.py
--------------------------
Extract label/value fields from PDF text using alias groups.

This layer is category-agnostic: it does not decide whether a document is an
Invoice, Sales Report, or Customer Application. Instead, it looks for common
business labels and normalizes different headings into one canonical key.

Example:
    "Sales Tax: $25.00" -> {"tax": 25.0}
    "Tarif: $25.00"     -> {"tax": 25.0}
    "VAT: $25.00"       -> {"tax": 25.0}

If a document contains multiple labels for the same normalized field, the
field value becomes a list:
    "Tax: $10.00" + "GST: $5.00" -> {"tax": [10.0, 5.0]}
"""

import re
from typing import Optional


MONEY_RE = re.compile(r"\$?\s*[\d,]+(?:\.\d{2})?")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?\d[\d\-\s\(\)]{7,}\d")


FIELD_ALIASES = {
    "invoice_number": [
        "invoice number",
        "invoice no",
        "invoice #",
        "invoice id",
        "inv no",
        "inv #",
    ],
    "invoice_date": ["invoice date", "bill date", "date issued"],
    "due_date": ["due date", "payment due date", "pay by"],
    "subtotal": ["subtotal", "sub total", "net amount"],
    "tax": ["tax", "sales tax", "vat", "gst", "tariff", "tarif", "levy", "duty"],
    "total_amount_due": [
        "total amount due",
        "amount due",
        "balance due",
        "amount payable",
        "total payable",
        "grand total",
        "total due",
    ],
    "customer_name": ["customer name", "client name", "bill to", "billed to"],
    "company_name": ["company name", "organization", "business name", "vendor"],
    "cashier_name": ["cashier", "cashier name", "served by", "prepared by"],
    "email": ["email", "email address", "contact email"],
    "phone": ["phone", "phone number", "contact number", "mobile"],
    "address": ["address", "billing address", "residential address"],
    "application_id": ["application id", "app id", "application number"],
    "applicant_name": ["applicant name", "full name", "name"],
    "date_of_birth": ["date of birth", "dob"],
    "account_type": ["account type", "account type requested"],
    "employer": ["employer", "company employer"],
    "annual_income": ["annual income", "income", "yearly income"],
    "reporting_period": ["reporting period", "period"],
    "quarter": ["quarter", "reporting quarter"],
    "region": ["region", "sales region"],
    "total_revenue": ["total revenue", "revenue total", "gross revenue"],
}

MONEY_FIELDS = {
    "subtotal",
    "tax",
    "total_amount_due",
    "annual_income",
    "total_revenue",
}


def _label_pattern(label: str) -> str:
    """Convert a readable label into a flexible whitespace regex."""
    escaped = re.escape(label)
    return escaped.replace(r"\ ", r"\s+")


def _money_to_float(value: str) -> Optional[float]:
    match = MONEY_RE.search(value or "")
    if not match:
        return None
    cleaned = match.group(0).replace("$", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clean_value(value: str) -> Optional[str]:
    value = re.sub(r"\s+", " ", value or "").strip(" :-\t")
    return value or None


def _normalize_value(field_name: str, raw_value: str):
    if field_name in MONEY_FIELDS:
        return _money_to_float(raw_value)
    if field_name == "email":
        match = EMAIL_RE.search(raw_value or "")
        return match.group(0) if match else _clean_value(raw_value)
    if field_name == "phone":
        match = PHONE_RE.search(raw_value or "")
        return match.group(0).strip() if match else _clean_value(raw_value)
    return _clean_value(raw_value)


def _extract_label_values(text: str, alias: str) -> list[str]:
    """
    Find values written as either:
        Label: value
        Label - value
        Label
        value-on-next-line
    """
    label = _label_pattern(alias)
    inline_pattern = re.compile(
        rf"(?im)^\s*({label})(?![A-Za-z0-9])(?:\s*\([^)]*\))?\s*[:\-]\s*(.+)$"
    )
    next_line_pattern = re.compile(
        rf"(?im)^\s*({label})(?![A-Za-z0-9])(?:\s*\([^)]*\))?\s*[:\-]?\s*$"
    )

    values = []
    lines = text.splitlines()
    for index, line in enumerate(lines):
        inline_match = inline_pattern.search(line)
        if inline_match:
            value = _clean_value(inline_match.group(2) or "")
            if value:
                values.append(value)
            continue

        if next_line_pattern.search(line):
            if index + 1 < len(lines):
                value = _clean_value(lines[index + 1])
                if value:
                    values.append(value)

    return values


def extract_generic_fields(text: str) -> dict:
    """
    Extract normalized fields and evidence.

    Returns:
        {
          "fields": {"tax": 148.75, "total_amount_due": 1023.75},
          "matches": {
            "tax": [
              {
                "matched_label": "Tax",
                "raw_value": "$148.75",
                "normalized_value": 148.75
              }
            ]
          }
        }
    """
    fields = {}
    matches = {}

    for field_name, aliases in FIELD_ALIASES.items():
        field_values = []
        field_matches = []

        for alias in sorted(aliases, key=len, reverse=True):
            raw_values = _extract_label_values(text, alias)
            for raw_value in raw_values:
                normalized = _normalize_value(field_name, raw_value)
                if normalized is None:
                    continue

                evidence = {
                    "matched_label": alias,
                    "raw_value": raw_value,
                    "normalized_value": normalized,
                }
                if evidence in field_matches:
                    continue

                field_values.append(normalized)
                field_matches.append(evidence)

        if not field_values:
            continue

        fields[field_name] = field_values[0] if len(field_values) == 1 else field_values
        matches[field_name] = field_matches

    return {"fields": fields, "matches": matches}
