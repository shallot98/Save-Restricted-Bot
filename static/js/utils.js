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

    getCalibrationTimeoutMs(linkCount) {
        const safeCount = Number.isFinite(linkCount) ? Math.max(1, Math.floor(linkCount)) : 1;
        const perLinkTimeoutMs = 90000; // 30s(qbt) + 60s(bot)
        const maxTimeoutMs = 10 * 60 * 1000; // 10 minutes
        return Math.min(perLinkTimeoutMs * safeCount, maxTimeoutMs);
    },

	    async fetchWithRetry(url, options = {}, maxRetries = null, customTimeout = null) {
	        if (!this.isOnline()) throw new Error('网络连接不可用,请检查您的网络设置');

        const timeout = customTimeout !== null ? customTimeout : this.getApiTimeout();
        const retries = maxRetries !== null ? maxRetries : this.getRetryCount();

        for (let attempt = 0; attempt <= retries; attempt++) {
            let timeoutId = null;
	            try {
	                const controller = new AbortController();
	                timeoutId = setTimeout(() => controller.abort(), timeout);

	                const fetchOptions = { ...options, signal: controller.signal };
	                const method = (fetchOptions.method || 'GET').toUpperCase();
	                if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)) {
	                    const metaTokenEl = document.querySelector('meta[name="csrf-token"]');
	                    const csrfToken = window.CSRF_TOKEN || (metaTokenEl ? metaTokenEl.getAttribute('content') : null);
	                    if (csrfToken) {
	                        if (fetchOptions.headers instanceof Headers) {
	                            if (!fetchOptions.headers.has('X-CSRFToken') && !fetchOptions.headers.has('X-CSRF-Token')) {
	                                fetchOptions.headers.set('X-CSRFToken', csrfToken);
	                            }
	                        } else {
	                            const existingHeaders = fetchOptions.headers || {};
	                            const headers = { ...existingHeaders };
	                            if (!headers['X-CSRFToken'] && !headers['X-CSRF-Token']) {
	                                headers['X-CSRFToken'] = csrfToken;
	                            }
	                            fetchOptions.headers = headers;
	                        }
	                    }
	                }

	                const response = await fetch(url, fetchOptions);

	                if (response.status >= 400 && response.status < 500) return response;
	                if (response.ok) return response;

                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            } catch (error) {
                const isLastAttempt = attempt === retries;

                if (error && error.name === 'AbortError') {
                    if (!isLastAttempt) {
                        const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                        await new Promise(r => setTimeout(r, backoffDelay));
                        continue;
                    }
                    throw new Error(`请求超时 (${timeout}ms),请稍后重试`);
                }

                if (error instanceof TypeError) {
                    if (!isLastAttempt) {
                        const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                        await new Promise(r => setTimeout(r, backoffDelay));
                        continue;
                    }
                    throw new Error('网络请求失败,请检查网络连接');
                }

                if (isLastAttempt) throw error;
                const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                await new Promise(r => setTimeout(r, backoffDelay));
            } finally {
                if (timeoutId) clearTimeout(timeoutId);
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

window.CalibrationClient = (function() {
    'use strict';

    const DEFAULT_POLL_INTERVAL_MS = 1000;
    const DEFAULT_POLL_MAX_MS = 60000;
    const DEFAULT_STATUS_TIMEOUT_MS = 5000;

    function isAsyncEnabled() {
        try {
            if (window.AppConfig && typeof window.AppConfig.useAsyncCalibration === 'boolean') {
                return window.AppConfig.useAsyncCalibration;
            }
            const stored = localStorage.getItem('useAsyncCalibration');
            if (stored === '0' || stored === 'false') return false;
            if (stored === '1' || stored === 'true') return true;
        } catch (e) {
            // ignore
        }
        return true;
    }

    function sleep(ms, signal) {
        return new Promise((resolve, reject) => {
            if (signal && signal.aborted) {
                reject(new DOMException('Aborted', 'AbortError'));
                return;
            }
            const timeoutId = setTimeout(resolve, ms);
            const onAbort = () => {
                clearTimeout(timeoutId);
                reject(new DOMException('Aborted', 'AbortError'));
            };
            if (signal) signal.addEventListener('abort', onAbort, { once: true });
        });
    }

    async function fetchJsonWithTimeout(url, options = {}, timeoutMs = DEFAULT_STATUS_TIMEOUT_MS, signal = null) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

        const onAbort = () => controller.abort();
        if (signal) {
            if (signal.aborted) controller.abort();
            else signal.addEventListener('abort', onAbort, { once: true });
        }

        try {
            const response = await fetch(url, { ...options, signal: controller.signal });
            const data = await response.json().catch(() => ({}));
            return { response, data };
        } finally {
            clearTimeout(timeoutId);
        }
    }

    async function submitNoteCalibration(noteId, timeoutMs = 10000) {
        const response = await window.NetworkManager.fetchWithRetry('/api/calibrate/async', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ note_id: noteId })
        }, 1, timeoutMs);

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data || !data.success || !data.task_id) {
            const msg = (data && data.error) ? data.error : `HTTP ${response.status}: ${response.statusText}`;
            throw new Error(msg || '提交异步校准任务失败');
        }
        return String(data.task_id);
    }

    async function getTaskStatus(taskId, options = {}) {
        const timeoutMs = Number.isFinite(options.timeoutMs) ? options.timeoutMs : DEFAULT_STATUS_TIMEOUT_MS;
        const signal = options.signal || null;
        const { response, data } = await fetchJsonWithTimeout(`/api/calibrate/status/${encodeURIComponent(taskId)}`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        }, timeoutMs, signal);

        if (!response.ok || !data || !data.success) {
            const msg = (data && data.error) ? data.error : `HTTP ${response.status}: ${response.statusText}`;
            throw new Error(msg || '查询任务状态失败');
        }
        return data;
    }

    async function pollTask(taskId, options = {}) {
        const intervalMs = Number.isFinite(options.intervalMs) ? options.intervalMs : DEFAULT_POLL_INTERVAL_MS;
        const maxMs = Number.isFinite(options.maxMs) ? options.maxMs : DEFAULT_POLL_MAX_MS;
        const signal = options.signal || null;
        const onTick = typeof options.onTick === 'function' ? options.onTick : null;

        const start = Date.now();
        let attempt = 0;

        while (true) {
            const elapsedMs = Date.now() - start;
            const elapsedSec = Math.floor(elapsedMs / 1000);
            const remainingSec = Math.max(0, Math.ceil((maxMs - elapsedMs) / 1000));

            if (elapsedMs > maxMs) {
                throw new Error('轮询超时（60秒）');
            }

            const status = await getTaskStatus(taskId, { signal });
            attempt += 1;

            if (onTick) {
                try {
                    onTick({
                        attempt,
                        elapsedSec,
                        remainingSec,
                        status
                    });
                } catch (e) {
                    // ignore UI callback errors
                }
            }

            if (status.status === 'completed') return status;
            if (status.status === 'failed') {
                throw new Error(status.error || '校准失败');
            }

            await sleep(intervalMs, signal);
        }
    }

    return {
        isAsyncEnabled,
        submitNoteCalibration,
        getTaskStatus,
        pollTask,
    };
})();
