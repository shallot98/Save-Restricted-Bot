/**
 * Network Detection and Timeout Management
 * Version: 1.0
 */

(function() {
    'use strict';

    const NetworkManager = {
        // Cached connection type
        connectionType: null,
        lastDetectionTime: 0,
        CACHE_DURATION: 30000, // 30 seconds

        // Connection type to timeout mapping (milliseconds)
        TIMEOUTS: {
            'slow-2g': 15000,
            '2g': 10000,
            '3g': 8000,
            '4g': 5000,
            'wifi': 5000,
            'unknown': 5000
        },

        // Connection type to retry count mapping
        RETRY_COUNTS: {
            'slow-2g': 3,
            '2g': 3,
            '3g': 2,
            '4g': 1,
            'wifi': 1,
            'unknown': 1
        },

        // Detect connection type using Network Information API
        detectConnectionType: function() {
            const now = Date.now();

            // Return cached value if still valid
            if (this.connectionType && (now - this.lastDetectionTime) < this.CACHE_DURATION) {
                return this.connectionType;
            }

            // Check if Network Information API is available
            if (navigator.connection && navigator.connection.effectiveType) {
                const effectiveType = navigator.connection.effectiveType;

                // Check if WiFi (some browsers support this)
                if (navigator.connection.type === 'wifi') {
                    this.connectionType = 'wifi';
                } else {
                    this.connectionType = effectiveType;
                }
            } else {
                // Fallback to 4G for browsers without API support
                this.connectionType = '4g';
            }

            this.lastDetectionTime = now;
            return this.connectionType;
        },

        // Get timeout for current connection
        getApiTimeout: function() {
            const connType = this.detectConnectionType();
            return this.TIMEOUTS[connType] || this.TIMEOUTS['unknown'];
        },

        // Get retry count for current connection
        getRetryCount: function() {
            const connType = this.detectConnectionType();
            return this.RETRY_COUNTS[connType] || this.RETRY_COUNTS['unknown'];
        },

        // Check if online
        isOnline: function() {
            return navigator.onLine;
        },

        // Fetch with retry and exponential backoff
        fetchWithRetry: async function(url, options, maxRetries) {
            if (!this.isOnline()) {
                throw new Error('网络连接不可用,请检查您的网络设置');
            }

            const timeout = this.getApiTimeout();
            const retries = maxRetries !== null && maxRetries !== undefined ? maxRetries : this.getRetryCount();

            for (let attempt = 0; attempt <= retries; attempt++) {
                try {
                    // Create AbortController for timeout
                    const controller = new AbortController();
                    const timeoutId = setTimeout(function() { controller.abort(); }, timeout);

                    // Add signal to fetch options
                    const fetchOptions = Object.assign({}, options || {}, {
                        signal: controller.signal
                    });

                    const response = await fetch(url, fetchOptions);
                    clearTimeout(timeoutId);

                    // Don't retry on client errors (4xx)
                    if (response.status >= 400 && response.status < 500) {
                        return response;
                    }

                    // Return successful response
                    if (response.ok) {
                        return response;
                    }

                    // Server error - retry
                    throw new Error('HTTP ' + response.status + ': ' + response.statusText);
                } catch (error) {
                    const isLastAttempt = attempt === retries;

                    // Check error type
                    if (error.name === 'AbortError') {
                        console.log('请求超时 (尝试 ' + (attempt + 1) + '/' + (retries + 1) + ')');
                        if (!isLastAttempt) {
                            const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                            console.log('等待 ' + backoffDelay + 'ms 后重试...');
                            await this.sleep(backoffDelay);
                            continue;
                        }
                        throw new Error('请求超时 (' + timeout + 'ms),请检查网络连接');
                    } else if (error instanceof TypeError) {
                        console.log('网络错误 (尝试 ' + (attempt + 1) + '/' + (retries + 1) + ')');
                        if (!isLastAttempt) {
                            const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                            console.log('等待 ' + backoffDelay + 'ms 后重试...');
                            await this.sleep(backoffDelay);
                            continue;
                        }
                        throw new Error('网络请求失败,请检查网络连接');
                    } else {
                        throw error;
                    }
                }
            }
        },

        // Sleep utility
        sleep: function(ms) {
            return new Promise(function(resolve) { setTimeout(resolve, ms); });
        },

        // Initialize connection change listener
        init: function() {
            // Listen for online/offline events
            window.addEventListener('online', function() {
                console.log('网络已连接');
                NetworkManager.hideOfflineBanner();
            });

            window.addEventListener('offline', function() {
                console.log('网络已断开');
                NetworkManager.showOfflineBanner();
            });

            // Listen for connection change
            if (navigator.connection) {
                navigator.connection.addEventListener('change', function() {
                    NetworkManager.connectionType = null; // Clear cache
                    console.log('网络连接类型变更:', NetworkManager.detectConnectionType());
                });
            }

            // Check initial state
            if (!this.isOnline()) {
                this.showOfflineBanner();
            }

            console.log('NetworkManager initialized - Connection:', this.detectConnectionType());
        },

        // Show offline banner
        showOfflineBanner: function() {
            let banner = document.getElementById('offlineBanner');
            if (!banner) {
                banner = document.createElement('div');
                banner.id = 'offlineBanner';
                banner.style.cssText = 'position: fixed; top: 0; left: 0; right: 0; background: #f44336; color: white; padding: 12px; text-align: center; z-index: 10000; font-size: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);';
                banner.textContent = '网络连接不可用 - 请检查您的网络设置';
                document.body.insertBefore(banner, document.body.firstChild);
            }
        },

        // Hide offline banner
        hideOfflineBanner: function() {
            const banner = document.getElementById('offlineBanner');
            if (banner) {
                banner.remove();
            }
        }
    };

    // Export to global namespace
    window.NetworkManager = NetworkManager;

})();
