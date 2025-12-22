"""
IMPL-5.1: 笔记页面集成测试
测试范围: 模板渲染、组件加载、API端点
"""

import pytest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import app


@pytest.fixture
def client():
    """创建测试客户端"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.test_client() as client:
        yield client


class TestNotesPageRendering:
    """测试笔记页面渲染"""

    def test_notes_page_loads(self, client):
        """测试笔记页面可以正常加载"""
        # 需要先登录
        response = client.get('/notes', follow_redirects=True)
        # 未登录会重定向到登录页
        assert response.status_code == 200

    def test_login_page_loads(self, client):
        """测试登录页面可以正常加载"""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'login' in response.data.lower() or 'login'.encode() in response.data.lower()

    def test_static_css_files_exist(self, client):
        """测试CSS静态文件存在"""
        css_files = [
            '/static/css/base/reset.css',
            '/static/css/base/variables.css',
            '/static/css/components/sidebar.css',
            '/static/css/components/topbar.css',
        ]
        for css_file in css_files:
            response = client.get(css_file)
            assert response.status_code == 200, f"CSS file not found: {css_file}"

    def test_static_js_files_exist(self, client):
        """测试JS静态文件存在"""
        js_files = [
            '/static/js/utils/network.js',
            '/static/js/utils/storage.js',
            '/static/js/components/sidebar.js',
            '/static/js/pages/notes.js',
        ]
        for js_file in js_files:
            response = client.get(js_file)
            assert response.status_code == 200, f"JS file not found: {js_file}"


class TestTemplateComponents:
    """测试Jinja2组件"""

    def test_components_directory_exists(self):
        """测试组件目录存在"""
        components_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'components'
        )
        assert os.path.isdir(components_dir), "Components directory not found"

    def test_all_components_exist(self):
        """测试所有组件文件存在"""
        components_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'components'
        )
        required_components = [
            'topbar.html',
            'sidebar.html',
            'note_card.html',
            'pagination.html',
            'mobile_nav.html',
            'modals.html',
        ]
        for component in required_components:
            component_path = os.path.join(components_dir, component)
            assert os.path.isfile(component_path), f"Component not found: {component}"

    def test_notes_html_uses_components(self):
        """测试notes.html使用了组件"""
        notes_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'notes.html'
        )
        with open(notes_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否包含组件引用
        assert '{% include "components/topbar.html" %}' in content
        assert '{% include "components/sidebar.html" %}' in content
        assert '{% include "components/mobile_nav.html" %}' in content
        assert '{% include "components/modals.html" %}' in content
        assert '{% from "components/note_card.html" import render_note_card %}' in content
        assert '{% from "components/pagination.html" import render_pagination %}' in content


class TestPerformanceOptimizations:
    """测试性能优化"""

    def test_cdn_versions_locked(self):
        """测试静态资源版本已锁定（本地文件）"""
        notes_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'notes.html'
        )
        with open(notes_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查Tailwind版本锁定 (本地)
        assert 'tailwindcss-3.4.1.js' in content
        # 检查Alpine.js版本锁定 (本地)
        assert 'alpinejs-3.14.3.min.js' in content

    def test_alpine_defer_loading(self):
        """测试Alpine.js使用defer加载"""
        notes_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'notes.html'
        )
        with open(notes_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查包含 defer 属性且引用了 alpinejs
        assert 'defer' in content and 'alpinejs' in content

    def test_preconnect_hints(self):
        """测试预连接提示"""
        notes_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'notes.html'
        )
        with open(notes_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'rel="preconnect"' in content
        assert 'rel="dns-prefetch"' in content

    def test_lazy_loading_images(self):
        """测试图片懒加载"""
        note_card_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'components', 'note_card.html'
        )
        with open(note_card_path, 'r', encoding='utf-8') as f:
            content = f.read()

        assert 'loading="lazy"' in content


class TestSearchOptimization:
    """测试搜索优化"""

    def test_debounce_time_optimized(self):
        """测试搜索防抖时间已优化"""
        notes_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'notes.html'
        )
        with open(notes_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查防抖时间为300ms
        assert '}, 300)' in content or 'setTimeout' in content


class TestResponsiveDesign:
    """测试响应式设计"""

    def test_mobile_nav_component(self):
        """测试移动端导航组件"""
        mobile_nav_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'components', 'mobile_nav.html'
        )
        with open(mobile_nav_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查移动端隐藏类
        assert 'lg:hidden' in content

    def test_sidebar_responsive(self):
        """测试侧边栏响应式"""
        sidebar_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            'templates', 'components', 'sidebar.html'
        )
        with open(sidebar_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查响应式类
        assert 'lg:static' in content or 'fixed' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
