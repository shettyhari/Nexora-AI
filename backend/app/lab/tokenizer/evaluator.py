"""
Tokenizer Research & Evaluation Engine.
Computes fertility, compression ratio, vocabulary coverage, and cross-lingual efficiency.
"""
from collections import Counter
import math
from typing import Any, Dict, List
from app.lab.tokenizer.bpe import BPETokenizer


class TokenizerEvaluator:
    """Rigorous evaluation suite for subword tokenizers."""

    @classmethod
    def evaluate(cls, tokenizer: BPETokenizer, test_text: str) -> Dict[str, Any]:
        """
        Computes core tokenizer metrics:
        - Fertility: tokens per word (lower is more compact, ideal ~ 1.0 - 1.4)
        - Compression Ratio: raw UTF-8 bytes per token (higher is more efficient)
        - Unknown token rate
        - Total tokens, words, and characters
        """
        if not test_text.strip():
            return {
                "fertility": 1.0,
                "compression_ratio": 1.0,
                "tokens_per_word": 1.0,
                "unknown_rate": 0.0,
                "total_tokens": 0,
                "total_words": 0,
                "total_bytes": 0,
            }

        raw_bytes = len(test_text.encode("utf-8"))
        words = test_text.strip().split()
        total_words = max(len(words), 1)

        token_ids = tokenizer.encode(test_text)
        total_tokens = max(len(token_ids), 1)

        unk_id = tokenizer.inverse_vocab.get("<unk>", 1)
        unk_count = sum(1 for tid in token_ids if tid == unk_id)

        fertility = round(total_tokens / total_words, 3)
        compression_ratio = round(raw_bytes / total_tokens, 3)
        unknown_rate = round(unk_count / total_tokens, 4)

        # Token length distribution
        token_lengths = [len(tokenizer.vocab.get(tid, "")) for tid in token_ids]
        avg_token_length = round(sum(token_lengths) / max(len(token_lengths), 1), 2)

        return {
            "fertility": fertility,
            "compression_ratio": compression_ratio,
            "tokens_per_word": fertility,
            "unknown_rate": unknown_rate,
            "total_tokens": total_tokens,
            "total_words": total_words,
            "total_bytes": raw_bytes,
            "avg_token_length_chars": avg_token_length,
            "token_ids_preview": token_ids[:30]
        }

    @classmethod
    def analyze_frequency_spectrum(cls, tokenizer: BPETokenizer, corpus: List[str]) -> Dict[str, Any]:
        """
        Analyzes token frequency distribution, Zipfian slope,
        and cumulative vocabulary coverage.
        """
        token_counter = Counter()
        for doc in corpus:
            tids = tokenizer.encode(doc)
            token_counter.update(tids)

        total_occurrences = sum(token_counter.values())
        most_common = token_counter.most_common(20)

        top_tokens = []
        for tid, count in most_common:
            token_str = tokenizer.vocab.get(tid, f"<id_{tid}>")
            top_tokens.append({
                "token_id": tid,
                "token": token_str,
                "frequency": count,
                "percentage": round(count / max(total_occurrences, 1) * 100, 2)
            })

        # Calculate coverage of top 100, 500, 1000 tokens
        cumulative = 0
        coverage_curve = {}
        for rank, (tid, count) in enumerate(token_counter.most_common(), start=1):
            cumulative += count
            if rank in (50, 100, 250, 500, 1000, 2000):
                coverage_curve[f"top_{rank}"] = round(cumulative / max(total_occurrences, 1) * 100, 2)

        return {
            "unique_tokens_used": len(token_counter),
            "total_tokens_generated": total_occurrences,
            "top_tokens": top_tokens,
            "coverage_curve": coverage_curve
        }

    @classmethod
    def evaluate_multilingual(cls, tokenizer: BPETokenizer) -> Dict[str, Any]:
        """
        Evaluates compression efficiency across multilingual reference samples.
        """
        samples = {
            "english": "Foundation models are trained on vast amounts of data using self-supervised learning.",
            "code_python": "def transformer_block(x, mask):\n    attn = multi_head_attention(norm(x))\n    return x + attn",
            "spanish": "Los modelos fundacionales se entrenan con grandes volúmenes de datos mediante aprendizaje auto-supervisado.",
            "german": "Grundlagenmodelle werden auf riesigen Datenmengen mit selbstüberwachtem Lernen trainiert.",
            "math": "E = mc^2 and the loss function L_CE = -sum(y_i * log(p_i)) over all vocabulary classes."
        }

        results = {}
        for lang, text in samples.items():
            metrics = cls.evaluate(tokenizer, text)
            results[lang] = {
                "fertility": metrics["fertility"],
                "compression_ratio": metrics["compression_ratio"],
                "total_tokens": metrics["total_tokens"],
                "bytes": metrics["total_bytes"]
            }

        return results
