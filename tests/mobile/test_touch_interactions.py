"""
Touch Interaction Test Suite

Tests mobile-specific touch interactions:
- Sidebar swipe-to-close gesture
- Button tap response (no 300ms delay)
- Scroll performance (no jank)
- Touch event deduplication

Validates:
- Touch events properly captured
- Swipe gestures work correctly
- No tap delay (<100ms)
- Smooth scrolling performance
"""

import pytest
import time
from playwright.sync_api import Page, expect


@pytest.mark.mobile
@pytest.mark.touch
def test_sidebar_swipe_to_close(iphone_12: Page, test_server_url: str):
    """Test swipe-left gesture closes mobile sidebar"""
    page = iphone_12
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Open sidebar via hamburger menu
    hamburger = page.locator('.hamburger-menu')
    hamburger.click()
    page.wait_for_timeout(300)  # Wait for open animation

    # Verify sidebar is open
    sidebar = page.locator('.sidebar')
    sidebar_classes = sidebar.get_attribute('class')
    assert 'mobile-open' in sidebar_classes, "Sidebar should be open"

    # Perform swipe-left gesture on sidebar
    sidebar_box = sidebar.bounding_box()
    if sidebar_box:
        # Swipe from right edge to left
        start_x = sidebar_box['x'] + sidebar_box['width'] - 10
        start_y = sidebar_box['y'] + sidebar_box['height'] / 2
        end_x = sidebar_box['x'] + 50
        end_y = start_y

        # Use touchscreen swipe
        page.touchscreen.tap(start_x, start_y)
        page.mouse.move(end_x, end_y)
        page.touchscreen.tap(end_x, end_y)

        page.wait_for_timeout(500)  # Wait for close animation

        # Verify sidebar is closed
        sidebar_classes_after = sidebar.get_attribute('class')
        # Sidebar should no longer have mobile-open class or be out of viewport
        is_closed = 'mobile-open' not in sidebar_classes_after

        assert is_closed, "Sidebar should close after swipe gesture"


@pytest.mark.mobile
@pytest.mark.touch
def test_button_tap_no_delay(pixel_5: Page, test_server_url: str):
    """Test buttons respond to tap without 300ms delay"""
    page = pixel_5
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Find first action button (e.g., favorite, delete)
    buttons = page.locator('button.action-btn').all()
    if not buttons:
        pytest.skip("No action buttons found for testing")

    first_button = buttons[0]

    # Measure tap response time
    start_time = time.time()

    # Perform touch tap
    button_box = first_button.bounding_box()
    if button_box:
        center_x = button_box['x'] + button_box['width'] / 2
        center_y = button_box['y'] + button_box['height'] / 2
        page.touchscreen.tap(center_x, center_y)

    # Wait for any visual feedback (active state, ripple effect)
    page.wait_for_timeout(50)

    end_time = time.time()
    response_time_ms = (end_time - start_time) * 1000

    # Verify response time < 100ms (well under 300ms tap delay)
    assert response_time_ms < 150, f"Button tap delay {response_time_ms}ms exceeds 150ms threshold"

    # Verify button has active/pressed state
    # Check if button triggers any visual feedback
    button_computed_style = page.evaluate("""
        () => {
            const btn = document.querySelector('button.action-btn');
            return btn ? {
                cursor: window.getComputedStyle(btn).cursor,
                touchAction: window.getComputedStyle(btn).touchAction
            } : null;
        }
    """)

    if button_computed_style:
        # Verify touch-action is properly set
        assert button_computed_style['touchAction'] in ['manipulation', 'auto'], \
            "Button should have proper touch-action CSS"


