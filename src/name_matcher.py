"""
Name Matcher - Translates player names between different data sources
(Betfair, Tennis Abstract, Tennis Explorer, etc.)
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, List
from difflib import SequenceMatcher

from config import DATA_DIR

# Path to mappings file
MAPPINGS_FILE = DATA_DIR / "name_mappings.json"


class NameMatcher:
    """Matches player names across different data sources."""

    def __init__(self):
        self.mappings = {}
        self.aliases = {}
        self.reverse_mappings = {}  # For reverse lookups
        self._load_mappings()

    def _load_mappings(self):
        """Load mappings from JSON file."""
        if MAPPINGS_FILE.exists():
            try:
                with open(MAPPINGS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.mappings = data.get('mappings', {})
                    self.aliases = data.get('aliases', {})

                    # Build reverse mappings for string values
                    for betfair_name, db_value in self.mappings.items():
                        if isinstance(db_value, str):
                            self.reverse_mappings[db_value.lower()] = betfair_name

                    # Add aliases to reverse mappings
                    for canonical, alias_list in self.aliases.items():
                        if isinstance(alias_list, list):
                            for alias in alias_list:
                                self.reverse_mappings[alias.lower()] = canonical

            except Exception as e:
                print(f"Error loading name mappings: {e}")

    def save_mappings(self):
        """Save current mappings to file."""
        MAPPINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "_comment": "Maps Betfair player names to database player names/IDs",
            "_usage": "Add entries as needed: 'Betfair Name': 'Database Name' or 'Betfair Name': player_id",
            "mappings": self.mappings,
            "aliases": self.aliases
        }
        with open(MAPPINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def add_mapping(self, betfair_name: str, db_name_or_id):
        """Add a new mapping."""
        self.mappings[betfair_name] = db_name_or_id
        if isinstance(db_name_or_id, str):
            self.reverse_mappings[db_name_or_id.lower()] = betfair_name
        self.save_mappings()

    def get_db_name(self, betfair_name: str) -> Optional[str]:
        """Get the database name for a Betfair name."""
        # Direct mapping
        if betfair_name in self.mappings:
            result = self.mappings[betfair_name]
            return result if isinstance(result, str) else None

        # Check aliases
        for canonical, alias_list in self.aliases.items():
            if betfair_name in alias_list or betfair_name == canonical:
                if canonical in self.mappings:
                    return self.mappings[canonical]
                return canonical

        return None

    def get_db_id(self, betfair_name: str) -> Optional[int]:
        """Get the database player ID for a Betfair name (if mapped to ID)."""
        if betfair_name in self.mappings:
            result = self.mappings[betfair_name]
            if isinstance(result, int):
                return result
            # Could be a string player name - need to look up separately
            return None
        # Try case-insensitive match
        betfair_lower = betfair_name.lower()
        for name, value in self.mappings.items():
            if name.lower() == betfair_lower and isinstance(value, int):
                return value
        return None

    def normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        # Remove hyphens, extra spaces, convert to lowercase
        normalized = name.replace('-', ' ').replace('  ', ' ').strip().lower()
        # Remove accents (basic)
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ä': 'a', 'ë': 'e', 'ï': 'i', 'ö': 'o', 'ü': 'u',
            'ñ': 'n', 'ç': 'c', 'ş': 's', 'ğ': 'g',
            'ą': 'a', 'ę': 'e', 'ł': 'l', 'ń': 'n', 'ś': 's', 'ź': 'z', 'ż': 'z',
            'č': 'c', 'ř': 'r', 'š': 's', 'ž': 'z', 'ě': 'e', 'ů': 'u',
            'ț': 't', 'ș': 's', 'ă': 'a', 'î': 'i', 'â': 'a',
            'ø': 'o', 'å': 'a', 'æ': 'ae',
            'ß': 'ss',
            'ı': 'i',
            'ć': 'c', 'đ': 'd',
            'ő': 'o', 'ű': 'u',
            'ý': 'y',
            'þ': 'th',
            'œ': 'oe',
            'ś': 's', 'ź': 'z', 'ż': 'z',
            'ñ': 'n',
            'ã': 'a', 'õ': 'o',
        }
        for accented, plain in replacements.items():
            normalized = normalized.replace(accented, plain)
        return normalized

    def extract_last_name(self, name: str) -> str:
        """Extract the last name from a full name."""
        parts = name.strip().split()
        if len(parts) >= 2:
            return parts[-1]
        return name

    def extract_first_name(self, name: str) -> str:
        """Extract the first name from a full name."""
        parts = name.strip().split()
        if len(parts) >= 1:
            return parts[0]
        return name

    def similarity_score(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names (0-1)."""
        n1 = self.normalize_name(name1)
        n2 = self.normalize_name(name2)
        return SequenceMatcher(None, n1, n2).ratio()

    def find_best_match(self, betfair_name: str, candidates: List[Dict],
                        threshold: float = 0.7) -> Optional[Dict]:
        """Find the best matching player from a list of candidates.

        Args:
            betfair_name: The name from Betfair
            candidates: List of player dicts with 'name' and 'id' keys
            threshold: Minimum similarity score (0-1) to consider a match

        Returns:
            Best matching player dict or None
        """
        # First check explicit mappings
        mapped_name = self.get_db_name(betfair_name)
        if mapped_name:
            for candidate in candidates:
                if self.normalize_name(candidate['name']) == self.normalize_name(mapped_name):
                    return candidate

        mapped_id = self.get_db_id(betfair_name)
        if mapped_id:
            for candidate in candidates:
                if candidate['id'] == mapped_id:
                    return candidate

        # Try normalized exact match
        normalized_betfair = self.normalize_name(betfair_name)
        for candidate in candidates:
            if self.normalize_name(candidate['name']) == normalized_betfair:
                return candidate

        # Try last name + first initial match
        betfair_last = self.extract_last_name(betfair_name).lower()
        betfair_first = self.extract_first_name(betfair_name).lower()

        for candidate in candidates:
            cand_name = candidate['name']
            cand_last = self.extract_last_name(cand_name).lower()
            cand_first = self.extract_first_name(cand_name).lower()

            # Last name exact match + first initial
            if cand_last == betfair_last:
                if cand_first and betfair_first and cand_first[0] == betfair_first[0]:
                    return candidate

        # Strategy 4: Try reversed name order (LastName FirstName vs FirstName LastName)
        # Handles "Sinner Jannik" vs "Jannik Sinner"
        betfair_parts = betfair_name.strip().split()
        if len(betfair_parts) >= 2:
            # Try "LastName FirstName" -> "FirstName LastName"
            reversed_name = ' '.join(betfair_parts[::-1])
            normalized_reversed = self.normalize_name(reversed_name)
            for candidate in candidates:
                if self.normalize_name(candidate['name']) == normalized_reversed:
                    return candidate

            # Also try just swapping first and last
            swapped_name = f"{betfair_parts[-1]} {' '.join(betfair_parts[:-1])}"
            normalized_swapped = self.normalize_name(swapped_name)
            for candidate in candidates:
                if self.normalize_name(candidate['name']) == normalized_swapped:
                    return candidate

        # Fuzzy matching as last resort
        best_match = None
        best_score = threshold

        for candidate in candidates:
            score = self.similarity_score(betfair_name, candidate['name'])
            if score > best_score:
                best_score = score
                best_match = candidate

        return best_match


# Singleton instance
name_matcher = NameMatcher()
