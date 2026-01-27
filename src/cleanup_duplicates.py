"""
Cleanup Duplicates - Populate player_aliases table for duplicate players.

This script:
1. Finds all players with duplicate names (normalized)
2. Picks a canonical ID for each (prefers positive ID with ranking)
3. Adds aliases mapping duplicate IDs to the canonical ID
4. Reports what was done

Run from src folder: python cleanup_duplicates.py
"""

from collections import defaultdict
from database import db


def normalize_name(name: str) -> str:
    """Normalize a player name for comparison."""
    return name.lower().replace('-', ' ').strip()


def pick_canonical_id(players: list) -> dict:
    """
    Pick the best canonical ID from a list of duplicate players.

    Priority:
    1. Positive ID with ranking (real ATP/WTA player)
    2. Positive ID without ranking
    3. Negative ID with ranking
    4. Negative ID without ranking (lowest/first created)
    """
    # Sort by priority
    def sort_key(p):
        has_positive_id = p['id'] > 0
        has_ranking = p.get('current_ranking') is not None
        rank_value = p.get('current_ranking') or 99999

        # Priority: (positive ID, has ranking, lower rank is better, higher ID for ties)
        return (
            0 if has_positive_id else 1,  # Positive IDs first
            0 if has_ranking else 1,       # Ranked players first
            rank_value,                     # Lower rank is better
            -p['id']                        # For ties, prefer higher positive ID or lower negative ID
        )

    sorted_players = sorted(players, key=sort_key)
    return sorted_players[0]


def cleanup_duplicates(dry_run: bool = False):
    """
    Find and fix duplicate players by populating the player_aliases table.

    Args:
        dry_run: If True, only report what would be done without making changes
    """
    print("=" * 70)
    print("DUPLICATE PLAYER CLEANUP")
    print("=" * 70)

    # Get all players
    all_players = db.get_all_players()
    print(f"\nTotal players in database: {len(all_players)}")

    # Group by normalized name
    name_groups = defaultdict(list)
    for p in all_players:
        normalized = normalize_name(p['name'])
        name_groups[normalized].append(p)

    # Find groups with duplicates
    duplicates = {k: v for k, v in name_groups.items() if len(v) > 1}
    print(f"Names with duplicates: {len(duplicates)}")

    total_duplicates = sum(len(v) - 1 for v in duplicates.values())
    print(f"Total duplicate records to alias: {total_duplicates}")

    if not duplicates:
        print("\nNo duplicates found!")
        return

    # Process each duplicate group
    aliases_to_add = []

    print("\n" + "-" * 70)
    print("PROCESSING DUPLICATES")
    print("-" * 70)

    for name, players in sorted(duplicates.items()):
        canonical = pick_canonical_id(players)
        canonical_id = canonical['id']
        canonical_rank = canonical.get('current_ranking', 'N/A')

        print(f"\n'{canonical['name']}' -> Canonical ID: {canonical_id} (Rank: {canonical_rank})")

        for p in players:
            if p['id'] != canonical_id:
                aliases_to_add.append({
                    'alias_id': p['id'],
                    'canonical_id': canonical_id,
                    'name': p['name']
                })
                p_rank = p.get('current_ranking', 'N/A')
                print(f"  - Alias: {p['id']} (Rank: {p_rank})")

    print("\n" + "=" * 70)
    print(f"SUMMARY: {len(aliases_to_add)} aliases to create")
    print("=" * 70)

    if dry_run:
        print("\n[DRY RUN] No changes made. Run with dry_run=False to apply.")
        return {'aliases_created': 0, 'dry_run': True}

    # Add aliases to database
    print("\nAdding aliases to database...")
    added = 0
    errors = 0

    for alias in aliases_to_add:
        try:
            db.add_player_alias(
                alias_id=alias['alias_id'],
                canonical_id=alias['canonical_id'],
                source='duplicate_cleanup'
            )
            added += 1
        except Exception as e:
            print(f"  Error adding alias {alias['alias_id']}: {e}")
            errors += 1

    print(f"\nDone! Added {added} aliases, {errors} errors.")

    return {
        'duplicates_found': len(duplicates),
        'aliases_created': added,
        'errors': errors
    }


def verify_aliases():
    """Verify the aliases are working correctly."""
    print("\n" + "=" * 70)
    print("VERIFYING ALIASES")
    print("=" * 70)

    # Check a known duplicate
    test_players = ['Felix Auger Aliassime', 'Sebastian Baez', 'Coco Gauff']

    for name in test_players:
        players = db.search_players(name.split()[-1], limit=50)
        matching = [p for p in players if normalize_name(p['name']) == normalize_name(name)]

        if matching:
            print(f"\n'{name}':")
            print(f"  Found {len(matching)} records")

            # Check canonical IDs
            canonical_ids = set()
            for p in matching:
                canonical = db.get_canonical_id(p['id'])
                canonical_ids.add(canonical)
                if canonical != p['id']:
                    print(f"  ID {p['id']} -> canonical {canonical}")

            print(f"  Unique canonical IDs: {len(canonical_ids)}")


if __name__ == "__main__":
    import sys

    # Check for --dry-run flag
    dry_run = '--dry-run' in sys.argv

    if dry_run:
        print("[DRY RUN MODE - No changes will be made]\n")

    result = cleanup_duplicates(dry_run=dry_run)

    if not dry_run and result.get('aliases_created', 0) > 0:
        verify_aliases()

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("1. Rankings UI will now filter out aliased players")
    print("2. Match queries will use canonical IDs automatically")
    print("3. Run this script again if new duplicates appear")
