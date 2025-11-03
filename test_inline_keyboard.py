"""
Tests for inline keyboard functionality and peer resolution
"""

import unittest
import json
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
from inline_ui import (
    get_watch_list_keyboard,
    get_watch_detail_keyboard,
    get_filter_list_keyboard,
    get_filter_menu_keyboard
)
from peer_utils import ensure_peer, warm_up_peers


class TestInlineKeyboardGeneration(unittest.TestCase):
    """Test inline keyboard generation without network calls"""
    
    def setUp(self):
        """Set up test data"""
        self.sample_watches = {
            "watch-1": {
                "id": "watch-1",
                "source": {
                    "id": "-1001234567890",
                    "type": "channel",
                    "title": "Test Channel"
                },
                "target_chat_id": "me",
                "forward_mode": "full",
                "preserve_source": False,
                "enabled": True,
                "monitor_filters": {
                    "keywords": ["test", "example"],
                    "patterns": ["/test/i"]
                },
                "extract_filters": {
                    "keywords": [],
                    "patterns": []
                }
            },
            "watch-2": {
                "id": "watch-2",
                "source": {
                    "id": "@testchannel",
                    "type": "channel",
                    "title": "Another Channel"
                },
                "target_chat_id": "12345678",
                "forward_mode": "extract",
                "preserve_source": True,
                "enabled": False,
                "monitor_filters": {
                    "keywords": [],
                    "patterns": []
                },
                "extract_filters": {
                    "keywords": ["extract"],
                    "patterns": []
                }
            }
        }
    
    def test_watch_list_keyboard_generation(self):
        """Test generating watch list keyboard"""
        keyboard = get_watch_list_keyboard(self.sample_watches, page=1)
        
        # Should have inline keyboard markup
        self.assertIsNotNone(keyboard)
        self.assertTrue(hasattr(keyboard, 'inline_keyboard'))
        
        # Should have buttons for each watch
        buttons = keyboard.inline_keyboard
        self.assertGreater(len(buttons), 0)
        
        # Check callback data format
        first_button = buttons[0][0]
        self.assertTrue(first_button.callback_data.startswith("w:"))
        self.assertIn(":detail", first_button.callback_data)
    
    def test_watch_list_keyboard_pagination(self):
        """Test pagination with many watches"""
        # Create 15 watches
        many_watches = {}
        for i in range(15):
            many_watches[f"watch-{i}"] = {
                "id": f"watch-{i}",
                "source": {
                    "id": f"-100{i}",
                    "type": "channel",
                    "title": f"Channel {i}"
                },
                "enabled": True
            }
        
        # First page (5 items per page by default)
        keyboard_p1 = get_watch_list_keyboard(many_watches, page=1, watches_per_page=5)
        buttons_p1 = keyboard_p1.inline_keyboard
        
        # Should have 5 watch buttons + pagination row
        self.assertGreaterEqual(len(buttons_p1), 6)
        
        # Should have next button
        pagination_row = buttons_p1[-1]
        self.assertTrue(any("➡️" in btn.text for btn in pagination_row))
        
        # Second page
        keyboard_p2 = get_watch_list_keyboard(many_watches, page=2, watches_per_page=5)
        buttons_p2 = keyboard_p2.inline_keyboard
        
        # Should have prev button
        pagination_row = buttons_p2[-1]
        self.assertTrue(any("⬅️" in btn.text for btn in pagination_row))
    
    def test_watch_detail_keyboard_generation(self):
        """Test generating watch detail keyboard"""
        watch_data = self.sample_watches["watch-1"]
        keyboard = get_watch_detail_keyboard("watch-1", watch_data)
        
        self.assertIsNotNone(keyboard)
        self.assertTrue(hasattr(keyboard, 'inline_keyboard'))
        
        # Should have mode toggle buttons
        buttons = keyboard.inline_keyboard
        mode_row = buttons[0]
        self.assertEqual(len(mode_row), 2)
        self.assertIn("Full", mode_row[0].text)
        self.assertIn("Extract", mode_row[1].text)
    
    def test_filter_list_keyboard_generation(self):
        """Test generating filter list keyboard"""
        items = ["keyword1", "keyword2", "keyword3"]
        keyboard = get_filter_list_keyboard(
            "watch-1", "monitor", "kw", items, page=1
        )
        
        self.assertIsNotNone(keyboard)
        buttons = keyboard.inline_keyboard
        
        # Should have 3 item rows + back button
        self.assertGreaterEqual(len(buttons), 4)
        
        # Each item row should have display button and delete button
        for i in range(len(items)):
            self.assertEqual(len(buttons[i]), 2)
            self.assertIn("🗑️", buttons[i][1].text)
    
    def test_callback_data_length(self):
        """Test that callback data doesn't exceed Telegram's 64-byte limit"""
        # Create watch with long ID
        long_watch_id = "a" * 30
        watch_data = {
            "id": long_watch_id,
            "source": {"id": "-1001234567890", "type": "channel", "title": "Test"},
            "enabled": True,
            "forward_mode": "full",
            "preserve_source": False,
            "monitor_filters": {"keywords": [], "patterns": []},
            "extract_filters": {"keywords": [], "patterns": []}
        }
        
        keyboard = get_watch_detail_keyboard(long_watch_id, watch_data)
        
        # Check all callback data lengths
        for row in keyboard.inline_keyboard:
            for button in row:
                if hasattr(button, 'callback_data') and button.callback_data:
                    self.assertLessEqual(
                        len(button.callback_data.encode('utf-8')),
                        64,
                        f"Callback data too long: {button.callback_data}"
                    )
    
    def test_keyboard_with_string_source_id(self):
        """Test keyboard generation with string source ID (backward compatibility)"""
        watch_data = {
            "id": "watch-old",
            "source": "-1001234567890",  # Old format: string instead of dict
            "enabled": True,
            "forward_mode": "full",
            "preserve_source": False,
            "monitor_filters": {"keywords": [], "patterns": []},
            "extract_filters": {"keywords": [], "patterns": []}
        }
        
        # Should not crash
        keyboard = get_watch_detail_keyboard("watch-old", watch_data)
        self.assertIsNotNone(keyboard)
    
    def test_empty_watch_list(self):
        """Test keyboard generation with empty watch list"""
        keyboard = get_watch_list_keyboard({}, page=1)
        
        # Should return empty keyboard or minimal keyboard
        self.assertIsNotNone(keyboard)


