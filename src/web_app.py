"""
Tennis Betting System - Progressive Web App
Mobile-friendly web interface with TRUE offline support
"""

import os
import sys
import json
from pathlib import Path

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, render_template_string, jsonify, request, redirect, url_for, send_from_directory
from datetime import datetime
import threading

from config import DB_PATH, SURFACES
from database import db
from match_analyzer import MatchAnalyzer

app = Flask(__name__, static_folder='static')
analyzer = MatchAnalyzer()

# ============================================================================
# HTML TEMPLATES (PWA-Enabled with Offline-First JavaScript)
# ============================================================================

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="theme-color" content="#6366f1">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="Tennis Bets">
    <link rel="manifest" href="/manifest.json">
    <link rel="apple-touch-icon" href="/icon-192.png">
    <title>Tennis Betting System</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #fff;
            min-height: 100vh;
            padding-bottom: 80px;
        }
        .container { max-width: 600px; margin: 0 auto; padding: 15px; }

        /* Header */
        .header {
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            padding: 20px 15px;
            text-align: center;
            margin-bottom: 20px;
            border-radius: 0 0 20px 20px;
            position: relative;
        }
        .header h1 { font-size: 1.5rem; margin-bottom: 5px; }
        .header p { font-size: 0.85rem; opacity: 0.9; }

        /* Sync Status */
        .sync-status {
            position: absolute;
            top: 10px;
            right: 15px;
            font-size: 0.7rem;
            padding: 4px 8px;
            border-radius: 10px;
            background: rgba(255,255,255,0.2);
        }
        .sync-status.online { background: rgba(76, 175, 80, 0.3); }
        .sync-status.offline { background: rgba(244, 67, 54, 0.3); }
        .sync-status.syncing { background: rgba(255, 152, 0, 0.3); animation: pulse 1s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }

        /* Navigation */
        .nav {
            display: flex;
            justify-content: space-around;
            background: #2d2d3d;
            padding: 10px;
            border-radius: 15px;
            margin-bottom: 20px;
        }
        .nav a {
            color: #b0b0b0;
            text-decoration: none;
            font-size: 0.8rem;
            padding: 8px 12px;
            border-radius: 10px;
            transition: all 0.2s;
        }
        .nav a.active, .nav a:hover {
            background: #6366f1;
            color: white;
        }

        /* Cards */
        .card {
            background: #2d2d3d;
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 15px;
        }
        .card-title {
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 10px;
            color: #4fc3f7;
        }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: #2d2d3d;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
        }
        .stat-value {
            font-size: 1.8rem;
            font-weight: bold;
            color: #4fc3f7;
        }
        .stat-label {
            font-size: 0.75rem;
            color: #888;
            margin-top: 5px;
        }

        /* Match Card */
        .match-card {
            background: #2d2d3d;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .match-header {
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: #888;
            margin-bottom: 10px;
        }
        .match-players {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .player {
            flex: 1;
            text-align: center;
        }
        .player-name {
            font-weight: 600;
            font-size: 0.9rem;
            margin-bottom: 5px;
        }
        .player-odds {
            font-size: 1.2rem;
            color: #4caf50;
            font-weight: bold;
        }
        .vs {
            padding: 0 10px;
            color: #666;
            font-size: 0.8rem;
        }
        .match-analysis {
            display: flex;
            justify-content: space-between;
            padding-top: 10px;
            border-top: 1px solid #3d3d4d;
            font-size: 0.8rem;
        }
        .prob { color: #4fc3f7; }
        .ev-positive { color: #4caf50; }
        .ev-negative { color: #f44336; }

        /* Buttons */
        .btn {
            display: inline-block;
            padding: 12px 24px;
            background: #6366f1;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            text-decoration: none;
            text-align: center;
            width: 100%;
            margin-top: 10px;
        }
        .btn:hover { background: #5558e3; }
        .btn:active { transform: scale(0.98); }
        .btn-success { background: #4caf50; }
        .btn-warning { background: #ff9800; }
        .btn-sync { background: linear-gradient(135deg, #00bcd4, #009688); }
        .btn-small {
            padding: 8px 16px;
            font-size: 0.8rem;
            width: auto;
        }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }

        /* Forms */
        .form-group { margin-bottom: 15px; }
        .form-label {
            display: block;
            font-size: 0.85rem;
            color: #888;
            margin-bottom: 5px;
        }
        .form-input {
            width: 100%;
            padding: 12px;
            background: #1e1e2e;
            border: 1px solid #3d3d4d;
            border-radius: 10px;
            color: white;
            font-size: 1rem;
        }
        .form-input:focus {
            outline: none;
            border-color: #6366f1;
        }

        /* Bet row */
        .bet-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: #1e1e2e;
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 0.85rem;
        }
        .bet-info { flex: 1; }
        .bet-result {
            padding: 4px 10px;
            border-radius: 5px;
            font-weight: 600;
            font-size: 0.75rem;
        }
        .bet-win { background: #4caf50; }
        .bet-loss { background: #f44336; }
        .bet-pending { background: #666; }

        /* Empty state */
        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: #666;
        }
        .empty-state p { margin-top: 10px; }

        /* Surface badge */
        .surface-badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.7rem;
            font-weight: 600;
            text-transform: capitalize;
        }
        .surface-hard { background: #3498db; }
        .surface-clay { background: #e67e22; }
        .surface-grass { background: #27ae60; }

        /* Value bet highlight */
        .value-bet-box {
            margin-top: 10px;
            padding: 10px;
            background: #1e1e2e;
            border-radius: 8px;
            border-left: 3px solid #4caf50;
        }

        /* Sync banner */
        .sync-banner {
            background: linear-gradient(135deg, #00bcd4, #009688);
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 15px;
            text-align: center;
        }
        .sync-banner p {
            font-size: 0.85rem;
            margin-bottom: 10px;
        }

        /* Offline banner */
        .offline-banner {
            background: linear-gradient(135deg, #ff9800, #f57c00);
            padding: 10px 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            text-align: center;
            font-size: 0.85rem;
            display: none;
        }
        .offline-banner.show { display: block; }

        /* Install prompt */
        .install-prompt {
            background: #2d2d3d;
            border: 2px dashed #6366f1;
            padding: 15px;
            border-radius: 12px;
            margin-bottom: 15px;
            text-align: center;
            display: none;
        }
        .install-prompt.show { display: block; }

        /* Toast notification */
        .toast {
            position: fixed;
            bottom: 90px;
            left: 50%;
            transform: translateX(-50%);
            background: #333;
            color: white;
            padding: 12px 24px;
            border-radius: 25px;
            font-size: 0.85rem;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s;
        }
        .toast.show { opacity: 1; }

        /* Loading spinner */
        .loading {
            text-align: center;
            padding: 40px;
            color: #888;
        }
        .spinner {
            width: 40px;
            height: 40px;
            border: 3px solid #3d3d4d;
            border-top-color: #6366f1;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 15px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="header">
        <h1>Tennis Betting</h1>
        <p>ATP Match Analysis & Value Betting</p>
        <div class="sync-status" id="syncStatus">Checking...</div>
    </div>

    <div class="container">
        <div class="offline-banner" id="offlineBanner">
            You're viewing cached data (offline mode)
        </div>

        <nav class="nav">
            <a href="/" class="{{ 'active' if page == 'home' else '' }}">Home</a>
            <a href="/matches" class="{{ 'active' if page == 'matches' else '' }}">Matches</a>
            <a href="/bets" class="{{ 'active' if page == 'bets' else '' }}">Bets</a>
            <a href="/sync" class="{{ 'active' if page == 'sync' else '' }}">Sync</a>
        </nav>

        <div id="content">
            {{ content | safe }}
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
    // ========================================================================
    // IndexedDB - Local Storage
    // ========================================================================
    const DB_NAME = 'TennisBettingDB';
    const DB_VERSION = 2;
    let localDB = null;

    async function initDB() {
        return new Promise((resolve, reject) => {
            const request = indexedDB.open(DB_NAME, DB_VERSION);

            request.onerror = () => reject(request.error);
            request.onsuccess = () => {
                localDB = request.result;
                resolve(localDB);
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Matches store
                if (!db.objectStoreNames.contains('matches')) {
                    const matchStore = db.createObjectStore('matches', { keyPath: 'id' });
                    matchStore.createIndex('date', 'date', { unique: false });
                }

                // Bets store
                if (!db.objectStoreNames.contains('bets')) {
                    const betStore = db.createObjectStore('bets', { keyPath: 'id', autoIncrement: true });
                    betStore.createIndex('date', 'date', { unique: false });
                    betStore.createIndex('synced', 'synced', { unique: false });
                }

                // Stats store
                if (!db.objectStoreNames.contains('stats')) {
                    db.createObjectStore('stats', { keyPath: 'key' });
                }

                // Meta store (for sync info)
                if (!db.objectStoreNames.contains('meta')) {
                    db.createObjectStore('meta', { keyPath: 'key' });
                }
            };
        });
    }

    async function saveToLocal(storeName, data) {
        if (!localDB) await initDB();
        return new Promise((resolve, reject) => {
            const tx = localDB.transaction(storeName, 'readwrite');
            const store = tx.objectStore(storeName);

            if (Array.isArray(data)) {
                data.forEach(item => store.put(item));
            } else {
                store.put(data);
            }

            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async function getFromLocal(storeName) {
        if (!localDB) await initDB();
        return new Promise((resolve, reject) => {
            const tx = localDB.transaction(storeName, 'readonly');
            const store = tx.objectStore(storeName);
            const request = store.getAll();

            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
    }

    async function clearStore(storeName) {
        if (!localDB) await initDB();
        return new Promise((resolve, reject) => {
            const tx = localDB.transaction(storeName, 'readwrite');
            const store = tx.objectStore(storeName);
            store.clear();
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    }

    async function getLocalStats() {
        try {
            const stats = await getFromLocal('stats');
            return stats.find(s => s.key === 'main') || null;
        } catch {
            return null;
        }
    }

    // ========================================================================
    // Network Status
    // ========================================================================
    let isOnline = navigator.onLine;
    let serverReachable = false;

    async function checkServerConnection() {
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 3000);

            const response = await fetch('/api/ping', {
                method: 'GET',
                cache: 'no-store',
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            serverReachable = response.ok;
        } catch {
            serverReachable = false;
        }
        updateSyncStatus();
        return serverReachable;
    }

    function updateSyncStatus() {
        const statusEl = document.getElementById('syncStatus');
        const offlineBanner = document.getElementById('offlineBanner');

        if (!statusEl) return;

        if (serverReachable) {
            statusEl.textContent = 'Online';
            statusEl.className = 'sync-status online';
            if (offlineBanner) offlineBanner.classList.remove('show');
        } else if (isOnline) {
            statusEl.textContent = 'Server Offline';
            statusEl.className = 'sync-status offline';
            if (offlineBanner) offlineBanner.classList.add('show');
        } else {
            statusEl.textContent = 'Offline';
            statusEl.className = 'sync-status offline';
            if (offlineBanner) offlineBanner.classList.add('show');
        }
    }

    window.addEventListener('online', () => {
        isOnline = true;
        checkServerConnection();
    });

    window.addEventListener('offline', () => {
        isOnline = false;
        serverReachable = false;
        updateSyncStatus();
    });

    // ========================================================================
    // Sync Functions
    // ========================================================================
    async function syncWithServer() {
        if (!serverReachable) {
            showToast('Cannot sync - server not reachable');
            return false;
        }

        const statusEl = document.getElementById('syncStatus');
        if (statusEl) {
            statusEl.textContent = 'Syncing...';
            statusEl.className = 'sync-status syncing';
        }

        try {
            const response = await fetch('/api/sync/pull');
            if (!response.ok) throw new Error('Sync failed');

            const data = await response.json();

            // Save to local storage
            if (data.matches) {
                await clearStore('matches');
                await saveToLocal('matches', data.matches);
            }
            if (data.bets) {
                await clearStore('bets');
                await saveToLocal('bets', data.bets.map(b => ({...b, synced: true})));
            }
            if (data.stats) {
                await saveToLocal('stats', { key: 'main', ...data.stats });
            }

            // Save sync timestamp
            await saveToLocal('meta', {
                key: 'lastSync',
                timestamp: new Date().toISOString(),
                serverIP: window.location.hostname
            });

            showToast('Sync complete! Data saved for offline use.');
            updateSyncStatus();
            return true;
        } catch (error) {
            console.error('Sync error:', error);
            showToast('Sync failed: ' + error.message);
            updateSyncStatus();
            return false;
        }
    }

    async function pushBetsToServer() {
        if (!serverReachable) {
            showToast('Cannot sync - server not reachable');
            return false;
        }

        try {
            const bets = await getFromLocal('bets');
            const unsyncedBets = bets.filter(b => !b.synced);

            if (unsyncedBets.length === 0) {
                showToast('No new bets to sync');
                return true;
            }

            const response = await fetch('/api/sync/push', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bets: unsyncedBets })
            });

            if (!response.ok) throw new Error('Push failed');

            // Mark as synced
            for (const bet of unsyncedBets) {
                bet.synced = true;
                await saveToLocal('bets', bet);
            }

            showToast(`Synced ${unsyncedBets.length} bets to desktop`);
            return true;
        } catch (error) {
            console.error('Push error:', error);
            showToast('Push failed: ' + error.message);
            return false;
        }
    }

    async function getLastSyncTime() {
        try {
            const meta = await getFromLocal('meta');
            const lastSync = meta.find(m => m.key === 'lastSync');
            return lastSync ? new Date(lastSync.timestamp) : null;
        } catch {
            return null;
        }
    }

    // ========================================================================
    // Client-Side Rendering for Offline Mode
    // ========================================================================

    function getSurfaceClass(surface) {
        if (!surface) return '';
        const s = surface.toLowerCase();
        if (s.includes('hard')) return 'surface-hard';
        if (s.includes('clay')) return 'surface-clay';
        if (s.includes('grass')) return 'surface-grass';
        return '';
    }

    async function renderMatchesFromLocal() {
        const container = document.getElementById('matchesContainer');
        if (!container) return;

        try {
            const matches = await getFromLocal('matches');

            if (!matches || matches.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No matches saved offline</p>
                        <p style="font-size: 0.8rem; margin-top: 10px;">Connect to home WiFi and sync to download matches</p>
                    </div>`;
                return;
            }

            let html = '';
            for (const match of matches) {
                const analysis = match.analysis || {};
                const p1Last = match.player1_name ? match.player1_name.split(' ').pop() : '';
                const p2Last = match.player2_name ? match.player2_name.split(' ').pop() : '';

                html += `
                <div class="match-card">
                    <div class="match-header">
                        <span>${match.tournament || 'Tournament'}</span>
                        <span class="surface-badge ${getSurfaceClass(match.surface)}">${match.surface || 'Hard'}</span>
                    </div>
                    <div class="match-players">
                        <div class="player">
                            <div class="player-name">${match.player1_name || 'Player 1'}</div>
                            <div class="player-odds">${match.player1_odds || '-'}</div>
                        </div>
                        <div class="vs">vs</div>
                        <div class="player">
                            <div class="player-name">${match.player2_name || 'Player 2'}</div>
                            <div class="player-odds">${match.player2_odds || '-'}</div>
                        </div>
                    </div>
                    ${analysis.p1_prob ? `
                    <div class="match-analysis">
                        <span class="prob">${p1Last}: ${analysis.p1_prob}%</span>
                        <span class="prob">${p2Last}: ${analysis.p2_prob}%</span>
                    </div>` : ''}
                    ${analysis.value_bet ? `
                    <div class="value-bet-box">
                        <span class="ev-positive">Value: ${analysis.value_bet.player} @ ${analysis.value_bet.odds} (+${analysis.value_bet.ev}% EV)</span>
                    </div>` : ''}
                </div>`;
            }

            container.innerHTML = html;
        } catch (error) {
            console.error('Error rendering matches:', error);
            container.innerHTML = '<div class="empty-state"><p>Error loading matches</p></div>';
        }
    }

    async function renderBetsFromLocal() {
        const container = document.getElementById('betsContainer');
        const statsContainer = document.getElementById('betsStats');
        if (!container) return;

        try {
            const bets = await getFromLocal('bets');
            const stats = await getLocalStats();

            // Update stats
            if (statsContainer && stats) {
                const profit = stats.profit || 0;
                statsContainer.innerHTML = `
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #4caf50;">${stats.wins || 0}</div>
                        <div style="font-size: 0.75rem; color: #888;">Wins</div>
                    </div>
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #f44336;">${stats.losses || 0}</div>
                        <div style="font-size: 0.75rem; color: #888;">Losses</div>
                    </div>
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: ${profit >= 0 ? '#4caf50' : '#f44336'};">${profit >= 0 ? '+' : ''}${profit.toFixed(2)}</div>
                        <div style="font-size: 0.75rem; color: #888;">Profit</div>
                    </div>`;
            }

            if (!bets || bets.length === 0) {
                container.innerHTML = `
                    <div class="empty-state">
                        <p>No bets tracked yet</p>
                    </div>`;
                return;
            }

            let html = '';
            for (const bet of bets.slice(0, 20)) {
                const resultClass = bet.result ? `bet-${bet.result.toLowerCase()}` : 'bet-pending';
                html += `
                <div class="bet-row">
                    <div class="bet-info">
                        <div style="font-weight: 600;">${bet.selection || 'Selection'}</div>
                        <div style="color: #888; font-size: 0.75rem;">${bet.match_description || ''} @ ${bet.odds || ''}</div>
                    </div>
                    <span class="bet-result ${resultClass}">
                        ${bet.result || 'Pending'}
                    </span>
                </div>`;
            }

            container.innerHTML = html;
        } catch (error) {
            console.error('Error rendering bets:', error);
            container.innerHTML = '<div class="empty-state"><p>Error loading bets</p></div>';
        }
    }

    async function renderHomeStats() {
        const statsGrid = document.getElementById('homeStats');
        if (!statsGrid) return;

        try {
            const stats = await getLocalStats();
            if (stats) {
                const roi = stats.roi || 0;
                statsGrid.innerHTML = `
                    <div class="stat-card">
                        <div class="stat-value">${(stats.players || 0).toLocaleString()}</div>
                        <div class="stat-label">Players</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${(stats.matches || 0).toLocaleString()}</div>
                        <div class="stat-label">Matches</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${stats.total_bets || 0}</div>
                        <div class="stat-label">Bets</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value" style="color: ${roi >= 0 ? '#4caf50' : '#f44336'};">${roi >= 0 ? '+' : ''}${roi.toFixed(1)}%</div>
                        <div class="stat-label">ROI</div>
                    </div>`;
            }
        } catch (error) {
            console.error('Error rendering home stats:', error);
        }
    }

    // ========================================================================
    // Toast Notifications
    // ========================================================================
    function showToast(message, duration = 3000) {
        const toast = document.getElementById('toast');
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), duration);
    }

    // ========================================================================
    // PWA Install
    // ========================================================================
    let deferredPrompt = null;

    window.addEventListener('beforeinstallprompt', (e) => {
        e.preventDefault();
        deferredPrompt = e;
        const installPrompt = document.getElementById('installPrompt');
        if (installPrompt) installPrompt.classList.add('show');
    });

    async function installApp() {
        if (!deferredPrompt) return;
        deferredPrompt.prompt();
        const result = await deferredPrompt.userChoice;
        if (result.outcome === 'accepted') {
            showToast('App installed!');
        }
        deferredPrompt = null;
        const installPrompt = document.getElementById('installPrompt');
        if (installPrompt) installPrompt.classList.remove('show');
    }

    // ========================================================================
    // Service Worker
    // ========================================================================
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js')
            .then(reg => console.log('SW registered'))
            .catch(err => console.log('SW registration failed:', err));
    }

    // ========================================================================
    // Initialize
    // ========================================================================
    document.addEventListener('DOMContentLoaded', async () => {
        await initDB();

        // Check server first
        const online = await checkServerConnection();

        // If offline, render from local data
        if (!online) {
            // Render local data for current page
            await renderHomeStats();
            await renderMatchesFromLocal();
            await renderBetsFromLocal();
        }

        // Check periodically
        setInterval(checkServerConnection, 30000);
    });
    </script>
</body>
</html>
"""

HOME_CONTENT = """
<div id="installPrompt" class="install-prompt">
    <p style="font-size: 0.9rem; margin-bottom: 10px;">Install this app on your phone for offline access!</p>
    <button class="btn btn-small" onclick="installApp()">Install App</button>
</div>

<div class="stats-grid" id="homeStats">
    <div class="stat-card">
        <div class="stat-value">{{ stats.players }}</div>
        <div class="stat-label">Players</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.matches }}</div>
        <div class="stat-label">Matches</div>
    </div>
    <div class="stat-card">
        <div class="stat-value">{{ stats.bets }}</div>
        <div class="stat-label">Bets</div>
    </div>
    <div class="stat-card">
        <div class="stat-value" style="color: {{ '#4caf50' if stats.roi_positive else '#f44336' }}">{{ stats.roi }}%</div>
        <div class="stat-label">ROI</div>
    </div>
</div>

<div class="card">
    <div class="card-title">Quick Actions</div>
    <a href="/matches" class="btn">View Matches</a>
    <a href="/bets" class="btn btn-success">Track Bets</a>
    <a href="/download-offline" class="btn" style="background: linear-gradient(135deg, #ff9800, #f57c00);">Download Offline App</a>
</div>

<div class="card">
    <div class="card-title">Offline Usage</div>
    <p style="font-size: 0.85rem; color: #888; line-height: 1.6;">
        1. Connect to home WiFi and tap <b>Sync</b><br>
        2. Data is saved to your phone<br>
        3. View matches anywhere - even offline!
    </p>
</div>
"""

MATCHES_CONTENT = """
<div class="card">
    <div class="card-title">Upcoming Matches</div>
</div>

<div id="matchesContainer">
{% if matches %}
    {% for match in matches %}
    <div class="match-card">
        <div class="match-header">
            <span>{{ match.tournament }}</span>
            <span class="surface-badge surface-{{ match.surface|lower }}">{{ match.surface }}</span>
        </div>
        <div class="match-players">
            <div class="player">
                <div class="player-name">{{ match.player1_name }}</div>
                <div class="player-odds">{{ match.player1_odds or '-' }}</div>
            </div>
            <div class="vs">vs</div>
            <div class="player">
                <div class="player-name">{{ match.player2_name }}</div>
                <div class="player-odds">{{ match.player2_odds or '-' }}</div>
            </div>
        </div>
        {% if match.analysis %}
        <div class="match-analysis">
            <span class="prob">{{ match.analysis.p1_name }}: {{ match.analysis.p1_prob }}%</span>
            <span class="prob">{{ match.analysis.p2_name }}: {{ match.analysis.p2_prob }}%</span>
        </div>
        {% if match.analysis.value_bet %}
        <div class="value-bet-box">
            <span class="ev-positive">Value: {{ match.analysis.value_bet.player }} @ {{ match.analysis.value_bet.odds }} (+{{ match.analysis.value_bet.ev }}% EV)</span>
        </div>
        {% endif %}
        {% endif %}
    </div>
    {% endfor %}
{% else %}
    <div class="empty-state">
        <p>No matches available</p>
        <a href="/sync" class="btn btn-sync" style="width: auto; margin-top: 15px;">Sync with Desktop</a>
    </div>
{% endif %}
</div>

<script>
// Load from IndexedDB if server data not available
document.addEventListener('DOMContentLoaded', async () => {
    const container = document.getElementById('matchesContainer');
    const isEmpty = container.querySelector('.empty-state') !== null;

    if (isEmpty || !serverReachable) {
        await renderMatchesFromLocal();
    }
});
</script>
"""

BETS_CONTENT = """
<div class="card">
    <div class="card-title">Bet Tracker</div>
    <div id="betsStats" style="display: flex; gap: 10px; margin-bottom: 15px;">
        <div style="flex: 1; text-align: center;">
            <div style="font-size: 1.5rem; font-weight: bold; color: #4caf50;">{{ stats.wins }}</div>
            <div style="font-size: 0.75rem; color: #888;">Wins</div>
        </div>
        <div style="flex: 1; text-align: center;">
            <div style="font-size: 1.5rem; font-weight: bold; color: #f44336;">{{ stats.losses }}</div>
            <div style="font-size: 0.75rem; color: #888;">Losses</div>
        </div>
        <div style="flex: 1; text-align: center;">
            <div style="font-size: 1.5rem; font-weight: bold; color: {{ '#4caf50' if stats.profit_positive else '#f44336' }}">{{ stats.profit }}</div>
            <div style="font-size: 0.75rem; color: #888;">Profit</div>
        </div>
    </div>
</div>

<div id="betsContainer">
{% if bets %}
    {% for bet in bets %}
    <div class="bet-row">
        <div class="bet-info">
            <div style="font-weight: 600;">{{ bet.selection }}</div>
            <div style="color: #888; font-size: 0.75rem;">{{ bet.match_description }} @ {{ bet.odds }}</div>
        </div>
        <span class="bet-result bet-{{ bet.result|lower if bet.result else 'pending' }}">
            {{ bet.result or 'Pending' }}
        </span>
    </div>
    {% endfor %}
{% else %}
    <div class="empty-state">
        <p>No bets tracked yet</p>
    </div>
{% endif %}
</div>

<a href="/add-bet" class="btn btn-success">Add Bet</a>

<script>
// Load from IndexedDB if needed
document.addEventListener('DOMContentLoaded', async () => {
    if (!serverReachable) {
        await renderBetsFromLocal();
    }
});
</script>
"""

ADD_BET_CONTENT = """
<div class="card">
    <div class="card-title">Add New Bet</div>
    <form id="addBetForm">
        <div class="form-group">
            <label class="form-label">Match</label>
            <input type="text" name="match_description" id="match_description" class="form-input" placeholder="e.g., Sinner vs Alcaraz" required>
        </div>
        <div class="form-group">
            <label class="form-label">Selection</label>
            <input type="text" name="selection" id="selection" class="form-input" placeholder="e.g., Sinner" required>
        </div>
        <div class="form-group">
            <label class="form-label">Odds</label>
            <input type="number" step="0.01" name="odds" id="odds" class="form-input" placeholder="e.g., 1.85" required>
        </div>
        <div class="form-group">
            <label class="form-label">Stake</label>
            <input type="number" step="0.01" name="stake" id="stake" class="form-input" placeholder="e.g., 10.00" required>
        </div>
        <button type="submit" class="btn btn-success">Add Bet</button>
        <a href="/bets" class="btn" style="background: #666;">Cancel</a>
    </form>
</div>

<script>
document.getElementById('addBetForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const bet = {
        id: Date.now(),
        date: new Date().toISOString().split('T')[0],
        match_description: document.getElementById('match_description').value,
        selection: document.getElementById('selection').value,
        odds: parseFloat(document.getElementById('odds').value),
        stake: parseFloat(document.getElementById('stake').value),
        market: 'Match Winner',
        result: null,
        synced: false
    };

    try {
        // Save to IndexedDB
        await saveToLocal('bets', bet);
        showToast('Bet saved locally');

        // Try to save to server if online
        if (serverReachable) {
            try {
                await fetch('/api/sync/push', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bets: [bet] })
                });
                bet.synced = true;
                await saveToLocal('bets', bet);
            } catch {}
        }

        window.location.href = '/bets';
    } catch (error) {
        showToast('Error saving bet');
        console.error(error);
    }
});
</script>
"""

SYNC_CONTENT = """
<div class="sync-banner">
    <h3 style="margin-bottom: 5px;">Take It With You</h3>
    <p>Download an offline version to view anywhere</p>
</div>

<div class="card" style="border: 2px solid #4caf50;">
    <div class="card-title" style="color: #4caf50;">Download Offline Version</div>
    <p style="font-size: 0.85rem; color: #888; margin-bottom: 15px;">
        Get a standalone file with all matches and analysis. Works without internet!
    </p>
    <a href="/download-offline" class="btn btn-success" style="text-decoration: none;">
        Download Offline App
    </a>
</div>

<div class="card">
    <div class="card-title">How It Works</div>
    <ol style="font-size: 0.85rem; color: #888; line-height: 1.8; padding-left: 20px;">
        <li>Tap "Download Offline App" above</li>
        <li>Save the file to your phone</li>
        <li>Open it anytime from your Downloads folder</li>
        <li>Works completely offline!</li>
        <li>Come back here to download updates</li>
    </ol>
</div>

<div class="card">
    <div class="card-title">Connection Status</div>
    <div class="bet-row">
        <span>Server</span>
        <span id="serverStatus" style="color: #888;">Checking...</span>
    </div>
</div>

<script>
document.addEventListener('DOMContentLoaded', async () => {
    const serverStatus = document.getElementById('serverStatus');
    const reachable = await checkServerConnection();
    serverStatus.textContent = reachable ? 'Connected' : 'Not reachable';
    serverStatus.style.color = reachable ? '#4caf50' : '#f44336';
});
</script>
"""

# ============================================================================
# STATIC FILE ROUTES
# ============================================================================

@app.route('/manifest.json')
def manifest():
    return send_from_directory(app.static_folder, 'manifest.json')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory(app.static_folder, 'service-worker.js')

@app.route('/icon-192.png')
def icon_192():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="192" height="192" viewBox="0 0 192 192">
        <rect width="192" height="192" rx="40" fill="#6366f1"/>
        <circle cx="96" cy="80" r="35" fill="#c8f026" stroke="#fff" stroke-width="3"/>
        <path d="M60 80 Q96 40 132 80 Q96 120 60 80" fill="none" stroke="#fff" stroke-width="3"/>
        <text x="96" y="160" text-anchor="middle" fill="#fff" font-size="24" font-family="Arial" font-weight="bold">TENNIS</text>
    </svg>'''
    from flask import Response
    return Response(svg, mimetype='image/svg+xml')

@app.route('/icon-512.png')
def icon_512():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
        <rect width="512" height="512" rx="100" fill="#6366f1"/>
        <circle cx="256" cy="200" r="90" fill="#c8f026" stroke="#fff" stroke-width="8"/>
        <path d="M150 200 Q256 90 362 200 Q256 310 150 200" fill="none" stroke="#fff" stroke-width="8"/>
        <text x="256" y="420" text-anchor="middle" fill="#fff" font-size="64" font-family="Arial" font-weight="bold">TENNIS</text>
    </svg>'''
    from flask import Response
    return Response(svg, mimetype='image/svg+xml')

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/ping')
def api_ping():
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})

@app.route('/download-offline')
def download_offline():
    """Generate a standalone HTML file with all data for true offline use."""
    try:
        # Get all data
        upcoming = db.get_upcoming_matches()
        for match in upcoming:
            if match.get('player1_id') and match.get('player2_id'):
                try:
                    result = analyzer.calculate_win_probability(
                        match['player1_id'],
                        match['player2_id'],
                        match.get('surface', 'Hard')
                    )
                    p1_last = match['player1_name'].split()[-1] if match.get('player1_name') else ''
                    p2_last = match['player2_name'].split()[-1] if match.get('player2_name') else ''
                    match['analysis'] = {
                        'p1_name': p1_last,
                        'p2_name': p2_last,
                        'p1_prob': round(result['p1_probability'] * 100),
                        'p2_prob': round(result['p2_probability'] * 100),
                    }
                    if match.get('player1_odds'):
                        ev = analyzer.find_value(result['p1_probability'], float(match['player1_odds']))
                        if ev and ev.get('expected_value', 0) > 0.05:
                            match['analysis']['value_bet'] = {
                                'player': match['player1_name'],
                                'odds': match['player1_odds'],
                                'ev': round(ev['expected_value'] * 100, 1)
                            }
                    if 'value_bet' not in match.get('analysis', {}) and match.get('player2_odds'):
                        ev = analyzer.find_value(result['p2_probability'], float(match['player2_odds']))
                        if ev and ev.get('expected_value', 0) > 0.05:
                            match['analysis']['value_bet'] = {
                                'player': match['player2_name'],
                                'odds': match['player2_odds'],
                                'ev': round(ev['expected_value'] * 100, 1)
                            }
                except:
                    pass

        bets = db.get_all_bets()
        db_stats = db.get_database_stats()
        bet_stats = db.get_betting_stats()

        # Generate standalone HTML
        html = generate_offline_html(upcoming, bets, db_stats, bet_stats)

        from flask import Response
        return Response(
            html,
            mimetype='text/html',
            headers={'Content-Disposition': f'attachment; filename=tennis_betting_{datetime.now().strftime("%Y%m%d")}.html'}
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_offline_html(matches, bets, db_stats, bet_stats):
    """Generate a complete standalone HTML file."""
    import json

    matches_json = json.dumps(matches, default=str)
    bets_json = json.dumps(bets, default=str)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <title>Tennis Betting - Offline</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1e1e2e;
            color: #fff;
            min-height: 100vh;
            padding-bottom: 80px;
        }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 15px; }}
        .header {{
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            padding: 20px 15px;
            text-align: center;
            margin-bottom: 20px;
            border-radius: 0 0 20px 20px;
        }}
        .header h1 {{ font-size: 1.5rem; margin-bottom: 5px; }}
        .header p {{ font-size: 0.85rem; opacity: 0.9; }}
        .offline-badge {{
            display: inline-block;
            background: rgba(255,152,0,0.3);
            padding: 4px 10px;
            border-radius: 10px;
            font-size: 0.7rem;
            margin-top: 8px;
        }}
        .nav {{
            display: flex;
            justify-content: space-around;
            background: #2d2d3d;
            padding: 10px;
            border-radius: 15px;
            margin-bottom: 20px;
        }}
        .nav button {{
            color: #b0b0b0;
            background: none;
            border: none;
            font-size: 0.85rem;
            padding: 8px 15px;
            border-radius: 10px;
            cursor: pointer;
        }}
        .nav button.active {{
            background: #6366f1;
            color: white;
        }}
        .card {{
            background: #2d2d3d;
            border-radius: 15px;
            padding: 15px;
            margin-bottom: 15px;
        }}
        .card-title {{
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 10px;
            color: #4fc3f7;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 20px;
        }}
        .stat-card {{
            background: #2d2d3d;
            border-radius: 12px;
            padding: 15px;
            text-align: center;
        }}
        .stat-value {{
            font-size: 1.8rem;
            font-weight: bold;
            color: #4fc3f7;
        }}
        .stat-label {{
            font-size: 0.75rem;
            color: #888;
            margin-top: 5px;
        }}
        .match-card {{
            background: #2d2d3d;
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 10px;
        }}
        .match-header {{
            display: flex;
            justify-content: space-between;
            font-size: 0.75rem;
            color: #888;
            margin-bottom: 10px;
        }}
        .match-players {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .player {{
            flex: 1;
            text-align: center;
        }}
        .player-name {{
            font-weight: 600;
            font-size: 0.9rem;
            margin-bottom: 5px;
        }}
        .player-odds {{
            font-size: 1.2rem;
            color: #4caf50;
            font-weight: bold;
        }}
        .vs {{
            padding: 0 10px;
            color: #666;
            font-size: 0.8rem;
        }}
        .match-analysis {{
            display: flex;
            justify-content: space-between;
            padding-top: 10px;
            border-top: 1px solid #3d3d4d;
            font-size: 0.8rem;
        }}
        .prob {{ color: #4fc3f7; }}
        .value-bet-box {{
            margin-top: 10px;
            padding: 10px;
            background: #1e1e2e;
            border-radius: 8px;
            border-left: 3px solid #4caf50;
        }}
        .ev-positive {{ color: #4caf50; }}
        .surface-badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.7rem;
            font-weight: 600;
        }}
        .surface-hard {{ background: #3498db; }}
        .surface-clay {{ background: #e67e22; }}
        .surface-grass {{ background: #27ae60; }}
        .bet-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: #1e1e2e;
            border-radius: 8px;
            margin-bottom: 8px;
            font-size: 0.85rem;
        }}
        .bet-info {{ flex: 1; }}
        .bet-result {{
            padding: 4px 10px;
            border-radius: 5px;
            font-weight: 600;
            font-size: 0.75rem;
        }}
        .bet-win {{ background: #4caf50; }}
        .bet-loss {{ background: #f44336; }}
        .bet-pending {{ background: #666; }}
        .page {{ display: none; }}
        .page.active {{ display: block; }}
        .empty-state {{
            text-align: center;
            padding: 40px 20px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Tennis Betting</h1>
        <p>ATP Match Analysis & Value Betting</p>
        <div class="offline-badge">Offline Version - {datetime.now().strftime("%d %b %Y %H:%M")}</div>
    </div>

    <div class="container">
        <nav class="nav">
            <button class="active" onclick="showPage('home')">Home</button>
            <button onclick="showPage('matches')">Matches</button>
            <button onclick="showPage('bets')">Bets</button>
        </nav>

        <!-- Home Page -->
        <div id="home" class="page active">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">{db_stats.get('total_players', 0):,}</div>
                    <div class="stat-label">Players</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{db_stats.get('total_matches', 0):,}</div>
                    <div class="stat-label">Matches</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{bet_stats.get('total_bets', 0) or 0}</div>
                    <div class="stat-label">Bets</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: {'#4caf50' if (bet_stats.get('roi', 0) or 0) >= 0 else '#f44336'};">{(bet_stats.get('roi', 0) or 0):+.1f}%</div>
                    <div class="stat-label">ROI</div>
                </div>
            </div>
            <div class="card">
                <div class="card-title">Offline Mode</div>
                <p style="font-size: 0.85rem; color: #888; line-height: 1.6;">
                    This is a snapshot of your tennis betting data.<br><br>
                    To update, connect to your home WiFi and download a new version from the web app.
                </p>
            </div>
        </div>

        <!-- Matches Page -->
        <div id="matches" class="page">
            <div class="card">
                <div class="card-title">Upcoming Matches</div>
            </div>
            <div id="matchesContainer"></div>
        </div>

        <!-- Bets Page -->
        <div id="bets" class="page">
            <div class="card">
                <div class="card-title">Bet Tracker</div>
                <div style="display: flex; gap: 10px; margin-bottom: 15px;">
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #4caf50;">{bet_stats.get('wins', 0) or 0}</div>
                        <div style="font-size: 0.75rem; color: #888;">Wins</div>
                    </div>
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: #f44336;">{bet_stats.get('losses', 0) or 0}</div>
                        <div style="font-size: 0.75rem; color: #888;">Losses</div>
                    </div>
                    <div style="flex: 1; text-align: center;">
                        <div style="font-size: 1.5rem; font-weight: bold; color: {'#4caf50' if (bet_stats.get('profit', 0) or 0) >= 0 else '#f44336'};">{(bet_stats.get('profit', 0) or 0):+.2f}</div>
                        <div style="font-size: 0.75rem; color: #888;">Profit</div>
                    </div>
                </div>
            </div>
            <div id="betsContainer"></div>
        </div>
    </div>

    <script>
    const MATCHES = {matches_json};
    const BETS = {bets_json};

    function showPage(pageId) {{
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        document.querySelectorAll('.nav button').forEach(b => b.classList.remove('active'));
        document.getElementById(pageId).classList.add('active');
        event.target.classList.add('active');
    }}

    function getSurfaceClass(surface) {{
        if (!surface) return '';
        const s = surface.toLowerCase();
        if (s.includes('hard')) return 'surface-hard';
        if (s.includes('clay')) return 'surface-clay';
        if (s.includes('grass')) return 'surface-grass';
        return '';
    }}

    function renderMatches() {{
        const container = document.getElementById('matchesContainer');
        if (!MATCHES || MATCHES.length === 0) {{
            container.innerHTML = '<div class="empty-state"><p>No matches available</p></div>';
            return;
        }}

        let html = '';
        for (const match of MATCHES) {{
            const analysis = match.analysis || {{}};
            html += `
            <div class="match-card">
                <div class="match-header">
                    <span>${{match.tournament || 'Tournament'}}</span>
                    <span class="surface-badge ${{getSurfaceClass(match.surface)}}">${{match.surface || 'Hard'}}</span>
                </div>
                <div class="match-players">
                    <div class="player">
                        <div class="player-name">${{match.player1_name || 'Player 1'}}</div>
                        <div class="player-odds">${{match.player1_odds || '-'}}</div>
                    </div>
                    <div class="vs">vs</div>
                    <div class="player">
                        <div class="player-name">${{match.player2_name || 'Player 2'}}</div>
                        <div class="player-odds">${{match.player2_odds || '-'}}</div>
                    </div>
                </div>
                ${{analysis.p1_prob ? `
                <div class="match-analysis">
                    <span class="prob">${{analysis.p1_name}}: ${{analysis.p1_prob}}%</span>
                    <span class="prob">${{analysis.p2_name}}: ${{analysis.p2_prob}}%</span>
                </div>` : ''}}
                ${{analysis.value_bet ? `
                <div class="value-bet-box">
                    <span class="ev-positive">Value: ${{analysis.value_bet.player}} @ ${{analysis.value_bet.odds}} (+${{analysis.value_bet.ev}}% EV)</span>
                </div>` : ''}}
            </div>`;
        }}
        container.innerHTML = html;
    }}

    function renderBets() {{
        const container = document.getElementById('betsContainer');
        if (!BETS || BETS.length === 0) {{
            container.innerHTML = '<div class="empty-state"><p>No bets tracked yet</p></div>';
            return;
        }}

        let html = '';
        for (const bet of BETS.slice(0, 20)) {{
            const resultClass = bet.result ? `bet-${{bet.result.toLowerCase()}}` : 'bet-pending';
            html += `
            <div class="bet-row">
                <div class="bet-info">
                    <div style="font-weight: 600;">${{bet.selection || 'Selection'}}</div>
                    <div style="color: #888; font-size: 0.75rem;">${{bet.match_description || ''}} @ ${{bet.odds || ''}}</div>
                </div>
                <span class="bet-result ${{resultClass}}">
                    ${{bet.result || 'Pending'}}
                </span>
            </div>`;
        }}
        container.innerHTML = html;
    }}

    // Initialize
    renderMatches();
    renderBets();
    </script>
</body>
</html>'''

@app.route('/api/sync/pull')
def api_sync_pull():
    """Pull all data for mobile sync."""
    try:
        # Get matches with analysis
        upcoming = db.get_upcoming_matches()
        for match in upcoming:
            if match.get('player1_id') and match.get('player2_id'):
                try:
                    result = analyzer.calculate_win_probability(
                        match['player1_id'],
                        match['player2_id'],
                        match.get('surface', 'Hard')
                    )
                    p1_last = match['player1_name'].split()[-1] if match.get('player1_name') else ''
                    p2_last = match['player2_name'].split()[-1] if match.get('player2_name') else ''

                    match['analysis'] = {
                        'p1_name': p1_last,
                        'p2_name': p2_last,
                        'p1_prob': round(result['p1_probability'] * 100),
                        'p2_prob': round(result['p2_probability'] * 100),
                        'confidence': round(result['confidence'] * 100)
                    }

                    # Check for value bets
                    if match.get('player1_odds'):
                        ev = analyzer.find_value(result['p1_probability'], float(match['player1_odds']))
                        if ev and ev.get('expected_value', 0) > 0.05:
                            match['analysis']['value_bet'] = {
                                'player': match['player1_name'],
                                'odds': match['player1_odds'],
                                'ev': round(ev['expected_value'] * 100, 1)
                            }
                    if 'value_bet' not in match.get('analysis', {}) and match.get('player2_odds'):
                        ev = analyzer.find_value(result['p2_probability'], float(match['player2_odds']))
                        if ev and ev.get('expected_value', 0) > 0.05:
                            match['analysis']['value_bet'] = {
                                'player': match['player2_name'],
                                'odds': match['player2_odds'],
                                'ev': round(ev['expected_value'] * 100, 1)
                            }
                except:
                    pass

        # Get bets
        bets = db.get_all_bets()

        # Get stats
        db_stats = db.get_database_stats()
        bet_stats = db.get_betting_stats()

        return jsonify({
            'matches': upcoming,
            'bets': bets,
            'stats': {
                'players': db_stats.get('total_players', 0),
                'matches': db_stats.get('total_matches', 0),
                'total_bets': bet_stats.get('total_bets', 0) or 0,
                'wins': bet_stats.get('wins', 0) or 0,
                'losses': bet_stats.get('losses', 0) or 0,
                'profit': bet_stats.get('profit', 0) or 0,
                'roi': bet_stats.get('roi', 0) or 0
            },
            'sync_time': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sync/push', methods=['POST'])
def api_sync_push():
    """Receive bets from mobile."""
    try:
        data = request.get_json()
        bets = data.get('bets', [])

        added = 0
        for bet in bets:
            try:
                db.add_bet({
                    'date': bet.get('date', datetime.now().strftime('%Y-%m-%d')),
                    'match_description': bet['match_description'],
                    'selection': bet['selection'],
                    'odds': float(bet['odds']),
                    'stake': float(bet['stake']),
                    'market': bet.get('market', 'Match Winner'),
                    'result': bet.get('result'),
                    'profit_loss': bet.get('profit_loss')
                })
                added += 1
            except Exception as e:
                print(f"Error adding bet: {e}")

        return jsonify({'status': 'ok', 'added': added})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
def home():
    try:
        db_stats = db.get_database_stats()
        bet_stats = db.get_betting_stats()
        roi_value = bet_stats.get('roi', 0) or 0

        stats = {
            'players': f"{db_stats.get('total_players', 0):,}",
            'matches': f"{db_stats.get('total_matches', 0):,}",
            'bets': bet_stats.get('total_bets', 0) or 0,
            'roi': f"{roi_value:+.1f}",
            'roi_positive': roi_value >= 0
        }
    except:
        stats = {'players': '0', 'matches': '0', 'bets': 0, 'roi': '0.0', 'roi_positive': True}

    content = render_template_string(HOME_CONTENT, stats=stats)
    return render_template_string(BASE_TEMPLATE, content=content, page='home')


@app.route('/matches')
def matches():
    upcoming = db.get_upcoming_matches()

    # Add analysis to each match
    for match in upcoming:
        if match.get('player1_id') and match.get('player2_id'):
            try:
                result = analyzer.calculate_win_probability(
                    match['player1_id'],
                    match['player2_id'],
                    match.get('surface', 'Hard')
                )

                analysis = {
                    'p1_name': match['player1_name'].split()[-1],
                    'p2_name': match['player2_name'].split()[-1],
                    'p1_prob': f"{result['p1_probability']*100:.0f}",
                    'p2_prob': f"{result['p2_probability']*100:.0f}",
                    'value_bet': None
                }

                # Check for value
                if match.get('player1_odds') and result['p1_probability'] > 0:
                    ev = analyzer.find_value(result['p1_probability'], float(match['player1_odds']))
                    if ev and ev.get('expected_value', 0) > 0.05:
                        analysis['value_bet'] = {
                            'player': match['player1_name'],
                            'odds': match['player1_odds'],
                            'ev': f"{ev['expected_value']*100:.1f}"
                        }

                if not analysis['value_bet'] and match.get('player2_odds') and result['p2_probability'] > 0:
                    ev = analyzer.find_value(result['p2_probability'], float(match['player2_odds']))
                    if ev and ev.get('expected_value', 0) > 0.05:
                        analysis['value_bet'] = {
                            'player': match['player2_name'],
                            'odds': match['player2_odds'],
                            'ev': f"{ev['expected_value']*100:.1f}"
                        }

                match['analysis'] = analysis
            except Exception as e:
                print(f"Analysis error: {e}")
                match['analysis'] = None

    content = render_template_string(MATCHES_CONTENT, matches=upcoming)
    return render_template_string(BASE_TEMPLATE, content=content, page='matches')


@app.route('/bets')
def bets():
    try:
        all_bets = db.get_all_bets()
        bet_stats = db.get_betting_stats()
        profit_value = bet_stats.get('profit', 0) or 0

        stats = {
            'wins': bet_stats.get('wins', 0) or 0,
            'losses': bet_stats.get('losses', 0) or 0,
            'profit': f"{profit_value:+.2f}",
            'profit_positive': profit_value >= 0
        }
    except:
        all_bets = []
        stats = {'wins': 0, 'losses': 0, 'profit': '0.00', 'profit_positive': True}

    content = render_template_string(BETS_CONTENT, bets=all_bets[:20], stats=stats)
    return render_template_string(BASE_TEMPLATE, content=content, page='bets')


@app.route('/add-bet', methods=['GET', 'POST'])
def add_bet():
    if request.method == 'POST':
        try:
            db.add_bet({
                'date': datetime.now().strftime('%Y-%m-%d'),
                'match_description': request.form['match_description'],
                'selection': request.form['selection'],
                'odds': float(request.form['odds']),
                'stake': float(request.form['stake']),
                'market': 'Match Winner'
            })
            return redirect(url_for('bets'))
        except Exception as e:
            print(f"Error adding bet: {e}")

    content = render_template_string(ADD_BET_CONTENT)
    return render_template_string(BASE_TEMPLATE, content=content, page='bets')


@app.route('/sync')
def sync_page():
    content = render_template_string(SYNC_CONTENT)
    return render_template_string(BASE_TEMPLATE, content=content, page='sync')


# ============================================================================
# RUN SERVER
# ============================================================================

def run_server(host='0.0.0.0', port=5000):
    """Run the web server."""
    import socket

    # Get local IP
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except:
        local_ip = "unknown"

    print(f"\n{'='*60}")
    print("  TENNIS BETTING SYSTEM - Web Server (PWA)")
    print(f"{'='*60}")
    print(f"\nServer running at:")
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://{local_ip}:{port}")
    print(f"\n{'='*60}")
    print("  MOBILE SETUP")
    print(f"{'='*60}")
    print(f"\n  1. On your phone, connect to your home WiFi")
    print(f"  2. Open browser and go to: http://{local_ip}:{port}")
    print(f"  3. Tap 'Add to Home Screen' to install the app")
    print(f"  4. Go to Sync > Download Matches")
    print(f"  5. Data is saved - view offline anywhere!")
    print(f"\n{'='*60}")
    print("Press Ctrl+C to stop the server")
    print(f"{'='*60}\n")

    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    run_server()
