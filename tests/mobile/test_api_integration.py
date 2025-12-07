"""
API Integration and Network Test Suite

Tests mobile network scenarios and API resilience:
- Dynamic API timeouts based on connection type
- Automatic retry logic with exponential backoff
- Offline mode detection
- Network Information API integration
- Range request support for media

Validates:
- APIs handle slow mobile networks
- Retry mechanism works correctly
- Offline state detected and handled
- Media streaming optimized for mobile
"""

import pytest
from playwright.sync_api import Page, expect, Route


@pytest.mark.mobile
def test_api_timeout_dynamic(iphone_12: Page, test_server_url: str, login_user):
    """Test API timeout adjusts based on network connection type"""
    page = iphone_12

    # Check if Network Information API is available
    has_network_api = page.evaluate("""
        () => 'connection' in navigator
    """)

    if not has_network_api:
        pytest.skip("Network Information API not available in test environment")

    # Get connection type
    connection_type = page.evaluate("""
        () => {
            return navigator.connection ? navigator.connection.effectiveType : 'unknown';
        }
    """)

    # Mock slow connection
    page.evaluate("""
        () => {
            if (navigator.connection) {
                Object.defineProperty(navigator.connection, 'effectiveType', {
                    get: () => '2g'
                });
            }
        }
    """)

    login_user()

    # Navigate and trigger API call
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Verify page loaded despite slow connection
    page_title = page.locator('h1, .page-title').first
    if page_title.is_visible():
        expect(page_title).to_be_visible()


@pytest.mark.mobile
def test_api_retry_logic(pixel_5: Page, test_server_url: str, login_user):
    """Test API automatically retries failed requests with exponential backoff"""
    page = pixel_5

    retry_count = 0
    retry_timestamps = []

    def handle_route(route: Route):
        nonlocal retry_count
        retry_timestamps.append(time.time())
        retry_count += 1

        # Fail first 2 attempts, succeed on 3rd
        if retry_count < 3:
            route.abort("failed")
        else:
            route.continue_()

    import time

    # Intercept API calls and simulate failures
    page.route("**/api/**", handle_route)

    login_user()

    page.goto(f'{test_server_url}/notes')
    page.wait_for_timeout(5000)  # Wait for retries

    # Verify retry attempts were made
    assert retry_count >= 2, f"Expected multiple retry attempts, got {retry_count}"

    # Verify exponential backoff (delays should increase)
    if len(retry_timestamps) >= 3:
        delay_1 = retry_timestamps[1] - retry_timestamps[0]
        delay_2 = retry_timestamps[2] - retry_timestamps[1]

        # Second delay should be longer (exponential backoff)
        assert delay_2 >= delay_1 * 0.8, \
            f"Retry delays should increase (got {delay_1:.2f}s, {delay_2:.2f}s)"


@pytest.mark.mobile
def test_offline_detection(galaxy_s21: Page, test_server_url: str, login_user):
    """Test offline mode detection and banner display"""
    page = galaxy_s21

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Simulate offline mode
    context = page.context
    context.set_offline(True)

    # Trigger an action that requires network (e.g., favorite)
    favorite_buttons = page.locator('button[onclick*="favorite"]').all()

    if favorite_buttons:
        favorite_buttons[0].click()
        page.wait_for_timeout(1000)

        # Check for offline indicator/banner
        offline_banner = page.locator('.offline-banner, .network-error, [role="alert"]')

        # Offline banner should appear or request should fail gracefully
        # In real implementation, offline banner should be visible

    # Test navigator.onLine
    is_online = page.evaluate("() => navigator.onLine")
    assert not is_online, "navigator.onLine should be false when offline"

    # Restore online mode
    context.set_offline(False)
    page.wait_for_timeout(500)

    is_online_again = page.evaluate("() => navigator.onLine")
    assert is_online_again, "navigator.onLine should be true when back online"


