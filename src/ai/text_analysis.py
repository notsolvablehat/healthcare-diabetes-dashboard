"""
Text analysis utilities for medical reports.

Uses TF-IDF to extract important keywords from medical documents.
"""
import logging
import re

from sklearn.feature_extraction.text import TfidfVectorizer

# Medical stopwords to ignore (common non-informative terms)
MEDICAL_STOPWORDS = {
    "patient", "doctor", "hospital", "clinic", "report", "date", "time",
    "name", "age", "sex", "male", "female", "mr", "mrs", "ms", "dr",
    "test", "result", "results", "value", "values", "unit", "units",
    "normal", "range", "reference", "specimen", "sample", "collected",
    "page", "printed", "laboratory", "lab", "department",
    "signed", "signature", "authorized", "certified", "copy",
}

logger = logging.getLogger(__name__)

def extract_keywords_tfidf(
    text: str,
    top_n: int = 20,
    min_word_length: int = 3,
) -> list[str]:
    """
    Extract important keywords from medical text using TF-IDF.
    Args:
        text: Raw text from medical report
        top_n: Number of top keywords to return
        min_word_length: Minimum word length to consider
    Returns:
        List of important keywords sorted by TF-IDF score
    """
    if not text or len(text.strip()) < 50:
        return []

    # Clean and preprocess text
    text_clean = text.lower()
    text_clean = re.sub(r'[^a-z0-9\s]', ' ', text_clean)
    text_clean = re.sub(r'\s+', ' ', text_clean).strip()

    # Filter out very short words and stopwords
    words = [
        w for w in text_clean.split()
        if len(w) >= min_word_length and w not in MEDICAL_STOPWORDS
    ]

    if len(words) < 10:
        return words[:top_n]

    # Use TF-IDF on word chunks (sentences/phrases)
    # Split into pseudo-sentences for better TF-IDF
    sentences = re.split(r'[.!?\n]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

    if len(sentences) < 2:
        # Not enough sentences, just return frequent words
        word_freq = {}
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:top_n]]

    try:
        # TF-IDF vectorization
        vectorizer = TfidfVectorizer(
            max_features=100,
            stop_words='english',
            min_df=1,
            max_df=0.9,
            token_pattern=r'\b[a-z]{3,}\b'
        )

        tfidf_matrix = vectorizer.fit_transform(sentences)
        feature_names = vectorizer.get_feature_names_out()

        # Sum TF-IDF scores across all sentences
        scores = tfidf_matrix.sum(axis=0).A1

        # Sort by score
        word_scores = list(zip(feature_names, scores, strict=True))
        word_scores.sort(key=lambda x: x[1], reverse=True)

        # Filter out medical stopwords and return top N
        keywords = [
            word for word, score in word_scores
            if word not in MEDICAL_STOPWORDS and score > 0
        ]

        return keywords[:top_n]

    except Exception:
        # Fallback to simple frequency if TF-IDF fails
        word_freq = {}
        for w in words:
            word_freq[w] = word_freq.get(w, 0) + 1
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w for w, _ in sorted_words[:top_n]]


def format_keywords_for_prompt(keywords: list[str]) -> str:
    """
    Format extracted keywords for inclusion in Gemini prompt.
    Args:
        keywords: List of important keywords
    Returns:
        Formatted string for prompt injection
    """
    if not keywords:
        return ""

    logger.info("Found keywords: %s", keywords)

    return (
        "\n\nIMPORTANT KEYWORDS IDENTIFIED (via TF-IDF analysis):\n"
        f"The following terms appear to be significant in this document. "
        f"Please ensure these are addressed in your analysis:\n"
        f"- {', '.join(keywords)}\n"
    )
