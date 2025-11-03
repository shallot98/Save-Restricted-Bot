"""
Unit tests for callback router

Run with: python3 test_callback_router.py
"""

import unittest
from callback_router import CallbackRouter, build_callback_data, validate_callback_length


class TestCallbackRouter(unittest.TestCase):
    """Test callback router parsing and routing"""
    
    def setUp(self):
        self.router = CallbackRouter()
    
    def test_parse_simple_callback(self):
        """Test parsing simple callback data"""
        data = "w:abc123|sec:m|act:menu"
        parsed = self.router.parse_callback_data(data)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["watch_id"], "abc123")
        self.assertEqual(parsed["sec"], "m")
        self.assertEqual(parsed["act"], "menu")
    
    def test_parse_with_parameters(self):
        """Test parsing callback with additional parameters"""
        data = "w:abc123|sec:m|act:del_kw|i:3"
        parsed = self.router.parse_callback_data(data)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["watch_id"], "abc123")
        self.assertEqual(parsed["sec"], "m")
        self.assertEqual(parsed["act"], "del_kw")
        self.assertEqual(parsed["i"], "3")
    
    def test_parse_pagination(self):
        """Test parsing callback with pagination"""
        data = "w:abc123|sec:e|act:list_kw|p:2"
        parsed = self.router.parse_callback_data(data)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["watch_id"], "abc123")
        self.assertEqual(parsed["p"], "2")
    
    def test_parse_list_page(self):
        """Test parsing list page callback"""
        data = "w:list|act:page|p:1"
        parsed = self.router.parse_callback_data(data)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["watch_id"], "list")
        self.assertEqual(parsed["act"], "page")
        self.assertEqual(parsed["p"], "1")
    
    def test_parse_noop(self):
        """Test parsing noop callback"""
        data = "w:noop"
        parsed = self.router.parse_callback_data(data)
        
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["watch_id"], "noop")
    
    def test_parse_invalid_format(self):
        """Test parsing invalid callback data"""
        # Not starting with w:
        data = "invalid:data"
        parsed = self.router.parse_callback_data(data)
        self.assertIsNone(parsed)
        
        # Legacy format (should not parse in new router)
        data = "w:abc:detail"
        parsed = self.router.parse_callback_data(data)
        self.assertIsNotNone(parsed)  # Parses but won't have sec/act
        self.assertEqual(parsed.get("sec"), None)
        self.assertEqual(parsed.get("act"), None)
    
    def test_register_and_route(self):
        """Test handler registration and routing"""
        handler_called = []
        
        def test_handler(bot, cq, parsed, config):
            handler_called.append(True)
        
        self.router.register("m", "menu", test_handler)
        
        parsed = {"watch_id": "abc123", "sec": "m", "act": "menu"}
        handler = self.router.route(parsed)
        
        self.assertIsNotNone(handler)
        self.assertEqual(handler, test_handler)
    
    def test_route_not_found(self):
        """Test routing with no matching handler"""
        parsed = {"watch_id": "abc123", "sec": "x", "act": "unknown"}
        handler = self.router.route(parsed)
        
        self.assertIsNone(handler)


class TestCallbackDataBuilder(unittest.TestCase):
    """Test callback data builder function"""
    
    def test_build_simple(self):
        """Test building simple callback data"""
        data = build_callback_data("abc123", sec="m", act="menu")
        self.assertEqual(data, "w:abc123|sec:m|act:menu")
    
    def test_build_with_params(self):
        """Test building callback with parameters"""
        data = build_callback_data("abc123", sec="m", act="del_kw", i=3)
        self.assertEqual(data, "w:abc123|sec:m|act:del_kw|i:3")
    
    def test_build_pagination(self):
        """Test building callback with pagination"""
        data = build_callback_data("abc123", sec="e", act="list_re", p=2)
        self.assertEqual(data, "w:abc123|sec:e|act:list_re|p:2")
    
    def test_build_no_section(self):
        """Test building callback without section"""
        data = build_callback_data("list", act="page", p=1)
        self.assertEqual(data, "w:list|act:page|p:1")
    
    def test_build_minimal(self):
        """Test building minimal callback"""
        data = build_callback_data("noop")
        self.assertEqual(data, "w:noop")
    
    def test_build_watch_detail(self):
        """Test building watch detail callback"""
        data = build_callback_data("abc123", sec="d", act="show")
        self.assertEqual(data, "w:abc123|sec:d|act:show")
    
    def test_validate_length(self):
        """Test callback data length validation"""
        # Valid length
        data = build_callback_data("abc123", sec="m", act="menu")
        self.assertTrue(validate_callback_length(data))
        
        # Should be under 64 bytes
        self.assertLess(len(data.encode('utf-8')), 64)
    
    def test_long_watch_id_truncation(self):
        """Test that long watch IDs get truncated"""
        long_id = "a" * 50
        data = build_callback_data(long_id, sec="m", act="menu")
        
        # Should be truncated
        self.assertIn("w:aaaaaaaa", data)
        
        # Should still be valid format
        router = CallbackRouter()
        parsed = router.parse_callback_data(data)
        self.assertIsNotNone(parsed)
    
    def test_special_watch_ids(self):
        """Test special watch ID values"""
        # List
        data = build_callback_data("list", act="page", p=1)
        self.assertEqual(data, "w:list|act:page|p:1")
        
        # Noop
        data = build_callback_data("noop")
        self.assertEqual(data, "w:noop")


