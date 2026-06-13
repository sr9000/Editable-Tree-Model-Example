"""Timing, scaling, and allocation measurement harness.

Provides a reusable measurement API so each test reports timings, scaling ratios,
and allocation outcomes in the same format.

Key functions:
- ``measure_call(callable, text)``: Measure a single call with timing and allocation.
- ``assert_within_budget(result)``: Assert a result is within the time budget.
- ``scaling_rows(callable, sizes, factory)``: Generate scaling rows for size doublings.
- ``classify_rows(rows)``: Classify rows by outcome (pass, budget_exceeded, etc.).
"""

from __future__ import annotations

import os
import statistics
import time
import tracemalloc
from dataclasses import dataclass, field
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Configuration constants (overridable via environment variables)
# ---------------------------------------------------------------------------

# Default per-call wall-clock budget in milliseconds
DEFAULT_BUDGET_MS = 100

# Default scaling ratio threshold for size doublings
DEFAULT_SCALING_RATIO_MAX = 3.0

# Default allocation cap for non-decoding paths (8 MB or 4x text length)
DEFAULT_ALLOCATION_CAP_BASE = 8 * 1024 * 1024
DEFAULT_ALLOCATION_CAP_MULTIPLIER = 4

# Default allocation cap for decode/decompress paths (16 MB or 2x text length)
DEFAULT_DECODE_ALLOCATION_CAP_BASE = 16 * 1024 * 1024
DEFAULT_DECODE_ALLOCATION_CAP_MULTIPLIER = 2


def get_budget_ms() -> float:
    """Return the per-call budget in milliseconds, from env or default."""
    return float(os.environ.get("PARSING_BUDGET_MS", DEFAULT_BUDGET_MS))


def get_scaling_ratio_max() -> float:
    """Return the scaling ratio threshold, from env or default."""
    return float(os.environ.get("PARSING_SCALING_RATIO_MAX", DEFAULT_SCALING_RATIO_MAX))


# ---------------------------------------------------------------------------
# Result data structures
# ---------------------------------------------------------------------------


@dataclass
class MeasurementResult:
    """Result of a single measurement."""

    function: str
    wrapper_name: str
    family: str
    size: int
    elapsed_median_ms: float
    raw_ms: list[float]  # All three raw timings
    peak_allocated_bytes: int
    outcome: str  # pass, budget_exceeded, superlinear, allocation_exceeded, error
    exception_text: str = ""
    scaling_ratio: float | None = None  # For scaling rows

    def to_dict(self) -> dict[str, Any]:
        """Convert to a dictionary for report generation."""
        return {
            "function": self.function,
            "wrapper_name": self.wrapper_name,
            "family": self.family,
            "size": self.size,
            "elapsed_median_ms": self.elapsed_median_ms,
            "raw_ms": self.raw_ms,
            "peak_allocated_bytes": self.peak_allocated_bytes,
            "outcome": self.outcome,
            "exception_text": self.exception_text,
            "scaling_ratio": self.scaling_ratio,
        }


# ---------------------------------------------------------------------------
# Measurement functions
# ---------------------------------------------------------------------------


def measure_call(
    callable_fn: Callable[[str], Any],
    text: str,
    *,
    function_name: str = "",
    wrapper_name: str = "",
    family: str = "",
    warmup: int = 1,
    repeats: int = 3,
    is_decode_path: bool = False,
) -> MeasurementResult:
    """Measure a callable with timing and allocation tracking.

    Performs one warmup call and records the median of three timed calls.
    Uses ``tracemalloc`` to track peak memory allocation.

    Args:
        callable_fn: The function to measure, accepting a single string argument.
        text: The input text to pass to the callable.
        function_name: Name of the function being measured.
        wrapper_name: Name of the wrapper used.
        family: Adversarial family label.
        warmup: Number of warmup calls (default 1).
        repeats: Number of timed calls (default 3).
        is_decode_path: If True, use decode path allocation caps.

    Returns:
        A MeasurementResult with timing and allocation data.
    """
    func_name = function_name or getattr(  # allow: perf harness needs function name from callable
        callable_fn,
        "__name__",
        "unknown",
    )
    wrap_name = wrapper_name or func_name

    # Warmup calls
    for _ in range(warmup):
        try:
            callable_fn(text)
        except Exception:
            pass  # Warmup failures are ignored

    # Timed calls with allocation tracking
    raw_ms: list[float] = []
    peak_bytes = 0

    tracemalloc.start()
    try:
        for _ in range(repeats):
            # Reset peak tracking for each call
            tracemalloc.reset_peak()
            start = time.perf_counter()
            try:
                callable_fn(text)
            except Exception as e:
                elapsed = (time.perf_counter() - start) * 1000
                raw_ms.append(elapsed)
                # Record the exception and return error outcome
                current, peak = tracemalloc.get_traced_memory()
                peak_bytes = max(peak_bytes, peak)
                tracemalloc.stop()
                return MeasurementResult(
                    function=func_name,
                    wrapper_name=wrap_name,
                    family=family,
                    size=len(text),
                    elapsed_median_ms=elapsed,
                    raw_ms=raw_ms,
                    peak_allocated_bytes=peak_bytes,
                    outcome="error",
                    exception_text=str(e),
                )
            elapsed = (time.perf_counter() - start) * 1000
            raw_ms.append(elapsed)
            current, peak = tracemalloc.get_traced_memory()
            peak_bytes = max(peak_bytes, peak)
    finally:
        tracemalloc.stop()

    median_ms = statistics.median(raw_ms)

    # Determine allocation cap
    text_len = len(text)
    if is_decode_path:
        alloc_cap = max(DEFAULT_DECODE_ALLOCATION_CAP_BASE, DEFAULT_DECODE_ALLOCATION_CAP_MULTIPLIER * text_len)
    else:
        alloc_cap = max(DEFAULT_ALLOCATION_CAP_BASE, DEFAULT_ALLOCATION_CAP_MULTIPLIER * text_len)

    # Classify outcome
    budget_ms = get_budget_ms()
    if median_ms > budget_ms:
        outcome = "budget_exceeded"
    elif peak_bytes > alloc_cap:
        outcome = "allocation_exceeded"
    else:
        outcome = "pass"

    return MeasurementResult(
        function=func_name,
        wrapper_name=wrap_name,
        family=family,
        size=text_len,
        elapsed_median_ms=median_ms,
        raw_ms=raw_ms,
        peak_allocated_bytes=peak_bytes,
        outcome=outcome,
    )


