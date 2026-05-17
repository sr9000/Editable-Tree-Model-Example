# Editable Tree Model Example
source: https://doc.qt.io/qt-6/qtwidgets-itemviews-editabletreemodel-example.html

- Pyside6

## Validation

The editor supports JSON Schema validation for open documents.

### Schema auto-detection

When a file is opened the editor looks for a schema in this order:

1. **Inline `$schema` key** — if the document contains a `"$schema"` string
   pointing to a local path (relative or absolute), that file is loaded as the
   schema.  Remote `http(s)://` URIs are ignored.
2. **Sibling file** — if a file named `<doc>.schema.json` exists next to the
   opened document, it is used automatically.
3. **Persisted manual binding** — if the user previously attached a schema
   manually (see below), that binding is restored automatically on reopen.

### Manual schema attachment

Use the **Schema ▸** → **Attach schema…** toolbar button in the Validation
dock to browse for any `.json`, `.yaml`, or `.yml` schema file, or paste an
`http(s)://` schema URL.  The binding is persisted per file path so the schema
is restored the next time the document is opened.

### Schema registry

Attached schemas are owned by a shared schema registry instead of being copied
into each document tab.  A schema source is identified as either a resolved
local file path or a normalised URL; tabs bound to the same source share one
loaded `SchemaEntry` and revalidate from that shared schema.

- **Local files** are watched with `QFileSystemWatcher`.  Editing a schema file
  externally reloads it in place and all bound tabs revalidate automatically.
- **URL schemas** use a normalised URL identity and are treated as read-only by
  the UI.  Reload fetches the URL again; conditional HTTP caching (`ETag` /
  `If-Modified-Since`) is not implemented yet.
- **Recent schemas** are persisted globally (cap 12) and are available from the
  attach dialog and the Validation dock's **Schema ▸ Recent** submenu.

Additional schema actions:

| Action | Description |
|---|---|
| **Reload schema** | Re-reads a local schema from disk, or re-fetches a URL schema, without changing the binding. |
| **Open schema file / URL** | Opens the attached local schema as a tab, or opens URL-backed schemas in the browser. |
| **Clear schema** | Detaches the schema and removes the persisted binding. |

### YAML multi-document support

YAML files containing multiple documents (separated by `---`) are loaded as
YAML multi-doc format.  Each document is validated independently against the
schema.  Issues are prefixed with `[doc N]` in the Validation panel so you can
identify which document triggered the error.  Clicking an issue navigates to
the correct row in the root array.

### Sanitization

The tree stores exact-rational values as `gmpy2.mpq` objects.  Before
validation, `validation._sanitize.to_jsonschema_input` converts `mpq` → `float`,
`Decimal` → `float`, `datetime`/`date`/`time` → ISO string, and
`bytes`/`bytearray` → Base64-encoded string.  This conversion is
**validation-only** and never modifies the data stored in the tree.

### Requirements

Validation requires the optional `jsonschema-rs` Python package:

```bash
pip install jsonschema-rs
```

If `jsonschema-rs` is not installed, the Validation panel is present but all
validation runs produce zero issues and the schema-picker actions are
non-functional.
