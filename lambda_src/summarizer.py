"""
summarizer.py
-------------
Lightweight extractive summarizer. Pure standard library + a small built-in
stopword list — no network downloads (NLTK data fetch is sandboxed away in
some environments). Picks the top-N highest-scoring sentences by normalized
word frequency.

For free-tier / cost-sensitive deployments this runs in microseconds and
fits the assignment's "open-source, local" constraint. The same module
interface (`summarize(text, num_sentences)`) lets you swap in an
Amazon Bedrock / Claude Haiku call later without touching the orchestrator.
"""

import re
from collections import Counter

# Minimal English stopword list — covers the high-frequency tokens that
# would otherwise dominate sentence scoring.
STOPWORDS = set("""
a an the and or but if then else for of on in at by to from with without
is are was were be been being am have has had do does did this that these
those it its as not no than too very can will would should could may might
must shall i you he she we they them us our your their my mine yours his
hers ours theirs which who whom whose what when where why how about above
after again against all also any because before below between both during
each few further here into more most other own same so some such only over
under up down out off again own same so much
""".split())

# Sentence splitter — handles . ! ? followed by whitespace, while
# avoiding splits on common abbreviations and decimals.
SENTENCE_SPLIT_RE = re.compile(r"(?<=[\.!?])\s+(?=[A-Z\"\']|$)")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z\-']+")


def _split_sentences(text: str) -> list:
    # Pre-clean: collapse whitespace, drop empty lines.
    cleaned = re.sub(r"\s+", " ", text.strip())
    # Naive but effective for the document types in scope.
    raw = SENTENCE_SPLIT_RE.split(cleaned)
    return [s.strip() for s in raw if s.strip() and len(s.strip().split()) >= 4]


def _tokenize(s: str) -> list:
    return [w.lower() for w in WORD_RE.findall(s)]


def summarize(text: str, num_sentences: int = 3) -> str:
    """
    Return an extractive summary built from the top-N scoring sentences,
    preserving their original order in the document.

    Scoring:
        - Compute word frequency over all non-stopword tokens.
        - Normalize by max frequency so common terms don't dominate.
        - Each sentence's score is the sum of its words' normalized
          frequencies, divided by sentence length (so we don't bias
          toward very long sentences).
    """
    if not text or not text.strip():
        return ""

    sentences = _split_sentences(text)
    if len(sentences) <= num_sentences:
        return " ".join(sentences)

    # --- term frequencies ---
    freq = Counter()
    for s in sentences:
        for tok in _tokenize(s):
            if tok in STOPWORDS or len(tok) <= 2:
                continue
            freq[tok] += 1

    if not freq:
        return " ".join(sentences[:num_sentences])

    max_f = max(freq.values())
    norm_freq = {w: c / max_f for w, c in freq.items()}

    # --- sentence scores ---
    scored = []
    for idx, s in enumerate(sentences):
        toks = [t for t in _tokenize(s) if t not in STOPWORDS and len(t) > 2]
        if not toks:
            continue
        score = sum(norm_freq.get(t, 0.0) for t in toks) / len(toks)
        scored.append((idx, score, s))

    # Pick top N by score, then return in original document order.
    top = sorted(scored, key=lambda x: x[1], reverse=True)[:num_sentences]
    top_sorted = sorted(top, key=lambda x: x[0])
    return " ".join(s for _, _, s in top_sorted)


if __name__ == "__main__":
    import sys
    from text_extractor import extract_text_from_pdf

    if len(sys.argv) < 2:
        print("Usage: python summarizer.py <pdf_path> [num_sentences]")
        sys.exit(1)
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    doc = extract_text_from_pdf(sys.argv[1])
    summary = summarize(doc["text"], num_sentences=n)
    print(f"--- Summary ({n} sentences) ---")
    print(summary)
