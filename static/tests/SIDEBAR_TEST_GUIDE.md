# Sidebar State Manual Test Guide

## Test Environment Setup

### Prerequisites
- Modern browser (Chrome, Firefox, Safari, Edge)
- Browser DevTools (F12)
- Ability to toggle device emulation mode

## Automated Tests

### Running Unit Tests

1. Open test page:
   ```
   http://localhost:5000/static/tests/sidebar-test.html
   ```

2. Click "Run Tests" button

3. Expected results:
   - All tests should pass (green)
   - Success rate: 100%
   - No errors in console output

### Test Coverage

The automated tests cover:
- Initial state persistence
- Toggle synchronization
- DOM class synchronization
- State verification
- Persist function return value
- State reload simulation
- Viewport transition handling

## Manual Tests

### Test 1: Mobile First Visit

**Objective**: Verify sidebar opens by default on mobile first visit

**Steps**:
1. Clear browser localStorage:
   ```javascript
   localStorage.clear()
   ```
2. Open DevTools and enable mobile emulation (375x667)
3. Navigate to `/notes`
4. Observe sidebar state

**Expected**:
- Sidebar should be open initially
- After 3 seconds, sidebar should auto-close
- localStorage should contain `mobileUIState` with `sidebarOpen: false`

**Verification**:
```javascript
// Check localStorage
JSON.parse(localStorage.getItem('mobileUIState'))
// Should show: {sidebarOpen: false, timestamp: ...}
```

---

### Test 2: Desktop First Visit

**Objective**: Verify sidebar is closed by default on desktop first visit

**Steps**:
1. Clear browser localStorage
2. Disable mobile emulation (1920x1080)
3. Navigate to `/notes`
4. Observe sidebar state

**Expected**:
- Sidebar should be closed initially
- localStorage should contain `mobileUIState` with `sidebarOpen: false`

---

### Test 3: State Persistence After Toggle

**Objective**: Verify state persists after manual toggle

**Steps**:
1. On mobile view, toggle sidebar open
2. Check localStorage:
   ```javascript
   JSON.parse(localStorage.getItem('mobileUIState'))
   ```
3. Refresh page (F5)
4. Observe sidebar state

**Expected**:
- localStorage should reflect toggled state
- After refresh, sidebar should maintain the same state
- No state mismatch warnings in console

---

### Test 4: State Persistence Across Page Refresh

**Objective**: Verify state survives page reload

**Steps**:
1. Set sidebar to open state
2. Note the state in localStorage
3. Hard refresh (Ctrl+F5)
4. Check sidebar state

**Expected**:
- Sidebar state should be identical before and after refresh
- Console should show "Loaded saved sidebar state: true"
- No state verification warnings

---

### Test 5: Mobile to Desktop Transition

**Objective**: Verify state handling during viewport changes

**Steps**:
1. Start in mobile view (375px width)
2. Close sidebar
3. Expand viewport to desktop (1024px width)
4. Observe sidebar state

**Expected**:
- Sidebar should auto-open when transitioning to desktop
- localStorage should update to `sidebarOpen: true`
- Console should show "Desktop mode: auto-opening sidebar"

---

### Test 6: Desktop to Mobile Transition

**Objective**: Verify state handling during viewport changes

**Steps**:
1. Start in desktop view (1024px width)
2. Open sidebar
3. Shrink viewport to mobile (375px width)
4. Observe sidebar state

**Expected**:
- Sidebar should auto-close when transitioning to mobile
- localStorage should update to `sidebarOpen: false`
- Console should show "Mobile mode: closing sidebar"

---

### Test 7: State Synchronization Verification

**Objective**: Test auto-fix mechanism for state mismatch

**Steps**:
1. Open browser console
2. Manually corrupt localStorage:
   ```javascript
   localStorage.setItem('mobileUIState', JSON.stringify({sidebarOpen: false}))
   ```
3. Set memory state to opposite:
   ```javascript
   MobileUIState.sidebarOpen = true
   ```
4. Call verification:
   ```javascript
   MobileUIState.verifyStateSync()
   ```

**Expected**:
- Console should show "State mismatch detected!"
- Auto-fix should persist current memory state
- localStorage should be updated to match memory state

---

### Test 8: DOM Class Synchronization

**Objective**: Verify DOM classes match state

**Steps**:
1. In mobile view, open sidebar
2. Inspect sidebar element classes
3. Close sidebar
4. Inspect sidebar element classes again

**Expected**:
- When open: sidebar should have `mobile-open` class
- When closed: sidebar should NOT have `mobile-open` class
- Toggle button text should update accordingly

---

### Test 9: Multiple Rapid Toggles

**Objective**: Test state consistency under rapid changes

**Steps**:
1. Click toggle button 10 times rapidly
2. Check final state in memory and localStorage
3. Refresh page
4. Verify state persisted correctly

**Expected**:
- Final state should be consistent
- No race conditions or state mismatches
- State should survive page refresh

---

### Test 10: Click Outside to Close (Mobile)

**Objective**: Verify clicking main content closes sidebar on mobile

**Steps**:
1. In mobile view, open sidebar
2. Click on main content area
3. Observe sidebar state

**Expected**:
- Sidebar should close
- localStorage should update to `sidebarOpen: false`
- Console should show state change

---

## Console Verification Commands

### Check Current State
```javascript
MobileUIState.getState()
```

### Check localStorage
```javascript
JSON.parse(localStorage.getItem('mobileUIState'))
```

### Force State Sync
```javascript
MobileUIState.verifyStateSync()
```

### Manual Toggle
```javascript
MobileUIState.toggleSidebar()
```

### Clear State
```javascript
localStorage.removeItem('mobileUIState')
```

## Expected Console Output

### Normal Initialization (First Visit - Mobile)
```
First visit on mobile: opening sidebar by default
State persisted to localStorage: {sidebarOpen: true, timestamp: ...}
DOM synced - Mode: mobile Open: true Classes: sidebar mobile-open
State verification passed - Memory and storage are in sync
MobileUIState initialized: {sidebarOpen: true, viewportWidth: 375, isMobile: true}
```

### Normal Initialization (Returning Visit)
```
Loaded saved sidebar state: false
DOM synced - Mode: mobile Open: false Classes: sidebar
State verification passed - Memory and storage are in sync
MobileUIState initialized: {sidebarOpen: false, viewportWidth: 375, isMobile: true}
```

### After Toggle
```
DOM synced - Mode: mobile Open: true Classes: sidebar mobile-open
State persisted to localStorage: {sidebarOpen: true, timestamp: ...}
Sidebar toggled: true
```

## Troubleshooting

### Issue: State not persisting
**Solution**: Check if localStorage is enabled and not full

### Issue: State mismatch warnings
**Solution**: Auto-fix should handle this, but verify by calling `verifyStateSync()`

### Issue: DOM classes not updating
**Solution**: Check if sidebar element exists with ID 'sidebar'

### Issue: Tests failing
**Solution**: Clear localStorage and reload page before running tests

## Success Criteria

All tests should pass with:
- No console errors
- State always synchronized between memory and localStorage
- DOM classes always match current state
- State persists across page refreshes
- Viewport transitions handled correctly
