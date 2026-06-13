APPLICATION_ID = "org.jeditor.204b2a8a-e956-4c62-911d-cfb29a4fe257"
MODAL_WINDOW_SIZE = (600, 440)
WINDOW_DEFAULT_SIZE = (800, 600)

# Warn before importing or manually editing large binary payloads.
BINARY_ATTACH_WARNING_LIMIT_BYTES = 100 * 1024
BINARY_EDIT_WARNING_LIMIT_BYTES = 100 * 1024
STRING_EDIT_WARNING_LIMIT_CHARS = 10_000
MULTILINE_EDIT_WARNING_LIMIT_CHARS = 100_000

# Secret field detection and masking defaults.
SECRET_WORD_PREFIXES: tuple[str, ...] = (
    "passw",
    "auth",
    "token",
    "key",
    "secret",
    "private",
    "cert",
)
SECRET_MASK_GLYPHS = 8
SECRET_MASK_CHAR = "•"
SECRET_HIDE_ON_FOCUS_OUT = True
SECRET_REVEAL_INACTIVITY_MS = 0

# Number-affix parsing/editor limits.
NUMBER_AFFIX_MAX_LEN = 20
NUMBER_AFFIX_MRU_SIZE = 50

# gmpy2/mpq safety limits. Very large scientific exponents can trigger
# low-level GMP aborts (not regular Python exceptions) while building mpz
# intermediates for powers-of-ten.
#
# Limits are enforced through ``decimal.Context`` traps in
# ``core.safe_mpq`` (Overflow / Underflow / Inexact / InvalidOperation),
# not regex filtering:
# - ``MPQ_SAFE_MAX_ABS_EXPONENT`` bounds context Emax/Emin.
# - ``MPQ_SAFE_MAX_SIG_DIGITS`` bounds significant digits via precision.
MPQ_SAFE_MAX_ABS_EXPONENT = 10_000
MPQ_SAFE_MAX_SIG_DIGITS = 4_300

# ---------------------------------------------------------------------------
# Inference safety limits (Plan 1 — length limits for expensive inference)
# ---------------------------------------------------------------------------
# These constants gate expensive inference work (regex, datetime parsing,
# color checks) during automatic type classification.
# They are NOT user-exposed settings and must not use QSettings.
#
# Values are justified by reports/parsing-vulnerability-2026-06-13.md which
# measured 832 rows across 16 registry entries and 13 adversarial families
# at sizes 1024, 4096, 16384, and 65536.
#
# Design decisions:
# - No INFERENCE_MAX_TOTAL_CHARS: individual gates (datetime, affix, color)
#   effectively skip all unnecessary checks; a top-level fast path is redundant.
# - No INFERENCE_MAX_BASE64_PROBE_CHARS: base64 uses content-based syntax
#   validation (len mod 4 + alphabet regex) instead of a length cap.
# - No EDITABLE_DECODE_LIMIT_BYTES: if base64 syntax is valid, decode is allowed.

# parse_datetime_text() regex and datetime conversion.
# Report: DATETIME_RE.fullmatch median is 0.00ms even at 65536 across all
# families; 40 is enough for any practically meaningful datetime string.
INFERENCE_MAX_DATETIME_CHARS: int = 40

# parse_number_affix() regex checks.
# Report: parse_number_affix is superlinear on digits, plain_ascii,
# pathological_repetition at 4096+ (ratio up to 4.89). 100 is well below
# the pre-existing 4300-digit integer limit, so the gate fires before the
# error path.
INFERENCE_MAX_AFFIX_CHARS: int = 100

# looks_like_color_rgb() and looks_like_color_rgba().
# Maximum length of #RGB, #RRGGBB, #RGBA, and #RRGGBBAA color strings.
INFERENCE_MAX_COLOR_CHARS: int = 10

# format_with_type() display preview decode cap.
# Preview needs only enough bytes to render the existing prefix text.
FORMAT_PREVIEW_DECODE_LIMIT_BYTES: int = 100

# ---------------------------------------------------------------------------
# Loading progress widget (Plan 2 — delayed progress bar for big files)
# ---------------------------------------------------------------------------
# The progress widget only appears if a load operation takes longer than this
# delay. Fast loads complete before the widget shows, avoiding visual noise.
LOADING_PROGRESS_DELAY_MS: int = 5000
