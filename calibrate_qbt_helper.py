#!/usr/bin/env python3
"""
磁力链接校准助手 - qBittorrent API版本
通过qBittorrent Web API获取种子的真实文件名
"""
import sys
import time
import requests
import os

# qBittorrent Web API配置
QBT_URL = os.environ.get('QBT_URL', 'http://localhost:8080')
QBT_USERNAME = os.environ.get('QBT_USERNAME', 'admin')
QBT_PASSWORD = os.environ.get('QBT_PASSWORD', '')  # localhost白名单无需密码

def login_qbt(session):
    """登录qBittorrent（如果需要）

    Args:
        session: requests会话对象

    Returns:
        是否登录成功
    """
    try:
        # 尝试访问API测试是否需要登录
        response = session.get(f"{QBT_URL}/api/v2/app/version", timeout=5)
        if response.status_code == 200:
            return True

        # 需要登录 - 总是尝试登录（即使密码为空）
        login_url = f"{QBT_URL}/api/v2/auth/login"
        response = session.post(login_url, data={
            'username': QBT_USERNAME,
            'password': QBT_PASSWORD
        }, timeout=5)

        if response.text == "Ok.":
            # 登录成功，再次验证
            response = session.get(f"{QBT_URL}/api/v2/app/version", timeout=5)
            return response.status_code == 200

        return False
    except Exception as e:
        print(f"登录失败: {e}", file=sys.stderr)
        return False

def calibrate_magnet(info_hash: str, timeout: int = 25) -> str:
    """通过qBittorrent API校准磁力链接，获取文件名

    Args:
        info_hash: 磁力链接的info hash
        timeout: 超时时间（秒）

    Returns:
        文件名，失败抛出异常
    """
    session = requests.Session()

    try:
        # 登录（如果需要）
        if not login_qbt(session):
            raise Exception("无法连接到qBittorrent API")

        # 构造磁力链接
        magnet_uri = f"magnet:?xt=urn:btih:{info_hash}"

        # 添加种子（暂停状态，只获取元数据）
        add_url = f"{QBT_URL}/api/v2/torrents/add"
        response = session.post(add_url, data={
            'urls': magnet_uri,
            'paused': 'true',  # 暂停状态
            'savepath': '/downloads/temp_calibration',
            'category': 'calibration',  # 标记为校准任务
            'skip_checking': 'true'  # 跳过文件检查
        }, timeout=10)

        if response.text != "Ok.":
            raise Exception(f"添加种子失败: {response.text}")

        # 等待元数据下载完成
        info_hash_lower = info_hash.lower()
        start_time = time.time()

        while time.time() - start_time < timeout:
            # 获取种子信息
            list_url = f"{QBT_URL}/api/v2/torrents/info"
            response = session.get(list_url, params={
                'hashes': info_hash_lower
            }, timeout=5)

            if response.status_code == 200:
                torrents = response.json()
                if torrents:
                    torrent = torrents[0]
                    name = torrent.get('name', '')

                    # 检查是否已获取元数据
                    # 当name不等于hash时，说明已获取到真实名称
                    if name and name.lower() != info_hash_lower:
                        # 删除种子（不删除文件）
                        delete_url = f"{QBT_URL}/api/v2/torrents/delete"
                        session.post(delete_url, data={
                            'hashes': info_hash_lower,
                            'deleteFiles': 'false'
                        }, timeout=5)

                        return name

            # 等待一段时间再检查
            time.sleep(0.5)

        # 超时，删除种子
        delete_url = f"{QBT_URL}/api/v2/torrents/delete"
        session.post(delete_url, data={
            'hashes': info_hash_lower,
            'deleteFiles': 'false'
        }, timeout=5)

        raise TimeoutError(f"获取元数据超时（{timeout}秒内未获得有效数据）")

    except requests.exceptions.RequestException as e:
        raise Exception(f"网络请求失败: {e}")
    except TimeoutError:
        raise
    except Exception as e:
        raise Exception(f"校准失败: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python3 calibrate_qbt_helper.py <info_hash>", file=sys.stderr)
        sys.exit(1)

    try:
        filename = calibrate_magnet(sys.argv[1])
        print(filename)
        sys.exit(0)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)
