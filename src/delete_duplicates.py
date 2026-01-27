"""
Delete duplicate players from the database.
Finds duplicates by name, keeps the canonical player (one with ranking or most matches).
Reassigns all matches to the canonical ID before deleting.
"""

from collections import defaultdict
from database import db


def normalize_name(name: str) -> str:
    """Normalize a player name for comparison."""
    return name.lower().replace('-', ' ').strip()


def pick_canonical(players: list) -> dict:
    """
    Pick the canonical player from a list of duplicates.
    Priority: has ranking > most matches > lowest ID
    """
    def sort_key(p):
        has_ranking = p.get('current_ranking') is not None
        rank_value = p.get('current_ranking') or 99999
        match_count = p.get('match_count', 0)
        return (
            0 if has_ranking else 1,  # Ranked players first
            rank_value,                # Lower rank is better
            -match_count,              # More matches is better
            p['id']                    # Lower ID as tiebreaker
        )

    sorted_players = sorted(players, key=sort_key)
    return sorted_players[0]


def delete_all_duplicates(dry_run=True):
    """
    Find and delete all duplicate players.
    Keeps the canonical one (with ranking or most matches).
    """

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Get all players with match counts
        cursor.execute('''
            SELECT
                p.id, p.name, p.current_ranking, p.tour,
                (SELECT COUNT(*) FROM matches m
                 WHERE m.winner_id = p.id OR m.loser_id = p.id) as match_count
            FROM players p
            WHERE p.name NOT LIKE '%/%'
        ''')
        all_players = [dict(row) for row in cursor.fetchall()]

        # Group by normalized name AND tour (don't merge ATP with WTA)
        name_groups = defaultdict(list)
        for p in all_players:
            normalized = normalize_name(p['name'])
            tour = p.get('tour', 'ATP') or 'ATP'  # Default to ATP if None
            key = (normalized, tour)
            name_groups[key].append(p)

        # Find duplicates
        duplicates = {k: v for k, v in name_groups.items() if len(v) > 1}

        if not duplicates:
            return None  # No duplicates found

        total_to_delete = sum(len(v) - 1 for v in duplicates.values())

        if dry_run:
            return {
                'duplicate_groups': len(duplicates),
                'players_to_delete': total_to_delete,
                'dry_run': True
            }

        # Process each duplicate group
        total_deleted = 0
        total_matches_updated = 0

        for name, players in duplicates.items():
            canonical = pick_canonical(players)
            canonical_id = canonical['id']

            # Get IDs to delete (all except canonical)
            ids_to_delete = [p['id'] for p in players if p['id'] != canonical_id]

            for delete_id in ids_to_delete:
                # Update matches: winner_id
                cursor.execute(
                    'UPDATE matches SET winner_id = ? WHERE winner_id = ?',
                    (canonical_id, delete_id)
                )
                total_matches_updated += cursor.rowcount

                # Update matches: loser_id
                cursor.execute(
                    'UPDATE matches SET loser_id = ? WHERE loser_id = ?',
                    (canonical_id, delete_id)
                )
                total_matches_updated += cursor.rowcount

                # Delete the duplicate player
                cursor.execute('DELETE FROM players WHERE id = ?', (delete_id,))
                total_deleted += cursor.rowcount

        # Also clear any stale aliases
        cursor.execute('DELETE FROM player_aliases')

        conn.commit()

        return {
            'duplicate_groups': len(duplicates),
            'players_deleted': total_deleted,
            'matches_updated': total_matches_updated
        }


if __name__ == "__main__":
    import sys

    force = '--force' in sys.argv

    if not force:
        print("[DRY RUN MODE - Use --force to actually delete]\n")
        result = delete_all_duplicates(dry_run=True)

        if result:
            print(f"Found {result['duplicate_groups']} duplicate name groups")
            print(f"Would delete {result['players_to_delete']} duplicate players")
            print("\nTo apply changes, run: python delete_duplicates.py --force")
        else:
            print("No duplicates found.")
    else:
        print("[FORCE MODE - Changes will be applied]\n")
        response = input("Are you sure you want to delete duplicate players? (yes/no): ")

        if response.lower() == 'yes':
            result = delete_all_duplicates(dry_run=False)
            if result:
                print(f"\nDeleted {result['players_deleted']} duplicate players")
                print(f"Updated {result['matches_updated']} match references")
            else:
                print("No duplicates found.")
        else:
            print("Aborted.")
