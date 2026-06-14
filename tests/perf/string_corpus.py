"""Adversarial string generators for parsing vulnerability measurement.

Each generator accepts ``size: int`` and returns ``(family_label: str, text: str)``.
The module imports only Python standard-library modules and ``settings`` for Plan 1
limit constants when available.
"""

from __future__ import annotations

import itertools
from typing import Callable

# Try to import Plan 1 limit constants; fall back to defaults if not yet defined.
try:
    from settings import NUMBER_AFFIX_MAX_LEN as _AFFIX_LIMIT
except ImportError:
    _AFFIX_LIMIT = 20


TRACE_EXAMPLE = """
AttributeErro                            Traceback (most recent call last)
Cell In[2], line 1
----> 1 json.load("models_output.xlsx")

File /usr/lib/python3.12/json/__init__.py:293, in load(fp, cls, object_hook, parse_float, parse_int, parse_constant, object_pairs_hook, **kw)
    274 def load(fp, *, cls=None, object_hook=None, parse_float=None,
    275         parse_int=None, parse_constant=None, object_pairs_hook=None, **kw):
    276     \"""Deserialize ``fp`` (a ``.read()``-supporting file-like object containing
277     a JSON document) to a Python object.
278
(...)
291     kwarg; otherwise ``JSONDecoder`` is used.
292     \"""
--> 293     return loads(fp.read(),
    294         cls=cls, object_hook=object_hook,
    295         parse_float=parse_float, parse_int=parse_int,
    296         parse_constant=parse_constant, object_pairs_hook=object_pairs_hook, **kw)

AttributeErro: 'str' object has no attribute 'read'

"""

SOURCE_CODE_EXAMPLE = """
import sys
import pygame

# Initialize core modules
pygame.init()

# Game display settings
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Pygame Movement Example")

# Timing control
clock = pygame.time.Clock()
FPS = 60

# Character definitions
player_color = (0, 128, 255)  # Blue
player_width = 50
player_height = 50
player_x = (SCREEN_WIDTH - player_width) // 2
player_y = (SCREEN_HEIGHT - player_height) // 2
player_speed = 5

# Main game loop
running = True
while running:
    # 1. Event Handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # 2. Input Handling & Screen Boundaries
    keys = pygame.key.get_pressed()
    if keys[pygame.K_LEFT] and player_x > 0:
        player_x -= player_speed
    if keys[pygame.K_RIGHT] and player_x < SCREEN_WIDTH - player_width:
        player_x += player_speed
    if keys[pygame.K_UP] and player_y > 0:
        player_y -= player_speed
    if keys[pygame.K_DOWN] and player_y < SCREEN_HEIGHT - player_height:
        player_y += player_speed

    # 3. Graphics Rendering
    screen.fill((30, 30, 30))  # Dark gray background

    # Draw the player square
    pygame.draw.rect(
        screen,
        player_color,
        (player_x, player_y, player_width, player_height),
    )

    # Refresh screen display
    pygame.display.flip()

    # Maintain constant frame rate
    clock.tick(FPS)

# Clean exit
pygame.quit()
sys.exit()

"""

