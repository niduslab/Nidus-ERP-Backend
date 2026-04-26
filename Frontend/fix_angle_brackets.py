#!/usr/bin/env python3
"""
fix_angle_brackets.py

Repairs shadcn/ui primitive files that lost their `<` character after
`React.forwardRef` (and similar generic-call sites) during a copy-paste
into VS Code.

THE BUG:
    When TypeScript code containing `React.forwardRef<` at the very end
    of a line is copy-pasted from a markdown rendering, the trailing `<`
    can be silently dropped (treated as a malformed HTML tag opener).
    Result: the file ends up with

        const Foo = React.forwardRef
          HTMLDivElement,
          React.HTMLAttributes<HTMLDivElement>
        >(({ className, ...props }, ref) => { ... })

    which is invalid TypeScript - the `>` on the third line has no
    matching `<`. Vite's oxc parser correctly reports it as an
    "Unexpected token".

THE FIX:
    Insert the missing `<` after `React.forwardRef` whenever it's
    immediately followed by a newline AND the next non-blank line
    looks like generic type arguments (an identifier, not a `(`).

We also patch two other known sites where the same drop can happen:
    - `export type FormFieldContextValue<` in form-field.ts
    - `export function FormField<` in form-field.ts

These are inside .ts files where oxc would not have flagged them, but
the drop pattern is the same and the resulting code is also invalid.

Idempotent: running twice has no additional effect.

Usage:
    cd <frontend folder>
    python fix_angle_brackets.py
"""

import re
import sys
from pathlib import Path

# ── Files to patch ──
TARGETS = [
    "src/components/ui/card.tsx",
    "src/components/ui/label.tsx",
    "src/components/ui/form.tsx",
    "src/components/ui/form-field.ts",
]

# ── Patterns we repair ──
#
# Each pattern matches the BROKEN form (missing `<`) and the replacement
# inserts the `<` back. We detect "broken" by looking for the keyword
# followed immediately by a line break and then an indented identifier
# (which is what generic args look like).

PATTERNS = [
    # React.forwardRef\n  → React.forwardRef<\n
    (
        re.compile(r"(React\.forwardRef)(\r?\n)(\s+)([A-Za-z_])"),
        r"\1<\2\3\4",
    ),
    # export type FormFieldContextValue\n  → export type FormFieldContextValue<\n
    (
        re.compile(r"(export type FormFieldContextValue)(\r?\n)(\s+)([A-Za-z_])"),
        r"\1<\2\3\4",
    ),
    # export function FormField\n  → export function FormField<\n
    (
        re.compile(r"(export function FormField)(\r?\n)(\s+)([A-Za-z_])"),
        r"\1<\2\3\4",
    ),
]


def patch_file(path: Path) -> int:
    """
    Patch a single file. Returns the number of replacements made.
    Preserves original line endings (CRLF on Windows, LF on Unix).
    """
    if not path.exists():
        print(f"  SKIP   {path}  (file not found)")
        return 0

    original_bytes = path.read_bytes()
    text = original_bytes.decode("utf-8")

    total = 0
    for pattern, replacement in PATTERNS:
        text, n = pattern.subn(replacement, text)
        total += n

    if total == 0:
        print(f"  CLEAN  {path}  (no repairs needed)")
        return 0

    path.write_bytes(text.encode("utf-8"))
    print(f"  FIXED  {path}  ({total} replacement{'s' if total != 1 else ''})")
    return total


def main():
    cwd = Path.cwd()
    print(f"Running from: {cwd}\n")

    if not (cwd / "src" / "components" / "ui").exists():
        print(
            "ERROR: src/components/ui/ not found.\n"
            "Run this script from the frontend/ folder root.\n"
            "Example:  cd C:\\NidusERP_s\\Nidus-ERP-Backend\\Frontend"
        )
        sys.exit(1)

    total = 0
    for relpath in TARGETS:
        total += patch_file(cwd / relpath)

    print()
    print(f"Done. Total replacements: {total}")
    if total == 0:
        print()
        print("No repairs were needed - all files appear to have their `<` characters")
        print("intact. If `npm run dev` still errors, the issue is something else;")
        print("paste the new error message for diagnosis.")
    else:
        print()
        print("Now restart your dev server:")
        print("  (Press Ctrl+C in the running vite terminal, then:)")
        print("  npm run dev")


if __name__ == "__main__":
    main()