/**
 * Utilities for Save-Restricted-Bot
 */

window.utils = {
    // Throttle: Limit function execution to once per interval
    throttle(fn, delay) {
        let lastCallTime = 0;
        let timeoutId = null;

        return function(...args) {
            const context = this;
            const now = Date.now();

            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }

            if (now - lastCallTime >= delay) {
                lastCallTime = now;
                fn.apply(context, args);
            } else {
                const remainingDelay = delay - (now - lastCallTime);
                timeoutId = setTimeout(() => {
                    lastCallTime = Date.now();
                    fn.apply(context, args);
                }, remainingDelay);
            }
        };
    },

    // Debounce: Delay execution until after no calls for specified delay
    debounce(fn, delay) {
        let timeoutId = null;

        return function(...args) {
            const context = this;
            if (timeoutId) clearTimeout(timeoutId);
            timeoutId = setTimeout(() => {
                fn.apply(context, args);
            }, delay);
        };
    }
};

window.NetworkManager = {
    connectionType: null,
    lastDetectionTime: 0,
    CACHE_DURATION: 30000,
    TIMEOUTS: {
        'slow-2g': 15000, '2g': 10000, '3g': 8000, '4g': 5000, 'wifi': 5000, 'unknown': 5000
    },
    RETRY_COUNTS: {
        'slow-2g': 3, '2g': 3, '3g': 2, '4g': 1, 'wifi': 1, 'unknown': 1
    },

    detectConnectionType() {
        const now = Date.now();
        if (this.connectionType && (now - this.lastDetectionTime) < this.CACHE_DURATION) {
            return this.connectionType;
        }
        if (navigator.connection && navigator.connection.effectiveType) {
            this.connectionType = navigator.connection.type === 'wifi' ? 'wifi' : navigator.connection.effectiveType;
        } else {
            this.connectionType = '4g';
        }
        this.lastDetectionTime = now;
        return this.connectionType;
    },

    getApiTimeout() {
        return this.TIMEOUTS[this.detectConnectionType()] || this.TIMEOUTS['unknown'];
    },

    getRetryCount() {
        return this.RETRY_COUNTS[this.detectConnectionType()] || this.RETRY_COUNTS['unknown'];
    },

    isOnline() {
        return navigator.onLine;
    },

    async fetchWithRetry(url, options = {}, maxRetries = null, customTimeout = null) {
        if (!this.isOnline()) throw new Error('网络连接不可用');

        const timeout = customTimeout !== null ? customTimeout : this.getApiTimeout();
        const retries = maxRetries !== null ? maxRetries : this.getRetryCount();

        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), timeout);

                const response = await fetch(url, { ...options, signal: controller.signal });
                clearTimeout(timeoutId);

                if (response.status >= 400 && response.status < 500) return response;
                if (response.ok) return response;

                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            } catch (error) {
                if (attempt === retries) throw error;
                const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                await new Promise(r => setTimeout(r, backoffDelay));
            }
        }
    },

    init() {
        window.addEventListener('online', () => console.log('网络已连接'));
        window.addEventListener('offline', () => console.log('网络已断开'));
        if (navigator.connection) {
            navigator.connection.addEventListener('change', () => { this.connectionType = null; });
        }
    }
};