def assert_within_budget(result: MeasurementResult) -> None:
    """Assert that a measurement result is within the time budget.

    Raises AssertionError if the outcome is not 'pass'.
    """
    if result.outcome != "pass":
        msg = f"{result.function} ({result.wrapper_name}) failed: {result.outcome}"
        if result.exception_text:
            msg += f" - {result.exception_text}"
        msg += f" (median={result.elapsed_median_ms:.2f}ms, peak={result.peak_allocated_bytes} bytes)"
        raise AssertionError(msg)


def scaling_rows(
    callable_fn: Callable[[str], Any],
    sizes: tuple[int, ...],
    factory: Callable[[int], tuple[str, str]],
    *,
    function_name: str = "",
    wrapper_name: str = "",
    is_decode_path: bool = False,
) -> list[MeasurementResult]:
    """Generate measurement rows for a sequence of sizes.

    Args:
        callable_fn: The function to measure.
        sizes: Tuple of sizes to test (should be doubling sequence).
        factory: Function that generates (family, text) for a given size.
        function_name: Name of the function being measured.
        wrapper_name: Name of the wrapper used.
        is_decode_path: If True, use decode path allocation caps.

    Returns:
        List of MeasurementResult, one per size.
    """
    rows: list[MeasurementResult] = []
    family_label, _ = factory(sizes[0]) if sizes else ("unknown", "")

    for size in sizes:
        _, text = factory(size)
        result = measure_call(
            callable_fn,
            text,
            function_name=function_name,
            wrapper_name=wrapper_name,
            family=family_label,
            is_decode_path=is_decode_path,
        )
        rows.append(result)

    return rows


def classify_rows(rows: list[MeasurementResult]) -> list[MeasurementResult]:
    """Classify rows by scaling ratio for size doublings.

    For each pair of consecutive rows where the size doubles, computes the
    median time ratio. If the ratio exceeds the threshold, marks the row
    as 'superlinear' (unless it already has a worse outcome).

    Args:
        rows: List of MeasurementResult from scaling_rows.

    Returns:
        The same list with scaling_ratio and potentially updated outcome.
    """
    if len(rows) < 2:
        return rows

    ratio_max = get_scaling_ratio_max()

    for i in range(1, len(rows)):
        prev = rows[i - 1]
        curr = rows[i]

        # Only compute ratio for size doublings
        if curr.size > prev.size and prev.elapsed_median_ms > 0:
            ratio = curr.elapsed_median_ms / prev.elapsed_median_ms
            curr.scaling_ratio = ratio

            # Update outcome if superlinear and not already worse
            if ratio > ratio_max and curr.outcome == "pass":
                curr.outcome = "superlinear"

    return rows


# ---------------------------------------------------------------------------
# Utility functions for tests
# ---------------------------------------------------------------------------


def make_linear_callable() -> Callable[[str], int]:
    """Return a callable with linear time complexity for testing."""

    def linear_fn(text: str) -> int:
        # Simple linear operation: sum of character codes
        return sum(ord(c) for c in text)

    return linear_fn


def make_quadratic_callable() -> Callable[[str], int]:
    """Return a callable with quadratic time complexity for testing."""

    def quadratic_fn(text: str) -> int:
        # Deliberately quadratic: nested loops over text
        result = 0
        for i in range(len(text)):
            for j in range(min(100, len(text))):  # Cap inner loop for very large texts
                result += ord(text[i % len(text)])
        return result

    return quadratic_fn


def make_allocating_callable(size_multiplier: int = 10) -> Callable[[str], bytes]:
    """Return a callable that allocates a large buffer for testing.

    Args:
        size_multiplier: Multiplier for the allocation size relative to input.
    """

    def allocating_fn(text: str) -> bytes:
        # Allocate a buffer proportional to input size
        alloc_size = len(text) * size_multiplier
        return b"x" * alloc_size

    return allocating_fn
