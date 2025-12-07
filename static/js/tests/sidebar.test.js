/**
 * Unit Tests for MobileUIState (Sidebar Component)
 * Version: 1.0
 */

(function() {
    'use strict';

    const SidebarTests = {
        // Test results storage
        results: [],
        passCount: 0,
        failCount: 0,

        // Test helper: assert
        assert: function(condition, testName, message) {
            if (condition) {
                this.passCount++;
                this.results.push({
                    status: 'PASS',
                    test: testName,
                    message: message || 'Test passed'
                });
                console.log('[PASS]', testName);
            } else {
                this.failCount++;
                this.results.push({
                    status: 'FAIL',
                    test: testName,
                    message: message || 'Test failed'
                });
                console.error('[FAIL]', testName, '-', message);
            }
        },

        // Test helper: assertEquals
        assertEquals: function(actual, expected, testName) {
            const passed = actual === expected;
            this.assert(passed, testName,
                       passed ? 'Values match' : 'Expected: ' + expected + ', Got: ' + actual);
        },

        // Setup: Create mock DOM elements
        setupDOM: function() {
            // Create sidebar element
            const sidebar = document.createElement('aside');
            sidebar.id = 'sidebar';
            sidebar.className = 'sidebar';
            document.body.appendChild(sidebar);

            // Create toggle button text
            const toggleText = document.createElement('span');
            toggleText.id = 'sidebarToggleText';
            sidebar.appendChild(toggleText);

            console.log('Test DOM setup complete');
        },

        // Teardown: Remove mock DOM elements
        teardownDOM: function() {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) {
                sidebar.remove();
            }
            console.log('Test DOM teardown complete');
        },

        // Test 1: Initial state persistence
        testInitialStatePersistence: function() {
            console.log('\n=== Test 1: Initial State Persistence ===');

            // Clear localStorage
            window.StorageManager.removeItem('mobileUIState');

            // Simulate mobile viewport
            Object.defineProperty(window, 'innerWidth', {
                writable: true,
                configurable: true,
                value: 375
            });

            // Initialize MobileUIState
            window.MobileUIState.init();

            // Check if state was persisted
            const saved = window.StorageManager.getItem('mobileUIState', null);
            this.assert(saved !== null, 'testInitialStatePersistence',
                       'Initial state should be saved to localStorage');

            if (saved) {
                this.assertEquals(saved.sidebarOpen, true, 'testInitialStatePersistence_MobileDefault');
            }
        },

        // Test 2: State synchronization after toggle
        testToggleSynchronization: function() {
            console.log('\n=== Test 2: Toggle Synchronization ===');

            // Get initial state
            const initialState = window.MobileUIState.sidebarOpen;

            // Toggle sidebar
            window.MobileUIState.toggleSidebar();

            // Check memory state changed
            this.assertEquals(window.MobileUIState.sidebarOpen, !initialState,
                            'testToggleSynchronization_MemoryState');

            // Check localStorage updated
            const saved = window.StorageManager.getItem('mobileUIState', null);
            if (saved) {
                this.assertEquals(saved.sidebarOpen, !initialState,
                                'testToggleSynchronization_StorageState');
            }
        },

        // Test 3: DOM class synchronization
        testDOMClassSync: function() {
            console.log('\n=== Test 3: DOM Class Synchronization ===');

            const sidebar = document.getElementById('sidebar');
            if (!sidebar) {
                this.assert(false, 'testDOMClassSync', 'Sidebar element not found');
                return;
            }

            // Test mobile mode - open
            window.MobileUIState.isMobile = true;
            window.MobileUIState.sidebarOpen = true;
            window.MobileUIState.syncDOM();

            this.assert(sidebar.classList.contains('mobile-open'),
                       'testDOMClassSync_MobileOpen',
                       'Sidebar should have mobile-open class when open in mobile mode');

            // Test mobile mode - closed
            window.MobileUIState.sidebarOpen = false;
            window.MobileUIState.syncDOM();

            this.assert(!sidebar.classList.contains('mobile-open'),
                       'testDOMClassSync_MobileClosed',
                       'Sidebar should not have mobile-open class when closed in mobile mode');

            // Test desktop mode - open
            window.MobileUIState.isMobile = false;
            window.MobileUIState.sidebarOpen = true;
            window.MobileUIState.syncDOM();

            this.assert(!sidebar.classList.contains('collapsed'),
                       'testDOMClassSync_DesktopOpen',
                       'Sidebar should not have collapsed class when open in desktop mode');

            // Test desktop mode - closed
            window.MobileUIState.sidebarOpen = false;
            window.MobileUIState.syncDOM();

            this.assert(sidebar.classList.contains('collapsed'),
                       'testDOMClassSync_DesktopClosed',
                       'Sidebar should have collapsed class when closed in desktop mode');
        },

        // Test 4: State verification function
        testStateVerification: function() {
            console.log('\n=== Test 4: State Verification ===');

            // Set memory state
            window.MobileUIState.sidebarOpen = true;

            // Manually corrupt localStorage
            window.StorageManager.setItem('mobileUIState', {
                sidebarOpen: false
            });

            // Run verification (should auto-fix)
            const isSync = window.MobileUIState.verifyStateSync();

            // Check if auto-fix worked
            const saved = window.StorageManager.getItem('mobileUIState', null);
            if (saved) {
                this.assertEquals(saved.sidebarOpen, true,
                                'testStateVerification_AutoFix');
            }
        },

        // Test 5: Persist function return value
        testPersistReturnValue: function() {
            console.log('\n=== Test 5: Persist Return Value ===');

            window.MobileUIState.sidebarOpen = true;
            const success = window.MobileUIState.persist();

            this.assert(success === true, 'testPersistReturnValue',
                       'persist() should return true on success');
        },

        // Test 6: State reload after page refresh simulation
        testStateReload: function() {
            console.log('\n=== Test 6: State Reload Simulation ===');

            // Set and persist a state
            window.MobileUIState.sidebarOpen = false;
            window.MobileUIState.persist();

            // Simulate page reload by re-initializing
            window.MobileUIState.init();

            // Check if state was restored
            this.assertEquals(window.MobileUIState.sidebarOpen, false,
                            'testStateReload_StateRestored');
        },

        // Test 7: Viewport transition handling
        testViewportTransition: function() {
            console.log('\n=== Test 7: Viewport Transition ===');

            // Start in desktop mode with sidebar open
            Object.defineProperty(window, 'innerWidth', {
                writable: true,
                configurable: true,
                value: 1024
            });
            window.MobileUIState.updateViewport();
            window.MobileUIState.sidebarOpen = true;
            window.MobileUIState.persist();

            // Transition to mobile
            Object.defineProperty(window, 'innerWidth', {
                writable: true,
                configurable: true,
                value: 375
            });
            window.MobileUIState.updateViewport();

            // Check if sidebar was closed
            this.assertEquals(window.MobileUIState.sidebarOpen, false,
                            'testViewportTransition_DesktopToMobile');

            // Transition back to desktop
            Object.defineProperty(window, 'innerWidth', {
                writable: true,
                configurable: true,
                value: 1024
            });
            window.MobileUIState.updateViewport();

            // Check if sidebar was opened
            this.assertEquals(window.MobileUIState.sidebarOpen, true,
                            'testViewportTransition_MobileToDesktop');
        },

        // Run all tests
        runAll: function() {
            console.log('\n========================================');
            console.log('Starting Sidebar State Tests');
            console.log('========================================\n');

            this.results = [];
            this.passCount = 0;
            this.failCount = 0;

            // Setup
            this.setupDOM();

            // Run tests
            try {
                this.testInitialStatePersistence();
                this.testToggleSynchronization();
                this.testDOMClassSync();
                this.testStateVerification();
                this.testPersistReturnValue();
                this.testStateReload();
                this.testViewportTransition();
            } catch (e) {
                console.error('Test execution error:', e);
            }

            // Teardown
            this.teardownDOM();

            // Print summary
            this.printSummary();
        },

        // Print test summary
        printSummary: function() {
            console.log('\n========================================');
            console.log('Test Summary');
            console.log('========================================');
            console.log('Total Tests:', this.results.length);
            console.log('Passed:', this.passCount);
            console.log('Failed:', this.failCount);
            console.log('Success Rate:', ((this.passCount / this.results.length) * 100).toFixed(2) + '%');
            console.log('========================================\n');

            if (this.failCount > 0) {
                console.log('Failed Tests:');
                this.results.filter(function(r) { return r.status === 'FAIL'; })
                    .forEach(function(r) {
                        console.log('  -', r.test, ':', r.message);
                    });
            }

            return {
                total: this.results.length,
                passed: this.passCount,
                failed: this.failCount,
                results: this.results
            };
        }
    };

    // Export to global namespace
    window.SidebarTests = SidebarTests;

    // Auto-run tests if in test mode
    if (window.location.search.includes('test=sidebar')) {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(function() {
                window.SidebarTests.runAll();
            }, 1000);
        });
    }

})();
