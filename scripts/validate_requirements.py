#!/usr/bin/env python3
"""
Validate requirements.txt before installation.

This script checks that all packages in requirements.txt exist on PyPI
with the specified versions. This prevents cryptic pip installation errors.

Usage:
    python validate_requirements.py
    python validate_requirements.py requirements.txt
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def parse_requirements(file_path: str) -> List[Tuple[str, str]]:
    """Parse requirements.txt file and extract package/version pairs.

    Args:
        file_path: Path to requirements.txt

    Returns:
        List of (package_name, version_spec) tuples
    """
    packages = []

    with open(file_path) as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Handle -r includes
            if line.startswith('-r'):
                # Parse the included file
                included_file = line[2:].strip()
                included_path = Path(file_path).parent / included_file
                if included_path.exists():
                    packages.extend(parse_requirements(str(included_path)))
                continue

            # Parse package requirement (simplified, handles most cases)
            # Format: package==version, package>=version, package
            # Remove environment markers
            line = re.split(r';|==|>=|<=|>|~|=', line)[0].strip()

            # Extract package name (before any version spec)
            match = re.match(r'^([a-zA-Z0-9._-]+)', line)
            if match:
                package = match.group(1)
                # Extract version specifier if present
                version_match = re.search(r'==([0-9.]+)', line)
                version = version_match.group(1) if version_match else ""
                packages.append((package, version))

    return packages


def check_package_exists(package: str, version: str = "") -> Tuple[bool, str, str]:
    """Check if a package exists on PyPI with the specified version.

    Args:
        package: Package name
        version: Version to check (empty = any version)

    Returns:
        Tuple of (exists, latest_version, error_message)
    """
    try:
        # Use pip index to check package availability
        if version:
            # Check specific version
            result = subprocess.run(
                ['pip', 'index', 'versions', package, '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=30
            )
        else:
            # Just check if package exists (get latest)
            result = subprocess.run(
                ['pip', 'index', 'versions', package, '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=30
            )

        if result.returncode != 0:
            return False, "", f"Package '{package}' not found on PyPI"

        import json
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return False, "", f"Could not parse response for '{package}'"

        if not data:
            return False, "", f"No versions found for '{package}'"

        # Extract available versions
        versions = data.get(package, [])
        if not versions:
            return False, "", f"Package '{package}' has no available versions"

        latest = versions[0]

        if version:
            # Check if specific version exists
            if version in versions:
                return True, latest, ""
            else:
                # Find closest available version
                available = ", ".join(versions[:5])  # Show first 5
                if len(versions) > 5:
                    available += ", ..."
                return False, latest, f"Version {version} not found. Available: {available}"
        else:
            return True, latest, ""

    except subprocess.TimeoutExpired:
        return False, "", f"Timeout checking '{package}'"
    except Exception as e:
        return False, "", f"Error checking '{package}': {str(e)}"


def validate_requirements(file_path: str = "requirements.txt") -> Tuple[bool, List[str]]:
    """Validate all packages in requirements.txt.

    Args:
        file_path: Path to requirements.txt

    returns:
        Tuple of (all_valid, error_messages)
    """
    if not Path(file_path).exists():
        return False, [f"File not found: {file_path}"]

    packages = parse_requirements(file_path)
    if not packages:
        return False, ["No packages found in file"]

    errors = []
    all_valid = True

    print(f"Validating {len(packages)} package(s) from {file_path}...")
    print()

    for package, version in packages:
        exists, latest, error = check_package_exists(package, version)

        if exists:
            if version:
                print(f"  ✓ {package}=={version}")
            else:
                print(f"  ✓ {package} (latest: {latest})")
        else:
            print(f"  ✗ {package}=={version or 'any'} - {error}")
            errors.append(f"{package}=={version or 'any'}: {error}")

            if latest:
                # Suggest the latest version
                errors[-1] += f" (try: {package}=={latest})"

            all_valid = False

    return all_valid, errors


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Validate requirements.txt packages before installation"
    )
    parser.add_argument(
        'file',
        nargs='?',
        default='requirements.txt',
        help='Path to requirements.txt (default: requirements.txt)'
    )
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Automatically fix outdated versions to latest'
    )

    args = parser.parse_args()
    file_path = args.file

    all_valid, errors = validate_requirements(file_path)

    print()
    if all_valid:
        print("✓ All packages are valid!")
        return 0
    else:
        print(f"\n✗ Found {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")

        if args.fix:
            print("\nAttempting to fix automatically...")
            # Auto-fix logic would go here
            print("Auto-fix not yet implemented. Please fix manually.")

        return 1


if __name__ == "__main__":
    sys.exit(main())
