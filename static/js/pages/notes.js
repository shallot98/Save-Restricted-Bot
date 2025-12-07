/**
 * Notes Page Main Logic
 * Version: 1.0
 */

(function() {
    'use strict';

    // Global function exports for inline onclick handlers
    window.toggleSidebar = function() {
        if (window.MobileUIState.clickSuppressed) return;
        window.MobileUIState.toggleSidebar();
    };

    window.toggleMobileSidebar = function() {
        if (window.MobileUIState.clickSuppressed) return;
        window.MobileUIState.toggleSidebar();
    };

    window.toggleTheme = function() {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-theme');
        html.setAttribute('data-theme', currentTheme === 'dark' ? '' : 'dark');
        window.StorageManager.setItem('theme', currentTheme === 'dark' ? 'light' : 'dark');
    };

    window.toggleSearch = function() {
        window.SearchManager.toggleSearch();
    };

    window.toggleFilter = function() {
        window.SearchManager.toggleFilter();
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
        window.ModalManager.openImageModal(src);
    };

    window.closeImageModal = function() {
        window.ModalManager.closeImageModal();
    };

    // Throttled API functions
    const toggleFavoriteThrottled = window.PerformanceUtils.throttle(function(noteId, btn) {
        window.NetworkManager.fetchWithRetry('/toggle_favorite/' + noteId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                btn.classList.toggle('active');
                btn.textContent = btn.classList.contains('active') ? '★' : '☆';
            }
        })
        .catch(function(error) {
            console.error('收藏操作失败:', error);
            alert('收藏操作失败: ' + error.message);
        });
    }, 1000);

    window.toggleFavorite = function(noteId, btn) {
        toggleFavoriteThrottled(noteId, btn);
    };

    const deleteNoteThrottled = window.PerformanceUtils.throttle(function(noteId) {
        if (!confirm('确定要删除这条笔记吗?此操作不可撤销。')) return;

        window.NetworkManager.fetchWithRetry('/delete_note/' + noteId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(function(response) { return response.json(); })
        .then(function(data) {
            if (data.success) {
                location.reload();
            } else {
                throw new Error(data.error || '删除失败');
            }
        })
        .catch(function(error) {
            console.error('删除笔记失败:', error);
            alert('删除笔记失败: ' + error.message);
        });
    }, 1000);

    window.deleteNote = function(noteId) {
        deleteNoteThrottled(noteId);
    };

    const calibrateNoteThrottled = window.PerformanceUtils.throttle(function(noteId, count, btn) {
        // 根据连接类型估算时间
        const connType = window.NetworkManager.detectConnectionType();
        const estimatedTime = Math.ceil(count * (connType === 'slow-2g' || connType === '2g' ? 15 : 10));

        if (!confirm('校准将向机器人发送 ' + count + ' 个磁力链接,预计需要约 ' + estimatedTime + ' 秒 (' + connType + ' 连接)。确定继续?')) return;

        btn.disabled = true;
        btn.textContent = '校准中...';
        const originalText = '校准' + (count > 1 ? '(' + count + ')' : '');

        // 使用更长的超时时间用于校准 API (基础超时 * 链接数)
        const baseTimeout = window.NetworkManager.getApiTimeout();
        const calibrateTimeout = Math.min(baseTimeout * count, 60000); // 最多60秒

        window.NetworkManager.fetchWithRetry('/api/calibrate/' + noteId, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        }, 2) // 校准操作最多重试2次
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status + ': ' + response.statusText);
            }
            return response.json();
        })
        .then(function(data) {
            if (data.success) {
                alert('校准完成!\n总共: ' + data.total + '\n成功: ' + data.success_count + '\n失败: ' + data.fail_count);
                setTimeout(function() { location.reload(); }, 1000);
            } else {
                throw new Error(data.error || '未知错误');
            }
        })
        .catch(function(error) {
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
        const savedTheme = window.StorageManager.getItem('theme', 'light');
        if (savedTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
        }

        // Initialize lazy loading with Intersection Observer
        window.LazyLoadManager.init();

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
                if (window.MobileUIState.isMobile && window.MobileUIState.sidebarOpen) {
                    window.MobileUIState.sidebarOpen = false;
                    window.MobileUIState.syncDOM();
                    window.MobileUIState.persist();
                }
            });
        }

        // Initialize unified UI state management
        window.MobileUIState.init();

        // Initialize search input handlers
        window.SearchManager.initSearchInput();

        // Initialize modal event listeners
        window.ModalManager.init();
    });

    // Window resize handler
    window.addEventListener('resize', function() {
        window.MobileUIState.updateViewport();
    });

    // Initialize NetworkManager
    window.NetworkManager.init();

})();
