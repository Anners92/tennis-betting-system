"""
Renumber all player IDs to be sequential (1, 2, 3, ...).
Updates players table and all match references.
"""

import json
from pathlib import Path
from database import db


def renumber_players(dry_run=True):
    """
    Renumber all player IDs to sequential integers starting from 1.

    Steps:
    1. Get all players ordered by ranking (ranked first), then by name
    2. Create old_id -> new_id mapping
    3. Update matches table
    4. Update players table
    5. Update name_mappings.json
    """

    print("=" * 60)
    print("RENUMBER PLAYER IDs")
    print("=" * 60)

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Step 1: Get all players, ordered alphabetically by name
        # Use REPLACE to strip leading parenthetical prefixes for sorting
        cursor.execute('''
            SELECT id, name, current_ranking, tour
            FROM players
            ORDER BY
                CASE WHEN name LIKE '(%' THEN 1 ELSE 0 END,
                UPPER(name) ASC
        ''')
        players = cursor.fetchall()

        print(f"\nTotal players to renumber: {len(players)}")

        # Step 2: Create mapping
        id_mapping = {}  # old_id -> new_id
        for new_id, player in enumerate(players, start=1):
            old_id = player['id']
            id_mapping[old_id] = new_id

        print(f"Created ID mapping for {len(id_mapping)} players")

        # Show some examples
        print("\nSample mappings (first 10):")
        for i, (old_id, new_id) in enumerate(list(id_mapping.items())[:10]):
            player = next(p for p in players if p['id'] == old_id)
            rank = player['current_ranking'] or 'N/A'
            print(f"  {old_id} -> {new_id} ({player['name']}, Rank: {rank})")

        if dry_run:
            print("\n[DRY RUN] No changes made.")
            return {'players': len(players), 'dry_run': True, 'mapping': id_mapping}

        # Step 3: Update matches - use temporary negative IDs to avoid conflicts
        print("\nUpdating matches (phase 1 - temporary IDs)...")

        # First pass: convert to negative temporary IDs
        for old_id, new_id in id_mapping.items():
            temp_id = -1000000 - new_id  # Temporary negative ID

            cursor.execute('UPDATE matches SET winner_id = ? WHERE winner_id = ?',
                          (temp_id, old_id))
            cursor.execute('UPDATE matches SET loser_id = ? WHERE loser_id = ?',
                          (temp_id, old_id))

        # Second pass: convert temp IDs to final IDs
        print("Updating matches (phase 2 - final IDs)...")
        for old_id, new_id in id_mapping.items():
            temp_id = -1000000 - new_id

            cursor.execute('UPDATE matches SET winner_id = ? WHERE winner_id = ?',
                          (new_id, temp_id))
            cursor.execute('UPDATE matches SET loser_id = ? WHERE loser_id = ?',
                          (new_id, temp_id))

        # Step 4: Update players table - same two-pass approach
        print("Updating players (phase 1 - temporary IDs)...")

        for old_id, new_id in id_mapping.items():
            temp_id = -1000000 - new_id
            cursor.execute('UPDATE players SET id = ? WHERE id = ?', (temp_id, old_id))

        print("Updating players (phase 2 - final IDs)...")
        for old_id, new_id in id_mapping.items():
            temp_id = -1000000 - new_id
            cursor.execute('UPDATE players SET id = ? WHERE id = ?', (new_id, temp_id))

        conn.commit()

        # Step 5: Update name_mappings.json
        print("\nUpdating name_mappings.json...")
        mappings_path = Path(__file__).parent / 'name_mappings.json'

        if mappings_path.exists():
            with open(mappings_path, 'r') as f:
                name_mappings = json.load(f)

            updated_mappings = {}
            updated_count = 0

            for name, old_id in name_mappings.items():
                if old_id in id_mapping:
                    updated_mappings[name] = id_mapping[old_id]
                    updated_count += 1
                else:
                    # ID not in mapping (might be deleted duplicate)
                    # Skip it
                    pass

            with open(mappings_path, 'w') as f:
                json.dump(updated_mappings, f, indent=2)

            print(f"  Updated {updated_count} name mappings")
            print(f"  Removed {len(name_mappings) - updated_count} stale mappings")
        else:
            print("  name_mappings.json not found, skipping")

        print("\n" + "=" * 60)
        print("RENUMBERING COMPLETE")
        print("=" * 60)

        return {
            'players_renumbered': len(players),
            'mapping': id_mapping
        }


def verify_renumbering():
    """Verify the renumbering was successful."""
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Check ID range
        cursor.execute('SELECT MIN(id) as min_id, MAX(id) as max_id, COUNT(*) as count FROM players')
        result = cursor.fetchone()

        print(f"\nPlayer IDs:")
        print(f"  Min ID: {result['min_id']}")
        print(f"  Max ID: {result['max_id']}")
        print(f"  Total: {result['count']}")

        if result['min_id'] == 1 and result['max_id'] == result['count']:
            print("  ✓ IDs are sequential from 1 to N")
        else:
            print("  ✗ IDs are not perfectly sequential")

        # Show top 10 players
        print("\nTop 10 players by ID:")
        cursor.execute('''
            SELECT id, name, current_ranking
            FROM players
            ORDER BY id
            LIMIT 10
        ''')
        for row in cursor.fetchall():
            rank = row['current_ranking'] or 'N/A'
            print(f"  ID {row['id']}: {row['name']} (Rank: {rank})")

        # Verify matches reference valid players
        cursor.execute('''
            SELECT COUNT(*) as cnt FROM matches m
            WHERE NOT EXISTS (SELECT 1 FROM players p WHERE p.id = m.winner_id)
               OR NOT EXISTS (SELECT 1 FROM players p WHERE p.id = m.loser_id)
        ''')
        orphaned = cursor.fetchone()['cnt']

        if orphaned == 0:
            print("\n  ✓ All match references are valid")
        else:
            print(f"\n  ✗ {orphaned} matches have invalid player references")


if __name__ == "__main__":
    import sys

    force = '--force' in sys.argv

    if not force:
        print("[DRY RUN MODE - Use --force to actually renumber]\n")
        renumber_players(dry_run=True)
        print("\n" + "-" * 60)
        print("To apply changes, run: python renumber_players.py --force")
    else:
        print("[FORCE MODE - Changes will be applied]\n")
        response = input("Are you sure you want to renumber all player IDs? (yes/no): ")

        if response.lower() == 'yes':
            renumber_players(dry_run=False)
            verify_renumbering()
        else:
            print("Aborted.")
