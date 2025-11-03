"""
Integration tests for inline UI v2 with callback router

Run with: python3 test_inline_ui_v2.py
"""

import unittest
from unittest.mock import MagicMock, patch
from callback_router import router, build_callback_data
from inline_ui_v2 import (
    get_watch_list_keyboard,
    get_watch_detail_keyboard,
    get_filter_menu_keyboard,
    get_filter_list_keyboard,
    user_input_states,
    handle_user_input
)


class TestKeyboardBuilders(unittest.TestCase):
    """Test keyboard builder functions"""
    
    def test_watch_list_keyboard(self):
        """Test watch list keyboard generation"""
        user_watches = {
            "abc123": {
                "source": {"title": "Test Channel"},
                "enabled": True
            },
            "def456": {
                "source": {"title": "Another Channel"},
                "enabled": False
            }
        }
        
        keyboard = get_watch_list_keyboard(user_watches, page=1)
        
        # Should have 2 watch buttons
        self.assertEqual(len(keyboard.inline_keyboard), 2)
        
        # Check first button
        first_button = keyboard.inline_keyboard[0][0]
        self.assertIn("Test Channel", first_button.text)
        self.assertIn("✅", first_button.text)
        
        # Check callback data format
        self.assertTrue(first_button.callback_data.startswith("w:"))
        self.assertIn("sec:d", first_button.callback_data)
    
    def test_watch_detail_keyboard(self):
        """Test watch detail keyboard generation"""
        watch_data = {
            "forward_mode": "full",
            "preserve_source": True,
            "enabled": True,
            "monitor_filters": {
                "keywords": ["test"],
                "patterns": ["/test/i"]
            },
            "extract_filters": {
                "keywords": [],
                "patterns": []
            }
        }
        
        keyboard = get_watch_detail_keyboard("abc12345", watch_data)
        
        # Should have multiple rows
        self.assertGreater(len(keyboard.inline_keyboard), 5)
        
        # Check mode buttons
        mode_row = keyboard.inline_keyboard[0]
        self.assertEqual(len(mode_row), 2)
        self.assertIn("Full", mode_row[0].text)
        self.assertIn("Extract", mode_row[1].text)
        
        # Check filter buttons
        found_monitor = False
        found_extract = False
        for row in keyboard.inline_keyboard:
            if row[0].text and "监控过滤器" in row[0].text:
                found_monitor = True
                # Should show counts
                self.assertIn("1+1", row[0].text)
            if row[0].text and "提取过滤器" in row[0].text:
                found_extract = True
                self.assertIn("0+0", row[0].text)
        
        self.assertTrue(found_monitor, "Monitor filter button not found")
        self.assertTrue(found_extract, "Extract filter button not found")
    
    def test_filter_menu_keyboard(self):
        """Test filter menu keyboard generation"""
        keyboard = get_filter_menu_keyboard("abc12345", "m")
        
        # Should have multiple actions
        self.assertGreater(len(keyboard.inline_keyboard), 4)
        
        # Check button texts
        button_texts = [row[0].text for row in keyboard.inline_keyboard]
        self.assertIn("➕ 添加关键词", button_texts)
        self.assertIn("➕ 添加正则", button_texts)
        
        # Check callback data format
        for row in keyboard.inline_keyboard:
            callback_data = row[0].callback_data
            self.assertTrue(callback_data.startswith("w:"))
            if "添加" in row[0].text:
                self.assertIn("sec:m", callback_data)
    
    def test_filter_list_keyboard(self):
        """Test filter list keyboard with pagination"""
        items = ["keyword1", "keyword2", "keyword3"]
        
        keyboard = get_filter_list_keyboard("abc12345", "e", "kw", items, page=1)
        
        # Should have item rows + back button
        self.assertGreater(len(keyboard.inline_keyboard), 3)
        
        # Check delete buttons
        for i in range(3):
            row = keyboard.inline_keyboard[i]
            self.assertEqual(len(row), 2)  # Display + delete
            self.assertIn("🗑️", row[1].text)
            self.assertIn(f"del_kw", row[1].callback_data)
    
    def test_filter_list_pagination(self):
        """Test filter list pagination"""
        items = [f"item{i}" for i in range(12)]
        
        # Page 1
        kb1 = get_filter_list_keyboard("abc12345", "m", "re", items, page=1, items_per_page=5)
        # Should have 5 items + pagination + back = 7 rows
        self.assertEqual(len(kb1.inline_keyboard), 7)
        
        # Check pagination row exists
        found_pagination = False
        for row in kb1.inline_keyboard:
            if len(row) > 1 and any("➡️" in btn.text for btn in row):
                found_pagination = True
                # Should show page info
                self.assertTrue(any("1/3" in btn.text for btn in row))
        
        self.assertTrue(found_pagination)
    
    def test_callback_data_length(self):
        """Test that all generated callback data is within limits"""
        user_watches = {
            f"watch{i:03d}{'x'*60}": {
                "source": {"title": f"Channel {i}"},
                "enabled": True,
                "monitor_filters": {"keywords": [], "patterns": []},
                "extract_filters": {"keywords": [], "patterns": []}
            }
            for i in range(3)
        }
        
        # Test watch list
        keyboard = get_watch_list_keyboard(user_watches, page=1)
        for row in keyboard.inline_keyboard:
            for button in row:
                byte_len = len(button.callback_data.encode('utf-8'))
                self.assertLessEqual(byte_len, 64, f"Callback data too long: {button.callback_data}")
        
        # Test watch detail
        watch_id = list(user_watches.keys())[0]
        watch_data = user_watches[watch_id]
        keyboard = get_watch_detail_keyboard(watch_id, watch_data)
        for row in keyboard.inline_keyboard:
            for button in row:
                byte_len = len(button.callback_data.encode('utf-8'))
                self.assertLessEqual(byte_len, 64, f"Callback data too long: {button.callback_data}")


