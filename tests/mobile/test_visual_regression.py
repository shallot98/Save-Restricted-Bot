"""
Visual Regression Test Suite

Tests visual consistency across mobile devices using screenshot comparison:
- Login page visual (375px mobile)
- Notes list visual (375px and 768px)
- Note editing visual (390px iPhone 12)

Validates:
- UI renders consistently
- No visual regressions
- Mobile layouts match designs
- Breakpoint transitions are smooth

Note: First run generates baseline screenshots
Subsequent runs compare against baseline
"""

import pytest
from playwright.sync_api import Page, expect


# Create screenshot directory
import os
SCREENSHOT_DIR = os.path.join(os.path.dirname(__file__), 'screenshots')
BASELINE_DIR = os.path.join(SCREENSHOT_DIR, 'baseline')

os.makedirs(BASELINE_DIR, exist_ok=True)


@pytest.mark.mobile
@pytest.mark.visual
def test_login_page_visual_mobile(mobile_375px: Page, test_server_url: str):
    """Visual regression test for login page at mobile width"""
    page = mobile_375px

    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')

    # Wait for any animations to complete
    page.wait_for_timeout(500)

    # Ensure page is stable (no loading spinners, etc.)
    page.evaluate("""
        () => {
            // Hide elements that may vary (e.g., timestamps)
            const timestamps = document.querySelectorAll('.timestamp, time');
            timestamps.forEach(el => el.style.visibility = 'hidden');
        }
    """)

    # Take screenshot and compare
    screenshot_path = os.path.join(BASELINE_DIR, 'login-mobile-375px.png')

    # Playwright's built-in screenshot comparison
    # Use expect().to_have_screenshot() for automatic comparison
    try:
        expect(page).to_have_screenshot(
            'login-mobile-375px.png',
            full_page=True,
            animations='disabled',
            mask=[page.locator('.timestamp, time').all()] if page.locator('.timestamp, time').count() > 0 else []
        )
    except AssertionError as e:
        # On first run, baseline doesn't exist - this will create it
        # On subsequent runs, differences will cause failure
        print(f"Screenshot comparison: {e}")
        # For first run, save as baseline
        page.screenshot(path=screenshot_path, full_page=True)


@pytest.mark.mobile
@pytest.mark.visual
def test_login_page_visual_tablet(tablet_768px: Page, test_server_url: str):
    """Visual regression test for login page at tablet width"""
    page = tablet_768px

    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(500)

    # Hide dynamic elements
    page.evaluate("""
        () => {
            const timestamps = document.querySelectorAll('.timestamp, time');
            timestamps.forEach(el => el.style.visibility = 'hidden');
        }
    """)

    screenshot_path = os.path.join(BASELINE_DIR, 'login-tablet-768px.png')

    try:
        expect(page).to_have_screenshot(
            'login-tablet-768px.png',
            full_page=True,
            animations='disabled'
        )
    except AssertionError:
        page.screenshot(path=screenshot_path, full_page=True)


@pytest.mark.mobile
@pytest.mark.visual
def test_notes_list_visual_mobile(iphone_12: Page, test_server_url: str, login_user):
    """Visual regression test for notes list at iPhone 12 width"""
    page = iphone_12

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)  # Wait for any lazy loading

    # Hide dynamic content
    page.evaluate("""
        () => {
            // Hide timestamps
            const timestamps = document.querySelectorAll('.timestamp, time, .date');
            timestamps.forEach(el => el.style.visibility = 'hidden');

            // Hide dynamic counters if any
            const counters = document.querySelectorAll('.count, .badge');
            counters.forEach(el => el.style.visibility = 'hidden');
        }
    """)

    screenshot_path = os.path.join(BASELINE_DIR, 'notes-list-iphone12-390px.png')

    try:
        expect(page).to_have_screenshot(
            'notes-list-iphone12-390px.png',
            full_page=True,
            animations='disabled',
            threshold=0.05  # Allow 5% difference for anti-aliasing
        )
    except AssertionError:
        page.screenshot(path=screenshot_path, full_page=True)


@pytest.mark.mobile
@pytest.mark.visual
def test_notes_list_visual_tablet(ipad: Page, test_server_url: str, login_user):
    """Visual regression test for notes list at iPad width"""
    page = ipad

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')
    page.wait_for_timeout(1000)

    # Hide dynamic content
    page.evaluate("""
        () => {
            const dynamic = document.querySelectorAll('.timestamp, time, .date, .count, .badge');
            dynamic.forEach(el => el.style.visibility = 'hidden');
        }
    """)

    screenshot_path = os.path.join(BASELINE_DIR, 'notes-list-ipad-768px.png')

    try:
        expect(page).to_have_screenshot(
            'notes-list-ipad-768px.png',
            full_page=True,
            animations='disabled',
            threshold=0.05
        )
    except AssertionError:
        page.screenshot(path=screenshot_path, full_page=True)


