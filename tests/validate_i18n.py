"""
i18n Validation Script

Validates consistency between translation files (en.json, ko.json).
Checks for:
- Missing keys
- Extra keys
- Format string consistency ({0}, {1}, etc.)
- Unused keys (optional)
"""

import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Set


class I18nValidator:
    """Validator for i18n translation files."""

    def __init__(self, i18n_dir: Path):
        self.i18n_dir = i18n_dir
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load_json(self, filename: str) -> Dict[str, str]:
        """Load JSON translation file."""
        filepath = self.i18n_dir / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.errors.append(f"ERROR: File not found: {filename}")
            return {}
        except json.JSONDecodeError as e:
            self.errors.append(f"ERROR: Invalid JSON in {filename}: {e}")
            return {}

    def extract_format_placeholders(self, text: str) -> Set[str]:
        """Extract format placeholders like {0}, {1} from text."""
        return set(re.findall(r"\{(\d+)\}", text))

    def validate_keys(
        self,
        base: Dict[str, str],
        target: Dict[str, str],
        base_name: str,
        target_name: str,
    ) -> None:
        """Validate that target has all keys from base."""
        base_keys = set(base.keys())
        target_keys = set(target.keys())

        missing = base_keys - target_keys
        if missing:
            self.errors.append(
                f"ERROR: {target_name} missing keys from {base_name}: {sorted(missing)}"
            )

        extra = target_keys - base_keys
        if extra:
            self.warnings.append(
                f"WARNING: {target_name} has extra keys not in {base_name}: {sorted(extra)}"
            )

    def validate_format_strings(
        self,
        base: Dict[str, str],
        target: Dict[str, str],
        base_name: str,
        target_name: str,
    ) -> None:
        """Validate format string consistency."""
        common_keys = set(base.keys()) & set(target.keys())

        for key in common_keys:
            base_placeholders = self.extract_format_placeholders(base[key])
            target_placeholders = self.extract_format_placeholders(target[key])

            if base_placeholders != target_placeholders:
                self.errors.append(
                    f"ERROR: Format mismatch in '{key}': "
                    f"{base_name}={base_placeholders}, {target_name}={target_placeholders}"
                )

    def validate(self) -> bool:
        """Run all validations."""
        print("Validating i18n files...\n")

        en = self.load_json("en.json")
        ko = self.load_json("ko.json")

        if not en or not ko:
            return False

        print(f"Loaded en.json: {len(en)} keys")
        print(f"Loaded ko.json: {len(ko)} keys\n")

        self.validate_keys(en, ko, "en.json", "ko.json")
        self.validate_keys(ko, en, "ko.json", "en.json")
        self.validate_format_strings(en, ko, "en.json", "ko.json")
        self.print_results()

        return len(self.errors) == 0

    def print_results(self) -> None:
        """Print validation results."""
        print("=" * 60)

        if self.errors:
            print("\nERRORS:\n")
            for error in self.errors:
                print(f"  {error}")

        if self.warnings:
            print("\nWARNINGS:\n")
            for warning in self.warnings:
                print(f"  {warning}")

        if not self.errors and not self.warnings:
            print("\nAll i18n keys are consistent.")
            print("All format strings match.")

        print("\n" + "=" * 60)

        error_count = len(self.errors)
        warning_count = len(self.warnings)

        if error_count > 0:
            print(f"\nValidation FAILED: {error_count} error(s), {warning_count} warning(s)")
        elif warning_count > 0:
            print(f"\nValidation PASSED with warnings: {warning_count} warning(s)")
        else:
            print("\nValidation PASSED: No issues found")


def main() -> None:
    """Main entry point."""
    script_dir = Path(__file__).parent
    i18n_dir = script_dir.parent / "app" / "i18n"

    if not i18n_dir.exists():
        print(f"ERROR: i18n directory not found: {i18n_dir}")
        sys.exit(1)

    validator = I18nValidator(i18n_dir)
    success = validator.validate()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