class TestCallbackHandlers(unittest.TestCase):
    """Test callback handler functions"""
    
    def setUp(self):
        """Set up test mocks"""
        self.bot = MagicMock()
        self.callback_query = MagicMock()
        self.callback_query.from_user.id = 12345
        self.callback_query.message.chat.id = 12345
        self.callback_query.message.id = 100
        
        self.watch_config = {
            "watches": {
                "12345": {
                    "abc12345": {
                        "source": {
                            "id": "-100123456789",
                            "title": "Test Channel",
                            "type": "channel"
                        },
                        "target_chat_id": "12345",
                        "forward_mode": "full",
                        "preserve_source": False,
                        "enabled": True,
                        "monitor_filters": {
                            "keywords": ["test"],
                            "patterns": []
                        },
                        "extract_filters": {
                            "keywords": [],
                            "patterns": []
                        }
                    }
                }
            }
        }
    
    def test_router_handles_watch_detail(self):
        """Test that router can handle watch detail callback"""
        self.callback_query.data = "w:abc12345|sec:d|act:show"
        
        parsed = router.parse_callback_data(self.callback_query.data)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["sec"], "d")
        self.assertEqual(parsed["act"], "show")
        
        # Find handler
        handler = router.route(parsed)
        self.assertIsNotNone(handler)
    
    def test_router_handles_monitor_menu(self):
        """Test that router can handle monitor filter menu"""
        self.callback_query.data = "w:abc12345|sec:m|act:menu"
        
        parsed = router.parse_callback_data(self.callback_query.data)
        handler = router.route(parsed)
        
        self.assertIsNotNone(handler)
    
    def test_router_handles_extract_menu(self):
        """Test that router can handle extract filter menu"""
        self.callback_query.data = "w:abc12345|sec:e|act:menu"
        
        parsed = router.parse_callback_data(self.callback_query.data)
        handler = router.route(parsed)
        
        self.assertIsNotNone(handler)
    
    def test_router_handles_delete_keyword(self):
        """Test that router can handle delete keyword"""
        self.callback_query.data = "w:abc12345|sec:m|act:del_kw|i:0"
        
        parsed = router.parse_callback_data(self.callback_query.data)
        handler = router.route(parsed)
        
        self.assertIsNotNone(handler)
        self.assertEqual(parsed["i"], "0")
    
    def test_router_handles_pagination(self):
        """Test that router can handle pagination"""
        self.callback_query.data = "w:abc12345|sec:e|act:list_re|p:2"
        
        parsed = router.parse_callback_data(self.callback_query.data)
        handler = router.route(parsed)
        
        self.assertIsNotNone(handler)
        self.assertEqual(parsed["p"], "2")
    
    def test_router_rejects_invalid_format(self):
        """Test that router rejects invalid callback data"""
        # Legacy format
        self.callback_query.data = "w:abc:detail"
        parsed = router.parse_callback_data(self.callback_query.data)
        
        # Parses but won't find handler
        if parsed:
            handler = router.route(parsed)
            self.assertIsNone(handler)
        
        # Invalid format
        self.callback_query.data = "invalid"
        parsed = router.parse_callback_data(self.callback_query.data)
        self.assertIsNone(parsed)


