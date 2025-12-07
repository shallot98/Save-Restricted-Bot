/**
 * Quick Verification Script for Sidebar State Fix
 * Run this in browser console to verify the fix
 */

(function() {
    'use strict';

    console.log('========================================');
    console.log('Sidebar State Fix Verification');
    console.log('========================================\n');

    const checks = [];

    // Check 1: MobileUIState exists
    if (typeof window.MobileUIState !== 'undefined') {
        checks.push({name: 'MobileUIState exists', pass: true});
        console.log('[PASS] MobileUIState exists');
    } else {
        checks.push({name: 'MobileUIState exists', pass: false});
        console.error('[FAIL] MobileUIState not found');
        return;
    }

    // Check 2: verifyStateSync function exists
    if (typeof window.MobileUIState.verifyStateSync === 'function') {
        checks.push({name: 'verifyStateSync function exists', pass: true});
        console.log('[PASS] verifyStateSync function exists');
    } else {
        checks.push({name: 'verifyStateSync function exists', pass: false});
        console.error('[FAIL] verifyStateSync function not found');
    }

    // Check 3: persist returns boolean
    const persistResult = window.MobileUIState.persist();
    if (typeof persistResult === 'boolean') {
        checks.push({name: 'persist returns boolean', pass: true});
        console.log('[PASS] persist returns boolean:', persistResult);
    } else {
        checks.push({name: 'persist returns boolean', pass: false});
        console.error('[FAIL] persist does not return boolean');
    }

    // Check 4: localStorage has state
    const savedState = window.StorageManager.getItem('mobileUIState', null);
    if (savedState !== null) {
        checks.push({name: 'localStorage has state', pass: true});
        console.log('[PASS] localStorage has state:', savedState);
    } else {
        checks.push({name: 'localStorage has state', pass: false});
        console.warn('[WARN] localStorage does not have state');
    }

    // Check 5: State has timestamp
    if (savedState && typeof savedState.timestamp === 'number') {
        checks.push({name: 'State has timestamp', pass: true});
        console.log('[PASS] State has timestamp:', new Date(savedState.timestamp).toISOString());
    } else {
        checks.push({name: 'State has timestamp', pass: false});
        console.warn('[WARN] State does not have timestamp');
    }

    // Check 6: State synchronization
    const isSync = window.MobileUIState.verifyStateSync();
    if (isSync) {
        checks.push({name: 'State is synchronized', pass: true});
        console.log('[PASS] State is synchronized');
    } else {
        checks.push({name: 'State is synchronized', pass: false});
        console.error('[FAIL] State is not synchronized');
    }

    // Check 7: DOM element exists
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        checks.push({name: 'Sidebar element exists', pass: true});
        console.log('[PASS] Sidebar element exists');
    } else {
        checks.push({name: 'Sidebar element exists', pass: false});
        console.error('[FAIL] Sidebar element not found');
    }

    // Check 8: DOM classes match state
    if (sidebar) {
        const isMobile = window.MobileUIState.isMobile;
        const isOpen = window.MobileUIState.sidebarOpen;
        let classesMatch = false;

        if (isMobile) {
            classesMatch = isOpen ? sidebar.classList.contains('mobile-open') : !sidebar.classList.contains('mobile-open');
        } else {
            classesMatch = isOpen ? !sidebar.classList.contains('collapsed') : sidebar.classList.contains('collapsed');
        }

        if (classesMatch) {
            checks.push({name: 'DOM classes match state', pass: true});
            console.log('[PASS] DOM classes match state');
        } else {
            checks.push({name: 'DOM classes match state', pass: false});
            console.error('[FAIL] DOM classes do not match state');
        }
    }

    // Summary
    console.log('\n========================================');
    console.log('Verification Summary');
    console.log('========================================');
    const passed = checks.filter(c => c.pass).length;
    const total = checks.length;
    console.log('Passed:', passed + '/' + total);
    console.log('Success Rate:', ((passed / total) * 100).toFixed(2) + '%');

    if (passed === total) {
        console.log('\n✅ All checks passed! Sidebar state fix is working correctly.');
    } else {
        console.log('\n❌ Some checks failed. Please review the issues above.');
    }

    console.log('========================================\n');

    return {
        passed: passed,
        total: total,
        checks: checks
    };
})();
