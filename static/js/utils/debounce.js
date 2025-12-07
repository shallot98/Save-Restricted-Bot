/**
 * Performance Optimization: Throttle and Debounce Utilities
 * Version: 1.0
 */

(function() {
    'use strict';

    // Throttle: Limit function execution to once per interval
    function throttle(fn, delay) {
        let lastCallTime = 0;
        let timeoutId = null;

        return function() {
            const context = this;
            const args = arguments;
            const now = Date.now();

            // Clear any pending timeout
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }

            // Check if enough time has passed
            if (now - lastCallTime >= delay) {
                lastCallTime = now;
                fn.apply(context, args);
            } else {
                // Queue the call for the remaining delay
                const remainingDelay = delay - (now - lastCallTime);
                timeoutId = setTimeout(function() {
                    lastCallTime = Date.now();
                    fn.apply(context, args);
                }, remainingDelay);
            }
        };
    }

    // Debounce: Delay execution until after no calls for specified delay
    function debounce(fn, delay) {
        let timeoutId = null;

        return function() {
            const context = this;
            const args = arguments;

            // Clear previous timeout
            if (timeoutId) {
                clearTimeout(timeoutId);
            }

            // Set new timeout
            timeoutId = setTimeout(function() {
                fn.apply(context, args);
            }, delay);
        };
    }

    // Export to global namespace
    window.PerformanceUtils = {
        throttle: throttle,
        debounce: debounce
    };

})();
