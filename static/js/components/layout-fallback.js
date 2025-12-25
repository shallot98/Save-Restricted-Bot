/**
 * Layout fallback for pages that do NOT load Alpine.js.
 *
 * 目标：
 * - 在 admin 等页面移除 Alpine 后，仍保持顶部栏/侧边栏基本交互可用
 * - 当 Alpine 存在时不介入，避免与现有 x-* 行为冲突
 */

(function() {
    'use strict';

    function init() {
        // 若页面加载了 Alpine（defer），按文档顺序 Alpine 会先执行，本脚本无需介入。
        if (typeof window.Alpine !== 'undefined') return;

        const sidebar = document.getElementById('sidebar');
        const overlay = document.getElementById('sidebarOverlay');
        const sidebarToggle = document.querySelector('[data-action="toggle-sidebar"]');

        const mobileSearchToggle = document.querySelector('[data-action="toggle-mobile-search"]');
        const mobileSearchContainer = document.getElementById('topbarMobileSearch');

        const themeToggle = document.querySelector('[data-action="toggle-theme"]');

        const userMenuToggle = document.querySelector('[data-action="toggle-user-menu"]');
        const userMenuDropdown = document.getElementById('userMenuDropdown');

        // 受控元素移除 x-cloak，改由 hidden 属性控制显隐
        [sidebar, overlay, mobileSearchContainer, userMenuDropdown].forEach(function(el) {
            if (el && el.hasAttribute('x-cloak')) el.removeAttribute('x-cloak');
        });

        let sidebarOpen = window.innerWidth >= 1024;
        let mobileSearchOpen = false;
        let userMenuOpen = false;

        function setHidden(el, hidden) {
            if (!el) return;
            el.hidden = !!hidden;
        }

        function syncSidebar() {
            if (!sidebar) return;
            setHidden(sidebar, !sidebarOpen);

            const isMobile = window.innerWidth < 1024;
            if (overlay) setHidden(overlay, !(isMobile && sidebarOpen));

            // 移动端打开侧边栏时锁定滚动，避免背景滚动穿透
            if (isMobile) {
                document.body.style.overflow = sidebarOpen ? 'hidden' : '';
            } else {
                document.body.style.overflow = '';
            }
        }

        function syncMobileSearch() {
            if (!mobileSearchContainer) return;
            setHidden(mobileSearchContainer, !mobileSearchOpen);
        }

        function syncUserMenu() {
            if (!userMenuDropdown) return;
            setHidden(userMenuDropdown, !userMenuOpen);
        }

        function closeUserMenu() {
            if (!userMenuOpen) return;
            userMenuOpen = false;
            syncUserMenu();
        }

        function closeMobileSearch() {
            if (!mobileSearchOpen) return;
            mobileSearchOpen = false;
            syncMobileSearch();
        }

        // 初始状态
        if (overlay) setHidden(overlay, true);
        if (mobileSearchContainer) setHidden(mobileSearchContainer, true);
        if (userMenuDropdown) setHidden(userMenuDropdown, true);
        syncSidebar();

        // 侧边栏切换
        if (sidebarToggle && sidebar) {
            sidebarToggle.addEventListener('click', function() {
                sidebarOpen = !sidebarOpen;
                syncSidebar();
            });
        }

        if (overlay) {
            overlay.addEventListener('click', function() {
                if (!sidebarOpen) return;
                sidebarOpen = false;
                syncSidebar();
            });
        }

        // 响应式：与原 adminApp 行为一致（桌面端默认打开，移动端默认关闭）
        window.addEventListener('resize', function() {
            sidebarOpen = window.innerWidth >= 1024;
            syncSidebar();
            closeUserMenu();
            closeMobileSearch();
        });

        // 移动端搜索展开/收起
        if (mobileSearchToggle && mobileSearchContainer) {
            mobileSearchToggle.addEventListener('click', function() {
                mobileSearchOpen = !mobileSearchOpen;
                syncMobileSearch();
                if (mobileSearchOpen) {
                    const input = document.getElementById('mobileSearchInput');
                    if (input) input.focus();
                }
            });
        }

        // 主题切换（依赖 topbar.html 内的 ThemeManager）
        if (themeToggle) {
            themeToggle.addEventListener('click', function() {
                if (window.ThemeManager && typeof window.ThemeManager.toggle === 'function') {
                    window.ThemeManager.toggle();
                } else {
                    document.documentElement.classList.toggle('dark');
                }
            });
        }

        // 用户菜单
        if (userMenuToggle && userMenuDropdown) {
            userMenuToggle.addEventListener('click', function(e) {
                e.preventDefault();
                userMenuOpen = !userMenuOpen;
                syncUserMenu();
            });

            document.addEventListener('click', function(e) {
                if (!userMenuOpen) return;
                const target = e.target;
                if (!target) return;
                if (userMenuDropdown.contains(target) || userMenuToggle.contains(target)) return;
                closeUserMenu();
            });

            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeUserMenu();
            });
        }

        // 搜索（Enter 跳转到 notes 搜索）
        function bindSearchEnter(inputId) {
            const input = document.getElementById(inputId);
            if (!input) return;
            input.addEventListener('keypress', function(e) {
                if (e.key !== 'Enter') return;
                const query = String(input.value || '').trim();
                if (!query) return;
                window.location.href = '/notes?page=1&search=' + encodeURIComponent(query);
            });
        }

        bindSearchEnter('topSearchInput');
        bindSearchEnter('mobileSearchInput');
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();