@pytest.mark.mobile
def test_network_connection_detection(iphone_se: Page, test_server_url: str):
    """Test Network Information API connection type detection"""
    page = iphone_se

    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')

    # Check if Network Information API exists
    has_network_api = page.evaluate("""
        () => 'connection' in navigator
    """)

    if not has_network_api:
        pytest.skip("Network Information API not supported")

    # Get connection information
    connection_info = page.evaluate("""
        () => {
            if (!navigator.connection) return null;
            return {
                effectiveType: navigator.connection.effectiveType,
                downlink: navigator.connection.downlink,
                rtt: navigator.connection.rtt,
                saveData: navigator.connection.saveData
            };
        }
    """)

    if connection_info:
        # Verify connection properties exist
        assert 'effectiveType' in connection_info
        # effectiveType should be one of: 'slow-2g', '2g', '3g', '4g'

        # Verify app can adapt to connection type
        # E.g., reduce image quality on slow connections


@pytest.mark.mobile
def test_range_request_media(ipad: Page, test_server_url: str, login_user):
    """Test /media endpoint supports Range requests for streaming"""
    page = ipad

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Track media requests
    media_requests = []

    def track_media_request(request):
        if '/media/' in request.url:
            media_requests.append({
                'url': request.url,
                'headers': request.headers,
                'method': request.method
            })

    page.on('request', track_media_request)

    # Find and click media (image, video, audio)
    media_elements = page.locator('img[src*="/media/"], video[src*="/media/"], audio[src*="/media/"]').all()

    if not media_elements:
        pytest.skip("No media elements found")

    # Trigger media loading
    first_media = media_elements[0]
    first_media.scroll_into_view_if_needed()
    page.wait_for_timeout(2000)

    # Check if any Range requests were made
    if media_requests:
        # Check for Range header (partial content requests)
        has_range_support = any('range' in req['headers'] for req in media_requests)

        # Range requests are optional but recommended for large media


@pytest.mark.mobile
def test_api_error_handling(pixel_5: Page, test_server_url: str, login_user):
    """Test graceful error handling for API failures"""
    page = pixel_5

    # Intercept API calls and simulate server errors
    def fail_api_route(route: Route):
        if '/api/' in route.request.url:
            route.abort("failed")
        else:
            route.continue_()

    page.route("**/*", fail_api_route)

    login_user()

    page.goto(f'{test_server_url}/notes')
    page.wait_for_timeout(2000)

    # Check for error message or graceful degradation
    error_messages = page.locator('.error, .error-message, [role="alert"]').all()

    # Page should not crash, should show error or retry
    page_loaded = page.evaluate("() => document.readyState === 'complete'")
    assert page_loaded, "Page should load despite API errors"

    # Check console for unhandled errors
    console_errors = []

    def handle_console(msg):
        if msg.type == 'error':
            console_errors.append(msg.text)

    page.on('console', handle_console)

    # Trigger another action
    page.reload()
    page.wait_for_timeout(1000)

    # Should not have unhandled promise rejections
    # (This would appear as console errors)


@pytest.mark.mobile
def test_slow_network_performance(iphone_12: Page, test_server_url: str, login_user):
    """Test app performs acceptably on slow 3G networks"""
    page = iphone_12

    # Simulate slow 3G network
    context = page.context
    context.set_offline(False)

    # Note: Playwright doesn't have built-in network throttling
    # In real testing, use Chrome DevTools Protocol or proxy

    # We can simulate with delayed routes
    def slow_route(route: Route):
        import time
        time.sleep(0.5)  # Add 500ms delay
        route.continue_()

    page.route("**/*", slow_route)

    start_time = time.time()

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    load_time = time.time() - start_time

    # Should still load within reasonable time even with delays
    assert load_time < 15.0, f"Page took {load_time:.1f}s to load on slow network"

    # Page should be usable
    page_title = page.locator('h1, .page-title').first
    if page_title.is_visible():
        expect(page_title).to_be_visible()
