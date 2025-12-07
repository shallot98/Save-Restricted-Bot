#!/usr/bin/env python3
"""
磁力链接校准助手
通过 info_hash 获取种子的真实文件名
"""
import sys
import libtorrent as lt
import time
import tempfile
import warnings

# 忽略废弃 API 的警告
warnings.filterwarnings('ignore', category=DeprecationWarning)

def calibrate_magnet(info_hash: str, timeout: int = 25) -> str:
    """校准磁力链接，获取文件名"""
    # 创建临时目录用于保存下载
    temp_dir = tempfile.mkdtemp()

    try:
        # 创建 libtorrent 会话（简化配置）
        ses = lt.session()

        # 创建磁力链接 URI
        magnet_uri = f"magnet:?xt=urn:btih:{info_hash}"

        # 创建添加参数对象
        params = lt.add_torrent_params()
        params.save_path = temp_dir

        # 尝试设置 URL（兼容不同版本）
        try:
            params.url = magnet_uri
        except:
            # 如果不支持，使用 parse_magnet_uri
            parsed = lt.parse_magnet_uri(magnet_uri)
            params = parsed

        # 添加到会话
        try:
            handle = ses.add_torrent(params)
        except TypeError:
            # 老版本 API 可能不同
            handle = ses.add_torrent_params(params)

        # 等待元数据
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # 尝试访问状态
                try:
                    if handle.status().has_metadata:
                        torrent_info = handle.get_torrent_info()
                        return torrent_info.name()
                except:
                    if handle.has_metadata():
                        torrent_info = handle.get_torrent_info()
                        return torrent_info.name()
            except Exception as e:
                pass

            time.sleep(0.5)

        raise TimeoutError(f"获取元数据超时（{timeout}秒内未获得有效数据）")
    finally:
        # 清理临时目录
        import shutil
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except:
            pass

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 calibrate_helper.py <info_hash>", file=sys.stderr)
        sys.exit(1)

    try:
        filename = calibrate_magnet(sys.argv[1])
        print(filename)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