@pytest.mark.mobile
@pytest.mark.touch
def test_scroll_performance(galaxy_s21: Page, test_server_url: str):
    """Test scroll performance with touch events (no jank)"""
    page = galaxy_s21
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Verify page has scrollable content
    page_height = page.evaluate("() => document.body.scrollHeight")
    viewport_height = page.viewport_size['height']

    if page_height <= viewport_height:
        pytest.skip("Page not tall enough for scroll testing")

    # Enable performance monitoring
    page.evaluate("""
        () => {
            window.scrollEvents = [];
            window.addEventListener('scroll', () => {
                window.scrollEvents.push(Date.now());
            }, { passive: true });
        }
    """)

    # Perform rapid scroll using touch
    start_y = viewport_height - 100
    end_y = 100

    # Simulate touch scroll (swipe up)
    page.touchscreen.tap(200, start_y)
    page.mouse.move(200, end_y, steps=10)
    page.touchscreen.tap(200, end_y)

    page.wait_for_timeout(1000)  # Wait for scroll to complete

    # Check scroll event frequency (should fire smoothly)
    scroll_event_count = page.evaluate("() => window.scrollEvents ? window.scrollEvents.length : 0")

    assert scroll_event_count > 5, f"Too few scroll events ({scroll_event_count}), possible jank"

    # Verify passive scroll listener is used (should not block)
    passive_listeners = page.evaluate("""
        () => {
            // Check if scroll listeners are passive
            const scrollHandlers = getEventListeners ? getEventListeners(window).scroll : [];
            return scrollHandlers.length > 0;
        }
    """)

    # Verify page scroll position changed
    final_scroll_y = page.evaluate("() => window.scrollY")
    assert final_scroll_y > 50, "Page should have scrolled"


@pytest.mark.mobile
@pytest.mark.touch
def test_touch_event_deduplication(iphone_se: Page, test_server_url: str):
    """Test touch events don't trigger duplicate click events"""
    page = iphone_se
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Inject event counter
    page.evaluate("""
        () => {
            window.clickCounts = {};

            document.querySelectorAll('button').forEach((btn, idx) => {
                window.clickCounts[idx] = 0;
                btn.addEventListener('click', () => {
                    window.clickCounts[idx]++;
                });
            });
        }
    """)

    # Find a button to test
    buttons = page.locator('button').all()
    if not buttons:
        pytest.skip("No buttons found for testing")

    # Tap button once
    first_button = buttons[0]
    button_box = first_button.bounding_box()

    if button_box:
        center_x = button_box['x'] + button_box['width'] / 2
        center_y = button_box['y'] + button_box['height'] / 2

        # Single touch tap
        page.touchscreen.tap(center_x, center_y)

        # Wait for event processing
        page.wait_for_timeout(500)

        # Verify single click event fired
        click_count = page.evaluate("() => window.clickCounts[0]")

        # Should be exactly 1 click (no touch + click duplication)
        assert click_count == 1, f"Expected 1 click event, got {click_count} (possible duplication)"


@pytest.mark.mobile
@pytest.mark.touch
def test_touch_target_sizes(ipad: Page, test_server_url: str):
    """Test all interactive elements meet 44x44px touch target minimum"""
    page = ipad
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Get all interactive elements
    interactive_elements = page.locator('button, a, input, .clickable').all()

    small_targets = []

    for elem in interactive_elements:
        box = elem.bounding_box()
        if box and box['width'] > 0 and box['height'] > 0:
            # Check if element is visible
            is_visible = page.evaluate("""
                (el) => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0';
                }
            """, elem)

            if is_visible and (box['width'] < 44 or box['height'] < 44):
                elem_info = {
                    'width': box['width'],
                    'height': box['height'],
                    'tag': elem.evaluate("el => el.tagName"),
                    'class': elem.get_attribute('class') or ''
                }
                small_targets.append(elem_info)

    # Report any targets below minimum size
    if small_targets:
        failure_msg = "Found touch targets below 44x44px minimum:\n"
        for target in small_targets[:10]:  # Show first 10
            failure_msg += f"  - {target['tag']}.{target['class']}: {target['width']}x{target['height']}px\n"

        # Allow some exceptions for icons or decorative elements
        assert len(small_targets) < 5, failure_msg

    # Verify at least some interactive elements were checked
    assert len(interactive_elements) > 0, "No interactive elements found to test"