class TestCallbackScenarios(unittest.TestCase):
    """Test realistic callback scenarios"""
    
    def test_monitor_filter_flow(self):
        """Test monitor filter management flow"""
        # Open monitor filter menu
        data1 = build_callback_data("abc123", sec="m", act="menu")
        self.assertEqual(data1, "w:abc123|sec:m|act:menu")
        
        # Add keyword
        data2 = build_callback_data("abc123", sec="m", act="add_kw")
        self.assertEqual(data2, "w:abc123|sec:m|act:add_kw")
        
        # List keywords
        data3 = build_callback_data("abc123", sec="m", act="list_kw", p=1)
        self.assertEqual(data3, "w:abc123|sec:m|act:list_kw|p:1")
        
        # Delete keyword
        data4 = build_callback_data("abc123", sec="m", act="del_kw", i=2)
        self.assertEqual(data4, "w:abc123|sec:m|act:del_kw|i:2")
    
    def test_extract_filter_flow(self):
        """Test extract filter management flow"""
        # Open extract filter menu
        data1 = build_callback_data("abc123", sec="e", act="menu")
        self.assertEqual(data1, "w:abc123|sec:e|act:menu")
        
        # Add regex
        data2 = build_callback_data("abc123", sec="e", act="add_re")
        self.assertEqual(data2, "w:abc123|sec:e|act:add_re")
        
        # List regex
        data3 = build_callback_data("abc123", sec="e", act="list_re", p=1)
        self.assertEqual(data3, "w:abc123|sec:e|act:list_re|p:1")
        
        # Delete regex
        data4 = build_callback_data("abc123", sec="e", act="del_re", i=0)
        self.assertEqual(data4, "w:abc123|sec:e|act:del_re|i:0")
    
    def test_watch_detail_flow(self):
        """Test watch detail management flow"""
        # Show detail
        data1 = build_callback_data("abc123", sec="d", act="show")
        self.assertEqual(data1, "w:abc123|sec:d|act:show")
        
        # Change mode
        data2 = build_callback_data("abc123", sec="d", act="mode", m="extract")
        self.assertEqual(data2, "w:abc123|sec:d|act:mode|m:extract")
        
        # Toggle preserve
        data3 = build_callback_data("abc123", sec="d", act="preserve")
        self.assertEqual(data3, "w:abc123|sec:d|act:preserve")
        
        # Preview
        data4 = build_callback_data("abc123", sec="d", act="preview")
        self.assertEqual(data4, "w:abc123|sec:d|act:preview")
        
        # Delete confirmation
        data5 = build_callback_data("abc123", sec="d", act="del_conf")
        self.assertEqual(data5, "w:abc123|sec:d|act:del_conf")
        
        # Confirm delete
        data6 = build_callback_data("abc123", sec="d", act="del_yes")
        self.assertEqual(data6, "w:abc123|sec:d|act:del_yes")
    
    def test_pagination_flow(self):
        """Test pagination in lists"""
        # List page 1
        data1 = build_callback_data("list", act="page", p=1)
        router = CallbackRouter()
        parsed1 = router.parse_callback_data(data1)
        self.assertEqual(parsed1["watch_id"], "list")
        self.assertEqual(parsed1["p"], "1")
        
        # Filter list page 2
        data2 = build_callback_data("abc123", sec="m", act="list_kw", p=2)
        parsed2 = router.parse_callback_data(data2)
        self.assertEqual(parsed2["p"], "2")
        
        # Next page
        data3 = build_callback_data("abc123", sec="e", act="list_re", p=3)
        parsed3 = router.parse_callback_data(data3)
        self.assertEqual(parsed3["p"], "3")


class TestCallbackDataLimits(unittest.TestCase):
    """Test callback data size limits"""
    
    def test_max_length(self):
        """Test that callback data respects 64 byte limit"""
        # Generate various callbacks and check length
        test_cases = [
            ("abc12345", "m", "menu", {}),
            ("abc12345", "m", "add_kw", {}),
            ("abc12345", "m", "list_kw", {"p": 99}),
            ("abc12345", "m", "del_kw", {"i": 99}),
            ("abc12345", "e", "clear_conf", {}),
            ("list", "", "page", {"p": 99}),
        ]
        
        for watch_id, sec, act, params in test_cases:
            data = build_callback_data(watch_id, sec=sec if sec else None, act=act, **params)
            byte_len = len(data.encode('utf-8'))
            self.assertLessEqual(
                byte_len, 64,
                f"Callback data too long ({byte_len} bytes): {data}"
            )
    
    def test_section_codes_are_short(self):
        """Test that section codes are kept short"""
        # All section codes should be 1 character
        sections = ["m", "e", "d", ""]
        for sec in sections:
            if sec:
                self.assertEqual(len(sec), 1, f"Section code too long: {sec}")
    
    def test_action_codes_are_short(self):
        """Test that action codes are reasonably short"""
        # Action codes should be under 10 characters
        actions = [
            "menu", "add_kw", "add_re", "list_kw", "list_re",
            "del_kw", "del_re", "clear_conf", "clear_yes",
            "show", "mode", "preserve", "enabled", "preview",
            "del_conf", "del_yes", "noop", "page"
        ]
        
        for act in actions:
            self.assertLessEqual(
                len(act), 10,
                f"Action code too long: {act}"
            )


if __name__ == "__main__":
    unittest.main()
