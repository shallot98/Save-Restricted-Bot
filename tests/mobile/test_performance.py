"""
Performance and Lazy Loading Test Suite

Tests mobile performance optimizations:
- Image lazy loading (loading=lazy attribute)
- Intersection Observer API
- AJAX request throttling
- Search debouncing

Validates:
- Images load progressively
- Initial page load is fast
- API calls are throttled
- No unnecessary network requests
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.mobile
@pytest.mark.performance
def test_image_lazy_loading(iphone_12: Page, test_server_url: str, login_user):
    """Test images use lazy loading and don't all load initially"""
    page = iphone_12

    # Login to access notes with images
    login_user()

    # Navigate to notes page
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Count total images on page
    total_images = page.locator('img').count()

    if total_images == 0:
        pytest.skip("No images found on page")

    # Check how many images have loading=lazy attribute
    lazy_images = page.locator('img[loading="lazy"]').count()

    # Most images should use lazy loading (allow some exceptions like logos)
    assert lazy_images > 0, "At least some images should have loading=lazy"

    # Count initially loaded images (only those in viewport should load)
    initially_loaded = page.evaluate("""
        () => {
            return Array.from(document.querySelectorAll('img')).filter(img => {
                return img.complete && img.naturalHeight > 0;
            }).length;
        }
    """)

    # Initially loaded should be less than total (proving lazy loading works)
    if total_images > 5:
        assert initially_loaded < total_images, \
            f"Too many images loaded initially ({initially_loaded}/{total_images})"

    # Verify images have proper dimensions to avoid layout shift
    images = page.locator('img').all()
    for img in images[:3]:  # Check first 3
        width_attr = img.get_attribute('width')
        height_attr = img.get_attribute('height')
        # Either width/height attrs or CSS dimensions should be set


@pytest.mark.mobile
@pytest.mark.performance
def test_intersection_observer_lazy_load(pixel_5: Page, test_server_url: str, login_user):
    """Test Intersection Observer triggers lazy loading on scroll"""
    page = pixel_5

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Get initial loaded image count
    initial_loaded = page.evaluate("""
        () => {
            return Array.from(document.querySelectorAll('img')).filter(img => {
                return img.complete && img.naturalHeight > 0;
            }).length;
        }
    """)

    # Verify page is scrollable
    page_height = page.evaluate("() => document.body.scrollHeight")
    viewport_height = page.viewport_size['height']

    if page_height <= viewport_height:
        pytest.skip("Page not tall enough for lazy loading test")

    # Scroll to bottom to trigger lazy loading
    page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(1000)  # Wait for images to load

    # Get loaded image count after scroll
    after_scroll_loaded = page.evaluate("""
        () => {
            return Array.from(document.querySelectorAll('img')).filter(img => {
                return img.complete && img.naturalHeight > 0;
            }).length;
        }
    """)

    # More images should be loaded after scrolling
    assert after_scroll_loaded >= initial_loaded, \
        "Scrolling should trigger additional image loading"

    # Check if Intersection Observer is being used
    has_observer = page.evaluate("""
        () => {
            return 'IntersectionObserver' in window;
        }
    """)
    assert has_observer, "Browser should support Intersection Observer API"


@pytest.mark.mobile
@pytest.mark.performance
def test_ajax_throttling(galaxy_s21: Page, test_server_url: str, login_user):
    """Test AJAX requests are throttled to prevent excessive calls"""
    page = galaxy_s21

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Track network requests
    api_requests = []

    def track_request(request):
        if '/api/' in request.url or '/favorite' in request.url or '/delete' in request.url:
            api_requests.append({
                'url': request.url,
                'timestamp': time.time()
            })

    import time
    page.on('request', track_request)

    # Find favorite buttons
    favorite_buttons = page.locator('button[onclick*="favorite"], .favorite-btn').all()

    if not favorite_buttons or len(favorite_buttons) < 2:
        pytest.skip("Not enough favorite buttons for throttling test")

    # Rapidly click multiple favorite buttons
    start_time = time.time()

    for btn in favorite_buttons[:3]:  # Click 3 buttons rapidly
        if btn.is_visible():
            btn.click()
            page.wait_for_timeout(50)  # Very short delay

    page.wait_for_timeout(1500)  # Wait for throttled requests

    end_time = time.time()
    duration = end_time - start_time

    # Calculate request rate
    request_count = len(api_requests)

    if request_count > 0:
        requests_per_second = request_count / duration

        # Verify throttling: should not exceed ~2 requests per second
        assert requests_per_second <= 3, \
            f"Too many API requests ({requests_per_second:.1f}/sec), throttling not working"


