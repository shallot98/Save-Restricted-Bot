/**
 * CSP Event Bindings
 *
 * 目标：在启用 CSP `script-src-attr 'none'` 后，替代模板中的 inline 事件属性。
 */

(function() {
    'use strict';

    document.addEventListener('click', function(e) {
        const target = e.target;
        if (!target || typeof target.closest !== 'function') return;

        const batchBtn = target.closest('[data-action="batch-calibrate"]');
        if (!batchBtn) return;

        e.preventDefault();

        if (typeof window.batchCalibrate === 'function') {
            window.batchCalibrate();
            return;
        }

        window.location.href = '/notes';
    });
})();

