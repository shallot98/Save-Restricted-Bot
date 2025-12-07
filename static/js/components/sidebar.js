/**
 * Unified Mobile UI State Management
 * Version: 1.0
 */

(function() {
    'use strict';

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
                const saved = window.StorageManager.getItem(this.STORAGE_KEY, null);
                if (saved) {
                    // 已有保存状态,加载并应用
                    // 移动端始终默认关闭侧边栏（用户可通过菜单按钮打开）
                    if (this.isMobile) {
                        this.sidebarOpen = false;
                        console.log('Mobile mode: sidebar closed by default');
                    } else {
                        // 桌面端使用保存的状态
                        this.sidebarOpen = saved.sidebarOpen !== false;
                        console.log('Desktop mode: loaded saved sidebar state:', this.sidebarOpen);
                    }
                } else {
                    // 首次访问
                    if (this.isMobile) {
                        // 移动端默认关闭侧边栏
                        this.sidebarOpen = false;
                        console.log('First visit on mobile: sidebar closed by default');
                    } else {
                        // 桌面端默认打开侧边栏
                        this.sidebarOpen = true;
                        console.log('First visit on desktop: sidebar open by default');
                    }
                    // 保存初始状态
                    this.persist();
                }
            } catch (e) {
                console.warn('Failed to load saved UI state:', e);
                this.sidebarOpen = this.isMobile ? false : true;
            }

            // Apply initial state to DOM
            this.syncDOM();

            // Verify state synchronization
            this.verifyStateSync();

            // Initialize touch event listeners
            this.initTouchEvents();

            // Initialize Virtual Viewport API for keyboard handling
            this.initVirtualViewport();

            // 移动端首次访问显示提示
            if (this.isMobile) {
                var self = this;
                setTimeout(function() {
                    self.showMobileHint();
                }, 1000);
            }

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
            if (!sidebar) {
                console.warn('Sidebar element not found, cannot sync DOM');
                return;
            }

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

            // Log state change for debugging
            console.log('DOM synced - Mode:', this.isMobile ? 'mobile' : 'desktop',
                       'Open:', this.sidebarOpen,
                       'Classes:', sidebar.className);
        },

        // Persist state to localStorage
        persist: function() {
            const stateToSave = {
                sidebarOpen: this.sidebarOpen,
                timestamp: Date.now()
            };

            const success = window.StorageManager.setItem(this.STORAGE_KEY, stateToSave);

            if (success) {
                console.log('State persisted to localStorage:', stateToSave);
            } else {
                console.error('Failed to persist state to localStorage');
            }

            return success;
        },

        // Verify state synchronization between memory and localStorage
        verifyStateSync: function() {
            try {
                const saved = window.StorageManager.getItem(this.STORAGE_KEY, null);
                if (saved) {
                    const isSync = saved.sidebarOpen === this.sidebarOpen;
                    if (!isSync) {
                        console.warn('State mismatch detected!',
                                   'Memory:', this.sidebarOpen,
                                   'Storage:', saved.sidebarOpen);
                        // Auto-fix: persist current state
                        this.persist();
                    } else {
                        console.log('State verification passed - Memory and storage are in sync');
                    }
                    return isSync;
                }
            } catch (e) {
                console.error('State verification failed:', e);
                return false;
            }
            return true;
        },

        // Initialize touch event listeners for swipe gestures
        initTouchEvents: function() {
            const sidebar = document.getElementById('sidebar');
            if (!sidebar) return;

            // touchstart: Record initial touch position and timestamp
            sidebar.addEventListener('touchstart', function(e) {
                const touch = e.touches[0];
                MobileUIState.touchState.startX = touch.clientX;
                MobileUIState.touchState.startY = touch.clientY;
                MobileUIState.touchState.currentX = touch.clientX;
                MobileUIState.touchState.currentY = touch.clientY;
                MobileUIState.touchState.startTime = Date.now();
                MobileUIState.touchState.isSwiping = false;
            }, { passive: true });

            // touchmove: Update current touch position with passive listener
            sidebar.addEventListener('touchmove', function(e) {
                if (e.touches.length === 0) return;
                const touch = e.touches[0];
                MobileUIState.touchState.currentX = touch.clientX;
                MobileUIState.touchState.currentY = touch.clientY;
                MobileUIState.touchState.isSwiping = true;
            }, { passive: true });

            // touchend: Calculate swipe and trigger action if threshold met
            sidebar.addEventListener('touchend', function(e) {
                MobileUIState.touchState.endTime = Date.now();
                MobileUIState.handleSwipeGesture();
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
                console.log('Swipe detected: deltaX=' + deltaX.toFixed(1) + 'px, velocity=' + velocity.toFixed(3) + 'px/ms');

                // Close sidebar
                this.toggleSidebar();

                // Suppress click events temporarily to prevent double-firing
                this.clickSuppressed = true;
                setTimeout(function() {
                    MobileUIState.clickSuppressed = false;
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

            visualViewport.addEventListener('resize', function() {
                // Detect if keyboard is open
                const viewportHeight = visualViewport.height;
                const windowHeight = window.innerHeight;
                const keyboardHeight = windowHeight - viewportHeight;

                if (keyboardHeight > 150) {
                    // Keyboard is open
                    const activeElement = document.activeElement;
                    if (activeElement && (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT')) {
                        // Scroll active input into view
                        setTimeout(function() {
                            activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }, 100);
                    }
                }
            });

            console.log('Virtual Viewport API initialized for keyboard handling');
        },

        // Show mobile hint
        showMobileHint: function() {
            // 检查是否已经显示过提示
            var hintShown = window.StorageManager.getItem('mobileHintShown', false);
            if (hintShown) {
                return;
            }

            // 创建提示元素
            var hint = document.createElement('div');
            hint.style.cssText = 'position: fixed; top: 70px; left: 50%; transform: translateX(-50%); ' +
                'background: var(--primary-color); color: white; padding: 12px 20px; ' +
                'border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); ' +
                'z-index: 10000; font-size: 14px; max-width: 90%; text-align: center; ' +
                'animation: slideDown 0.3s ease-out;';
            hint.innerHTML = '💡 点击左上角的 <strong>☰</strong> 按钮可以打开侧边栏菜单';

            // 添加动画样式
            var style = document.createElement('style');
            style.textContent = '@keyframes slideDown { from { opacity: 0; transform: translateX(-50%) translateY(-20px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }';
            document.head.appendChild(style);

            document.body.appendChild(hint);

            // 3秒后自动消失
            setTimeout(function() {
                hint.style.animation = 'slideUp 0.3s ease-out';
                hint.style.opacity = '0';
                hint.style.transform = 'translateX(-50%) translateY(-20px)';
                setTimeout(function() {
                    if (hint.parentNode) {
                        hint.parentNode.removeChild(hint);
                    }
                }, 300);
            }, 3000);

            // 标记已显示
            window.StorageManager.setItem('mobileHintShown', true);
            console.log('Mobile hint displayed');
        }
    };

    // Export to global namespace
    window.MobileUIState = MobileUIState;

})();
