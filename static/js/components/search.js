/**
 * Search Component
 * Version: 1.0
 */

(function() {
    'use strict';

    const SearchManager = {
        // Toggle search box visibility
        toggleSearch: function() {
            const searchBox = document.getElementById('topbarSearch');
            const input = document.getElementById('topSearchInput');

            if (searchBox.classList.contains('active')) {
                searchBox.classList.remove('active');
            } else {
                searchBox.classList.add('active');
                setTimeout(function() { input.focus(); }, 300);
            }
        },

        // Toggle filter panel visibility
        toggleFilter: function() {
            const filterPanel = document.getElementById('filterPanel');
            if (filterPanel) {
                filterPanel.classList.toggle('active');
            }
        },

        // Initialize search input handlers
        initSearchInput: function() {
            const topSearchInput = document.getElementById('topSearchInput');
            if (!topSearchInput) return;

            // Handle Enter key for immediate search
            topSearchInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    const searchQuery = this.value.trim();
                    if (searchQuery) {
                        window.location.href = '/notes?page=1&search=' + encodeURIComponent(searchQuery);
                    }
                }
            });

            // Debounced input handler for auto-search (300ms delay)
            const debouncedSearch = window.PerformanceUtils.debounce(function(e) {
                const searchQuery = e.target.value.trim();
                // Only trigger auto-search for queries >= 3 characters
                if (searchQuery.length >= 3) {
                    console.log('Auto-search triggered for:', searchQuery);
                    // Optional: uncomment to enable auto-search
                    // window.location.href = '/notes?page=1&search=' + encodeURIComponent(searchQuery);
                }
            }, 300);

            // Attach debounced input listener
            topSearchInput.addEventListener('input', debouncedSearch);
        }
    };

    // Export to global namespace
    window.SearchManager = SearchManager;

})();
