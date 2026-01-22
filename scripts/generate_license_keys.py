#!/usr/bin/env python3
"""
License Key Generator for BrainDock.

Generates license keys for distribution.
Run this script to create new license keys that can be given to users.

Usage:
    python scripts/generate_license_keys.py --count 10
    python scripts/generate_license_keys.py --count 5 --prefix BETA
    python scripts/generate_license_keys.py --add-to-file
"""

import argparse
import json
import secrets
import string
import sys
from pathlib import Path
from datetime import datetime
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_key(prefix: str = "BD", length: int = 16) -> str:
    """
    Generate a random license key.
    
    Args:
        prefix: Prefix for the key (e.g., "BD" for BrainDock).
        length: Length of the random part (excluding prefix and dashes).
        
    Returns:
        A formatted license key like "BD-XXXX-XXXX-XXXX-XXXX".
    """
    # Characters to use (uppercase letters and digits, excluding confusing chars)
    chars = string.ascii_uppercase + string.digits
    # Remove confusing characters: 0, O, I, 1, L
    chars = chars.replace('0', '').replace('O', '').replace('I', '').replace('1', '').replace('L', '')
    
    # Generate random characters
    random_part = ''.join(secrets.choice(chars) for _ in range(length))
    
    # Format with dashes every 4 characters
    parts = [random_part[i:i+4] for i in range(0, len(random_part), 4)]
    
    return f"{prefix}-" + "-".join(parts)


def generate_keys(count: int, prefix: str = "BD") -> List[str]:
    """
    Generate multiple license keys.
    
    Args:
        count: Number of keys to generate.
        prefix: Prefix for the keys.
        
    Returns:
        List of plain text license keys.
    """
    return [generate_key(prefix=prefix) for _ in range(count)]


def load_existing_keys(keys_file: Path) -> dict:
    """
    Load existing license keys from file.
    
    Args:
        keys_file: Path to the license keys JSON file.
        
    Returns:
        Dictionary of plain keys and their metadata.
    """
    if keys_file.exists():
        try:
            with open(keys_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"keys": []}


def save_keys(keys_file: Path, keys_data: dict) -> None:
    """
    Save license keys to file.
    
    Args:
        keys_file: Path to the license keys JSON file.
        keys_data: Dictionary of key hashes and their metadata.
    """
    keys_file.parent.mkdir(parents=True, exist_ok=True)
    with open(keys_file, 'w') as f:
        json.dump(keys_data, f, indent=2)


def main():
    """Main entry point for the key generator."""
    parser = argparse.ArgumentParser(
        description="Generate license keys for BrainDock",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Generate 10 keys and display them:
    python scripts/generate_license_keys.py --count 10

  Generate 5 keys with custom prefix:
    python scripts/generate_license_keys.py --count 5 --prefix BETA

  Generate keys and add to the license_keys.json file:
    python scripts/generate_license_keys.py --count 10 --add-to-file

  Show existing keys in the file:
    python scripts/generate_license_keys.py --show-existing
        """
    )
    parser.add_argument(
        "--count",
        type=int,
        default=5,
        help="Number of keys to generate (default: 5)"
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="BD",
        help="Prefix for generated keys (default: BD)"
    )
    parser.add_argument(
        "--add-to-file",
        action="store_true",
        help="Add generated keys to the license_keys.json file"
    )
    parser.add_argument(
        "--show-existing",
        action="store_true",
        help="Show existing keys in the license_keys.json file"
    )
    parser.add_argument(
        "--output-file",
        type=str,
        help="Path to output file (default: data/license_keys.json)"
    )
    
    args = parser.parse_args()
    
    # Determine keys file path
    if args.output_file:
        keys_file = Path(args.output_file)
    else:
        keys_file = Path(__file__).parent.parent / "data" / "license_keys.json"
    
    # Show existing keys if requested
    if args.show_existing:
        existing = load_existing_keys(keys_file)
        keys_list = existing.get("keys", [])
        if not keys_list:
            print("No existing keys found.")
        else:
            print(f"\nExisting keys in {keys_file}:")
            print("-" * 70)
            for i, key in enumerate(keys_list, 1):
                print(f"  {i:2}. {key}")
            print(f"\nTotal: {len(keys_list)} keys")
        return
    
    # Generate new keys
    print(f"\nGenerating {args.count} license keys with prefix '{args.prefix}'...")
    print("-" * 70)
    
    keys = generate_keys(args.count, prefix=args.prefix)
    
    # Display generated keys
    print("\n🔑 Generated License Keys:\n")
    for i, key in enumerate(keys, 1):
        print(f"  {i:2}. {key}")
    
    print("\n" + "-" * 70)
    
    # Add to file if requested
    if args.add_to_file:
        existing = load_existing_keys(keys_file)
        keys_list = existing.get("keys", [])
        
        # Add new keys (avoid duplicates)
        for key in keys:
            if key not in keys_list:
                keys_list.append(key)
        
        existing["keys"] = keys_list
        existing["updated_at"] = datetime.now().isoformat()
        
        save_keys(keys_file, existing)
        print(f"\n✅ Keys saved to: {keys_file}")
        print(f"   Total keys in file: {len(keys_list)}")
    else:
        print("\n💡 Tip: Use --add-to-file to save these keys to the license file")
    
    print()


if __name__ == "__main__":
    main()
