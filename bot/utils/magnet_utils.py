"""
磁力链接工具模块
统一处理磁力链接的解析、提取和构建
"""
import re
from typing import Optional, List, Dict
from urllib.parse import quote, unquote_plus, urlparse, parse_qs
import logging

logger = logging.getLogger(__name__)


class MagnetLinkParser:
    """磁力链接解析器"""

    # 磁力链接起始标记（用于从文本中定位磁力链接的开始位置）
    # 容忍btih:后面的空格
    MAGNET_START_PATTERN = re.compile(r'magnet:\?xt=urn:btih:\s*[a-zA-Z0-9]+', re.IGNORECASE)
    INFO_HASH_PATTERN = r'xt=urn:btih:\s*([a-zA-Z0-9]+)'
    DN_PARAMETER_PATTERN = r'[&?]dn=([^\n\r&]+)'
    _FILENAME_EXTENSION_PATTERN = re.compile(r'\.[A-Za-z0-9]{1,8}(?=(&|\s|$))')

    @staticmethod
    def extract_all_magnets(text: str) -> List[str]:
        """从文本中提取所有磁力链接

        Args:
            text: 包含磁力链接的文本

        Returns:
            磁力链接列表
        """
        if not text:
            return []

        starts = list(MagnetLinkParser.MAGNET_START_PATTERN.finditer(text))
        if not starts:
            return []

        magnets: List[str] = []
        for idx, start_match in enumerate(starts):
            start_pos = start_match.start()
            end_limit = starts[idx + 1].start() if idx + 1 < len(starts) else len(text)
            segment = text[start_pos:end_limit]

            # 磁力链接通常不会跨行；限定在当前行内，避免吞掉后续文本
            newline_pos = len(segment)
            for ch in ("\n", "\r"):
                pos = segment.find(ch)
                if pos != -1:
                    newline_pos = min(newline_pos, pos)
            segment = segment[:newline_pos]

            magnet = MagnetLinkParser._extract_single_magnet_from_segment(segment)
            if magnet:
                magnets.append(magnet.rstrip())

        return magnets

    @staticmethod
    def _extract_single_magnet_from_segment(segment: str) -> Optional[str]:
        """从以 magnet: 开头的片段中提取单条磁力链接

        兼容处理：
        1. dn 参数值中包含未编码空格的场景（例如 dn=My Document Name.pdf）
        2. btih: 后面可能有空格的场景（例如 btih: abc123）
        """
        if not segment or not segment.lower().startswith("magnet:"):
            return None

        # 默认：遇到空白字符即认为磁力链接结束
        whitespace_match = re.search(r"\s", segment)
        default_end = whitespace_match.start() if whitespace_match else len(segment)

        dn_match = re.search(r"[&?]dn=", segment, re.IGNORECASE)
        if not dn_match:
            # 没有dn参数：提取基础磁力链接（容忍btih:后的空格）
            # 匹配 magnet:?xt=urn:btih: 后面的info_hash（40个十六进制字符）
            base_match = re.match(r'magnet:\?xt=urn:btih:\s*([a-zA-Z0-9]{40})', segment, re.IGNORECASE)
            if base_match:
                # 返回标准格式（去掉空格）
                info_hash = base_match.group(1)
                return f"magnet:?xt=urn:btih:{info_hash}"

            # 如果不是标准的40字符hash，按原逻辑处理（遇到空白字符即结束）
            return segment[:default_end]

        # 有dn参数：提取到下一个&或空白字符
        dn_value_start = dn_match.end()
        next_amp_pos = segment.find("&", dn_value_start)

        if next_amp_pos != -1:
            # 有下一个参数，dn值到&为止
            dn_value_end = next_amp_pos
        else:
            # 没有下一个参数，尝试查找文件扩展名
            # 如果dn值中包含未编码空格（如 dn=My Document Name.pdf），
            # 应该提取到文件扩展名之后，而不是在第一个空格处停止
            ext_match = MagnetLinkParser._FILENAME_EXTENSION_PATTERN.search(segment, dn_value_start)
            if ext_match:
                # 找到文件扩展名，提取到扩展名之后
                dn_value_end = ext_match.end()
            else:
                # 没有找到文件扩展名，继续查找下一行或段落结束
                # 优先在换行符处停止，因为磁力链接不应跨行
                # 如果没有换行符，则提取到段落结束
                dn_value_end = len(segment)
                for i in range(dn_value_start, len(segment)):
                    if segment[i] in '\n\r':
                        dn_value_end = i
                        break

        # 继续提取后续参数（如&tr=等）
        end_pos = dn_value_end
        if dn_value_end < len(segment) and segment[dn_value_end] == "&":
            while end_pos < len(segment) and not segment[end_pos].isspace():
                end_pos += 1

        return segment[:end_pos]

    @staticmethod
    def extract_info_hash(magnet: str) -> Optional[str]:
        """从磁力链接提取info hash

        Args:
            magnet: 磁力链接

        Returns:
            info hash（大写），失败返回None
        """
        if not magnet:
            return None

        match = re.search(
            MagnetLinkParser.INFO_HASH_PATTERN,
            magnet,
            re.IGNORECASE
        )

        if match:
            return match.group(1).upper()
        return None

    @staticmethod
    def extract_dn_parameter(magnet: str) -> Optional[str]:
        """从磁力链接提取dn参数（文件名）

        Args:
            magnet: 磁力链接

        Returns:
            解码后的dn参数，失败返回None
        """
        if not magnet:
            return None

        # 方法1: 使用正则提取
        match = re.search(MagnetLinkParser.DN_PARAMETER_PATTERN, magnet)
        if match:
            dn_encoded = match.group(1)
            dn_decoded = unquote_plus(dn_encoded)
            # 清理可能的HTML标签和多余空格
            dn_decoded = re.sub(r'<[^>]+>', '', dn_decoded).strip()
            return dn_decoded

        # 方法2: 使用urlparse（更严格）
        try:
            parsed = urlparse(magnet)
            params = parse_qs(parsed.query)
            dn_values = params.get('dn', [])
            if dn_values:
                dn_decoded = unquote_plus(dn_values[0])
                dn_decoded = re.sub(r'<[^>]+>', '', dn_decoded).strip()
                return dn_decoded
        except Exception as e:
            logger.debug(f"解析dn参数失败: {e}")

        return None

    @staticmethod
    def build_magnet_link(info_hash: str, filename: Optional[str] = None,
                         trackers: Optional[List[str]] = None) -> str:
        """构建磁力链接

        Args:
            info_hash: info hash
            filename: 文件名（可选）
            trackers: tracker列表（可选）

        Returns:
            完整的磁力链接
        """
        magnet = f"magnet:?xt=urn:btih:{info_hash.upper()}"

        if filename:
            # URL编码文件名
            encoded_filename = quote(filename)
            magnet += f"&dn={encoded_filename}"

        if trackers:
            for tracker in trackers:
                encoded_tracker = quote(tracker)
                magnet += f"&tr={encoded_tracker}"

        return magnet

    @staticmethod
    def clean_filename(filename: str) -> str:
        """清理文件名，去除HTML标签、磁力链接和多余空格

        Args:
            filename: 原始文件名

        Returns:
            清理后的文件名
        """
        if not filename:
            return ''

        # 去除HTML标签（如<br>）
        cleaned = re.sub(r'<[^>]+>', '', filename)

        # 去除 magnet: 开头的部分（文件名后面可能跟着另一个磁力链接）
        cleaned = re.split(r'[\s\r\n]*magnet:', cleaned, flags=re.IGNORECASE)[0]

        # 去除换行符和多余空格
        cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)

        return cleaned.strip()

    @staticmethod
    def extract_magnet_from_text(message_text: str) -> Optional[str]:
        """从消息文本中提取并构建标准磁力链接

        提取规则：
        1. 如果磁力链接中已有dn参数，提取dn=后面的文本到行结束作为文件名
        2. 如果没有dn参数，从文本开头到第一个#号之前提取作为文件名

        Args:
            message_text: 消息文本

        Returns:
            标准化的磁力链接，失败返回None
        """
        if not message_text:
            return None

        magnets = MagnetLinkParser.extract_all_magnets(message_text)
        if not magnets:
            return None

        magnet_link = magnets[0].rstrip()

        # 提取info_hash
        info_hash = MagnetLinkParser.extract_info_hash(magnet_link)
        if not info_hash:
            return None

        # 检测是否有 dn 参数（兼容dn值中包含空格/+/URL编码）
        dn_decoded = MagnetLinkParser.extract_dn_parameter(magnet_link)
        if dn_decoded:
            return MagnetLinkParser.build_magnet_link(info_hash, dn_decoded)

        # 没有dn参数，只返回基础磁力链接（让校准系统后续处理）
        return MagnetLinkParser.build_magnet_link(info_hash)

    @staticmethod
    def extract_all_magnet_info(message_text: str, filename: Optional[str] = None) -> List[Dict]:
        """从消息文本中提取所有磁力链接的完整信息

        Args:
            message_text: 消息文本
            filename: 校准后的文件名（可选，用于第一个磁力链接）

        Returns:
            磁力链接信息列表 [{'magnet': ..., 'info_hash': ..., 'dn': ...}, ...]
        """
        result = []

        # 提取所有磁力链接
        all_magnets = MagnetLinkParser.extract_all_magnets(message_text)

        for idx, magnet in enumerate(all_magnets):
            # 提取info_hash
            info_hash = MagnetLinkParser.extract_info_hash(magnet)

            # 对于第一个磁力链接，如果有filename字段（校准结果），优先使用filename
            # 因为message_text中的磁力链接可能不完整或dn参数未编码
            if idx == 0 and filename:
                dn = filename
            else:
                # 其他情况从磁力链接自身提取dn参数
                dn = MagnetLinkParser.extract_dn_parameter(magnet)

            if info_hash or dn:  # 只要有info_hash或dn就添加
                result.append({
                    'magnet': magnet,
                    'info_hash': info_hash,
                    'dn': dn
                })

        return result