JSON_TO_BE_ESCAPED = """
{
  "status": "success",
  "code": 200,
  "message": "Data retrieved successfully",
  "data": {
    "items": [
      {
        "id": 1,
        "title": "Wireless Bluetooth Headphones",
        "description": "Premium quality wireless headphones with active noise cancellation and 30-hour battery life",
        "price": 199.99,
        "originalPrice": 249.99,
        "discount": 20,
        "category": "electronics",
        "brand": "AudioTech",
        "inStock": true,
        "quantity": 45,
        "tags": [
          "popular",
          "new",
          "featured",
          "wireless",
          "noise-cancelling"
        ],
        "ratings": {
          "average": 4.5,
          "count": 128,
          "distribution": {
            "5": 78,
            "4": 32,
            "3": 12,
            "2": 4,
            "1": 2
          }
        },
        "images": [
          "https://example.com/products/headphones-1.jpg",
          "https://example.com/products/headphones-2.jpg"
        ],
        "specifications": {
          "color": [
            "Black",
            "White",
            "Blue"
          ],
          "weight": "250g",
          "batteryLife": "30 hours",
          "connectivity": [
            "Bluetooth 5",
            "3.5mm jack"
          ]
        }
      },
      {
        "id": 2,
        "title": "Smart Fitness Watch",
        "description": "Advanced fitness tracking with heart rate monitor, GPS, and smartphone integration",
        "price": 299.99,
        "originalPrice": 349.99,
        "discount": 15,
        "category": "wearables",
        "brand": "FitTech",
        "inStock": false,
        "quantity": 0,
        "tags": [
          "bestseller",
          "fitness",
          "smartwatch",
          "gps"
        ],
        "ratings": {
          "average": 4.2,
          "count": 89,
          "distribution": {
            "5": 45,
            "4": 28,
            "3": 12,
            "2": 3,
            "1": 1
          }
        },
        "images": [
          "https://example.com/products/watch-1.jpg",
          "https://example.com/products/watch-2.jpg"
        ],
        "specifications": {
          "color": [
            "Black",
            "Silver",
            "Rose Gold"
          ],
          "weight": "45g",
          "batteryLife": "7 days",
          "waterResistance": "50m"
        }
      },
      {
        "id": 3,
        "title": "4K Webcam Pro",
        "description": "Professional 4K webcam with auto-focus, built-in microphone, and studio-quality video",
        "price": 149.99,
        "originalPrice": 199.99,
        "discount": 25,
        "category": "accessories",
        "brand": "StreamTech",
        "inStock": true,
        "quantity": 23,
        "tags": [
          "professional",
          "4k",
          "streaming",
          "webcam"
        ],
        "ratings": {
          "average": 4.8,
          "count": 256,
          "distribution": {
            "5": 205,
            "4": 38,
            "3": 9,
            "2": 3,
            "1": 1
          }
        },
        "images": [
          "https://example.com/products/webcam-1.jpg",
          "https://example.com/products/webcam-2.jpg"
        ],
        "specifications": {
          "resolution": "4K 30fps",
          "fieldOfView": "90 degrees",
          "microphone": "Built-in stereo",
          "compatibility": [
            "Windows",
            "Mac",
            "Linux"
          ]
        }
      }
    ],
    "pagination": {
      "currentPage": 1,
      "totalPages": 10,
      "totalItems": 30,
      "itemsPerPage": 3,
      "hasNext": true,
      "hasPrevious": false,
      "nextPage": 2
    },
    "filters": {
      "category": "all",
      "priceRange": {
        "min": 0,
        "max": 1000
      },
      "inStock": "all",
      "sortBy": "popularity",
      "sortOrder": "desc",
      "brands": [
        "AudioTech",
        "FitTech",
        "StreamTech"
      ]
    }
  },
  "meta": {
    "requestId": "req_abc123def456",
    "timestamp": "2024-01-20T15:30:00Z",
    "executionTime": 42,
    "version": "v2.1",
    "server": "api-prod-1",
    "cache": false
  }
}
"""

# ---------------------------------------------------------------------------
# Family generators
# ---------------------------------------------------------------------------


def plain_ascii(size: int) -> tuple[str, str]:
    """Return ``size`` ASCII 'a' characters."""
    return ("plain_ascii", "a" * size)


def whitespace(size: int) -> tuple[str, str]:
    """Return ``size`` whitespace characters including at least one newline."""
    if size < 3:
        # Ensure we have space for at least one newline
        text = " \n"[:size] if size > 0 else ""
    else:
        # Mix spaces, tabs, and newlines; ensure at least one newline
        cycle = itertools.cycle([" ", " ", "\t", " ", "\n", " "])
        text = "".join(itertools.islice(cycle, size))
    return ("whitespace", text)


def digits(size: int) -> tuple[str, str]:
    """Return ``size`` digit '9' characters."""
    return ("digits", "9" * size)


