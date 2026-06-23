#!/usr/bin/env python3
"""
从 IPTV 抓包文件中提取鉴权参数
用法: python3 extract_auth.py <抓包文件>
"""

import re
import sys

def extract_auth_params(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    params = {}

    # IPTV 服务器地址
    host_match = re.search(r'Host:\s*([\d.]+:\d+)', content)
    if host_match:
        params['IPTV_SERVER'] = f"http://{host_match.group(1)}"

    # UserID
    user_id = re.search(r'UserID[=&](\d+)', content)
    if user_id:
        params['USER_ID'] = user_id.group(1)

    # Authenticator（鉴权接口的长token）
    authenticator = re.search(r'Authenticator=([A-F0-9]{100,})', content)
    if authenticator:
        params['AUTHENTICATOR'] = authenticator.group(1)

    # userToken（鉴权接口）
    user_token = re.search(r'userToken=([A-F0-9]{32})', content, re.IGNORECASE)
    if user_token:
        params['USER_TOKEN'] = user_token.group(1)

    # UserToken（频道列表接口）
    user_token_service = re.search(r"UserToken[='\"]([A-Za-z0-9]{32})", content)
    if user_token_service:
        params['USER_TOKEN_SERVICE'] = user_token_service.group(1)

    # tempKey
    temp_key = re.search(r'tempKey[=]([A-F0-9]{32})', content, re.IGNORECASE)
    if temp_key:
        params['TEMP_KEY'] = temp_key.group(1)

    # STBID
    stb_id = re.search(r'STBID=([A-F0-9]{32})', content, re.IGNORECASE)
    if stb_id:
        params['STB_ID'] = stb_id.group(1)

    # MAC
    mac = re.search(r'mac=([A-F0-9]{2}(?:%3A|:)[A-F0-9]{2}(?:%3A|:)[A-F0-9]{2}(?:%3A|:)[A-F0-9]{2}(?:%3A|:)[A-F0-9]{2}(?:%3A|:)[A-F0-9]{2})', content, re.IGNORECASE)
    if mac:
        params['MAC'] = mac.group(1).replace('%3A', ':').upper()

    # areaId
    area_id = re.search(r'areaId[=](\d+)', content)
    if area_id:
        params['AREA_ID'] = area_id.group(1)

    # STBVersion
    stb_version = re.search(r'STBVersion=([A-Za-z0-9\-]+)', content)
    if stb_version:
        params['STB_VERSION'] = stb_version.group(1)

    # stbid（短格式）
    stb_id_short = re.search(r"stbid[='](\d{6})", content)
    if stb_id_short:
        params['STB_ID_SHORT'] = stb_id_short.group(1)

    return params

def generate_env(params):
    """生成 .env 文件内容"""
    lines = [
        "# IPTV服务器",
        f"IPTV_SERVER={params.get('IPTV_SERVER', 'http://your-server:port')}",
        "RTSP_SERVER_IP=REDACTED_RTSP_SERVER",
        "",
        "# 直播/回看端口",
        "LIVE_PORT=5140",
        "REPLAY_PORT=554",
        "WEB_PORT=2000",
        "",
        "# 内网/外网服务器",
        "LAN_SERVER=192.168.1.100",
        "BOFANG_SERVER=192.168.1.101",
        "NET_SERVER=your-domain.com",
        "",
        "# 文件路径",
        "WEB_PATH=/app/output/lighttpd/root/",
        "LOGO_PATH=/app/output/lighttpd/root/logo/",
        "",
        "# 鉴权参数（从抓包提取）",
        f"USER_ID={params.get('USER_ID', '')}",
        f"AUTHENTICATOR={params.get('AUTHENTICATOR', '')}",
        f"USER_TOKEN={params.get('USER_TOKEN', '')}",
        f"STB_ID={params.get('STB_ID', '')}",
        f"MAC={params.get('MAC', '')}",
        f"STB_VERSION={params.get('STB_VERSION', '')}",
        f"AREA_ID={params.get('AREA_ID', '')}",
        "",
        "# 服务入口参数",
        f"USER_TOKEN_SERVICE={params.get('USER_TOKEN_SERVICE', '')}",
        f"TEMP_KEY={params.get('TEMP_KEY', '')}",
        f"STB_ID_SHORT={params.get('STB_ID_SHORT', '')}",
        "",
        "# RTSP代理",
        "RTSP_PROXY_TARGET=REDACTED_PROXY_TARGET",
        "RTSP_PROXY_BAD_TARGET=REDACTED_BAD_TARGET",
        "RTSP_PROXY_PORT=554",
    ]
    return '\n'.join(lines)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python3 extract_auth.py <抓包文件>")
        print("示例: python3 extract_auth.py 123.txt")
        sys.exit(1)

    filepath = sys.argv[1]
    print(f"正在解析: {filepath}\n")

    params = extract_auth_params(filepath)

    if not params:
        print("❌ 未找到任何鉴权参数")
        sys.exit(1)

    print("=" * 50)
    print("提取到的鉴权参数：")
    print("=" * 50)
    for key, value in params.items():
        display = value if len(value) <= 40 else value[:20] + "..." + value[-10:]
        print(f"  {key:25s} = {display}")

    print("\n" + "=" * 50)
    print("生成的 .env 内容：")
    print("=" * 50)
    env_content = generate_env(params)
    print(env_content)

    # 保存到文件
    output_file = filepath.rsplit('.', 1)[0] + '.env'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(env_content)
    print(f"\n✅ 已保存到: {output_file}")