# 便捷函数（向后兼容）
def extract_all_magnets_from_text(text: str) -> List[str]:
    """从文本中提取所有磁力链接（向后兼容）"""
    return MagnetLinkParser.extract_all_magnets(text)


def extract_dn_from_magnet(magnet_link: str, message_text: Optional[str] = None,
                           filename: Optional[str] = None) -> Optional[str]:
    """从磁力链接中提取dn参数（向后兼容）

    优先级：filename字段 > magnet_link的dn参数 > message_text提取
    """
    # 优先使用filename字段（校准后的完整文件名）
    if filename:
        return filename

    # 其次尝试从磁力链接中提取 dn= 参数
    dn = MagnetLinkParser.extract_dn_parameter(magnet_link)
    if dn:
        return dn

    # 如果磁力链接没有dn参数，返回None（不再从文本提取）
    return None


def extract_all_dns_from_note(note: Dict) -> List[Dict]:
    """从笔记中提取所有磁力链接的dn参数（向后兼容）

    Args:
        note: 笔记字典，包含magnet_link、message_text和filename

    Returns:
        [{'magnet': 磁力链接, 'dn': dn参数, 'info_hash': info_hash}, ...]
    """
    message_text = note.get('message_text', '')
    filename = note.get('filename')  # 获取校准后的完整文件名

    return MagnetLinkParser.extract_all_magnet_info(message_text, filename)
