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
