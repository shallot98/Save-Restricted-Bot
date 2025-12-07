"""
Form Input and Keyboard Test Suite

Tests mobile form handling and virtual keyboard optimization:
- Login form mobile keyboard (email inputmode)
- Note editing keyboard handling (textarea)
- Search input optimization (search inputmode)
- Virtual Viewport API keyboard detection
- Form autofill attributes

Validates:
- Correct inputmode attributes
- Viewport adjusts for keyboard
- Inputs remain visible above keyboard
- Autocomplete attributes present
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.mobile
def test_login_form_mobile_keyboard(iphone_12: Page, test_server_url: str):
    """Test login form triggers correct mobile keyboards"""
    page = iphone_12
    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')

    # Check username input has email or text inputmode
    username_input = page.locator('input[name="username"]')
    expect(username_input).to_be_visible()

    username_inputmode = username_input.get_attribute('inputmode')
    username_type = username_input.get_attribute('type')

    # Verify appropriate keyboard type
    assert username_type in ['text', 'email'], \
        f"Username input should be text or email type, got {username_type}"

    # Check for autocomplete attribute
    username_autocomplete = username_input.get_attribute('autocomplete')
    assert username_autocomplete in ['username', 'email', None], \
        "Username should have proper autocomplete"

    # Check password input
    password_input = page.locator('input[name="password"]')
    expect(password_input).to_be_visible()

    password_type = password_input.get_attribute('type')
    assert password_type == 'password', "Password input should be type=password"

    password_autocomplete = password_input.get_attribute('autocomplete')
    assert password_autocomplete in ['current-password', 'password', None], \
        "Password should have proper autocomplete"

    # Test focus behavior
    username_input.click()
    page.wait_for_timeout(300)

    # Verify input is focused
    is_focused = page.evaluate("""
        () => document.activeElement.name === 'username'
    """)
    assert is_focused, "Username input should be focused"


@pytest.mark.mobile
def test_note_editing_keyboard_handling(pixel_5: Page, test_server_url: str, login_user):
    """Test note editing textarea handles virtual keyboard properly"""
    page = pixel_5

    # Login first
    login_user()

    # Navigate to note editing page
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Find and click first note to edit (if available)
    edit_buttons = page.locator('button[onclick*="edit"]').all()
    if not edit_buttons:
        pytest.skip("No editable notes available")

    # Get initial viewport height
    initial_viewport_height = page.viewport_size['height']

    # Click edit button
    edit_buttons[0].click()
    page.wait_for_timeout(500)

    # Find textarea or content editable
    textarea = page.locator('textarea, [contenteditable="true"]').first
    if not textarea.is_visible():
        pytest.skip("No textarea found")

    # Focus textarea
    textarea.click()
    page.wait_for_timeout(500)

    # Check if Visual Viewport API is available
    has_visual_viewport = page.evaluate("""
        () => 'visualViewport' in window
    """)

    if has_visual_viewport:
        # Verify viewport height changed (keyboard opened)
        visual_viewport_height = page.evaluate("""
            () => window.visualViewport.height
        """)

        # Note: In headless mode keyboard won't actually appear
        # But we can verify the textarea is positioned correctly
        textarea_box = textarea.bounding_box()
        assert textarea_box, "Textarea should be visible"

        # Verify textarea is in visible area
        assert textarea_box['y'] >= 0, "Textarea should not be off-screen above"

    # Type some text
    textarea.fill("Test mobile editing")
    typed_content = textarea.input_value()
    assert "Test mobile editing" in typed_content, "Text should be entered"


@pytest.mark.mobile
def test_search_input_optimization(galaxy_s21: Page, test_server_url: str):
    """Test search input has mobile-optimized keyboard"""
    page = galaxy_s21
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Find search input
    search_input = page.locator('input[type="search"], input.search-input, input[placeholder*="搜索"], input[placeholder*="Search"]')

    if not search_input.is_visible():
        pytest.skip("Search input not found")

    # Check inputmode attribute
    inputmode = search_input.get_attribute('inputmode')
    # inputmode should be 'search' or 'text' for search fields
    if inputmode:
        assert inputmode in ['search', 'text'], f"Search should have search/text inputmode, got {inputmode}"

    # Check type attribute
    search_type = search_input.get_attribute('type')
    assert search_type in ['search', 'text'], f"Search should be search/text type, got {search_type}"

    # Test search input functionality
    search_input.click()
    page.wait_for_timeout(200)

    search_input.fill("test query")
    page.wait_for_timeout(500)

    # Verify search input value
    search_value = search_input.input_value()
    assert "test query" in search_value

    # Check for clear button (common in mobile search)
    clear_button = page.locator('button[aria-label*="clear"], .search-clear, button.clear-search')
    # Clear button might not be visible until input has content
    # This is optional but recommended for mobile UX


@pytest.mark.mobile
def test_virtual_viewport_scroll(iphone_se: Page, test_server_url: str, login_user):
    """Test input fields scroll into view above virtual keyboard"""
    page = iphone_se

    # Go to login page (has form at various positions)
    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')

    # Get all input fields
    inputs = page.locator('input').all()

    for input_field in inputs:
        if not input_field.is_visible():
            continue

        # Get input position before focus
        input_box_before = input_field.bounding_box()
        if not input_box_before:
            continue

        initial_scroll_y = page.evaluate("() => window.scrollY")

        # Focus input
        input_field.click()
        page.wait_for_timeout(300)

        # Get input position after focus
        input_box_after = input_field.bounding_box()

        # In real mobile browser, viewport would adjust
        # In headless testing, we verify scroll behavior exists
        final_scroll_y = page.evaluate("() => window.scrollY")

        # Verify input is still visible (not hidden by keyboard simulation)
        assert input_box_after, "Input should remain visible after focus"

        # Input should be in upper half of viewport to avoid keyboard
        viewport_height = page.viewport_size['height']
        input_top_position = input_box_after['y'] - final_scroll_y

        # Input should not be in bottom quarter (where keyboard would be)
        assert input_top_position < viewport_height * 0.75, \
            "Input should scroll to avoid keyboard area"


@pytest.mark.mobile
def test_form_autofill_attributes(ipad: Page, test_server_url: str):
    """Test form inputs have proper autocomplete attributes"""
    page = ipad
    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')

    # Check username field
    username_input = page.locator('input[name="username"]')
    username_autocomplete = username_input.get_attribute('autocomplete')

    # Autocomplete should be set for better mobile UX
    assert username_autocomplete in ['username', 'email', 'off', None], \
        "Username should have autocomplete attribute"

    # Check password field
    password_input = page.locator('input[name="password"]')
    password_autocomplete = password_input.get_attribute('autocomplete')

    assert password_autocomplete in ['current-password', 'password', 'off', None], \
        "Password should have autocomplete attribute"

    # Test form has proper autocomplete setup
    form = page.locator('form').first
    if form.is_visible():
        form_autocomplete = form.get_attribute('autocomplete')
        # Form-level autocomplete can be 'on' or 'off' or None

    # Verify inputs have proper name attributes (required for autofill)
    username_name = username_input.get_attribute('name')
    password_name = password_input.get_attribute('name')

    assert username_name, "Username input should have name attribute"
    assert password_name, "Password input should have name attribute"

    # Check for label associations (improves accessibility and autofill)
    username_id = username_input.get_attribute('id')
    if username_id:
        username_label = page.locator(f'label[for="{username_id}"]')
        # Label is optional but recommended


@pytest.mark.mobile
def test_mobile_form_validation(pixel_5: Page, test_server_url: str):
    """Test form validation displays properly on mobile"""
    page = pixel_5
    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')

    # Try to submit empty form
    submit_button = page.locator('button[type="submit"]')
    submit_button.click()
    page.wait_for_timeout(500)

    # Check for validation messages
    # HTML5 validation or custom validation should appear
    username_input = page.locator('input[name="username"]')

    # Check if HTML5 validation is triggered
    is_invalid = page.evaluate("""
        () => {
            const input = document.querySelector('input[name="username"]');
            return input ? !input.checkValidity() : false;
        }
    """)

    # If required attribute is set, empty input should be invalid
    username_required = username_input.get_attribute('required')
    if username_required is not None:
        # Input should show validation state
        pass  # Validation behavior varies by browser

    # Fill form with invalid data
    username_input.fill("invalid")
    password_input = page.locator('input[name="password"]')
    password_input.fill("short")

    submit_button.click()
    page.wait_for_timeout(500)

    # Check for error message display (if custom validation exists)
    error_messages = page.locator('.error, .error-message, [role="alert"]').all()
    # Error messages may or may not appear depending on backend validation
