#!/usr/bin/env python3
import argparse
import os
import sys
from typing import List

from skellybobs_lib import generate_from_template, parse_params


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate initial hexagonal architecture code from a YAML template with ${...} placeholders."
        )
    )
    parser.add_argument(
        "-t",
        "--template",
        default=os.path.join(os.getcwd(), "template.yaml"),
        help="Path to template.yaml (default: ./template.yaml)",
    )
    parser.add_argument(
        "-o",
        "--out",
        default=os.path.join(os.getcwd(), "habuild"),
        help="Output directory (default: ./habuild)",
    )
    parser.add_argument(
        "-p",
        "--param",
        action="append",
        default=[],
        help=(
            "Placeholder assignment. Repeatable. Accepts key=value, key-value, or key:value. "
            "Example: -p service=happiness -p group=peanuts -p adapter=http -p adapter=kafka"
        ),
    )

    args = parser.parse_args(argv)

    try:
        params = parse_params(args.param)
    except Exception as e:
        print(f"Error parsing parameters: {e}", file=sys.stderr)
        return 2

    try:
        generate_from_template(args.template, args.out, params)
    except Exception as e:
        print(f"Generation failed: {e}", file=sys.stderr)
        return 1

    print(f"Generation completed. Output at: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
