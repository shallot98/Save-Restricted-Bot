"""
Mobile Testing Configuration with Device Emulation Fixtures

Provides 5 mobile device configurations for comprehensive mobile testing:
- iPhone SE (375x667): Small mobile baseline
- iPhone 12 (390x844): Modern iPhone
- Pixel 5 (393x851): Modern Android
- iPad (768x1024): Tablet portrait
- Galaxy S21 (360x800): Standard Android
"""

import pytest
from playwright.sync_api import Page, Browser


# ======================
# Device Configurations
# ======================

DEVICE_CONFIGS = {
    'iphone_se': {
        'viewport': {'width': 375, 'height': 667},
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'device_scale_factor': 2,
        'is_mobile': True,
        'has_touch': True,
    },
    'iphone_12': {
        'viewport': {'width': 390, 'height': 844},
        'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
        'device_scale_factor': 3,
        'is_mobile': True,
        'has_touch': True,
    },
    'pixel_5': {
        'viewport': {'width': 393, 'height': 851},
        'user_agent': 'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.91 Mobile Safari/537.36',
        'device_scale_factor': 2.75,
        'is_mobile': True,
        'has_touch': True,
    },
    'ipad': {
        'viewport': {'width': 768, 'height': 1024},
        'user_agent': 'Mozilla/5.0 (iPad; CPU OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1',
        'device_scale_factor': 2,
        'is_mobile': True,
        'has_touch': True,
    },
    'galaxy_s21': {
        'viewport': {'width': 360, 'height': 800},
        'user_agent': 'Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36',
        'device_scale_factor': 3,
        'is_mobile': True,
        'has_touch': True,
    }
}


# ======================
# Device Fixtures
# ======================

@pytest.fixture
def iphone_se(browser: Browser) -> Page:
    """iPhone SE device emulation (375x667)"""
    context = browser.new_context(**DEVICE_CONFIGS['iphone_se'])
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def iphone_12(browser: Browser) -> Page:
    """iPhone 12 device emulation (390x844)"""
    context = browser.new_context(**DEVICE_CONFIGS['iphone_12'])
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def pixel_5(browser: Browser) -> Page:
    """Pixel 5 device emulation (393x851)"""
    context = browser.new_context(**DEVICE_CONFIGS['pixel_5'])
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def ipad(browser: Browser) -> Page:
    """iPad device emulation (768x1024)"""
    context = browser.new_context(**DEVICE_CONFIGS['ipad'])
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def galaxy_s21(browser: Browser) -> Page:
    """Galaxy S21 device emulation (360x800)"""
    context = browser.new_context(**DEVICE_CONFIGS['galaxy_s21'])
    page = context.new_page()
    yield page
    context.close()


# ======================
# Custom Viewport Fixtures
# ======================

@pytest.fixture
def mobile_320px(browser: Browser) -> Page:
    """Custom viewport: 320px width (minimum mobile)"""
    context = browser.new_context(
        viewport={'width': 320, 'height': 568},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def mobile_375px(browser: Browser) -> Page:
    """Custom viewport: 375px width (iPhone standard)"""
    context = browser.new_context(
        viewport={'width': 375, 'height': 667},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def tablet_768px(browser: Browser) -> Page:
    """Custom viewport: 768px width (tablet portrait)"""
    context = browser.new_context(
        viewport={'width': 768, 'height': 1024},
        device_scale_factor=2,
        is_mobile=True,
        has_touch=True
    )
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def desktop_1024px(browser: Browser) -> Page:
    """Custom viewport: 1024px width (desktop/tablet landscape)"""
    context = browser.new_context(
        viewport={'width': 1024, 'height': 768},
        device_scale_factor=1,
        is_mobile=False,
        has_touch=False
    )
    page = context.new_page()
    yield page
    context.close()


# ======================
# Test Server Fixtures
# ======================

@pytest.fixture(scope='session')
def test_server_url():
    """Base URL for test Flask server"""
    return 'http://localhost:5000'


@pytest.fixture
def login_user(page: Page, test_server_url: str):
    """Helper fixture to login a test user"""
    def _login(username='admin', password='admin'):
        page.goto(f'{test_server_url}/login')
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', password)
        page.click('button[type="submit"]')
        page.wait_for_load_state('networkidle')
    return _login
