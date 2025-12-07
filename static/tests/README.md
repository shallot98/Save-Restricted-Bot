# Sidebar State Tests

## Overview

This directory contains testing tools for the sidebar state management fix (IMPL-3.1).

## Files

### Test Files
- **sidebar-test.html** - Interactive test page with UI
- **sidebar.test.js** - Unit test suite (7 test cases)
- **verify-sidebar-fix.js** - Quick verification script for browser console

### Documentation
- **SIDEBAR_TEST_GUIDE.md** - Comprehensive manual testing guide
- **README.md** - This file

## Quick Start

### Option 1: Automated Tests (Recommended)

1. Start the application server
2. Open browser and navigate to:
   ```
   http://localhost:5000/static/tests/sidebar-test.html
   ```
3. Click "Run Tests" button
4. Review results (should show 100% pass rate)

### Option 2: Quick Console Verification

1. Open any page with sidebar (e.g., `/notes`)
2. Open browser DevTools (F12)
3. Load verification script:
   ```javascript
   // Copy and paste the content of verify-sidebar-fix.js
   // Or load it via script tag
   ```
4. Check console output for verification results

### Option 3: Manual Testing

Follow the detailed guide in `SIDEBAR_TEST_GUIDE.md` for comprehensive manual testing scenarios.

## Test Coverage

### Automated Tests (7 test cases)

1. **Initial State Persistence** - Verifies state is saved on first visit
2. **Toggle Synchronization** - Verifies state syncs after toggle
3. **DOM Class Sync** - Verifies DOM classes match state (mobile/desktop)
4. **State Verification** - Tests auto-fix mechanism
5. **Persist Return Value** - Verifies persist() returns boolean
6. **State Reload** - Tests state persistence across page refresh
7. **Viewport Transition** - Tests mobile ↔ desktop transitions

### Manual Test Scenarios (10 scenarios)

1. Mobile first visit
2. Desktop first visit
3. State persistence after toggle
4. State persistence across page refresh
5. Mobile to desktop transition
6. Desktop to mobile transition
7. State synchronization verification
8. DOM class synchronization
9. Multiple rapid toggles
10. Click outside to close (mobile)

## Expected Results

### All Tests Should Pass

- **Automated Tests**: 7/7 passed (100%)
- **Manual Tests**: All scenarios working as expected
- **Console Verification**: All checks passed

### Key Behaviors

1. **Mobile First Visit**:
   - Sidebar opens by default
   - Auto-closes after 3 seconds
   - State saved to localStorage

2. **State Persistence**:
   - State survives page refresh
   - State syncs between memory and localStorage
   - Auto-fix mechanism corrects mismatches

3. **Viewport Transitions**:
   - Mobile → Desktop: Sidebar auto-opens if closed
   - Desktop → Mobile: Sidebar auto-closes

## Troubleshooting

### Tests Failing

1. Clear localStorage:
   ```javascript
   localStorage.clear()
   ```
2. Reload page
3. Run tests again

### State Mismatch Warnings

This is expected behavior - the auto-fix mechanism will correct it automatically.

### Console Errors

Check that all required scripts are loaded:
- `/static/js/utils/storage.js`
- `/static/js/components/sidebar.js`

## Browser Compatibility

Tested on:
- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers

## Development

### Adding New Tests

Edit `sidebar.test.js` and add new test methods:

```javascript
testNewFeature: function() {
    console.log('\n=== Test: New Feature ===');

    // Test logic here
    this.assert(condition, 'testNewFeature', 'Description');
}
```

Then add to `runAll()` method:

```javascript
this.testNewFeature();
```

### Debugging Tests

Enable verbose logging in browser console:
```javascript
localStorage.setItem('debug', 'true');
```

## Support

For issues or questions, refer to:
- Task summary: `/.workflow/active/WFS-web-refactor-bugfix/.summaries/IMPL-3.1-summary.md`
- Test guide: `SIDEBAR_TEST_GUIDE.md`
- Source code: `/static/js/components/sidebar.js`

## License

Part of Save-Restricted-Bot project.
