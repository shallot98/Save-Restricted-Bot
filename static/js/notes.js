/**
 * Notes Page JavaScript Module
 * Extracted from templates/notes.html for better maintainability
 * Version: 1.0
 */

(function() {
    'use strict';

    // Lazy Loading with Intersection Observer
    // SVG placeholder image (gray rectangle with loading indicator)
    const PLACEHOLDER_IMAGE = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300"%3E%3Crect width="400" height="300" fill="%23f0f0f0"/%3E%3Ctext x="50%25" y="50%25" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="16" fill="%23999"%3ELoading...%3C/text%3E%3C/svg%3E';

    function initLazyLoading() {
        // Check if browser supports Intersection Observer
        if (!('IntersectionObserver' in window)) {
            // Fallback: load all images immediately on unsupported browsers
            console.warn('IntersectionObserver not supported, loading all images immediately');
            return;
        }

        // Create Intersection Observer with 200px threshold
        const imageObserver = new IntersectionObserver(function(entries, observer) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    const img = entry.target;

                    // Swap data-src to src and add loading class
                    if (img.dataset.src) {
                        img.classList.add('image-loading');

                        // Load the actual image
                        const actualImg = new Image();
                        actualImg.onload = function() {
                            img.src = img.dataset.src;
                            img.classList.remove('image-loading');
                            img.classList.add('image-loaded');
                        };
                        actualImg.onerror = function() {
                            img.classList.remove('image-loading');
                            img.classList.add('image-error');
                        };
                        actualImg.src = img.dataset.src;

                        // Stop observing this image
                        observer.unobserve(img);
                    }
                }
            });
        }, {
            rootMargin: '200px', // Load images 200px before entering viewport
            threshold: 0.01
        });

        // Observe all note card images with loading="lazy"
        const lazyImages = document.querySelectorAll('.note-media img[loading="lazy"]');
        lazyImages.forEach(function(img) {
            // Store original src in data-src
            if (img.src && !img.dataset.src) {
                img.dataset.src = img.src;
                img.src = PLACEHOLDER_IMAGE;
            }

            // Start observing
            imageObserver.observe(img);
        });
    }

    // Unified Mobile UI State Management
    const MobileUIState = {
        // State properties
        sidebarOpen: false,
        viewportWidth: window.innerWidth,
        isMobile: window.innerWidth < 768,

        // Touch state for gesture detection
        touchState: {
            startX: 0,
            startY: 0,
            currentX: 0,
            currentY: 0,
            startTime: 0,
            endTime: 0,
            isSwiping: false
        },

        // Click suppression flag to prevent double-firing
        clickSuppressed: false,

        // localStorage key
        STORAGE_KEY: 'mobileUIState',

        // Initialize state from localStorage or defaults
        init: function() {
            this.viewportWidth = window.innerWidth;
            this.isMobile = this.viewportWidth < 768;

            try {
                const saved = localStorage.getItem(this.STORAGE_KEY);
                if (saved) {
                    // 已有保存状态,加载并应用
                    const state = JSON.parse(saved);
                    this.sidebarOpen = state.sidebarOpen || false;
                } else {
                    // 首次访问且移动端,默认打开侧边栏
                    if (this.isMobile) {
                        this.sidebarOpen = true;
                        console.log('First visit on mobile: opening sidebar by default');

                        // 应用初始状态到DOM
                        this.syncDOM();

                        // 3秒后自动关闭侧边栏并显示提示
                        setTimeout(() => {
                            this.sidebarOpen = false;
                            this.syncDOM();
                            this.persist();
                            this.showMobileHint();
                        }, 3000);
                    } else {
                        // 桌面端首次访问,默认关闭
                        this.sidebarOpen = false;
                    }
                }
            } catch (e) {
                console.warn('Failed to load saved UI state:', e);
                this.sidebarOpen = false;
            }

            // Apply initial state to DOM
            this.syncDOM();

            // Initialize touch event listeners
            this.initTouchEvents();

            // Initialize Virtual Viewport API for keyboard handling
            this.initVirtualViewport();

            console.log('MobileUIState initialized:', this.getState());
        },

        // Get current state snapshot
        getState: function() {
            return {
                sidebarOpen: this.sidebarOpen,
                viewportWidth: this.viewportWidth,
                isMobile: this.isMobile
            };
        },

        // Toggle sidebar state
        toggleSidebar: function() {
            this.sidebarOpen = !this.sidebarOpen;
            this.syncDOM();
            this.persist();
            console.log('Sidebar toggled:', this.sidebarOpen);
        },

        // Update viewport dimensions
        updateViewport: function() {
            const oldIsMobile = this.isMobile;
            this.viewportWidth = window.innerWidth;
            this.isMobile = this.viewportWidth < 768;

            // Handle mobile <-> desktop transitions
            if (oldIsMobile && !this.isMobile) {
                // Transitioning from mobile to desktop: auto-open if closed
                if (!this.sidebarOpen) {
                    this.sidebarOpen = true;
                    console.log('Desktop mode: auto-opening sidebar');
                }
            } else if (!oldIsMobile && this.isMobile) {
                // Transitioning from desktop to mobile: close sidebar
                this.sidebarOpen = false;
                console.log('Mobile mode: closing sidebar');
            }

            this.syncDOM();
            this.persist();
        },

        // Sync state to DOM classes
        syncDOM: function() {
            const sidebar = document.getElementById('sidebar');
            if (!sidebar) return;

            if (this.isMobile) {
                // Mobile mode: use mobile-open class
                sidebar.classList.remove('collapsed');
                if (this.sidebarOpen) {
                    sidebar.classList.add('mobile-open');
                } else {
                    sidebar.classList.remove('mobile-open');
                }
            } else {
                // Desktop mode: use collapsed class
                sidebar.classList.remove('mobile-open');
                if (this.sidebarOpen) {
                    sidebar.classList.remove('collapsed');
                } else {
                    sidebar.classList.add('collapsed');
                }
            }

            // Update toggle button text if exists
            const toggleText = document.getElementById('sidebarToggleText');
            if (toggleText) {
                toggleText.textContent = this.sidebarOpen ? '收起侧边栏' : '展开侧边栏';
            }
        },

        // Persist state to localStorage
        persist: function() {
            try {
                localStorage.setItem(this.STORAGE_KEY, JSON.stringify({
                    sidebarOpen: this.sidebarOpen
                }));
            } catch (e) {
                console.warn('Failed to persist UI state:', e);
            }
        },

        // Initialize touch event listeners for swipe gestures
        initTouchEvents: function() {
            const sidebar = document.getElementById('sidebar');
            if (!sidebar) return;

            // touchstart: Record initial touch position and timestamp
            sidebar.addEventListener('touchstart', (e) => {
                const touch = e.touches[0];
                this.touchState.startX = touch.clientX;
                this.touchState.startY = touch.clientY;
                this.touchState.currentX = touch.clientX;
                this.touchState.currentY = touch.clientY;
                this.touchState.startTime = Date.now();
                this.touchState.isSwiping = false;
            }, { passive: true });

            // touchmove: Update current touch position with passive listener
            sidebar.addEventListener('touchmove', (e) => {
                if (e.touches.length === 0) return;
                const touch = e.touches[0];
                this.touchState.currentX = touch.clientX;
                this.touchState.currentY = touch.clientY;
                this.touchState.isSwiping = true;
            }, { passive: true });

            // touchend: Calculate swipe and trigger action if threshold met
            sidebar.addEventListener('touchend', (e) => {
                this.touchState.endTime = Date.now();
                this.handleSwipeGesture();
            }, { passive: true });

            console.log('Touch event listeners initialized for sidebar');
        },

        // Handle swipe gesture detection and action
        handleSwipeGesture: function() {
            // Only process if sidebar is open and in mobile mode
            if (!this.isMobile || !this.sidebarOpen || !this.touchState.isSwiping) {
                this.touchState.isSwiping = false;
                return;
            }

            const deltaX = this.touchState.currentX - this.touchState.startX;
            const deltaY = this.touchState.currentY - this.touchState.startY;
            const duration = this.touchState.endTime - this.touchState.startTime;

            // Calculate velocity (px/ms)
            const velocity = Math.abs(deltaX) / duration;

            // Check if horizontal swipe (|deltaX| > |deltaY|)
            const isHorizontalSwipe = Math.abs(deltaX) > Math.abs(deltaY);

            // Swipe threshold: 50px or velocity > 0.3px/ms
            const swipeThreshold = 50;
            const velocityThreshold = 0.3;

            const isSwipeLeft = deltaX < -swipeThreshold;
            const isFastSwipe = velocity > velocityThreshold && deltaX < 0;

            if (isHorizontalSwipe && (isSwipeLeft || isFastSwipe)) {
                console.log(`Swipe detected: deltaX=${deltaX.toFixed(1)}px, velocity=${velocity.toFixed(3)}px/ms`);

                // Close sidebar
                this.toggleSidebar();

                // Suppress click events temporarily to prevent double-firing
                this.clickSuppressed = true;
                setTimeout(() => {
                    this.clickSuppressed = false;
                }, 300);
            }

            // Reset swipe state
            this.touchState.isSwiping = false;
        },

        // Initialize Virtual Viewport API for keyboard handling
        initVirtualViewport: function() {
            if (!window.visualViewport) {
                console.log('Visual Viewport API not supported, using fallback');
                return;
            }

            visualViewport.addEventListener('resize', () => {
                // Detect if keyboard is open
                const viewportHeight = visualViewport.height;
                const windowHeight = window.innerHeight;
                const keyboardHeight = windowHeight - viewportHeight;

                if (keyboardHeight > 150) {
                    // Keyboard is open
                    const activeElement = document.activeElement;
                    if (activeElement && (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT')) {
                        // Scroll active input into view
                        setTimeout(() => {
                            activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }, 100);
                    }
                }
            });

            console.log('Virtual Viewport API initialized for keyboard handling');
        },

        // Show mobile hint (placeholder for future implementation)
        showMobileHint: function() {
            // Future: Show a hint to users about sidebar functionality
            console.log('Mobile hint: Sidebar can be toggled using the menu button');
        }
    };

    // Performance Optimization: Throttle and Debounce Utilities
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

    // Network Detection and Timeout Management
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
        fetchWithRetry: async function(url, options = {}, maxRetries = null) {
            if (!this.isOnline()) {
                throw new Error('网络连接不可用,请检查您的网络设置');
            }

            const timeout = this.getApiTimeout();
            const retries = maxRetries !== null ? maxRetries : this.getRetryCount();

            for (let attempt = 0; attempt <= retries; attempt++) {
                try {
                    // Create AbortController for timeout
                    const controller = new AbortController();
                    const timeoutId = setTimeout(() => controller.abort(), timeout);

                    // Add signal to fetch options
                    const fetchOptions = {
                        ...options,
                        signal: controller.signal
                    };

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
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                } catch (error) {
                    const isLastAttempt = attempt === retries;

                    // Check error type
                    if (error.name === 'AbortError') {
                        console.log(`请求超时 (尝试 ${attempt + 1}/${retries + 1})`);
                        if (!isLastAttempt) {
                            const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                            console.log(`等待 ${backoffDelay}ms 后重试...`);
                            await this.sleep(backoffDelay);
                            continue;
                        }
                        throw new Error(`请求超时 (${timeout}ms),请检查网络连接`);
                    } else if (error instanceof TypeError) {
                        console.log(`网络错误 (尝试 ${attempt + 1}/${retries + 1})`);
                        if (!isLastAttempt) {
                            const backoffDelay = Math.min(1000 * Math.pow(2, attempt), 10000);
                            console.log(`等待 ${backoffDelay}ms 后重试...`);
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
            return new Promise(resolve => setTimeout(resolve, ms));
        },

        // Initialize connection change listener
        init: function() {
            // Listen for online/offline events
            window.addEventListener('online', () => {
                console.log('网络已连接');
                this.hideOfflineBanner();
            });

            window.addEventListener('offline', () => {
                console.log('网络已断开');
                this.showOfflineBanner();
            });

            // Listen for connection change
            if (navigator.connection) {
                navigator.connection.addEventListener('change', () => {
                    this.connectionType = null; // Clear cache
                    console.log('网络连接类型变更:', this.detectConnectionType());
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
                banner.style.cssText = `
                    position: fixed;
                    top: 0;
                    left: 0;
                    right: 0;
                    background: #f44336;
                    color: white;
                    padding: 12px;
                    text-align: center;
                    z-index: 10000;
                    font-size: 14px;
                    box-shadow: 0 2px 4px rgba(0,0,0,0.2);
                `;
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

    // Global function exports for inline onclick handlers
    window.toggleSidebar = function() {
        if (MobileUIState.clickSuppressed) return;
        MobileUIState.toggleSidebar();
    };

    window.toggleMobileSidebar = function() {
        if (MobileUIState.clickSuppressed) return;
        MobileUIState.toggleSidebar();
    };

    window.toggleTheme = function() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        html.setAttribute('data-theme', currentTheme === 'dark' ? '' : 'dark');
        localStorage.setItem('theme', currentTheme === 'dark' ? 'light' : 'dark');
    };

    window.toggleSearch = function() {
        const searchBox = document.getElementById('topbarSearch');
        const input = document.getElementById('topSearchInput');

        if (searchBox.classList.contains('active')) {
            searchBox.classList.remove('active');
        } else {
            searchBox.classList.add('active');
            setTimeout(() => input.focus(), 300);
        }
    };

    window.toggleFilter = function() {
        const filterPanel = document.getElementById('filterPanel');
        if (filterPanel) {
            filterPanel.classList.toggle('active');
        }
    };

    window.toggleUserMenu = function() {
        console.log('User menu clicked');
    };

    window.toggleText = function(noteId) {
        const textEl = document.getElementById('text-' + noteId);
        const btnEl = document.getElementById('expand-' + noteId);

        if (textEl.classList.contains('expanded')) {
            textEl.classList.remove('expanded');
            btnEl.textContent = '展开全文 ▼';
        } else {
            textEl.classList.add('expanded');
            btnEl.textContent = '收起 ▲';
        }
    };

    window.openImageModal = function(src) {
        const modal = document.getElementById('imageModal');
        const img = document.getElementById('modalImage');
        modal.classList.add('active');
        img.src = src;
        document.body.style.overflow = 'hidden';
    };

    window.closeImageModal = function() {
        document.getElementById('imageModal').classList.remove('active');
        document.body.style.overflow = 'auto';
    };

    // Throttled API functions
    const toggleFavoriteThrottled = throttle(function(noteId, btn) {
        NetworkManager.fetchWithRetry(`/toggle_favorite/${noteId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                btn.classList.toggle('active');
                btn.textContent = btn.classList.contains('active') ? '★' : '☆';
            }
        })
        .catch(error => {
            console.error('收藏操作失败:', error);
            alert('收藏操作失败: ' + error.message);
        });
    }, 1000);

    window.toggleFavorite = function(noteId, btn) {
        toggleFavoriteThrottled(noteId, btn);
    };

    const deleteNoteThrottled = throttle(function(noteId) {
        if (!confirm('确定要删除这条笔记吗?此操作不可撤销。')) return;

        NetworkManager.fetchWithRetry(`/delete_note/${noteId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                throw new Error(data.error || '删除失败');
            }
        })
        .catch(error => {
            console.error('删除笔记失败:', error);
            alert('删除笔记失败: ' + error.message);
        });
    }, 1000);

    window.deleteNote = function(noteId) {
        deleteNoteThrottled(noteId);
    };

    const calibrateNoteThrottled = throttle(function(noteId, count, btn) {
        // 根据连接类型估算时间
        const connType = NetworkManager.detectConnectionType();
        const estimatedTime = Math.ceil(count * (connType === 'slow-2g' || connType === '2g' ? 15 : 10));

        if (!confirm(`校准将向机器人发送 ${count} 个磁力链接,预计需要约 ${estimatedTime} 秒 (${connType} 连接)。确定继续?`)) return;

        btn.disabled = true;
        btn.textContent = '校准中...';
        const originalText = `校准${count > 1 ? '(' + count + ')' : ''}`;

        // 使用更长的超时时间用于校准 API (基础超时 * 链接数)
        const baseTimeout = NetworkManager.getApiTimeout();
        const calibrateTimeout = Math.min(baseTimeout * count, 60000); // 最多60秒

        NetworkManager.fetchWithRetry(`/api/calibrate/${noteId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        }, 2) // 校准操作最多重试2次
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                alert(`校准完成!\n总共: ${data.total}\n成功: ${data.success_count}\n失败: ${data.fail_count}`);
                setTimeout(() => location.reload(), 1000);
            } else {
                throw new Error(data.error || '未知错误');
            }
        })
        .catch(error => {
            console.error('校准出错:', error);
            alert('校准失败: ' + error.message);
            btn.disabled = false;
            btn.textContent = originalText;
        });
    }, 1000);

    window.calibrateNote = function(noteId, count, btn) {
        calibrateNoteThrottled(noteId, count, btn);
    };

    // DOMContentLoaded event handler
    document.addEventListener('DOMContentLoaded', function() {
        // Initialize saved theme
        const savedTheme = localStorage.getItem('theme');
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        }

        // Initialize lazy loading with Intersection Observer
        initLazyLoading();

        // Check text length and show expand button
        document.querySelectorAll('.note-text').forEach(function(el) {
            if (el.scrollHeight > 120) {
                const id = el.id.replace('text-', '');
                const expandBtn = document.getElementById('expand-' + id);
                if (expandBtn) {
                    expandBtn.style.display = 'inline-block';
                }
            }
        });

        // Click outside sidebar to close (mobile only)
        const sidebar = document.getElementById('sidebar');
        const mainContent = document.querySelector('.main-content');

        if (sidebar && mainContent) {
            mainContent.addEventListener('click', function(e) {
                if (MobileUIState.isMobile && MobileUIState.sidebarOpen) {
                    MobileUIState.sidebarOpen = false;
                    MobileUIState.syncDOM();
                    MobileUIState.persist();
                }
            });
        }

        // Initialize unified UI state management
        MobileUIState.init();

        // Top search input with Enter key and debounce
        const topSearchInput = document.getElementById('topSearchInput');
        if (topSearchInput) {
            // Handle Enter key for immediate search
            topSearchInput.addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    const searchQuery = this.value.trim();
                    if (searchQuery) {
                        window.location.href = `/notes?page=1&search=${encodeURIComponent(searchQuery)}`;
                    }
                }
            });

            // Debounced input handler for auto-search (300ms delay)
            const debouncedSearch = debounce(function(e) {
                const searchQuery = e.target.value.trim();
                // Only trigger auto-search for queries >= 3 characters
                if (searchQuery.length >= 3) {
                    console.log('Auto-search triggered for:', searchQuery);
                    // Optional: uncomment to enable auto-search
                    // window.location.href = `/notes?page=1&search=${encodeURIComponent(searchQuery)}`;
                }
            }, 300);

            // Attach debounced input listener
            topSearchInput.addEventListener('input', debouncedSearch);
        }
    });

    // Window resize handler
    window.addEventListener('resize', function() {
        MobileUIState.updateViewport();
    });

    // ESC key to close modal
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            window.closeImageModal();
        }
    });

    // Initialize NetworkManager
    NetworkManager.init();

})();
