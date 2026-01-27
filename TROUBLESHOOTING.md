# Tennis Betting System - Troubleshooting Guide

Common issues and how to resolve them.

---

## Betfair Issues

### "Missing credentials" error

**Symptom:** Cannot capture odds from Betfair.

**Cause:** Betfair API credentials not configured.

**Solution:**
1. Create `credentials.json` in the data folder:
   - Dev: `<project>/data/credentials.json`
   - Installed: `C:/Users/Public/Documents/Tennis Betting System/data/credentials.json`

2. Format:
```json
{
  "username": "your_betfair_username",
  "password": "your_betfair_password",
  "app_key": "your_app_key"
}
```

3. Get an app key from [Betfair Developer Portal](https://developer.betfair.com/)

---

### No matches returned from Betfair

**Symptom:** Capture completes but shows 0 matches.

**Possible causes:**
1. No tennis events currently live on Betfair
2. Session expired - try capturing again
3. API rate limiting - wait a few minutes
4. All markets filtered by £100 minimum liquidity (thin markets)

---

### Matches showing "SKIP" status

**Symptom:** Matches captured but marked as SKIP.

**Cause:** Betfair odds are worse than Pinnacle by >15%.

**This is expected behavior:** The system compares Betfair odds against Pinnacle (sharp bookmaker). When Betfair offers worse value, the bet is flagged. Only "GOOD VALUE" or "CAUTION" matches should be bet on.

---

## The Odds API Issues

### Pinnacle comparison not working

**Symptom:** No Pinnacle odds shown for captured matches.

**Checklist:**
1. Is the API key configured in `credentials.json`?
   ```json
   {
     "odds_api_key": "YOUR_API_KEY"
   }
   ```
2. Have you exceeded the API quota? (Free tier: 500 requests/month)
3. Is the match a tennis match covered by the API?
4. Check network connectivity

---

### "API quota exhausted" message

**Symptom:** Pinnacle comparison stops working mid-month.

**Cause:** Free tier has 500 requests/month limit.

**Solutions:**
1. Wait until next month (quota resets)
2. Upgrade to paid API tier
3. Continue betting without Pinnacle comparison (risky)

**Note:** The 15-minute cache helps preserve quota. Avoid rapid re-captures.

---

## Player Matching Issues

### "Player unknown" / "P1 unknown"

**Symptom:** Match shows but one or both players marked as unknown.

**Cause:** Name matching failed between Betfair name and database.

**Solution:**
1. Open `data/name_mappings.json`
2. Find the entry with the Betfair name
3. Look up the correct player ID in the database
4. Update the mapping:
```json
{
  "Betfair Name": 12345678
}
```
5. Restart the app

**Finding player IDs:**
- Use the app's player search
- Or query the database: `SELECT id, name FROM players WHERE name LIKE '%Smith%'`

---

### Wrong player matched

**Symptom:** Analysis shows wrong opponent or stats don't match.

**Cause:** Name matcher picked wrong player (common with similar names).

**Solution:**
1. Find the Betfair name in `name_mappings.json`
2. Correct the player ID
3. Restart the app

---

## Database Issues

### "No matches found" for a player

**Symptom:** Player exists but shows no match history.

**Possible causes:**

1. **Matches not imported yet**
   - Run a data refresh to import matches

2. **Corrupt data (winner_id = loser_id)**
   - Check: `SELECT COUNT(*) FROM matches WHERE winner_id = loser_id`
   - Fix: `DELETE FROM matches WHERE winner_id = loser_id` then re-import

3. **Wrong database**
   - Dev uses: `<project>/data/tennis_betting.db`
   - Installed uses: `C:/Users/Public/Documents/Tennis Betting System/data/tennis_betting.db`
   - Make sure you're looking at the right one

---

### Blank tournament names

**Symptom:** Matches show but tournament field is empty.

**Cause:** Legacy data from before column name fix (v1.1.0).

**Solution:**
1. Delete matches with blank tournaments:
   ```sql
   DELETE FROM matches WHERE tournament IS NULL OR tournament = ''
   ```
2. Re-run scraper to re-import

Or just ignore - doesn't affect functionality significantly.

---

### Database locked

**Symptom:** "database is locked" error.

**Cause:** Another process has the database open.

**Solution:**
1. Close all instances of the app
2. Check for Python processes: `taskkill /f /im python.exe`
3. Try again

---

## Scraper Issues

### Scraper returns 0 matches

**Symptom:** Import completes but nothing imported.

**Possible causes:**

1. **HTML structure changed**
   - Tennis Explorer may have updated their site
   - Check `tennis_explorer_scraper.py` parsing logic

2. **Player not found in rankings**
   - Scraper uses ranking pages to find players
   - Very low-ranked players may not be found

3. **Rate limiting**
   - Wait a few minutes between scrape attempts

---

### Wrong dates on matches

**Symptom:** Match dates are wrong (e.g., 2025 instead of 2026).

**Cause:** Year boundary parsing issue for January tournaments.

**Fixed in v1.1.0.** If still occurring:
1. Check `tennis_explorer_scraper.py` date parsing
2. Tournament pages use previous year in URL for January events

---

## Discord Notification Issues

### Notifications not sending

**Symptom:** Actions complete but no Discord message.

**Checklist:**
1. Is webhook URL configured? (Bet Tracker > Settings)
2. Is the URL correct? (Test with "Test Webhook" button)
3. Is the Discord channel/server active?
4. Check Windows firewall isn't blocking

---

### Test webhook fails

**Symptom:** "Failed to send test message"

**Possible causes:**
1. Invalid webhook URL - regenerate in Discord
2. Webhook deleted - create a new one
3. Network issue - check internet connection
4. Discord API down - try again later

---

## UI Issues

### Window appears behind other windows

**Symptom:** After an action, the window goes behind.

**Solution:** This is fixed in v1.1.0. Update to latest version.

---

### Bet tracker shows wrong data

**Symptom:** Stats don't match actual bets.

**Solution:**
1. Click "Refresh" button
2. If still wrong, check database directly:
   ```sql
   SELECT * FROM bets ORDER BY created_at DESC LIMIT 10
   ```

---

## Build Issues

### PyInstaller fails

**Symptom:** `pyinstaller` command fails during build.

**Common fixes:**
1. Run as administrator
2. Close OneDrive sync temporarily
3. Delete `build/` and `dist/` folders, try again
4. Check all imports resolve correctly

---

### OneDrive file locks

**Symptom:** Cannot delete or overwrite files in `dist/`.

**Solution:**
1. Pause OneDrive sync
2. Or build to a temp folder:
   ```bash
   pyinstaller --distpath C:\Temp\dist TennisBetting.spec
   ```
3. Copy files after OneDrive releases locks

---

## Performance Issues

### App is slow to start

**Cause:** Large database or slow disk.

**Solutions:**
1. The database grows over time - this is normal
2. Consider SSD if using HDD
3. Close other applications

---

### Analysis takes too long

**Cause:** Many matches to analyze or slow queries.

**Solutions:**
1. Ensure database indexes exist (run `database.py` standalone to create)
2. Reduce `FORM_SETTINGS["max_matches"]` in config
3. Analyze fewer matches at once

---

## Getting Help

If you can't resolve an issue:

1. **Check session logs** - Previous fixes may apply
2. **Check the database** - Use SQLite browser to inspect data
3. **Enable debug output** - Add print statements to problematic code
4. **Document the issue** - Note exact error messages and steps to reproduce
