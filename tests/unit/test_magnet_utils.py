"""
磁力链接工具模块的单元测试
"""
import pytest
from bot.utils.magnet_utils import MagnetLinkParser


class TestMagnetLinkParser:
    """测试MagnetLinkParser类"""

    def test_extract_all_magnets_single(self):
        """测试提取单个磁力链接"""
        text = "这是一个测试 magnet:?xt=urn:btih:ABC123&dn=test_file.mp4 链接"
        magnets = MagnetLinkParser.extract_all_magnets(text)

        assert len(magnets) == 1
        assert "ABC123" in magnets[0]
        assert "dn=test_file.mp4" in magnets[0]

    def test_extract_all_magnets_multiple(self):
        """测试提取多个磁力链接"""
        text = """
        第一个: magnet:?xt=urn:btih:ABC123&dn=file1.mp4
        第二个: magnet:?xt=urn:btih:DEF456&dn=file2.mkv
        """
        magnets = MagnetLinkParser.extract_all_magnets(text)

        assert len(magnets) == 2
        assert "ABC123" in magnets[0]
        assert "DEF456" in magnets[1]

    def test_extract_all_magnets_empty(self):
        """测试空文本"""
        assert MagnetLinkParser.extract_all_magnets("") == []
        assert MagnetLinkParser.extract_all_magnets(None) == []

    def test_extract_all_magnets_no_match(self):
        """测试没有磁力链接的文本"""
        text = "这是一段普通文本，没有磁力链接"
        magnets = MagnetLinkParser.extract_all_magnets(text)

        assert len(magnets) == 0

    def test_extract_info_hash_uppercase(self):
        """测试提取info hash（应该大写）"""
        magnet = "magnet:?xt=urn:btih:abc123def456&dn=test"
        info_hash = MagnetLinkParser.extract_info_hash(magnet)

        assert info_hash == "ABC123DEF456"

    def test_extract_info_hash_already_uppercase(self):
        """测试提取已经大写的info hash"""
        magnet = "magnet:?xt=urn:btih:ABC123DEF456&dn=test"
        info_hash = MagnetLinkParser.extract_info_hash(magnet)

        assert info_hash == "ABC123DEF456"

    def test_extract_info_hash_invalid(self):
        """测试无效的磁力链接"""
        assert MagnetLinkParser.extract_info_hash("invalid") is None
        assert MagnetLinkParser.extract_info_hash("") is None
        assert MagnetLinkParser.extract_info_hash(None) is None

    def test_extract_dn_parameter_simple(self):
        """测试提取简单的dn参数"""
        magnet = "magnet:?xt=urn:btih:ABC123&dn=test_file.mp4"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        assert dn == "test_file.mp4"

    def test_extract_dn_parameter_url_encoded(self):
        """测试提取URL编码的dn参数"""
        magnet = "magnet:?xt=urn:btih:ABC123&dn=test%20file%20with%20spaces.mp4"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        assert dn == "test file with spaces.mp4"

    def test_extract_dn_parameter_plus_encoded(self):
        """测试提取+编码的dn参数（空格编码为+）"""
        magnet = "magnet:?xt=urn:btih:ABC123&dn=My+Document+Name.pdf"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        assert dn == "My Document Name.pdf"

    def test_extract_dn_parameter_chinese(self):
        """测试提取中文dn参数"""
        magnet = "magnet:?xt=urn:btih:ABC123&dn=%E6%B5%8B%E8%AF%95%E6%96%87%E4%BB%B6.mp4"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        assert dn == "测试文件.mp4"

    def test_extract_dn_parameter_no_dn(self):
        """测试没有dn参数的磁力链接"""
        magnet = "magnet:?xt=urn:btih:ABC123"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        assert dn is None

    def test_extract_dn_parameter_with_html_tags(self):
        """测试包含HTML标签的dn参数"""
        magnet = "magnet:?xt=urn:btih:ABC123&dn=test<br>file.mp4"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        # 应该清理HTML标签
        assert "<br>" not in dn
        assert "test" in dn
        assert "file.mp4" in dn

    def test_build_magnet_link_basic(self):
        """测试构建基本磁力链接"""
        magnet = MagnetLinkParser.build_magnet_link("abc123")

        assert magnet == "magnet:?xt=urn:btih:ABC123"

    def test_build_magnet_link_with_filename(self):
        """测试构建带文件名的磁力链接"""
        magnet = MagnetLinkParser.build_magnet_link("abc123", "test file.mp4")

        assert "magnet:?xt=urn:btih:ABC123" in magnet
        assert "dn=test%20file.mp4" in magnet

    def test_build_magnet_link_with_trackers(self):
        """测试构建带tracker的磁力链接"""
        trackers = ["http://tracker1.com", "http://tracker2.com"]
        magnet = MagnetLinkParser.build_magnet_link("abc123", "test.mp4", trackers)

        assert "magnet:?xt=urn:btih:ABC123" in magnet
        # URL编码可能不完全编码斜杠，检查tracker是否存在即可
        assert "tr=" in magnet
        assert "tracker1.com" in magnet
        assert "tracker2.com" in magnet

    def test_clean_filename_html_tags(self):
        """测试清理HTML标签"""
        filename = "test<br>file<span>name</span>.mp4"
        cleaned = MagnetLinkParser.clean_filename(filename)

        assert "<br>" not in cleaned
        assert "<span>" not in cleaned
        assert "</span>" not in cleaned
        assert "testfilename.mp4" == cleaned

    def test_clean_filename_magnet_link(self):
        """测试清理文件名中的磁力链接"""
        filename = "test_file.mp4 magnet:?xt=urn:btih:ABC123"
        cleaned = MagnetLinkParser.clean_filename(filename)

        assert "magnet:" not in cleaned
        assert cleaned == "test_file.mp4"

    def test_clean_filename_newlines(self):
        """测试清理换行符"""
        filename = "test\nfile\r\nname.mp4"
        cleaned = MagnetLinkParser.clean_filename(filename)

        assert "\n" not in cleaned
        assert "\r" not in cleaned
        assert cleaned == "test file name.mp4"

    def test_clean_filename_multiple_spaces(self):
        """测试清理多余空格"""
        filename = "test    file     name.mp4"
        cleaned = MagnetLinkParser.clean_filename(filename)

        assert cleaned == "test file name.mp4"

    def test_extract_magnet_from_text_with_dn(self):
        """测试从文本提取带dn参数的磁力链接"""
        text = "测试 magnet:?xt=urn:btih:ABC123&dn=test_file.mp4 链接"
        magnet = MagnetLinkParser.extract_magnet_from_text(text)

        assert magnet is not None
        assert "ABC123" in magnet
        assert "dn=" in magnet

    def test_extract_magnet_from_text_with_dn_unencoded_spaces(self):
        """测试从文本提取dn包含未编码空格的磁力链接"""
        text = "测试 magnet:?xt=urn:btih:ABC123&dn=My Document Name.pdf 链接"
        magnet = MagnetLinkParser.extract_magnet_from_text(text)

        assert magnet is not None
        assert "ABC123" in magnet
        assert "dn=My%20Document%20Name.pdf" in magnet

    def test_extract_magnet_from_text_without_dn(self):
        """测试从文本提取没有dn参数的磁力链接"""
        text = "文件名在这里 #标签 magnet:?xt=urn:btih:ABC123"
        magnet = MagnetLinkParser.extract_magnet_from_text(text)

        assert magnet is not None
        assert "ABC123" in magnet
        # 没有dn参数时，只返回基础磁力链接（让校准系统后续处理）
        assert "dn=" not in magnet

    def test_extract_all_magnet_info_single(self):
        """测试提取单个磁力链接的完整信息"""
        text = "测试 magnet:?xt=urn:btih:ABC123&dn=test.mp4 链接"
        info_list = MagnetLinkParser.extract_all_magnet_info(text)

        assert len(info_list) == 1
        assert info_list[0]['info_hash'] == "ABC123"
        assert info_list[0]['dn'] == "test.mp4"
        assert "magnet:" in info_list[0]['magnet']

    def test_extract_all_magnet_info_with_filename(self):
        """测试使用校准后的filename"""
        text = "测试 magnet:?xt=urn:btih:ABC123&dn=old_name.mp4 链接"
        filename = "calibrated_name.mp4"
        info_list = MagnetLinkParser.extract_all_magnet_info(text, filename)

        assert len(info_list) == 1
        # 第一个磁力链接应该使用校准后的filename
        assert info_list[0]['dn'] == "calibrated_name.mp4"

    def test_extract_all_magnet_info_multiple(self):
        """测试提取多个磁力链接的信息"""
        text = """
        第一个: magnet:?xt=urn:btih:ABC123&dn=file1.mp4
        第二个: magnet:?xt=urn:btih:DEF456&dn=file2.mkv
        """
        filename = "calibrated_file1.mp4"
        info_list = MagnetLinkParser.extract_all_magnet_info(text, filename)

        assert len(info_list) == 2
        # 第一个使用校准后的filename
        assert info_list[0]['dn'] == "calibrated_file1.mp4"
        # 第二个使用自己的dn
        assert info_list[1]['dn'] == "file2.mkv"



    def test_extract_dn_parameter_unencoded_space_no_extension(self):
        """测试未编码空格且无扩展名的dn参数（修复空格截断bug）"""
        magnet = "magnet:?xt=urn:btih:ABC123&dn=大车司机夜晚路边招嫖 卡车后站立后入 卡车后站立后入"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        # 应该提取完整文件名,不应在第一个空格处截断
        assert dn == "大车司机夜晚路边招嫖 卡车后站立后入 卡车后站立后入"
        assert "卡车后站立后入" in dn

    def test_extract_all_magnets_unencoded_space_no_extension(self):
        """测试从文本提取包含未编码空格且无扩展名的磁力链接（修复空格截断bug）"""
        text = "magnet:?xt=urn:btih:ABC123&dn=My Document Name Without Extension"
        magnets = MagnetLinkParser.extract_all_magnets(text)

        assert len(magnets) == 1
        assert magnets[0] == "magnet:?xt=urn:btih:ABC123&dn=My Document Name Without Extension"

        # 验证dn参数完整性
        dn = MagnetLinkParser.extract_dn_parameter(magnets[0])
        assert dn == "My Document Name Without Extension"

    def test_extract_dn_parameter_unencoded_space_with_newline(self):
        """测试未编码空格且有换行符的dn参数（应在换行符处停止）"""
        magnet = "magnet:?xt=urn:btih:ABC123&dn=My Document Name\nNext Line"
        dn = MagnetLinkParser.extract_dn_parameter(magnet)

        # 应在换行符处停止
        assert dn == "My Document Name"
        assert "Next Line" not in dn


