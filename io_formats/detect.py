from pathlib import Path

SAVE_FORMAT_JSON = "json"
SAVE_FORMAT_YAML = "yaml"
SAVE_FORMAT_YAML_MULTI = "yaml-multi"
SAVE_FORMAT_JSONL = "jsonl"


def detect_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".json":
        return SAVE_FORMAT_JSON
    if ext in (".jsonl", ".ndjson"):
        return SAVE_FORMAT_JSONL
    if ext in (".yaml", ".yml"):
        return SAVE_FORMAT_YAML
    raise ValueError(f"Unknown file format: {ext}")
