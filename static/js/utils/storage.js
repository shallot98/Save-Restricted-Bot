/**
 * Storage Management Utilities
 * Version: 1.0
 */

(function() {
    'use strict';

    const StorageManager = {
        // Get item from localStorage with error handling
        getItem: function(key, defaultValue) {
            try {
                const value = localStorage.getItem(key);
                return value !== null ? JSON.parse(value) : defaultValue;
            } catch (e) {
                console.warn('Failed to get item from localStorage:', key, e);
                return defaultValue;
            }
        },

        // Set item to localStorage with error handling
        setItem: function(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch (e) {
                console.warn('Failed to set item to localStorage:', key, e);
                return false;
            }
        },

        // Remove item from localStorage
        removeItem: function(key) {
            try {
                localStorage.removeItem(key);
                return true;
            } catch (e) {
                console.warn('Failed to remove item from localStorage:', key, e);
                return false;
            }
        },

        // Clear all items from localStorage
        clear: function() {
            try {
                localStorage.clear();
                return true;
            } catch (e) {
                console.warn('Failed to clear localStorage:', e);
                return false;
            }
        }
    };

    // Export to global namespace
    window.StorageManager = StorageManager;

})();
