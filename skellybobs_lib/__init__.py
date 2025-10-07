"""
ha_generator: A small library to generate a filesystem for hexagonal-architecture Java apps
from a YAML template with simple Mustache-style placeholders like ${name}.

Public API:
- parse_params(param_args: list[str]) -> dict[str, list[str]]
- generate_from_template(template_path: str, output_dir: str = "habuild", params: dict[str, list[str] | str] = None) -> None
- generate_template_from_directory(input_dir: str, output_template_path: str) -> None

The generator supports:
- Directories and files with names and contents containing placeholders.
- Recursive YAML structure with fields: type (file|directory), name (string), content (mixed).
- Path-like directory names (e.g., "api/src/main/java") — all intermediate directories are created.
- If a placeholder has multiple values in the context of a directory subtree, the directory is
  processed repeatedly for each combination of those placeholder values used within that subtree.
- Scanning an existing directory to produce a template.yaml that can be used later for generation.
"""
from .generator import generate_from_template, parse_params, generate_template_from_directory

__all__ = [
    "generate_from_template",
    "parse_params",
    "generate_template_from_directory",
]
