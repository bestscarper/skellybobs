import os
import re
import itertools
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "PyYAML is required to run this generator. Please install it: pip install pyyaml"
    ) from e

PLACEHOLDER_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_\-\.]+)\}")
COND_PATTERN = re.compile(r"^\s*(\$\{[^}]+\})\s*(==|!=)\s*([\'\"])\s*(.*?)\s*\3\s*$")


def parse_params(param_args: Optional[Sequence[str]]) -> Dict[str, List[str]]:
    """
    Parse a sequence of -p arguments into a dict mapping placeholder -> list of values.

    Accepted forms per item:
    - key=value
    - key:value
    - key value  (if provided as separate tokens by caller)
    The CLI wrapper will pass each -p occurrence as a single string, but we keep this flexible.

    Example inputs:
    ["service=happiness", "group=peanuts", "adapter=http", "adapter=kafka"]
    ["service:happiness", "group=peanuts"]
    """
    result: Dict[str, List[str]] = {}
    if not param_args:
        return result

    for raw in param_args:
        if raw is None:
            continue
        s = str(raw).strip()
        if not s:
            continue
        key: Optional[str] = None
        val: Optional[str] = None

        # Allow quotes around the entire token
        if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
            s = s[1:-1]

        # Try key=value first
        for sep in ("=", ":"):
            if sep in s:
                parts = s.split(sep, 1)
                if len(parts) == 2 and parts[0] and parts[1]:
                    key, val = parts[0].strip(), parts[1].strip()
                    break
        # If not matched, treat whole as key with empty value? Better: if it contains '-' later
        if key is None or val is None:
            # As a last attempt, split on whitespace
            tokens = s.split()
            if len(tokens) == 2:
                key, val = tokens[0].strip(), tokens[1].strip()
        if key is None or val is None:
            # If only a single token, we cannot infer value; ignore
            raise ValueError(f"Invalid -p parameter format: {raw!r}. Expect key=value or key-value.")

        result.setdefault(key, []).append(val)

    return result


