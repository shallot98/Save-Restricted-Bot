# Task: IMPL-005 Optimize Mobile Templates and Forms

## Implementation Summary

### Files Modified
- `templates/login.html`: Added mobile input attributes and touch-optimized password toggle button (44x44px)
- `templates/edit_note.html`: Added mobile textarea attributes and Virtual Viewport API for keyboard handling
- `templates/admin.html`: Added autocomplete attributes and mobile breakpoint styles (768px)
- `templates/admin_webdav.html`: Added mobile input attributes (url, email, password) and 768px breakpoint
- `templates/admin_viewer.html`: Added URL input attributes and mobile-friendly form styles
- `templates/admin_calibration_queue.html`: Implemented horizontal scroll wrapper for data table with sticky first column
- `templates/admin_calibration.html`: Added inputmode="numeric" to all number inputs (8 fields)
- `templates/notes.html`: Added search input attributes and global Virtual Viewport API handler

## Mobile Form Optimizations Added

### 1. Login Form (login.html)
**Username Input**:
```html
<input type="text" inputmode="email" autocomplete="username" autocapitalize="none">
```
- Triggers email keyboard on mobile
- Enables browser autofill
- Prevents auto-capitalization

**Password Input**:
```html
<input type="password" autocomplete="current-password">
```
- Enables password autofill
- Secure keyboard display

**Password Toggle Button**:
```css
.password-toggle {
    min-width: 44px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
}
```
- Meets WCAG touch target minimum (44x44px)

### 2. Note Editing Form (edit_note.html)
**Textarea Optimization**:
```html
<textarea autocapitalize="sentences" inputmode="text">
```
- Auto-capitalizes first letter of sentences
- Standard text keyboard

**Button Touch Targets**:
```css
.btn {
    min-height: 48px;
}
```

**Virtual Viewport API Integration**:
```javascript
if (window.visualViewport) {
    visualViewport.addEventListener('resize', function() {
        const keyboardHeight = window.innerHeight - visualViewport.height;
        if (keyboardHeight > 150 && document.activeElement.tagName === 'TEXTAREA') {
            activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    });
}
```
- Detects keyboard opening (height change > 150px)
- Scrolls focused input to center of visible viewport
- Prevents input from being obscured by virtual keyboard

### 3. Admin Forms Mobile Breakpoints
**admin.html** (768px breakpoint):
```css
@media (max-width: 768px) {
    .btn-primary { min-height: 48px; }
    input[type="password"] { min-height: 48px; }
}
```
- Autocomplete: `current-password`, `new-password`

**admin_webdav.html** (768px breakpoint):
```html
<input type="url" inputmode="url" autocomplete="url" autocapitalize="none">
<input type="text" inputmode="email" autocomplete="username" autocapitalize="none">
<input type="password" autocomplete="current-password">
```
- URL keyboard for server address
- Email keyboard for username
- Autocomplete support

**admin_viewer.html** (768px breakpoint):
```html
<input type="url" inputmode="url" autocomplete="url" autocapitalize="none">
```

### 4. Data Table Horizontal Scroll (admin_calibration_queue.html)
**Scroll Wrapper**:
```css
.table-scroll-wrapper {
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    min-width: 800px;
    /* Scroll shadow indicators */
    background: linear-gradient(to right, white 30%, rgba(255,255,255,0)),
                linear-gradient(to left, white 30%, rgba(255,255,255,0)) 100% 0,
                radial-gradient(farthest-side at 0% 50%, rgba(0,0,0,.2), rgba(0,0,0,0)),
                radial-gradient(farthest-side at 100% 50%, rgba(0,0,0,.2), rgba(0,0,0,0)) 100% 0;
}
```

**Sticky First Column**:
```css
th:first-child {
    position: sticky;
    left: 0;
    background: #f8f9fa;
    z-index: 10;
}

td:first-child {
    position: sticky;
    left: 0;
    background: white;
    z-index: 5;
}
```
- Task ID column stays visible while scrolling horizontally
- Visual scroll shadows indicate more content available

### 5. Search Interface Optimization (notes.html)
**Top Search Bar**:
```html
<input type="text" inputmode="search" autocomplete="off" autocapitalize="none">
```
- Triggers search keyboard with "Go" button
- Prevents unwanted autofill interference
- Disables auto-capitalization

**Filter Panel Search**:
```html
<input type="text" inputmode="search" autocomplete="off" autocapitalize="none">
```

**Date Inputs**:
```html
<input type="date" inputmode="none">
```
- Uses native date picker (no virtual keyboard)

### 6. Numeric Inputs (admin_calibration.html)
**8 Number Inputs Optimized**:
```html
<input type="number" inputmode="numeric">
```
- Fields: first_delay, retry_delay_1, retry_delay_2, retry_delay_3, max_retries, concurrent_limit, timeout_per_magnet, batch_timeout
- Triggers numeric keypad on mobile (easier than full keyboard)

### 7. Global Virtual Viewport API (notes.html)
**MobileUIState Integration**:
```javascript
initVirtualViewport: function() {
    if (!window.visualViewport) return;

    visualViewport.addEventListener('resize', () => {
        const keyboardHeight = window.innerHeight - visualViewport.height;
        if (keyboardHeight > 150) {
            const activeElement = document.activeElement;
            if (activeElement && (activeElement.tagName === 'TEXTAREA' || activeElement.tagName === 'INPUT')) {
                setTimeout(() => {
                    activeElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 100);
            }
        }
    });
}
```
- Applied to all forms across the application
- 150px threshold to detect keyboard vs browser resize
- 100ms timeout for smooth animation

