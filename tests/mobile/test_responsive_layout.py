"""
Responsive Layout Test Suite

Tests responsive design across 4 breakpoints:
- 320px: Minimum mobile width
- 375px: Standard mobile (iPhone)
- 768px: Tablet portrait
- 1024px: Desktop/tablet landscape

Validates:
- Single-column layout on mobile
- Sidebar visibility at breakpoints
- Grid system responsiveness
- Touch target sizes (44x44px minimum)
- Breakpoint transitions
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.mobile
@pytest.mark.responsive
def test_mobile_320px_layout(mobile_320px: Page, test_server_url: str):
    """Test layout at 320px breakpoint (minimum mobile width)"""
    page = mobile_320px
    page.goto(f'{test_server_url}/notes')

    # Wait for page load
    page.wait_for_load_state('networkidle')

    # Verify viewport dimensions
    viewport = page.viewport_size
    assert viewport['width'] == 320

    # Verify sidebar is off-canvas (not visible)
    sidebar = page.locator('.sidebar')
    if sidebar.is_visible():
        # Sidebar should have mobile-open class removed by default
        sidebar_classes = sidebar.get_attribute('class')
        assert 'mobile-open' not in sidebar_classes, "Sidebar should be hidden at 320px"

    # Verify hamburger menu visible
    hamburger = page.locator('.hamburger-menu')
    expect(hamburger).to_be_visible()

    # Verify notes grid uses single column
    notes_grid = page.locator('.notes-grid')
    grid_columns = page.evaluate("""
        () => {
            const grid = document.querySelector('.notes-grid');
            return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        }
    """)
    assert grid_columns == 1, f"Expected 1 column at 320px, got {grid_columns}"

    # Verify touch target sizes (buttons should be >= 44px)
    buttons = page.locator('button').all()
    for button in buttons[:5]:  # Check first 5 buttons
        box = button.bounding_box()
        if box:
            assert box['height'] >= 44, f"Button height {box['height']}px < 44px"


@pytest.mark.mobile
@pytest.mark.responsive
def test_mobile_375px_layout(mobile_375px: Page, test_server_url: str):
    """Test layout at 375px breakpoint (standard iPhone)"""
    page = mobile_375px
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Verify viewport
    viewport = page.viewport_size
    assert viewport['width'] == 375

    # Verify mobile optimizations
    sidebar = page.locator('.sidebar')
    hamburger = page.locator('.hamburger-menu')

    expect(hamburger).to_be_visible()

    # Verify search bar responsive
    search_container = page.locator('.search-container')
    if search_container.is_visible():
        search_width = page.evaluate("""
            () => {
                const search = document.querySelector('.search-container');
                return search.offsetWidth;
            }
        """)
        # Search should use most of available width on mobile
        assert search_width > 300, "Search bar should expand on mobile"

    # Verify note cards adapt to mobile width
    note_cards = page.locator('.note-card').all()
    if note_cards:
        first_card_width = page.evaluate("""
            () => {
                const card = document.querySelector('.note-card');
                return card.offsetWidth;
            }
        """)
        # Cards should span full grid column
        assert first_card_width > 340, "Note cards should use full width at 375px"


@pytest.mark.mobile
@pytest.mark.responsive
def test_tablet_768px_layout(tablet_768px: Page, test_server_url: str):
    """Test layout at 768px breakpoint (tablet portrait)"""
    page = tablet_768px
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Verify viewport
    viewport = page.viewport_size
    assert viewport['width'] == 768

    # Verify sidebar visibility transitions
    # At 768px, sidebar should be visible or toggleable
    sidebar = page.locator('.sidebar')

    # Check grid columns (should be 2-3 at tablet width)
    grid_columns = page.evaluate("""
        () => {
            const grid = document.querySelector('.notes-grid');
            if (!grid) return 1;
            return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        }
    """)
    assert grid_columns >= 2, f"Expected >= 2 columns at 768px, got {grid_columns}"

    # Verify topbar layout adapts
    topbar = page.locator('.topbar')
    if topbar.is_visible():
        topbar_height = page.evaluate("""
            () => {
                const topbar = document.querySelector('.topbar');
                return topbar ? topbar.offsetHeight : 0;
            }
        """)
        assert topbar_height > 0, "Topbar should be visible at 768px"


@pytest.mark.mobile
@pytest.mark.responsive
def test_desktop_1024px_layout(desktop_1024px: Page, test_server_url: str):
    """Test layout at 1024px breakpoint (desktop)"""
    page = desktop_1024px
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Verify viewport
    viewport = page.viewport_size
    assert viewport['width'] == 1024

    # Verify sidebar should be visible at desktop width
    sidebar = page.locator('.sidebar')
    expect(sidebar).to_be_visible()

    # Hamburger menu should be hidden on desktop
    hamburger = page.locator('.hamburger-menu')
    hamburger_display = page.evaluate("""
        () => {
            const hamburger = document.querySelector('.hamburger-menu');
            return hamburger ? window.getComputedStyle(hamburger).display : 'none';
        }
    """)
    assert hamburger_display == 'none', "Hamburger should be hidden at desktop width"

    # Verify multi-column grid
    grid_columns = page.evaluate("""
        () => {
            const grid = document.querySelector('.notes-grid');
            if (!grid) return 1;
            return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        }
    """)
    assert grid_columns >= 3, f"Expected >= 3 columns at 1024px, got {grid_columns}"


@pytest.mark.mobile
@pytest.mark.responsive
def test_breakpoint_transitions(iphone_12: Page, test_server_url: str):
    """Test smooth layout transitions when resizing viewport"""
    page = iphone_12
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Start at mobile width (390px)
    initial_viewport = page.viewport_size
    assert initial_viewport['width'] == 390

    # Verify mobile layout
    hamburger = page.locator('.hamburger-menu')
    expect(hamburger).to_be_visible()

    mobile_grid_columns = page.evaluate("""
        () => {
            const grid = document.querySelector('.notes-grid');
            if (!grid) return 1;
            return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        }
    """)

    # Resize to tablet (768px)
    page.set_viewport_size({'width': 768, 'height': 1024})
    page.wait_for_timeout(500)  # Allow transition

    tablet_grid_columns = page.evaluate("""
        () => {
            const grid = document.querySelector('.notes-grid');
            if (!grid) return 1;
            return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        }
    """)

    # Verify columns increased
    assert tablet_grid_columns > mobile_grid_columns, "Grid should adapt to larger viewport"

    # Resize to desktop (1024px)
    page.set_viewport_size({'width': 1024, 'height': 768})
    page.wait_for_timeout(500)

    desktop_grid_columns = page.evaluate("""
        () => {
            const grid = document.querySelector('.notes-grid');
            if (!grid) return 1;
            return window.getComputedStyle(grid).gridTemplateColumns.split(' ').length;
        }
    """)

    # Verify further column increase
    assert desktop_grid_columns >= tablet_grid_columns, "Desktop should have more or equal columns"

    # Verify sidebar becomes visible at desktop
    sidebar = page.locator('.sidebar')
    expect(sidebar).to_be_visible()
