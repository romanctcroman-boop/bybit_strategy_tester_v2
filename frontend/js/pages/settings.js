/**
 * 📄 Settings Page JavaScript
 * 
 * Page-specific scripts for settings.html
 * Extracted during Phase 1 Week 3: JS Extraction
 * 
 * @version 1.0.0
 * @date 2025-12-21
 */

// Import shared utilities
import { apiClient, API_CONFIG } from '../api.js';
import { formatNumber, formatCurrency, formatDate, debounce } from '../utils.js';

// Navigation
        document.querySelectorAll('.settings-nav-item').forEach(item => {
            item.addEventListener('click', () => {
                document.querySelectorAll('.settings-nav-item').forEach(i => i.classList.remove('active'));
                document.querySelectorAll('.settings-section').forEach(s => s.classList.remove('active'));
                
                item.classList.add('active');
                document.getElementById(`${item.dataset.section}-section`).classList.add('active');
            });
        });

        function selectTheme(theme) {
            document.querySelectorAll('.theme-option').forEach(o => o.classList.remove('active'));
            event.currentTarget.classList.add('active');
            console.log(`Theme selected: ${theme}`);
        }

        function selectColor(color) {
            document.querySelectorAll('.color-option').forEach(o => o.classList.remove('active'));
            event.currentTarget.classList.add('active');
            console.log(`Color selected: ${color}`);
        }

        function toggleApiKeyVisibility() {
            const display = document.getElementById('apiKeyDisplay');
            const icon = event.currentTarget.querySelector('i');
            
            if (display.textContent.includes('•')) {
                display.textContent = 'ABC123XYZ789...';
                icon.className = 'bi bi-eye-slash';
            } else {
                display.textContent = '••••••••••••••••';
                icon.className = 'bi bi-eye';
            }
        }

        function copyApiKey() {
            navigator.clipboard.writeText('API_KEY_HERE');
            alert('API key copied to clipboard');
        }

        function testConnection() {
            alert('Testing API connection...');
        }

        function saveSettings() {
            alert('Settings saved successfully!');
        }

        function resetSettings() {
            if (confirm('Reset all settings to default?')) {
                location.reload();
            }
        }

        function exportData() {
            alert('Export data dialog would open here');
        }

        function importData() {
            alert('Import data dialog would open here');
        }

        function clearCache(type) {
            if (confirm(`Clear ${type} cache?`)) {
                alert(`${type} cache cleared`);
            }
        }

        function resetAllSettings() {
            if (confirm('This will reset all settings. Are you sure?')) {
                localStorage.clear();
                location.reload();
            }
        }

        function clearAllData() {
            if (confirm('This will delete ALL local data. This cannot be undone. Continue?')) {
                localStorage.clear();
                indexedDB.deleteDatabase('strategy_tester');
                location.reload();
            }
        }

        function deleteAccount() {
            if (confirm('This will permanently delete your account. Are you sure?')) {
                alert('Account deletion would be processed here');
            }
        }

// ============================================
// EXPORTS
// ============================================

// Export functions for potential external use
// Exported functions: selectTheme, selectColor, toggleApiKeyVisibility, copyApiKey, testConnection

// Attach to window for backwards compatibility
if (typeof window !== 'undefined') {
    window.settingsPage = {
        // Add public methods here
    };
}