def _load_yaml(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _render_string(template: str, context: Mapping[str, Any]) -> str:
    def classify_key(k: str) -> Tuple[str, str]:
        # Returns (canonical_key, style): style in {"lower", "title", "upper"}
        canonical = k.lower()
        if k.upper() == k and any(ch.isalpha() for ch in k):
            return canonical, "upper"
        # Initial capital only if first alpha is uppercase and remaining cased letters are lowercase
        # e.g., "Service", "Service-name" -> title
        first_alpha_idx = next((i for i, ch in enumerate(k) if ch.isalpha()), None)
        if first_alpha_idx is not None:
            first_alpha = k[first_alpha_idx]
            rest = ''.join(ch for ch in k[first_alpha_idx + 1:] if ch.isalpha())
            if first_alpha.isupper() and (not rest or rest.lower() == rest):
                return canonical, "title"
        return canonical, "lower"

    def apply_style(val: str, style: str) -> str:
        if style == "upper":
            return val.upper()
        if style == "title":
            # Uppercase only the first character of the value (if any), leave the rest unchanged
            return (val[:1].upper() + val[1:]) if val else val
        return val

    def repl(match: re.Match[str]) -> str:
        raw_key = match.group(1)
        canonical_key, style = classify_key(raw_key)
        # Lookup by exact key first, then by canonical lowercase, then by case-insensitive scan
        val = context.get(raw_key)
        if val is None:
            val = context.get(canonical_key)
        if val is None:
            # Try case-insensitive lookup as a last resort
            for k in context.keys():
                if str(k).lower() == canonical_key:
                    val = context[k]
                    break
        # If still None, leave placeholder as-is
        if val is None:
            return match.group(0)
        # If list, take the first element for rendering
        if isinstance(val, list):
            val = val[0] if val else ""
        sval = str(val)
        return apply_style(sval, style)

    return PLACEHOLDER_PATTERN.sub(repl, template)


def _find_placeholders_in_string(s: str) -> List[str]:
    # Return canonical (lowercased) placeholder keys for expansion logic
    return list({m.group(1).lower() for m in PLACEHOLDER_PATTERN.finditer(s or "")})


def _find_placeholders_in_block(block: Any) -> List[str]:
    found: set[str] = set()
    if not isinstance(block, dict):
        return []
    name = block.get("name")
    if isinstance(name, str):
        found.update(_find_placeholders_in_string(name))
    # Include placeholders referenced in a conditional expression
    cond = block.get("cond")
    if isinstance(cond, str):
        found.update(_find_placeholders_in_string(cond))
    if block.get("type") == "file":
        content = block.get("content")
        if isinstance(content, str):
            found.update(_find_placeholders_in_string(content))
    # Recurse into content for directories
    if block.get("type") == "directory":
        content = block.get("content")
        if isinstance(content, list):
            for child in content:
                found.update(_find_placeholders_in_block(child))
    return list(found)


def _expand_contexts_for_block(block: Mapping[str, Any], base_context: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """
    Given a block and base_context, compute a list of concrete contexts by expanding any placeholders
    that have multiple values AND are referenced somewhere within this block's subtree.
    """
    used_keys = _find_placeholders_in_block(block)
    multi_items: List[Tuple[str, List[str]]] = []
    fixed_items: Dict[str, Any] = {}

    for k, v in base_context.items():
        if k in used_keys and isinstance(v, list) and len(v) > 1:
            multi_items.append((k, v))
        else:
            fixed_items[k] = v[0] if isinstance(v, list) and len(v) == 1 else v

    if not multi_items:
        return [dict(fixed_items)]

    keys = [k for k, _ in multi_items]
    values_lists = [vals for _, vals in multi_items]
    contexts: List[Dict[str, Any]] = []
    for combo in itertools.product(*values_lists):
        ctx = dict(fixed_items)
        for k, val in zip(keys, combo):
            ctx[k] = val
        contexts.append(ctx)
    return contexts


def _create_path(base_dir: str, name: str, is_dir: bool) -> str:
    # name may contain subdirectories like "a/b/c"; also allow relative subpaths in file names
    path = os.path.join(base_dir, name)
    dir_path = path if is_dir else os.path.dirname(path)
    if dir_path:
        _ensure_dir(dir_path)
    if is_dir:
        _ensure_dir(path)
    return path


def _is_condition_met(block: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    cond = block.get("cond")
    if cond is None:
        return True
    if isinstance(cond, bool):
        return bool(cond)
    if not isinstance(cond, str):
        return True
    m = COND_PATTERN.match(cond)
    if not m:
        # If pattern unrecognized, default to False to be safe
        return False
    left_token, op, _, right_literal = m.groups()
    # Render the left token (e.g., a single placeholder like ${adapter}) against the context
    left_value = _render_string(left_token, context)
    # Compare as strings
    if op == "==":
        return left_value == right_literal
    else:
        return left_value != right_literal


def _process_file(base_dir: str, block: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    # Evaluate condition for this file
    if not _is_condition_met(block, context):
        return
    raw_name = block.get("name", "")
    name = _render_string(str(raw_name), context)
    path = _create_path(base_dir, name, is_dir=False)

    content = block.get("content", None)
    if content is None:
        data = ""
    elif isinstance(content, str):
        data = _render_string(content, context)
    else:
        # Non-string content treated as empty
        data = ""

    with open(path, "w", encoding="utf-8") as f:
        f.write(data)


def _process_directory(base_dir: str, block: Mapping[str, Any], base_context: Mapping[str, Any]) -> None:
    # Expand contexts for this directory, duplicating if multi-valued placeholders are used here
    for ctx in _expand_contexts_for_block(block, base_context):
        # If this directory has a condition and it's not met for this context, skip entirely
        if not _is_condition_met(block, ctx):
            continue
        raw_name = block.get("name", "")
        name = _render_string(str(raw_name), ctx)
        dir_path = _create_path(base_dir, name, is_dir=True)
        content = block.get("content", None)
        if isinstance(content, list):
            for child in content:
                if not isinstance(child, dict):
                    continue
                # Skip child if its condition is not met in this context
                if not _is_condition_met(child, ctx):
                    continue
                t = child.get("type")
                if t == "directory":
                    _process_directory(dir_path, child, ctx)
                elif t == "file":
                    _process_file(dir_path, child, ctx)
                else:
                    # Unknown type: treat as empty file if name exists
                    if "name" in child:
                        _process_file(dir_path, child, ctx)
        else:
            # No content => empty directory already created
            pass


def generate_from_template(template_path: str, output_dir: str = "habuild", params: Optional[Mapping[str, Any]] = None) -> None:
    """
    Generate the filesystem under output_dir based on the YAML template at template_path.

    - template top-level is expected to have a single key 'root' whose value is a list of blocks.
    - params is a mapping of placeholder -> value or list of values.
    """
    tmpl = _load_yaml(template_path)
    root = tmpl.get("root") if isinstance(tmpl, dict) else None
    if not isinstance(root, list):
        raise ValueError("template.yaml must contain a top-level 'root' list")

    # Normalize params to dict[str, list|str]
    context: Dict[str, Any] = {}
    if params:
        for k, v in params.items():
            context[k] = v

    _ensure_dir(output_dir)

    for block in root:
        if not isinstance(block, dict):
            continue
        t = block.get("type")
        if t == "directory":
            _process_directory(output_dir, block, context)
        elif t == "file":
            _process_file(output_dir, block, context)
        else:
            # Unknown type: skip
            continue


# ---- Scanning existing directories into a template.yaml ----

def _scan_directory_to_blocks(directory: str) -> List[Dict[str, Any]]:
    """Recursively scan a directory into a list of template blocks.

    Each entry becomes a dict with keys: type (directory|file), name, and optional content.
    For directories, content is a list of child blocks (omitted if empty).
    For files, content is the UTF-8 text (omitted if file is empty or undecodable as UTF-8).
    """
    try:
        entries = sorted(os.listdir(directory))
    except FileNotFoundError:
        return []

    blocks: List[Dict[str, Any]] = []
    for entry in entries:
        if entry in (".", ".."):
            continue
        full_path = os.path.join(directory, entry)
        if os.path.isdir(full_path):
            # Compact chains of single-child empty directories into a single path segment
            compact_name = entry
            compact_path = full_path
            while True:
                try:
                    child_entries = sorted(os.listdir(compact_path))
                except FileNotFoundError:
                    break
                # Exclude current/parent pointers
                child_entries = [e for e in child_entries if e not in (".", "..")]
                # Classify children
                dir_children: List[str] = []
                file_children: List[str] = []
                other_children: List[str] = []
                for ce in child_entries:
                    ce_path = os.path.join(compact_path, ce)
                    if os.path.isdir(ce_path):
                        dir_children.append(ce)
                    elif os.path.isfile(ce_path):
                        file_children.append(ce)
                    else:
                        other_children.append(ce)
                # We can compact only when there is exactly one directory child and no files/others
                if len(dir_children) == 1 and len(file_children) == 0 and len(other_children) == 0:
                    compact_name = os.path.join(compact_name, dir_children[0])
                    compact_path = os.path.join(compact_path, dir_children[0])
                    continue
                break
            # Now scan the deepest compacted directory for its children
            child_blocks = _scan_directory_to_blocks(compact_path)
            block: Dict[str, Any] = {"type": "directory", "name": compact_name}
            if child_blocks:
                block["content"] = child_blocks
            blocks.append(block)
        elif os.path.isfile(full_path):
            block_f: Dict[str, Any] = {"type": "file", "name": entry}
            try:
                size = os.path.getsize(full_path)
            except OSError:
                size = None
            data_added = False
            if size and size > 0:
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        text = f.read()
                    # Only add content if text is non-empty
                    if text:
                        block_f["content"] = text
                        data_added = True
                except UnicodeDecodeError:
                    # Binary or non-UTF8: omit content
                    data_added = False
                except Exception:
                    data_added = False
            # If size is 0 or undecodable, we omit content to denote empty file
            blocks.append(block_f)
        else:
            # Skip other types (symlinks, devices) for simplicity/minimalism
            continue
    return blocks


def generate_template_from_directory(input_dir: str, output_template_path: str) -> None:
    """Generate a template YAML by scanning an existing directory structure.

    The resulting YAML will have a top-level 'root' key containing the list of blocks.
    """
    if not os.path.isdir(input_dir):
        raise ValueError(f"Input directory does not exist or is not a directory: {input_dir}")
    blocks = _scan_directory_to_blocks(input_dir)
    tmpl = {"root": blocks}

    # Dump YAML ensuring multiline strings (like file contents) use literal block style (|)
    class _LiteralSafeDumper(yaml.SafeDumper):
        pass

    def _str_presenter(dumper: yaml.SafeDumper, data: str):  # type: ignore[name-defined]
        # Use literal block style for any string containing a newline
        style = '|' if ('\n' in data) else None
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style=style)

    _LiteralSafeDumper.add_representer(str, _str_presenter)  # type: ignore[arg-type]

    with open(output_template_path, "w", encoding="utf-8") as f:
        yaml.dump(tmpl, f, Dumper=_LiteralSafeDumper, sort_keys=False, allow_unicode=True)
