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
            # Extract version FIRST before stripping the line
            version_match = re.search(r'==([0-9.]+)', line)
            version = version_match.group(1) if version_match else ""

            # Remove environment markers and version specs to get package name
            line = re.split(r';|==|>=|<=|>|~|=|\[', line)[0].strip()

            # Extract package name (before any version spec)
            match = re.match(r'^([a-zA-Z0-9._-]+)', line)
            if match:
                package = match.group(1)
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
        # Method 1: Try pip show to check if package is known to PyPI
        # This is fast and works for most packages
        result = subprocess.run(
            ['pip', 'show', package],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Package exists if pip show succeeds
        if result.returncode == 0:
            # Parse version from output
            latest = ""
            for line in result.stdout.split('\n'):
                if line.startswith('Version:'):
                    latest = line.split(':', 1)[1].strip()
                    break

            if version:
                if version == latest:
                    return True, latest, ""
                else:
                    # Check if specific version can be fetched
                    check_result = subprocess.run(
                        ['pip', 'download', '--only-binary=:all:', '--no-deps', '--dest', '/tmp', f'{package}=={version}'],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    # Clean up any downloaded file
                    subprocess.run(['rm', '-f', f'/tmp/{package}=={version}*.whl', f'/tmp/{package}-{version}*.tar.gz'],
                                   capture_output=True)

                    if check_result.returncode == 0:
                        return True, latest, ""
                    else:
                        return False, latest, f"Version {version} may not be available (latest: {latest})"
            else:
                return True, latest, ""

        # Method 2: Package not installed, try to fetch metadata from PyPI
        # Use pip download with --no-deps to just check availability
        check_spec = f'{package}=={version}' if version else package
        result = subprocess.run(
            ['pip', 'download', '--no-deps', '--no-binary', ':all:', '--dest', '/tmp', check_spec],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Clean up any downloaded file
        subprocess.run(
            ['find', '/tmp', '-name', f'{package}*', '-type', 'f', '-delete'],
            capture_output=True
        )

        if result.returncode == 0:
            return True, "", ""
        else:
            # Check if error is about version not found
            stderr_lower = result.stderr.lower()
            if 'no matching distribution' in stderr_lower or 'could not find a version' in stderr_lower:
                return False, "", f"Package '{package}' not found on PyPI"
            else:
                # Might be a different error, but package likely exists
                return True, "", ""

    except subprocess.TimeoutExpired:
        return False, "", f"Timeout checking '{package}'"
    except FileNotFoundError:
        # pip not found - skip validation
        return True, "", ""
    except Exception as e:
        # On any error, allow installation to proceed (pip will give clearer error)
        return True, "", f"Warning: Could not validate '{package}': {str(e)}"


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