class TestPeerResolution(unittest.TestCase):
    """Test peer resolution utilities"""
    
    def test_ensure_peer_with_valid_numeric_id(self):
        """Test peer resolution with valid numeric ID"""
        mock_app = Mock()
        mock_chat = Mock()
        mock_chat.id = -1001234567890
        mock_chat.title = "Test Channel"
        mock_app.get_chat.return_value = mock_chat
        
        watch_data = {
            "source": {
                "id": "-1001234567890",
                "title": "Test Channel"
            }
        }
        
        success, error_msg, chat = ensure_peer(mock_app, watch_data)
        
        self.assertTrue(success)
        self.assertIsNone(error_msg)
        self.assertIsNotNone(chat)
        mock_app.get_chat.assert_called_once_with(-1001234567890)
    
    def test_ensure_peer_with_username(self):
        """Test peer resolution with username"""
        mock_app = Mock()
        mock_chat = Mock()
        mock_chat.id = -1001234567890
        mock_chat.title = "Test Channel"
        mock_app.get_chat.return_value = mock_chat
        
        watch_data = {
            "source": {
                "id": "@testchannel",
                "title": "Test Channel"
            }
        }
        
        success, error_msg, chat = ensure_peer(mock_app, watch_data)
        
        self.assertTrue(success)
        self.assertIsNone(error_msg)
        self.assertIsNotNone(chat)
        mock_app.get_chat.assert_called_once_with("@testchannel")
    
    def test_ensure_peer_with_peer_id_invalid(self):
        """Test peer resolution with PeerIdInvalid error"""
        from pyrogram.errors import PeerIdInvalid
        
        mock_app = Mock()
        mock_app.get_chat.side_effect = PeerIdInvalid()
        
        watch_data = {
            "source": {
                "id": "-1001234567890",
                "title": "Invalid Channel"
            }
        }
        
        success, error_msg, chat = ensure_peer(mock_app, watch_data)
        
        self.assertFalse(success)
        self.assertIsNotNone(error_msg)
        self.assertIn("ID无效", error_msg)
        self.assertIsNone(chat)
    
    def test_ensure_peer_with_channel_private(self):
        """Test peer resolution with ChannelPrivate error"""
        from pyrogram.errors import ChannelPrivate
        
        mock_app = Mock()
        mock_app.get_chat.side_effect = ChannelPrivate()
        
        watch_data = {
            "source": {
                "id": "-1001234567890",
                "title": "Private Channel"
            }
        }
        
        success, error_msg, chat = ensure_peer(mock_app, watch_data)
        
        self.assertFalse(success)
        self.assertIsNotNone(error_msg)
        self.assertIn("私有", error_msg)
        self.assertIsNone(chat)
    
    def test_ensure_peer_with_empty_source(self):
        """Test peer resolution with empty source"""
        mock_app = Mock()
        
        watch_data = {
            "source": {
                "id": "",
                "title": "Empty"
            }
        }
        
        success, error_msg, chat = ensure_peer(mock_app, watch_data)
        
        self.assertFalse(success)
        self.assertIsNotNone(error_msg)
        self.assertIsNone(chat)
        # Should not call get_chat
        mock_app.get_chat.assert_not_called()
    
    def test_warm_up_peers_without_session(self):
        """Test warm-up gracefully handles no session"""
        # Should not crash
        warm_up_peers(None, {"users": {}})
    
    def test_warm_up_peers_with_multiple_watches(self):
        """Test warm-up with multiple watches"""
        mock_app = Mock()
        mock_chat = Mock()
        mock_chat.id = -1001234567890
        mock_app.get_chat.return_value = mock_chat
        
        watch_config = {
            "users": {
                "123": {
                    "watch-1": {
                        "source": {"id": "-1001111111111", "title": "Channel 1"}
                    },
                    "watch-2": {
                        "source": {"id": "-1001222222222", "title": "Channel 2"}
                    }
                }
            }
        }
        
        # Should not crash
        warm_up_peers(mock_app, watch_config)
        
        # Should attempt to resolve both
        self.assertEqual(mock_app.get_chat.call_count, 2)


class TestCallbackDataValidation(unittest.TestCase):
    """Test callback data format and validation"""
    
    def test_callback_data_parsing(self):
        """Test parsing various callback data formats"""
        test_cases = [
            ("w:watch-id:detail", ["w", "watch-id", "detail"]),
            ("w:watch-id:mode:full", ["w", "watch-id", "mode", "full"]),
            ("w:list:1", ["w", "list", "1"]),
            ("iktest:ok", ["iktest", "ok"]),
            ("iktest:refresh", ["iktest", "refresh"]),
        ]
        
        for callback_data, expected_parts in test_cases:
            parts = callback_data.split(":")
            self.assertEqual(parts, expected_parts, f"Failed for: {callback_data}")
    
    def test_short_callback_data(self):
        """Test that common callbacks are short"""
        short_callbacks = [
            "w:list:1",
            "iktest:ok",
            "w:abc123:detail",
            "w:abc123:mode:full",
        ]
        
        for callback_data in short_callbacks:
            byte_length = len(callback_data.encode('utf-8'))
            self.assertLessEqual(
                byte_length, 
                40,  # Well under the 64-byte limit
                f"Callback too long: {callback_data}"
            )


if __name__ == '__main__':
    unittest.main()