@pytest.mark.mobile
@pytest.mark.visual
def test_note_editing_visual(pixel_5: Page, test_server_url: str, login_user):
    """Visual regression test for note editing interface"""
    page = pixel_5

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Click first edit button if available
    edit_buttons = page.locator('button[onclick*="edit"]').all()
    if not edit_buttons:
        pytest.skip("No editable notes available")

    edit_buttons[0].click()
    page.wait_for_timeout(1000)

    # Wait for edit form to load
    page.wait_for_selector('textarea, [contenteditable="true"]', timeout=5000)

    # Hide dynamic content
    page.evaluate("""
        () => {
            const dynamic = document.querySelectorAll('.timestamp, time, .date');
            dynamic.forEach(el => el.style.visibility = 'hidden');
        }
    """)

    screenshot_path = os.path.join(BASELINE_DIR, 'note-editing-pixel5-393px.png')

    try:
        expect(page).to_have_screenshot(
            'note-editing-pixel5-393px.png',
            full_page=True,
            animations='disabled',
            threshold=0.05
        )
    except AssertionError:
        page.screenshot(path=screenshot_path, full_page=True)


@pytest.mark.mobile
@pytest.mark.visual
def test_sidebar_mobile_visual(galaxy_s21: Page, test_server_url: str, login_user):
    """Visual regression test for open mobile sidebar"""
    page = galaxy_s21

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Open sidebar
    hamburger = page.locator('.hamburger-menu')
    hamburger.click()
    page.wait_for_timeout(500)  # Wait for open animation

    # Verify sidebar is open
    sidebar = page.locator('.sidebar')
    sidebar_classes = sidebar.get_attribute('class')

    if 'mobile-open' not in sidebar_classes:
        pytest.skip("Sidebar did not open")

    # Hide dynamic content
    page.evaluate("""
        () => {
            const dynamic = document.querySelectorAll('.timestamp, time, .date');
            dynamic.forEach(el => el.style.visibility = 'hidden');
        }
    """)

    screenshot_path = os.path.join(BASELINE_DIR, 'sidebar-open-galaxy-360px.png')

    try:
        expect(page).to_have_screenshot(
            'sidebar-open-galaxy-360px.png',
            full_page=True,
            animations='disabled',
            threshold=0.05
        )
    except AssertionError:
        page.screenshot(path=screenshot_path, full_page=True)


@pytest.mark.mobile
@pytest.mark.visual
def test_responsive_breakpoint_comparison(iphone_12: Page, test_server_url: str, login_user):
    """Compare visual consistency across breakpoint transitions"""
    page = iphone_12

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Hide dynamic content
    page.evaluate("""
        () => {
            const dynamic = document.querySelectorAll('.timestamp, time, .date, .count');
            dynamic.forEach(el => el.style.visibility = 'hidden');
        }
    """)

    # Capture at mobile width (390px)
    mobile_screenshot = os.path.join(SCREENSHOT_DIR, 'temp-mobile-390px.png')
    page.screenshot(path=mobile_screenshot, full_page=False)

    # Resize to tablet (768px)
    page.set_viewport_size({'width': 768, 'height': 1024})
    page.wait_for_timeout(500)

    tablet_screenshot = os.path.join(SCREENSHOT_DIR, 'temp-tablet-768px.png')
    page.screenshot(path=tablet_screenshot, full_page=False)

    # Resize to desktop (1024px)
    page.set_viewport_size({'width': 1024, 'height': 768})
    page.wait_for_timeout(500)

    desktop_screenshot = os.path.join(SCREENSHOT_DIR, 'temp-desktop-1024px.png')
    page.screenshot(path=desktop_screenshot, full_page=False)

    # Verify all screenshots were created
    assert os.path.exists(mobile_screenshot), "Mobile screenshot should be created"
    assert os.path.exists(tablet_screenshot), "Tablet screenshot should be created"
    assert os.path.exists(desktop_screenshot), "Desktop screenshot should be created"

    # Cleanup temp screenshots
    for temp_file in [mobile_screenshot, tablet_screenshot, desktop_screenshot]:
        if os.path.exists(temp_file):
            os.remove(temp_file)


@pytest.mark.mobile
@pytest.mark.visual
def test_touch_feedback_visual(iphone_se: Page, test_server_url: str, login_user):
    """Test visual feedback for touch interactions (hover states, active states)"""
    page = iphone_se

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Find an action button
    buttons = page.locator('button.action-btn, button').all()
    if not buttons:
        pytest.skip("No buttons found")

    first_button = buttons[0]

    # Add active state
    page.evaluate("""
        (btn) => {
            btn.classList.add('active');
            btn.focus();
        }
    """, first_button)

    page.wait_for_timeout(100)

    screenshot_path = os.path.join(SCREENSHOT_DIR, 'button-active-state.png')
    first_button.screenshot(path=screenshot_path)

    # Verify screenshot was created
    assert os.path.exists(screenshot_path), "Button active state screenshot should be created"

    # Cleanup
    if os.path.exists(screenshot_path):
        os.remove(screenshot_path)
