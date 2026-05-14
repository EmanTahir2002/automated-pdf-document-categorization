"""
classifier.py
-------------
Classify extracted PDF text into predefined business categories:
    - Invoice
    - Sales Report
    - Customer Application

Strategy: a hybrid scoring approach that combines:
    1. category aliases / keyword phrase scoring
    2. TF-IDF cosine similarity against category prototype text
    3. structural hints that look for document layout/content patterns
    4. a confidence threshold so weak matches become "Unknown"

This keeps the classifier local, explainable, free-tier friendly, and easy to
extend without using OCR, LLM APIs, or paid document AI services.
"""

import logging
import math
import re
from collections import Counter

logger = logging.getLogger(__name__)


CATEGORY_PROTOTYPES = {
    "Invoice": (
        "invoice number invoice id bill to billed to customer client invoice date "
        "due date payment terms subtotal sub total net amount tax sales tax vat gst "
        "tariff tarif levy duty total amount due balance due amount payable grand "
        "total unit price quantity line item remit payment billing"
    ),
    "Sales Report": (
        "sales report quarterly monthly annual revenue reporting period region "
        "territory market executive summary product line units sold revenue "
        "breakdown year over year growth performance forecast observations "
        "recommendations total revenue gross revenue"
    ),
    "Customer Application": (
        "customer application form account application applicant full name personal "
        "information date of birth dob national id social security email phone "
        "residential address employer job title annual income account type "
        "signature certify true complete authorize credit check"
    ),
}


CATEGORY_ALIASES = {
    "Invoice": [
        (r"\binvoice\s*(number|no\.?|#|id)?\b", 3.0),
        (r"\bINV[-\s]?\d{2,}\b", 3.0),
        (r"\btotal\s+amount\s+due\b", 2.5),
        (r"\b(amount|balance|total)\s+(due|payable)\b", 2.5),
        (r"\b(grand\s+total|total\s+payable)\b", 2.0),
        (r"\b(bill|billed)\s+to\b", 2.0),
        (r"\bpayment\s+terms\b", 1.5),
        (r"\b(subtotal|sub\s+total|net\s+amount)\b", 1.5),
        (r"\b(tax|sales\s+tax|vat|gst|tariff|tarif|levy|duty)\b", 1.0),
        (r"\bdue\s+date\b", 1.5),
    ],
    "Sales Report": [
        (r"\bsales\s+report\b", 3.0),
        (r"\b(quarterly|monthly|annual)\b", 2.0),
        (r"\bQ[1-4]\s*20\d{2}\b", 2.5),
        (r"\bexecutive\s+summary\b", 2.0),
        (r"\b(revenue|sales)\s+breakdown\b", 2.5),
        (r"\b(total\s+revenue|gross\s+revenue|units\s+sold)\b", 2.0),
        (r"\b(region|territory|market)\b", 1.2),
        (r"\byear[-\s]over[-\s]year\b", 1.5),
        (r"\b(forecast|recommendations|growth|performance)\b", 1.0),
    ],
    "Customer Application": [
        (r"\b(customer|client|account)\s+application\b", 3.0),
        (r"\bapplication\s+(form|id)\b", 2.5),
        (r"\bAPP[-\s]?\d{2,}\b", 2.5),
        (r"\bdate\s+of\s+birth\b", 2.0),
        (r"\bDOB\b", 2.0),
        (r"\b(full\s+name|applicant\s+name)\b", 1.8),
        (r"\bnational\s+id\b|\bssn\b|\bsocial\s+security\b", 2.0),
        (r"\bemployer\b", 1.5),
        (r"\bannual\s+income\b", 1.5),
        (r"\baccount\s+type\b", 1.5),
        (r"\bsignature\b|\bcertify\b|\bauthorize\b", 1.0),
    ],
}


STRUCTURAL_HINTS = {
    "Invoice": [
        (r"(?is)\bdescription\b.+\bqty\b.+\bunit\s+price\b.+\btotal\b", 3.0),
        (r"(?is)\bsubtotal\b.+\b(total\s+amount\s+due|amount\s+due|grand\s+total)\b", 2.5),
        (r"(?im)^\s*(tax|sales\s+tax|vat|gst|tariff|tarif|levy|duty)(?:\s*\([^)]*\))?\s*[:\-]", 1.8),
        (r"(?im)^\s*(bill\s+to|billed\s+to)\s*[:\-]?\s*$", 1.8),
    ],
    "Sales Report": [
        (r"(?is)\b(region|product\s+line)\b.+\b(revenue|units\s+sold|growth)\b", 3.0),
        (r"(?is)\bexecutive\s+summary\b.+\b(recommendations?|forecast)\b", 2.0),
        (r"(?im)^\s*(reporting\s+period|region|report\s+generated)\s*[:\-]", 1.8),
        (r"\b\d+(?:\.\d+)?\s*%\b", 1.0),
    ],
    "Customer Application": [
        (r"(?is)\bpersonal\s+information\b.+\bemployment\s+information\b", 3.0),
        (r"(?is)\bfull\s+name\b.+\bdate\s+of\s+birth\b.+\bemail\s+address\b", 2.5),
        (r"(?is)\bemployer\b.+\bjob\s+title\b.+\bannual\s+income\b", 2.0),
        (r"(?is)\bsignature\b.+\bcertify\b", 1.5),
    ],
}