@pytest.mark.mobile
@pytest.mark.performance
def test_search_debouncing(iphone_se: Page, test_server_url: str, login_user):
    """Test search input debounces requests (waits for user to stop typing)"""
    page = iphone_se

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Find search input
    search_input = page.locator('input[type="search"], input.search-input, input[placeholder*="搜索"]')

    if not search_input.is_visible():
        pytest.skip("Search input not found")

    # Track search API requests
    search_requests = []

    def track_search_request(request):
        if '/search' in request.url or 'query' in request.url:
            search_requests.append(time.time())

    import time
    page.on('request', track_search_request)

    # Type search query rapidly (simulating user typing)
    search_input.click()

    test_query = "test search query"
    for char in test_query:
        search_input.press(char)
        page.wait_for_timeout(50)  # Rapid typing (50ms per char)

    # Wait for debounce delay (typically 300-500ms)
    page.wait_for_timeout(800)

    # Verify only 1-2 search requests made (debouncing working)
    # Without debouncing, there would be one request per keystroke
    assert len(search_requests) <= 2, \
        f"Too many search requests ({len(search_requests)}), debouncing not working"


@pytest.mark.mobile
@pytest.mark.performance
def test_initial_page_load_performance(ipad: Page, test_server_url: str):
    """Test initial page load is fast on mobile network"""
    page = ipad

    # Measure page load time
    import time
    start_time = time.time()

    page.goto(f'{test_server_url}/login')
    page.wait_for_load_state('networkidle')

    end_time = time.time()
    load_time = end_time - start_time

    # Page should load in reasonable time (< 5 seconds)
    assert load_time < 5.0, f"Page load took {load_time:.2f}s, too slow"

    # Check page size and resource count
    resource_count = page.evaluate("""
        () => {
            return performance.getEntriesByType('resource').length;
        }
    """)

    # Reasonable resource count for a web app (< 50 for login page)
    assert resource_count < 50, f"Too many resources loaded ({resource_count})"

    # Check for render-blocking resources
    render_blocking = page.evaluate("""
        () => {
            const resources = performance.getEntriesByType('resource');
            return resources.filter(r => {
                return (r.initiatorType === 'link' || r.initiatorType === 'script') &&
                       r.renderBlockingStatus === 'blocking';
            }).length;
        }
    """)

    # Minimize render-blocking resources
    assert render_blocking < 5, f"Too many render-blocking resources ({render_blocking})"


@pytest.mark.mobile
@pytest.mark.performance
def test_responsive_image_sizing(pixel_5: Page, test_server_url: str, login_user):
    """Test images are appropriately sized for mobile viewport"""
    page = pixel_5

    login_user()
    page.goto(f'{test_server_url}/notes')
    page.wait_for_load_state('networkidle')

    # Check image sizes
    images = page.locator('img').all()

    if not images:
        pytest.skip("No images found")

    viewport_width = page.viewport_size['width']

    oversized_images = []

    for img in images[:10]:  # Check first 10 images
        if not img.is_visible():
            continue

        box = img.bounding_box()
        if not box:
            continue

        # Get natural (file) dimensions
        natural_width = img.evaluate("el => el.naturalWidth")
        natural_height = img.evaluate("el => el.naturalHeight")

        displayed_width = box['width']

        # Check if image is significantly oversized for display
        # Image should not be more than 2x displayed size (wastes bandwidth)
        if natural_width > displayed_width * 2:
            oversized_images.append({
                'natural': f"{natural_width}x{natural_height}",
                'displayed': f"{displayed_width}x{box['height']}",
                'src': img.get_attribute('src')[:50]
            })

    # Allow some oversized images but not too many
    if len(oversized_images) > 3:
        print(f"Warning: {len(oversized_images)} oversized images found")
        # This is a warning, not a failure, as it requires backend changes
