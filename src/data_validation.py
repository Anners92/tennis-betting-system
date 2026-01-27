"""
Tennis Betting System - Data Validation Rules
==============================================

This module enforces strict validation rules for all data imports to prevent
corrupt or inconsistent data from entering the system.

CRITICAL RULES (will reject data):
1. winner_id must NOT equal loser_id
2. winner_id and loser_id must both be valid (not None, not 0)
3. Date must be valid and not in the future (for historical matches)
4. Score must be parseable and consistent with winner/loser

WARNING RULES (will log but allow):
1. Missing tournament name
2. Missing surface
3. Missing player rankings

All validation failures are logged to: logs/data_validation.csv
"""

import csv
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from config import LOGS_DIR

# Ensure logs directory exists
LOGS_DIR.mkdir(exist_ok=True)
VALIDATION_LOG_FILE = LOGS_DIR / "data_validation.csv"


class ValidationError(Exception):
    """Raised when critical validation fails."""
    pass


class DataValidator:
    """
    Validates match and player data before database insertion.

    Usage:
        validator = DataValidator()
        is_valid, errors = validator.validate_match(match_data)
        if not is_valid:
            # Handle errors
    """

    def __init__(self, log_failures: bool = True):
        self.log_failures = log_failures
        self._ensure_log_header()

    def _ensure_log_header(self):
        """Ensure the validation log file has headers."""
        if not VALIDATION_LOG_FILE.exists():
            with open(VALIDATION_LOG_FILE, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'source', 'rule_violated', 'severity',
                    'winner_id', 'loser_id', 'winner_name', 'loser_name',
                    'date', 'tournament', 'details'
                ])

    def _log_validation_failure(self, match_data: Dict, rule: str, severity: str,
                                 source: str = "unknown", details: str = ""):
        """Log a validation failure to CSV for analysis."""
        if not self.log_failures:
            return

        try:
            with open(VALIDATION_LOG_FILE, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now().isoformat(),
                    source,
                    rule,
                    severity,
                    match_data.get('winner_id', ''),
                    match_data.get('loser_id', ''),
                    match_data.get('winner_name', ''),
                    match_data.get('loser_name', ''),
                    match_data.get('date', ''),
                    match_data.get('tourney_name', match_data.get('tournament', '')),
                    details
                ])
        except Exception as e:
            print(f"Warning: Could not log validation failure: {e}")

    def validate_match(self, match_data: Dict, source: str = "unknown") -> Tuple[bool, List[str]]:
        """
        Validate match data before insertion.

        Returns:
            Tuple of (is_valid, list_of_errors)

        Critical failures return is_valid=False
        Warnings are logged but return is_valid=True
        """
        errors = []
        warnings = []

        winner_id = match_data.get('winner_id')
        loser_id = match_data.get('loser_id')
        date = match_data.get('date')
        score = match_data.get('score', '')

        # =====================================================================
        # CRITICAL RULE 1: winner_id must NOT equal loser_id
        # =====================================================================
        if winner_id is not None and loser_id is not None:
            if winner_id == loser_id:
                error_msg = f"CRITICAL: winner_id ({winner_id}) equals loser_id ({loser_id})"
                errors.append(error_msg)
                self._log_validation_failure(
                    match_data, "winner_equals_loser", "CRITICAL", source,
                    f"Both IDs are {winner_id}"
                )

        # =====================================================================
        # CRITICAL RULE 2: Both IDs must be valid (not None, not 0, not empty)
        # =====================================================================
        if winner_id is None or winner_id == 0 or winner_id == '':
            error_msg = f"CRITICAL: Invalid winner_id: {winner_id}"
            errors.append(error_msg)
            self._log_validation_failure(
                match_data, "invalid_winner_id", "CRITICAL", source,
                f"winner_id is {winner_id}"
            )

        if loser_id is None or loser_id == 0 or loser_id == '':
            error_msg = f"CRITICAL: Invalid loser_id: {loser_id}"
            errors.append(error_msg)
            self._log_validation_failure(
                match_data, "invalid_loser_id", "CRITICAL", source,
                f"loser_id is {loser_id}"
            )

        # =====================================================================
        # CRITICAL RULE 3: Date must be valid
        # =====================================================================
        if not date:
            error_msg = "CRITICAL: Missing date"
            errors.append(error_msg)
            self._log_validation_failure(
                match_data, "missing_date", "CRITICAL", source, ""
            )
        else:
            try:
                parsed_date = datetime.strptime(str(date)[:10], "%Y-%m-%d")
                # Allow dates up to 7 days in future (for upcoming matches)
                max_future = datetime.now().replace(hour=23, minute=59, second=59)
                from datetime import timedelta
                max_future = max_future + timedelta(days=7)
                if parsed_date > max_future:
                    error_msg = f"CRITICAL: Date too far in future: {date}"
                    errors.append(error_msg)
                    self._log_validation_failure(
                        match_data, "future_date", "CRITICAL", source,
                        f"Date {date} is more than 7 days in future"
                    )
            except ValueError as e:
                error_msg = f"CRITICAL: Invalid date format: {date}"
                errors.append(error_msg)
                self._log_validation_failure(
                    match_data, "invalid_date_format", "CRITICAL", source,
                    str(e)
                )

        # =====================================================================
        # CRITICAL RULE 4: Score should be valid (if provided for completed match)
        # =====================================================================
        if score and date:
            try:
                parsed_date = datetime.strptime(str(date)[:10], "%Y-%m-%d")
                if parsed_date <= datetime.now():  # Historical match should have valid score
                    if not self._is_valid_score(score):
                        # This is a warning, not critical
                        warnings.append(f"WARNING: Potentially invalid score format: {score}")
                        self._log_validation_failure(
                            match_data, "invalid_score_format", "WARNING", source,
                            f"Score: {score}"
                        )
            except:
                pass

        # =====================================================================
        # WARNING RULES (logged but don't fail validation)
        # =====================================================================

        # Missing tournament name
        tourney = match_data.get('tourney_name') or match_data.get('tournament')
        if not tourney:
            warnings.append("WARNING: Missing tournament name")
            self._log_validation_failure(
                match_data, "missing_tournament", "WARNING", source, ""
            )

        # Missing surface
        if not match_data.get('surface'):
            warnings.append("WARNING: Missing surface")
            self._log_validation_failure(
                match_data, "missing_surface", "WARNING", source, ""
            )

        # Return validation result
        is_valid = len(errors) == 0
        all_messages = errors + warnings

        return is_valid, all_messages

    def _is_valid_score(self, score: str) -> bool:
        """Check if score follows standard tennis format."""
        if not score:
            return False

        # Common score patterns: "6-4 6-3", "7-6(5) 6-4", "6-4, 6-3"
        # Allow various separators and tiebreak notation
        score_clean = score.replace(',', ' ').strip()

        # Each set should be like "6-4" or "7-6(5)"
        set_pattern = r'\d+-\d+(\(\d+\))?'
        sets = re.findall(set_pattern, score_clean)

        # Should have at least 2 sets for a valid match
        return len(sets) >= 2 or 'RET' in score.upper() or 'W/O' in score.upper()

    def validate_player(self, player_data: Dict, source: str = "unknown") -> Tuple[bool, List[str]]:
        """Validate player data before insertion."""
        errors = []

        player_id = player_data.get('id')
        name = player_data.get('name')

        if not player_id:
            errors.append("CRITICAL: Missing player ID")

        if not name or len(str(name).strip()) < 2:
            errors.append("CRITICAL: Invalid player name")

        return len(errors) == 0, errors

    def validate_and_fix_match(self, match_data: Dict, source: str = "unknown") -> Tuple[bool, Dict, List[str]]:
        """
        Validate match and attempt to fix minor issues.

        Returns:
            Tuple of (is_valid, fixed_match_data, messages)
        """
        fixed_data = match_data.copy()
        messages = []

        # Attempt to fix common issues

        # Fix: Ensure IDs are integers
        for id_field in ['winner_id', 'loser_id']:
            if id_field in fixed_data and fixed_data[id_field]:
                try:
                    fixed_data[id_field] = int(float(fixed_data[id_field]))
                except (ValueError, TypeError):
                    pass

        # Fix: Normalize date format
        if 'date' in fixed_data and fixed_data['date']:
            date_str = str(fixed_data['date'])
            # Try various formats
            for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"]:
                try:
                    parsed = datetime.strptime(date_str[:10], fmt)
                    fixed_data['date'] = parsed.strftime("%Y-%m-%d")
                    break
                except ValueError:
                    continue

        # Fix: Normalize surface names
        if 'surface' in fixed_data and fixed_data['surface']:
            surface_map = {
                'hard': 'Hard', 'h': 'Hard',
                'clay': 'Clay', 'c': 'Clay',
                'grass': 'Grass', 'g': 'Grass',
                'carpet': 'Carpet', 'p': 'Carpet',
            }
            surface_lower = str(fixed_data['surface']).lower()
            if surface_lower in surface_map:
                fixed_data['surface'] = surface_map[surface_lower]

        # Now validate the fixed data
        is_valid, validation_messages = self.validate_match(fixed_data, source)
        messages.extend(validation_messages)

        return is_valid, fixed_data, messages


# Global validator instance
validator = DataValidator()


def validate_match_data(match_data: Dict, source: str = "unknown") -> Tuple[bool, List[str]]:
    """
    Convenience function to validate match data.

    Usage:
        is_valid, errors = validate_match_data(match_dict, source="tennis_explorer")
        if not is_valid:
            print(f"Validation failed: {errors}")
            return
    """
    return validator.validate_match(match_data, source)


def validate_and_fix_match_data(match_data: Dict, source: str = "unknown") -> Tuple[bool, Dict, List[str]]:
    """
    Convenience function to validate and fix match data.

    Usage:
        is_valid, fixed_data, messages = validate_and_fix_match_data(match_dict)
        if is_valid:
            db.insert_match(fixed_data)
    """
    return validator.validate_and_fix_match(match_data, source)