def base64_like(size: int) -> tuple[str, str]:
    """Return ``size`` base64-like characters, padded to a multiple of 4."""
    # Use 'A' which is valid base64 (decodes to 0x00 bytes)
    text = "A" * size
    # Pad to multiple of 4
    remainder = len(text) % 4
    if remainder:
        text += "=" * (4 - remainder)
    return ("base64_like", text)


def near_datetime(size: int) -> tuple[str, str]:
    """Return a string that starts with a date-like prefix but does not parse as datetime.

    Shape: date-like prefix + long digit run + invalid suffix.
    """
    prefix = "2026-06-13"
    if size <= len(prefix):
        # Just return the prefix truncated/padded
        text = prefix[:size] if size > 0 else ""
    else:
        # Add a long digit run and invalid suffix to prevent datetime parsing
        remaining = size - len(prefix)
        if remaining > 10:
            digit_run = "9" * (remaining - 3)
            suffix = "XYZ"  # Invalid suffix that prevents datetime parsing
            text = prefix + digit_run + suffix
        else:
            # For small sizes, just add digits and an invalid char
            text = prefix + "9" * (remaining - 1) + "X"
    return ("near_datetime", text)


def near_affix(size: int) -> tuple[str, str]:
    """Return a string with a currency/unit prefix plus a digit run exceeding the affix limit.

    The digit run is longer than ``NUMBER_AFFIX_MAX_LEN`` to stress the affix parser.
    """
    # Use a currency prefix that would be valid if the number were shorter
    prefix = "$"
    # Create a digit run that exceeds the affix limit
    digit_len = max(size - len(prefix), _AFFIX_LIMIT + 10)
    if size > len(prefix) + digit_len:
        # Pad with spaces if needed
        text = prefix + "9" * digit_len + " " * (size - len(prefix) - digit_len)
    else:
        text = prefix + "9" * digit_len
    # Truncate or pad to exact size
    if len(text) > size:
        text = text[:size]
    elif len(text) < size:
        text = text + " " * (size - len(text))
    return ("near_affix", text)


def near_color(size: int) -> tuple[str, str]:
    """Return a string that starts with '#' followed by hex characters.

    For stress sizes (size > 9), this exceeds valid color length.
    """
    if size < 1:
        return ("near_color", "")
    if size == 1:
        return ("near_color", "#")
    # '#' + 'f' * (size - 1)
    text = "#" + "f" * (size - 1)
    return ("near_color", text)


def unicode_bulk(size: int) -> tuple[str, str]:
    """Return ``size`` repetitions of a non-ASCII code point."""
    # Use 'é' (U+00E9) which has ord > 127
    return ("unicode_bulk", "é" * size)


def pathological_repetition(size: int) -> tuple[str, str]:
    """Return repeated regex-sensitive motifs such as 'ab' and '#fff'.

    The generated length is within one motif of ``size``.
    """
    if size < 1:
        return ("pathological_repetition", "")
    # Alternate between regex-sensitive motifs
    motifs = ["ab", "#fff", "9.9", "2026-"]
    motif_cycle = itertools.cycle(motifs)
    parts = []
    current_len = 0
    while current_len < size:
        motif = next(motif_cycle)
        if current_len + len(motif) <= size + len(motifs[-1]):  # Allow within one motif
            parts.append(motif)
            current_len += len(motif)
        else:
            break
    text = "".join(parts)
    # Truncate to exact size if we overshot
    if len(text) > size:
        text = text[:size]
    return ("pathological_repetition", text)