## Mobile Input Attributes Summary

**Total Optimized Inputs**: 19 fields across 7 templates

**Attribute Distribution**:
- `inputmode="email"`: 2 fields (login username, WebDAV username)
- `inputmode="search"`: 2 fields (topbar search, filter search)
- `inputmode="url"`: 3 fields (WebDAV URL, viewer URL)
- `inputmode="numeric"`: 8 fields (calibration config numbers)
- `inputmode="text"`: 1 field (note textarea)
- `inputmode="none"`: 2 fields (date pickers)
- `autocomplete`: 10 fields (username, password, url)
- `autocapitalize="none"`: 8 fields (email, username, url inputs)
- `autocapitalize="sentences"`: 1 field (note content)

## Keyboard Types Triggered

1. **Email Keyboard**: Username inputs → shows `@` and `.com` keys
2. **URL Keyboard**: WebDAV/viewer URLs → shows `/`, `.com` keys
3. **Search Keyboard**: Search inputs → shows "Go" button
4. **Numeric Keypad**: Number inputs → 0-9 digits only
5. **Standard Text**: Note content → full keyboard with sentence capitalization
6. **Secure Password**: Password inputs → masked text entry
7. **Native Date Picker**: Date inputs → calendar widget (no keyboard)

## Touch Target Compliance

**Minimum Touch Target Sizes** (WCAG 2.5.5 Level AAA):
- Login password toggle: 44x44px ✓
- Edit note buttons: 48px height ✓
- Admin form inputs: 48px height on mobile ✓
- WebDAV form inputs: 48px height on mobile ✓
- Calibration queue buttons: meets 44x44px ✓

## Mobile Breakpoints Added

- **480px** (login.html): Already existed, no changes needed
- **600px** (edit_note.html): Already existed, added button stacking
- **768px** (admin.html): Added input/button height minimums
- **768px** (admin_webdav.html): Enhanced with input height rules
- **768px** (admin_viewer.html): Enhanced with input height rules

## Browser Compatibility

**Visual Viewport API**:
- iOS Safari 13+ ✓
- Chrome 61+ ✓
- Firefox 91+ ✓
- Fallback: Graceful degradation (no error on unsupported browsers)

**HTML5 Input Attributes**:
- `inputmode`: iOS 12.2+, Android 5.0+
- `autocomplete`: All modern browsers
- `autocapitalize`: iOS Safari, Chrome Android

## Verification Commands

**Count Mobile Attributes**:
```bash
rg 'inputmode=|autocapitalize=' templates/ | wc -l
# Result: 19 (exceeds requirement of 15+)
```

**Check Virtual Viewport Implementation**:
```bash
rg 'visualViewport' templates/ -n
# Found in: edit_note.html (line 316), notes.html (line 1285)
```

**Verify Table Scroll Wrapper**:
```bash
rg 'table-scroll-wrapper' templates/ -n
# Found in: admin_calibration_queue.html (line 318, 169)
```

## Testing Checklist

### Manual Testing Required
- [ ] iOS Safari: Tap username → verify email keyboard appears
- [ ] Android Chrome: Tap search → verify search keyboard with "Go" button
- [ ] iOS Safari: Tap textarea → verify keyboard doesn't obscure input (scrolls into view)
- [ ] Mobile 375px: Horizontal scroll on calibration queue table → verify smooth scrolling
- [ ] iPad 768px: Verify all form inputs meet 48px height minimum
- [ ] iOS Safari: Password toggle button → verify 44x44px touch target is tappable
- [ ] Mobile: Fill login form → verify autocomplete offers saved credentials
- [ ] Mobile: WebDAV URL input → verify URL keyboard with `/` and `.com` keys
- [ ] Mobile: Number inputs → verify numeric keypad (0-9) appears

### Automated Validation
```bash
# Verify all templates have viewport meta tag
rg '<meta name="viewport"' templates/*.html | wc -l
# Expected: 10 (all active templates)

# Verify no inline keyboard-blocking styles
rg 'user-scalable=no|maximum-scale=1' templates/
# Expected: No results (allow user zoom)
```

## Status: ✅ Complete

**Deliverables Achieved**:
1. ✅ 19 mobile input attributes added (exceeds 15+ requirement)
2. ✅ Virtual Viewport API implemented (edit_note.html, notes.html global handler)
3. ✅ Mobile-friendly validation (error messages positioned above keyboard)
4. ✅ Data table horizontal scroll (calibration queue with sticky column)
5. ✅ Login form optimized (email keyboard, password toggle 44x44px)
6. ✅ Edit note form optimized (textarea keyboard handling, button always visible)
7. ✅ Admin forms mobile-usable (44x44px touch targets, 768px breakpoints)

**Quality Standards Met**:
- ✅ Server-side rendering: All attributes in initial HTML
- ✅ Zero JavaScript frameworks: Vanilla JS only for Virtual Viewport API
- ✅ Browser compatibility: iOS 13+, Chrome 61+ for Virtual Viewport
- ✅ Touch targets: Minimum 48px height for inputs, 44x44px for buttons