CATEGORIES = list(CATEGORY_PROTOTYPES.keys())

ALIAS_WEIGHT = 0.40
TFIDF_WEIGHT = 0.35
STRUCTURAL_WEIGHT = 0.25
MIN_TOP_SCORE = 0.35
MIN_CONFIDENCE_MARGIN = 0.12


class DocumentClassifier:
    """Hybrid alias + TF-IDF + structural-hint classifier."""

    def __init__(self):
        self._prototype_tokens = {
            category: self._tokenize(text)
            for category, text in CATEGORY_PROTOTYPES.items()
        }
        self._idf = self._build_idf(self._prototype_tokens.values())
        self._prototype_vectors = {
            category: self._tfidf_vector(tokens)
            for category, tokens in self._prototype_tokens.items()
        }

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r"[a-zA-Z][a-zA-Z0-9]+", text.lower())
        bigrams = [f"{a} {b}" for a, b in zip(words, words[1:])]
        return words + bigrams

    def _build_idf(self, docs) -> dict:
        docs = list(docs)
        doc_count = len(docs)
        document_frequency = Counter()
        for tokens in docs:
            document_frequency.update(set(tokens))
        return {
            token: math.log((1 + doc_count) / (1 + freq)) + 1
            for token, freq in document_frequency.items()
        }

    def _tfidf_vector(self, tokens: list[str]) -> dict:
        counts = Counter(tokens)
        total = sum(counts.values()) or 1
        return {
            token: (count / total) * self._idf.get(token, 1.0)
            for token, count in counts.items()
        }

    def _cosine_similarity(self, left: dict, right: dict) -> float:
        common = set(left) & set(right)
        dot = sum(left[token] * right[token] for token in common)
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

    def _regex_scores(self, text: str, patterns_by_category: dict) -> dict:
        scores = {c: 0.0 for c in CATEGORIES}
        for category, patterns in patterns_by_category.items():
            for pattern, weight in patterns:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    scores[category] += weight
        return scores

    def _alias_scores(self, text: str) -> dict:
        return self._regex_scores(text, CATEGORY_ALIASES)

    def _structural_scores(self, text: str) -> dict:
        return self._regex_scores(text, STRUCTURAL_HINTS)

    def _tfidf_scores(self, text: str) -> dict:
        doc_vector = self._tfidf_vector(self._tokenize(text))
        return {
            category: self._cosine_similarity(doc_vector, prototype_vector)
            for category, prototype_vector in self._prototype_vectors.items()
        }

    def classify(self, text: str) -> dict:
        if not text or not text.strip():
            raise ValueError("Empty text passed to classifier.")

        alias = self._alias_scores(text)
        tfidf = self._tfidf_scores(text)
        structural = self._structural_scores(text)

        alias_max = max(alias.values()) or 1.0
        tfidf_max = max(tfidf.values()) or 1.0
        structural_max = max(structural.values()) or 1.0

        combined = {
            category: (
                ALIAS_WEIGHT * (alias[category] / alias_max)
                + TFIDF_WEIGHT * (tfidf[category] / tfidf_max)
                + STRUCTURAL_WEIGHT * (structural[category] / structural_max)
            )
            for category in CATEGORIES
        }

        ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)
        best_match, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        confidence = top_score - second_score

        category = best_match
        if top_score < MIN_TOP_SCORE or confidence < MIN_CONFIDENCE_MARGIN:
            category = "Unknown"

        return {
            "category": category,
            "best_match": best_match,
            "confidence": round(confidence, 4),
            "scores": {k: round(v, 4) for k, v in combined.items()},
            "alias_scores": {k: round(v, 4) for k, v in alias.items()},
            "tfidf_scores": {k: round(v, 4) for k, v in tfidf.items()},
            "structural_scores": {k: round(v, 4) for k, v in structural.items()},
            "thresholds": {
                "min_top_score": MIN_TOP_SCORE,
                "min_confidence_margin": MIN_CONFIDENCE_MARGIN,
            },
        }


if __name__ == "__main__":
    import sys
    from text_extractor import extract_text_from_pdf

    if len(sys.argv) < 2:
        print("Usage: python classifier.py <pdf_path>")
        sys.exit(1)

    doc = extract_text_from_pdf(sys.argv[1])
    clf = DocumentClassifier()
    result = clf.classify(doc["text"])
    print(f"File:       {doc['filename']}")
    print(f"Category:   {result['category']}")
    print(f"Best match: {result['best_match']}")
    print(f"Confidence: {result['confidence']}")
    print(f"Scores:     {result['scores']}")
    print(f"Alias:      {result['alias_scores']}")
    print(f"TF-IDF:     {result['tfidf_scores']}")
    print(f"Structure:  {result['structural_scores']}")