class TestInputFlows(unittest.TestCase):
    """Test user input flow handling"""
    
    def setUp(self):
        """Set up test mocks"""
        self.bot = MagicMock()
        self.message = MagicMock()
        self.message.from_user.id = 12345
        self.message.chat.id = 12345
        self.message.text = "test keyword"
        
        self.acc = MagicMock()
        
        # Clear input states
        user_input_states.clear()
    
    def tearDown(self):
        """Clean up input states"""
        user_input_states.clear()
    
    @patch('inline_ui_v2.load_watch_config')
    @patch('inline_ui_v2.get_user_watches')
    @patch('inline_ui_v2.get_watch_by_id')
    @patch('inline_ui_v2.add_watch_keyword')
    def test_add_keyword_flow(self, mock_add_kw, mock_get_watch, mock_get_watches, mock_load_config):
        """Test adding keyword through input flow"""
        # Set up mocks
        mock_get_watches.return_value = {"abc12345": {}}
        mock_get_watch.return_value = {
            "monitor_filters": {"keywords": [], "patterns": []},
            "extract_filters": {"keywords": [], "patterns": []}
        }
        mock_add_kw.return_value = (True, "添加成功")
        
        # Set input state
        user_input_states["12345"] = {
            "action": "add_keyword",
            "watch_id": "abc12345",
            "filter_type": "monitor",
            "section": "m",
            "message_id": 100
        }
        
        # Handle input
        result = handle_user_input(self.bot, self.message, self.acc)
        
        self.assertTrue(result)
        mock_add_kw.assert_called_once()
        self.bot.send_message.assert_called()
        
        # State should be cleared
        self.assertNotIn("12345", user_input_states)
    
    @patch('inline_ui_v2.load_watch_config')
    @patch('inline_ui_v2.get_user_watches')
    @patch('inline_ui_v2.get_watch_by_id')
    @patch('inline_ui_v2.add_watch_pattern')
    def test_add_regex_flow(self, mock_add_re, mock_get_watch, mock_get_watches, mock_load_config):
        """Test adding regex through input flow"""
        # Set up mocks
        mock_get_watches.return_value = {"abc12345": {}}
        mock_get_watch.return_value = {
            "monitor_filters": {"keywords": [], "patterns": []},
            "extract_filters": {"keywords": [], "patterns": []}
        }
        mock_add_re.return_value = (True, "添加成功")
        
        # Set input state
        user_input_states["12345"] = {
            "action": "add_pattern",
            "watch_id": "abc12345",
            "filter_type": "extract",
            "section": "e",
            "message_id": 100
        }
        
        # Set message text to regex
        self.message.text = "/test/i"
        
        # Handle input
        result = handle_user_input(self.bot, self.message, self.acc)
        
        self.assertTrue(result)
        mock_add_re.assert_called_once()
        
        # State should be cleared
        self.assertNotIn("12345", user_input_states)
    
    def test_no_input_state(self):
        """Test handling message when no input state exists"""
        result = handle_user_input(self.bot, self.message, self.acc)
        self.assertFalse(result)


class TestCallbackDataConsistency(unittest.TestCase):
    """Test that callback data format is consistent across all keyboards"""
    
    def test_all_callbacks_use_new_format(self):
        """Test that all generated keyboards use the new callback format"""
        watch_data = {
            "forward_mode": "full",
            "preserve_source": False,
            "enabled": True,
            "monitor_filters": {"keywords": ["test"], "patterns": ["/test/i"]},
            "extract_filters": {"keywords": ["extract"], "patterns": []}
        }
        
        keyboards = [
            get_watch_list_keyboard({"abc12345": watch_data}),
            get_watch_detail_keyboard("abc12345", watch_data),
            get_filter_menu_keyboard("abc12345", "m"),
            get_filter_menu_keyboard("abc12345", "e"),
            get_filter_list_keyboard("abc12345", "m", "kw", ["test"]),
            get_filter_list_keyboard("abc12345", "e", "re", ["/test/i"]),
        ]
        
        for keyboard in keyboards:
            for row in keyboard.inline_keyboard:
                for button in row:
                    # All should start with w:
                    self.assertTrue(
                        button.callback_data.startswith("w:"),
                        f"Invalid callback data: {button.callback_data}"
                    )
                    
                    # Should use | as delimiter (new format)
                    if len(button.callback_data) > 10:  # Skip minimal ones like "w:noop"
                        self.assertIn(
                            "|",
                            button.callback_data,
                            f"Should use new format: {button.callback_data}"
                        )
                        
                        # Should NOT use : as delimiter (except w:)
                        parts = button.callback_data.split("|")
                        for part in parts[1:]:  # Skip first part (w:id)
                            self.assertIn(
                                ":",
                                part,
                                f"Part should have key:value format: {part}"
                            )


class TestErrorHandling(unittest.TestCase):
    """Test error handling in callbacks"""
    
    def test_router_handles_unknown_action(self):
        """Test that router handles unknown actions gracefully"""
        callback_query = MagicMock()
        callback_query.data = "w:abc12345|sec:x|act:unknown"
        callback_query.id = "query123"
        callback_query.from_user.id = 12345
        
        bot = MagicMock()
        watch_config = {}
        
        # Should handle without crashing
        result = router.handle_callback(callback_query, bot, watch_config)
        self.assertTrue(result)
        
        # Should answer callback query
        bot.answer_callback_query.assert_called_once()
        
        # Should show error message
        args = bot.answer_callback_query.call_args[0]
        self.assertIn("未知操作", args[1])


if __name__ == "__main__":
    unittest.main()
