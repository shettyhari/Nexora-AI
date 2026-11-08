"""
Byte-Pair Encoding (BPE) Tokenizer Research Engine.
Supports vocabulary learning from corpora, merge rule serialization,
special token management, and subword encoding/decoding.
"""
from collections import defaultdict
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple


class BPETokenizer:
    """
    Authentic Byte-Pair Encoding (BPE) implementation.
    Iteratively learns character/byte merges from training text.
    """

    DEFAULT_SPECIAL_TOKENS = ["<pad>", "<unk>", "<s>", "</s>", "<bos>", "<eos>", "<mask_token>"]

    def __init__(self, special_tokens: Optional[List[str]] = None):
        self.special_tokens = special_tokens or list(self.DEFAULT_SPECIAL_TOKENS)
        self.vocab: Dict[int, str] = {}
        self.inverse_vocab: Dict[str, int] = {}
        self.merges: List[Tuple[str, str]] = []

        # Initialize special tokens
        for idx, token in enumerate(self.special_tokens):
            self.vocab[idx] = token
            self.inverse_vocab[token] = idx

    def train(self, corpus: List[str], target_vocab_size: int = 500, min_frequency: int = 2):
        """
        Trains BPE merge rules on the provided text corpus until
        target_vocab_size is reached or no frequent pairs remain.
        """
        # 1. Segment words into character tuples ending with end-of-word marker </w>
        word_freqs: Dict[Tuple[str, ...], int] = defaultdict(int)
        for text in corpus:
            words = text.strip().split()
            for word in words:
                if not word:
                    continue
                # Character tokens + boundary marker
                chars = tuple(list(word) + ["</w>"])
                word_freqs[chars] += 1

        # 2. Add base alphabet characters to vocabulary
        current_idx = len(self.vocab)
        initial_chars: Set[str] = set()
        for chars in word_freqs:
            for ch in chars:
                initial_chars.add(ch)

        for ch in sorted(initial_chars):
            if ch not in self.inverse_vocab:
                self.vocab[current_idx] = ch
                self.inverse_vocab[ch] = current_idx
                current_idx += 1

        # 3. Iterative merge learning
        self.merges = []
        while len(self.vocab) < target_vocab_size:
            pairs = self._get_stats(word_freqs)
            if not pairs:
                break

            best_pair, best_freq = max(pairs.items(), key=lambda item: item[1])
            if best_freq < min_frequency:
                break

            # Create merged token
            merged_token = "".join(best_pair)
            self.merges.append(best_pair)
            self.vocab[current_idx] = merged_token
            self.inverse_vocab[merged_token] = current_idx
            current_idx += 1

            # Apply merge to word frequencies table
            word_freqs = self._merge_vocab(best_pair, word_freqs)

    @staticmethod
    def _get_stats(word_freqs: Dict[Tuple[str, ...], int]) -> Dict[Tuple[str, str], int]:
        """Counts adjacent pair occurrences across the corpus vocabulary."""
        pairs: Dict[Tuple[str, str], int] = defaultdict(int)
        for word_tuple, freq in word_freqs.items():
            for i in range(len(word_tuple) - 1):
                pair = (word_tuple[i], word_tuple[i + 1])
                pairs[pair] += freq
        return pairs

    @staticmethod
    def _merge_vocab(
        pair: Tuple[str, str],
        word_freqs: Dict[Tuple[str, ...], int]
    ) -> Dict[Tuple[str, ...], int]:
        """Merges all occurrences of the target pair in word tuples."""
        new_word_freqs: Dict[Tuple[str, ...], int] = {}
        first, second = pair

        for word_tuple, freq in word_freqs.items():
            new_tuple = []
            i = 0
            while i < len(word_tuple):
                if i < len(word_tuple) - 1 and word_tuple[i] == first and word_tuple[i + 1] == second:
                    new_tuple.append(first + second)
                    i += 2
                else:
                    new_tuple.append(word_tuple[i])
                    i += 1
            new_word_freqs[tuple(new_tuple)] = freq

        return new_word_freqs

    def encode(self, text: str) -> List[int]:
        """Encodes text string into a sequence of token IDs using learned BPE merges."""
        if not text:
            return []

        unk_id = self.inverse_vocab.get("<unk>", 1)
        tokens_out: List[int] = []

        # Split text while preserving special tokens
        special_regex = "|".join(re.escape(tok) for tok in self.special_tokens)
        parts = re.split(f"({special_regex})", text) if special_regex else [text]

        for part in parts:
            if not part:
                continue
            if part in self.inverse_vocab:
                tokens_out.append(self.inverse_vocab[part])
                continue

            words = part.strip().split()
            for word in words:
                subwords = list(word) + ["</w>"]

                # Iteratively apply merges
                for pair in self.merges:
                    first, second = pair
                    merged = first + second
                    i = 0
                    new_subwords = []
                    while i < len(subwords):
                        if i < len(subwords) - 1 and subwords[i] == first and subwords[i + 1] == second:
                            new_subwords.append(merged)
                            i += 2
                        else:
                            new_subwords.append(subwords[i])
                            i += 1
                    subwords = new_subwords

                for sw in subwords:
                    tokens_out.append(self.inverse_vocab.get(sw, unk_id))

        return tokens_out

    def decode(self, token_ids: List[int]) -> str:
        """Decodes token IDs back into natural text."""
        pieces: List[str] = []
        for tid in token_ids:
            token = self.vocab.get(tid, "<unk>")
            if token in self.special_tokens:
                pieces.append(f" {token} ")
            elif token.endswith("</w>"):
                pieces.append(token[:-4] + " ")
            else:
                pieces.append(token)

        return "".join(pieces).strip()

    def serialize(self) -> Dict[str, Any]:
        """Serializes tokenizer vocabulary and learned merge rules to JSON-compatible dict."""
        return {
            "algorithm": "bpe",
            "vocab_size": len(self.vocab),
            "special_tokens": self.special_tokens,
            "merges": self.merges,
            "vocab": self.vocab,
            "inverse_vocab": self.inverse_vocab,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "BPETokenizer":
        """Instantiates a BPETokenizer from serialized dictionary."""
        tokenizer = cls(special_tokens=data.get("special_tokens"))
        tokenizer.merges = [tuple(p) for p in data.get("merges", [])]
        tokenizer.vocab = {int(k): v for k, v in data.get("vocab", {}).items()}
        tokenizer.inverse_vocab = {k: int(v) for k, v in data.get("inverse_vocab", {}).items()}
        return tokenizer