class TestBackwardCompatibility:
    """测试向后兼容的便捷函数"""

    def test_extract_all_magnets_from_text(self):
        """测试向后兼容的extract_all_magnets_from_text函数"""
        from bot.utils.magnet_utils import extract_all_magnets_from_text

        text = "测试 magnet:?xt=urn:btih:ABC123&dn=test.mp4"
        magnets = extract_all_magnets_from_text(text)

        assert len(magnets) == 1
        assert "ABC123" in magnets[0]

    def test_extract_dn_from_magnet(self):
        """测试向后兼容的extract_dn_from_magnet函数"""
        from bot.utils.magnet_utils import extract_dn_from_magnet

        # 优先使用filename参数
        dn = extract_dn_from_magnet("magnet:?xt=urn:btih:ABC123&dn=old.mp4", None, "new.mp4")
        assert dn == "new.mp4"

        # 其次从磁力链接提取
        dn = extract_dn_from_magnet("magnet:?xt=urn:btih:ABC123&dn=test.mp4", None, None)
        assert dn == "test.mp4"

        # 没有dn参数返回None
        dn = extract_dn_from_magnet("magnet:?xt=urn:btih:ABC123", None, None)
        assert dn is None

    def test_extract_all_dns_from_note(self):
        """测试向后兼容的extract_all_dns_from_note函数"""
        from bot.utils.magnet_utils import extract_all_dns_from_note

        note = {
            'message_text': 'magnet:?xt=urn:btih:ABC123&dn=test.mp4',
            'filename': 'calibrated_name.mp4'
        }

        dns_list = extract_all_dns_from_note(note)

        assert len(dns_list) == 1
        # 第一个磁力链接应该使用filename字段
        assert dns_list[0]['dn'] == 'calibrated_name.mp4'
        assert dns_list[0]['info_hash'] == 'ABC123'
