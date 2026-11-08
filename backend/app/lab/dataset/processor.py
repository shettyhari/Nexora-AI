"""
Dataset Management & Data Cleaning Platform.
Implements text normalization, PII detection, deduplication, quality filtering,
language identification, and deterministic dataset splitting.
"""
import hashlib
import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple


class PIIFinding:
    def __init__(self, pii_type: str, matched_text: str, start: int, end: int):
        self.pii_type = pii_type
        self.matched_text = matched_text
        self.start = start
        self.end = end

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pii_type": self.pii_type,
            "matched_text": self.matched_text,
            "start": self.start,
            "end": self.end,
        }


class DatasetProcessor:
    """Enterprise-grade training data processor and provenance manager."""

    # Regex patterns for PII
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
    PHONE_PATTERN = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    IPV4_PATTERN = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")
    CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")

    @classmethod
    def clean_and_normalize(cls, text: str) -> str:
        """
        Applies Unicode NFKC normalization, whitespace collapse,
        and invalid control character stripping.
        """
        if not text:
            return ""

        # Unicode normalization NFKC
        text = unicodedata.normalize("NFKC", text)

        # Normalize curly quotes and apostrophes
        text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        text = text.replace("–", "-").replace("—", "-")

        # Strip non-printable/control chars except \n, \t, \r
        cleaned_chars = []
        for ch in text:
            cat = unicodedata.category(ch)
            if cat.startswith("C") and ch not in ("\n", "\t", "\r"):
                continue
            cleaned_chars.append(ch)
        text = "".join(cleaned_chars)

        # Collapse excessive whitespace and blank lines (keep max 2 newlines)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def detect_and_redact_pii(cls, text: str, redact: bool = True) -> Tuple[str, List[PIIFinding], Dict[str, int]]:
        """
        Scans for personally identifiable information (PII) including emails,
        phone numbers, SSNs, IPv4 addresses, and credit cards.
        Optionally redacts matches with safe placeholders.
        """
        findings: List[PIIFinding] = []
        counts: Dict[str, int] = {
            "email": 0,
            "phone": 0,
            "ssn": 0,
            "ipv4": 0,
            "credit_card": 0
        }

        # Helper to record matches
        def record_matches(pattern: re.Pattern, pii_type: str):
            for match in pattern.finditer(text):
                matched = match.group(0)
                # For credit card, verify Luhn algorithm
                if pii_type == "credit_card":
                    digits = re.sub(r"\D", "", matched)
                    if not cls._validate_luhn(digits):
                        continue
                findings.append(PIIFinding(pii_type, matched, match.start(), match.end()))
                counts[pii_type] += 1

        record_matches(cls.EMAIL_PATTERN, "email")
        record_matches(cls.PHONE_PATTERN, "phone")
        record_matches(cls.SSN_PATTERN, "ssn")
        record_matches(cls.IPV4_PATTERN, "ipv4")
        record_matches(cls.CREDIT_CARD_PATTERN, "credit_card")

        if not redact or not findings:
            return text, findings, counts

        # Sort findings in reverse order of appearance to replace without shifting offsets
        findings_sorted = sorted(findings, key=lambda f: f.start, reverse=True)
        redacted_text = text
        for f in findings_sorted:
            placeholder = f"<{f.pii_type.upper()}_REDACTED>"
            redacted_text = redacted_text[:f.start] + placeholder + redacted_text[f.end:]

        return redacted_text, findings, counts

    @staticmethod
    def _validate_luhn(card_number: str) -> bool:
        """Luhn algorithm verification for credit card numbers."""
        if len(card_number) < 13 or len(card_number) > 19:
            return False
        total = 0
        reverse_digits = card_number[::-1]
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 1:
                n *= 2
                if n > 9:
                    n -= 9
            total += n
        return total % 10 == 0

    @classmethod
    def passes_quality_filter(
        cls,
        text: str,
        min_chars: int = 50,
        max_chars: int = 500000,
        min_alpha_ratio: float = 0.60
    ) -> Tuple[bool, str]:
        """
        Heuristic quality filtering for training text:
        - Character bounds
        - Alpha/alphabet character ratio (filters garbled binary/OCR noise)
        - Repetition loops / boilerplate detection
        """
        if len(text) < min_chars:
            return False, f"Too short ({len(text)} < {min_chars} chars)"
        if len(text) > max_chars:
            return False, f"Too long ({len(text)} > {max_chars} chars)"

        # Alpha ratio
        alpha_count = sum(1 for c in text if c.isalpha())
        alpha_ratio = alpha_count / max(len(text), 1)
        if alpha_ratio < min_alpha_ratio:
            return False, f"Low alpha ratio ({alpha_ratio:.2f} < {min_alpha_ratio})"

        # Repetition detection (e.g., repeated lines or phrases > 4 times)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) >= 6:
            line_counts: Dict[str, int] = {}
            for line in lines:
                line_counts[line] = line_counts.get(line, 0) + 1
            most_frequent = max(line_counts.values()) if line_counts else 0
            if most_frequent > len(lines) * 0.4:
                return False, f"Repetitive text detected ({most_frequent} identical lines)"

        return True, "Passed"

    @classmethod
    def identify_language(cls, text: str) -> Dict[str, float]:
        """
        Heuristic language identifier distinguishing English, Code, and Multilingual.
        """
        if not text:
            return {"en": 1.0}

        # Code markers
        code_markers = ["def ", "class ", "import ", "return ", "const ", "function", "var ", "{", "}", ";"]
        code_hits = sum(1 for marker in code_markers if marker in text)
        if code_hits >= 3:
            return {"code": 0.85, "en": 0.15}

        # Common stop words
        en_words = {"the", "and", "of", "to", "in", "is", "that", "for", "it", "with", "as", "was", "on"}
        es_words = {"de", "la", "que", "el", "en", "y", "a", "los", "se", "del", "las", "un", "por", "con"}
        fr_words = {"de", "la", "le", "et", "les", "des", "en", "un", "du", "une", "que", "est", "pour"}

        words = set(re.findall(r"\b[a-zA-Z]{2,}\b", text.lower()))
        en_score = len(words.intersection(en_words))
        es_score = len(words.intersection(es_words))
        fr_score = len(words.intersection(fr_words))

        total = en_score + es_score + fr_score
        if total == 0:
            return {"en": 1.0}

        return {
            "en": round(en_score / total, 3),
            "es": round(es_score / total, 3),
            "fr": round(fr_score / total, 3)
        }

    @classmethod
    def deduplicate(cls, samples: List[str]) -> Tuple[List[str], int]:
        """
        Exact SHA-256 deduplication of dataset samples.
        Returns deduplicated samples and the number of duplicates removed.
        """
        seen_hashes: Set[str] = set()
        deduped: List[str] = []
        duplicates_count = 0

        for sample in samples:
            h = hashlib.sha256(sample.encode("utf-8")).hexdigest()
            if h in seen_hashes:
                duplicates_count += 1
            else:
                seen_hashes.add(h)
                deduped.append(sample)

        return deduped, duplicates_count

    @classmethod
    def split_dataset(
        cls,
        samples: List[Any],
        train_ratio: float = 0.80,
        val_ratio: float = 0.10,
        test_ratio: float = 0.10,
        seed: int = 42
    ) -> Dict[str, List[Any]]:
        """
        Deterministically splits dataset into train, validation, and test subsets.
        """
        import random
        rng = random.Random(seed)
        shuffled = list(samples)
        rng.shuffle(shuffled)

        n = len(shuffled)
        train_end = int(n * train_ratio)
        val_end = train_end + int(n * val_ratio)

        train_data = shuffled[:train_end]
        val_data = shuffled[train_end:val_end]
        test_data = shuffled[val_end:]

        return {
            "train": train_data,
            "validation": val_data,
            "test": test_data
        }

    @classmethod
    def process_raw_dataset(
        cls,
        raw_samples: List[str],
        license_name: str,
        source_name: str,
        redact_pii: bool = True,
        seed: int = 42
    ) -> Dict[str, Any]:
        """
        Complete end-to-end dataset transformation pipeline:
        1. Normalization
        2. Quality filtering
        3. PII scanning & optional redaction
        4. Deduplication
        5. Language profiling
        6. Train/Val/Test splitting
        7. Full provenance digest
        """
        raw_bytes = sum(len(s.encode("utf-8")) for s in raw_samples)
        raw_count = len(raw_samples)
        raw_hash = hashlib.sha256("\n".join(raw_samples).encode("utf-8")).hexdigest()

        cleaned_samples = []
        total_pii_counts: Dict[str, int] = {"email": 0, "phone": 0, "ssn": 0, "ipv4": 0, "credit_card": 0}
        quality_dropped = 0

        for s in raw_samples:
            norm = cls.clean_and_normalize(s)
            passes, _ = cls.passes_quality_filter(norm)
            if not passes:
                quality_dropped += 1
                continue

            redacted, _, pii_counts = cls.detect_and_redact_pii(norm, redact=redact_pii)
            for k, v in pii_counts.items():
                total_pii_counts[k] += v

            cleaned_samples.append(redacted)

        # Deduplication
        deduped_samples, duplicates_count = cls.deduplicate(cleaned_samples)

        # Language distribution
        combined_text = " ".join(deduped_samples[:50])
        lang_dist = cls.identify_language(combined_text)

        # Splits
        splits = cls.split_dataset(deduped_samples, seed=seed)

        cleaned_bytes = sum(len(s.encode("utf-8")) for s in deduped_samples)
        cleaned_hash = hashlib.sha256("\n".join(deduped_samples).encode("utf-8")).hexdigest()

        provenance = {
            "author": "NEXORA Model Lab Curator",
            "source_name": source_name,
            "license": license_name,
            "raw_sha256": raw_hash,
            "cleaned_sha256": cleaned_hash,
            "split_seed": seed,
            "pipeline_version": "1.0.0-nfkc-pii-dedup-v1"
        }

        return {
            "raw_count": raw_count,
            "raw_size_bytes": raw_bytes,
            "cleaned_count": len(deduped_samples),
            "cleaned_size_bytes": cleaned_bytes,
            "train_count": len(splits["train"]),
            "val_count": len(splits["validation"]),
            "test_count": len(splits["test"]),
            "language_distribution": lang_dist,
            "pii_findings": total_pii_counts,
            "cleaning_stats": {
                "quality_dropped": quality_dropped,
                "duplicates_removed": duplicates_count,
                "total_retained": len(deduped_samples)
            },
            "provenance": provenance,
            "splits": splits
        }
