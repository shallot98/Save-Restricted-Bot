#!/usr/bin/env python3
"""
测试qBittorrent Web API是否可用于校准磁力链接
"""
import requests
import time
import sys

# qBittorrent Web API配置
QBT_URL = "http://localhost:8080"
QBT_USERNAME = "admin"
QBT_PASSWORD = "V7IuSLWYF"  # 临时密码（从docker logs获取）

def test_qbt_connection():
    """测试qBittorrent连接"""
    try:
        # 登录
        session = requests.Session()
        login_url = f"{QBT_URL}/api/v2/auth/login"
        response = session.post(login_url, data={
            'username': QBT_USERNAME,
            'password': QBT_PASSWORD
        })

        if response.text == "Ok.":
            print("✅ qBittorrent登录成功")
            return session
        else:
            print(f"❌ qBittorrent登录失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 连接qBittorrent失败: {e}")
        return None

def get_torrent_name_from_qbt(session, info_hash, timeout=30):
    """通过qBittorrent API获取种子名称

    Args:
        session: requests会话
        info_hash: 磁力链接的info hash
        timeout: 超时时间（秒）

    Returns:
        种子名称，失败返回None
    """
    try:
        # 构造磁力链接
        magnet_link = f"magnet:?xt=urn:btih:{info_hash}"

        # 添加种子（暂停状态）
        add_url = f"{QBT_URL}/api/v2/torrents/add"
        response = session.post(add_url, data={
            'urls': magnet_link,
            'paused': 'true',  # 暂停状态，只获取元数据
            'savepath': '/downloads/temp_calibration'
        })

        if response.text != "Ok.":
            print(f"❌ 添加种子失败: {response.text}")
            return None

        print(f"✅ 种子已添加到qBittorrent，等待元数据...")

        # 等待元数据下载完成
        start_time = time.time()
        while time.time() - start_time < timeout:
            # 获取种子列表
            list_url = f"{QBT_URL}/api/v2/torrents/info"
            response = session.get(list_url, params={'hashes': info_hash.lower()})

            if response.status_code == 200:
                torrents = response.json()
                if torrents:
                    torrent = torrents[0]
                    # 检查是否已获取元数据
                    if torrent.get('name') and torrent['name'] != info_hash:
                        name = torrent['name']
                        print(f"✅ 成功获取种子名称: {name}")

                        # 删除种子（不删除文件）
                        delete_url = f"{QBT_URL}/api/v2/torrents/delete"
                        session.post(delete_url, data={
                            'hashes': info_hash.lower(),
                            'deleteFiles': 'false'
                        })

                        return name

            time.sleep(1)

        print(f"❌ 获取元数据超时（{timeout}秒）")

        # 超时后删除种子
        delete_url = f"{QBT_URL}/api/v2/torrents/delete"
        session.post(delete_url, data={
            'hashes': info_hash.lower(),
            'deleteFiles': 'false'
        })

        return None

    except Exception as e:
        print(f"❌ 获取种子名称失败: {e}")
        return None

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python3 test_qbt_api.py <info_hash>")
        print("示例: python3 test_qbt_api.py 1234567890ABCDEF1234567890ABCDEF12345678")
        sys.exit(1)

    info_hash = sys.argv[1]

    # 测试连接
    session = test_qbt_connection()
    if not session:
        sys.exit(1)

    # 获取种子名称
    name = get_torrent_name_from_qbt(session, info_hash, timeout=30)

    if name:
        print(f"\n✅ 校准成功！")
        print(f"种子名称: {name}")
        sys.exit(0)
    else:
        print(f"\n❌ 校准失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