def mixed_interleaved(size: int) -> tuple[str, str]:
    """Return newline-separated chunks from at least three other families.

    The chunks are interleaved with newlines to stress multi-line parsing paths.
    """
    if size < 10:
        # For very small sizes, just combine a few short chunks
        chunks = [
            plain_ascii(max(1, size // 4))[1],
            digits(max(1, size // 4))[1],
            unicode_bulk(max(1, size // 4))[1],
        ]
        text = "\n".join(chunks)[:size]
        return ("mixed_interleaved", text)

    # Distribute size across at least 3 families plus newlines
    num_families = min(5, max(3, size // 100 + 3))  # 3-5 families based on size
    chunk_size = (size - num_families + 1) // num_families  # Account for newlines

    families_to_use = [
        plain_ascii,
        digits,
        unicode_bulk,
        base64_like,
        near_color,
    ][:num_families]

    chunks = []
    remaining = size
    for i, factory in enumerate(families_to_use):
        if i == len(families_to_use) - 1:
            # Last chunk gets remaining size minus newlines
            this_size = remaining - (len(families_to_use) - 1 - i)
        else:
            this_size = chunk_size
        this_size = max(1, min(this_size, remaining - (len(families_to_use) - 1 - i)))
        _, chunk_text = factory(this_size)
        chunks.append(chunk_text)
        remaining -= len(chunk_text) + 1  # +1 for newline

    text = "\n".join(chunks)
    # Ensure exact size
    if len(text) > size:
        text = text[:size]
    elif len(text) < size:
        text = text + " " * (size - len(text))
    return ("mixed_interleaved", text)


def trace_repetition(size: int) -> tuple[str, str]:
    """Return TRACE_EXAMPLE repeated to reach desired size.

    Extends to array of same format messages by repeating the trace example.
    This tests performance on realistic multi-line error trace content.
    """
    if size < 1:
        return ("trace_repetition", "")
    # Repeat the trace example to reach the desired size
    trace_len = len(TRACE_EXAMPLE)
    if trace_len == 0:
        return ("trace_repetition", "")
    repeats = (size // trace_len) + 1
    text = (TRACE_EXAMPLE * repeats)[:size]
    return ("trace_repetition", text)


def source_code_repetition(size: int) -> tuple[str, str]:
    """Return SOURCE_CODE_EXAMPLE repeated to reach desired size.

    Uses concatenation to produce long source code-like content.
    This tests performance on realistic multi-line code content.
    """
    if size < 1:
        return ("source_code_repetition", "")
    # Repeat the source code example to reach the desired size
    source_len = len(SOURCE_CODE_EXAMPLE)
    if source_len == 0:
        return ("source_code_repetition", "")
    repeats = (size // source_len) + 1
    text = (SOURCE_CODE_EXAMPLE * repeats)[:size]
    return ("source_code_repetition", text)


def escape_heavy(size: int) -> tuple[str, str]:
    """Return JSON_TO_BE_ESCAPED with heavy escaping (double/triple backslashes).

    Builds escape-heavy strings by applying multiple levels of escaping to the
    JSON content. This tests performance on strings with many backslash sequences.
    """
    if size < 1:
        return ("escape_heavy", "")
    # Start with the JSON content and apply escaping
    base = JSON_TO_BE_ESCAPED.strip()
    if not base:
        return ("escape_heavy", "")

    # Apply double escaping: replace backslashes and quotes with escaped versions
    # This creates strings like \\" and \\\\ which stress escape handling
    escaped_once = base.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    # Apply triple escaping for even more backslash density
    escaped_twice = escaped_once.replace("\\", "\\\\").replace('"', '\\"')

    # Concatenate to reach desired size
    text_len = len(escaped_twice)
    if text_len == 0:
        return ("escape_heavy", "")
    repeats = (size // text_len) + 1
    text = (escaped_twice * repeats)[:size]
    return ("escape_heavy", text)


# ---------------------------------------------------------------------------
# Registry of all families
# ---------------------------------------------------------------------------

FAMILY_REGISTRY: dict[str, Callable[[int], tuple[str, str]]] = {
    "plain_ascii": plain_ascii,
    "whitespace": whitespace,
    "digits": digits,
    "base64_like": base64_like,
    "near_datetime": near_datetime,
    "near_affix": near_affix,
    "near_color": near_color,
    "unicode_bulk": unicode_bulk,
    "pathological_repetition": pathological_repetition,
    "mixed_interleaved": mixed_interleaved,
    "trace_repetition": trace_repetition,
    "source_code_repetition": source_code_repetition,
    "escape_heavy": escape_heavy,
}

# Default sizes for normal local runs
DEFAULT_SIZES: tuple[int, ...] = (1024, 4096, 16384, 65536)

# Extended sizes for milestone reports
EXTENDED_SIZES: tuple[int, ...] = (262144, 1048576, 10485760)
