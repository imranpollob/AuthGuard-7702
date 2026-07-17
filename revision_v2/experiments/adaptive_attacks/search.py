#!/usr/bin/env python3
"""Deterministic valid-action random and score-guided beam search."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable

import numpy as np


ACTIONS = ("metadata", "address", "selector", "neutral25",
           "flood25", "flood50", "flood100", "flood200")
FLOOD_ACTIONS = {"flood25", "flood50", "flood100", "flood200"}


@dataclass
class Candidate:
    sequence: tuple[str, ...]
    bytecode: str
    score: float
    query_index: int
    structural_valid: bool = True


def sequence_allowed(sequence: tuple[str, ...], action: str) -> bool:
    if action in sequence:
        return False
    if action in FLOOD_ACTIONS and any(item in FLOOD_ACTIONS for item in sequence):
        return False
    return True


def deterministic_rng(seed_material: str, seed: int = 7702):
    value = int.from_bytes(hashlib.blake2b(
        seed_material.encode(), digest_size=8, salt=seed.to_bytes(8, "little")).digest(),
        "little")
    return np.random.default_rng(value)


def random_sequences(seed_material: str, budget: int, max_depth: int = 4):
    rng = deterministic_rng(seed_material)
    seen: set[tuple[str, ...]] = set()
    ordered: list[tuple[str, ...]] = []
    attempts = 0
    while len(seen) < budget and attempts < budget * 100:
        attempts += 1
        depth = int(rng.integers(1, max_depth + 1))
        available = list(ACTIONS)
        sequence: list[str] = []
        while available and len(sequence) < depth:
            index = int(rng.integers(0, len(available)))
            action = available.pop(index)
            if not sequence_allowed(tuple(sequence), action):
                continue
            sequence.append(action)
            if action in FLOOD_ACTIONS:
                available = [item for item in available if item not in FLOOD_ACTIONS]
        item = tuple(sequence)
        if item and item not in seen:
            seen.add(item); ordered.append(item)
    return ordered


def choose_best(clean_hex: str, clean_score: float, queried: list[Candidate]):
    clean = Candidate(sequence=(), bytecode=clean_hex, score=float(clean_score), query_index=0)
    return min([clean, *queried], key=lambda c: (c.score, c.query_index, c.sequence))


def random_search(clean_hex: str, clean_score: float, threshold: float, seed_material: str,
                  apply_sequence: Callable[[tuple[str, ...]], str | None],
                  score_batch: Callable[[list[str]], np.ndarray], budget: int = 64,
                  max_depth: int = 4):
    sequences = random_sequences(seed_material, budget, max_depth)
    bytecodes, kept_sequences, seen_hex = [], [], set()
    for sequence in sequences:
        candidate = apply_sequence(sequence)
        if candidate is None or candidate in seen_hex or candidate == clean_hex:
            continue
        seen_hex.add(candidate); bytecodes.append(candidate); kept_sequences.append(sequence)
        if len(bytecodes) >= budget:
            break
    scores = score_batch(bytecodes) if bytecodes else np.asarray([], dtype=float)
    queried = [Candidate(sequence=seq, bytecode=bc, score=float(score), query_index=i + 1)
               for i, (seq, bc, score) in enumerate(zip(kept_sequences, bytecodes, scores))]
    first_success = next((c.query_index for c in queried if c.score < threshold), None)
    return choose_best(clean_hex, clean_score, queried), queried, first_success


def beam_search(clean_hex: str, clean_score: float, threshold: float,
                apply_from_state: Callable[[tuple[str, ...], str, str], str | None],
                score_batch: Callable[[list[str]], np.ndarray], budget: int = 64,
                width: int = 4, max_depth: int = 4):
    beam = [Candidate(sequence=(), bytecode=clean_hex, score=float(clean_score), query_index=0)]
    queried: list[Candidate] = []
    seen_hex = {clean_hex}
    query_index = 0
    for _depth in range(1, max_depth + 1):
        expanded: list[tuple[tuple[str, ...], str]] = []
        for parent in beam:
            for action in ACTIONS:
                if not sequence_allowed(parent.sequence, action):
                    continue
                sequence = parent.sequence + (action,)
                candidate = apply_from_state(parent.sequence, parent.bytecode, action)
                if candidate is None or candidate in seen_hex:
                    continue
                seen_hex.add(candidate)
                expanded.append((sequence, candidate))
                if len(queried) + len(expanded) >= budget:
                    break
            if len(queried) + len(expanded) >= budget:
                break
        if not expanded:
            break
        scores = score_batch([bytecode for _, bytecode in expanded])
        depth_candidates = []
        for (sequence, bytecode), score in zip(expanded, scores):
            query_index += 1
            depth_candidates.append(Candidate(sequence=sequence, bytecode=bytecode,
                                              score=float(score), query_index=query_index))
        queried.extend(depth_candidates)
        beam = sorted(depth_candidates, key=lambda c: (c.score, c.query_index, c.sequence))[:width]
        if len(queried) >= budget:
            break
    first_success = next((c.query_index for c in queried if c.score < threshold), None)
    return choose_best(clean_hex, clean_score, queried), queried, first_success
