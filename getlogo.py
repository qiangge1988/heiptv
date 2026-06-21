import re
import time
import datetime
import requests
import os
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('getlogo.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def log_info(message):
    logging.info(message)

def log_error(message):
    logging.error(message)

# 从环境变量读取配置
IPTVhost = os.getenv('IPTV_SERVER', 'http://REDACTED_IPTV_SERVER')
logo_path = os.getenv('LOGO_PATH', r'/app/output/lighttpd/root/logo/')

# 鉴权参数
USER_ID = os.getenv('USER_ID', '')
AUTHENTICATOR = os.getenv('AUTHENTICATOR', '')
USER_TOKEN = os.getenv('USER_TOKEN', '')
STB_ID = os.getenv('STB_ID', '')
MAC = os.getenv('MAC', '')
STB_VERSION = os.getenv('STB_VERSION', '')
AREA_ID = os.getenv('AREA_ID', '')
USER_TOKEN_SERVICE = os.getenv('USER_TOKEN_SERVICE', '')
TEMP_KEY = os.getenv('TEMP_KEY', '')
STB_ID_SHORT = os.getenv('STB_ID_SHORT', '')

def create_session_with_retry(retries=3, backoff_factor=0.3):
    """创建带重试机制的session"""
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# 确保logo目录存在
def ensure_logo_directory():
    if not os.path.exists(logo_path):
        os.makedirs(logo_path)
        log_info(f"创建logo目录: {logo_path}")

# 鉴权验证
def getValidAuthenticationHWCU():
    session = create_session_with_retry()

    try:
        # 第一步：GET请求获取初始页面
        get_url = f'{IPTVhost}/EPG/jsp/AuthenticationURL?UserID={USER_ID}&Action=Login'
        session.get(get_url, timeout=10)

        # 第二步：POST请求进行基础认证
        auth_data = {
            'UserID': USER_ID,
            'VIP': ''
        }
        session.post(f'{IPTVhost}/EPG/jsp/authLoginHWCU.jsp', data=auth_data, timeout=10)

        # 第三步：POST请求进行详细鉴权验证
        form_data = {
            'UserID': USER_ID,
            'Lang': '',
            'SupportHD': '1',
            'NetUserID': f'{USER_ID}@iptv',
            'Authenticator': AUTHENTICATOR,
            'STBType': 'HG680-L',
            'STBVersion': STB_VERSION,
            'conntype': 'dhcp',
            'STBID': STB_ID,
            'templateName': 'defaultnew1_v6',
            'areaId': AREA_ID,
            'userToken': USER_TOKEN,
            'userGroupId': '',
            'productPackageId': '',
            'mac': MAC,
            'SoftwareVersion': STB_VERSION,
            'VIP': ''
        }
        response = session.post(f'{IPTVhost}/EPG/jsp/ValidAuthenticationHWCU.jsp', data=form_data, timeout=10)
        log_info("鉴权验证成功")

    except requests.exceptions.Timeout:
        log_error("鉴权请求超时")
        raise
    except requests.exceptions.RequestException as e:
        log_error(f"鉴权请求失败: {e}")
        raise

    #返回经过验证的会话
    return session

#根据序号确定是否重新验证，如需修改间隔，则修改Frequency参数，例如每100次重新鉴权
def ReValidAuthentication(index):
    Frequency = 60
    return (index - 1) % Frequency == 0

def download_logo(session, logo_url, logo_filename, max_retries=3):
    """下载logo文件，支持重试机制"""
    for attempt in range(max_retries):
        try:
            logoresponse = session.get(logo_url, timeout=10)
            if logoresponse.status_code == 200:
                # 将图片内容写入本地文件
                with open(logo_filename, "wb") as file:
                    file.write(logoresponse.content)
                return True
            else:
                log_error(f"下载logo失败，HTTP状态码: {logoresponse.status_code} (尝试 {attempt + 1}/{max_retries})")
        except Exception as e:
            log_error(f"下载logo时出错: {e} (尝试 {attempt + 1}/{max_retries})")

        if attempt < max_retries - 1:
            time.sleep(2)  # 重试前等待2秒

    return False

def extract_channel_ids_from_js(html_content):
    """从JavaScript代码中提取频道ID"""
    channel_ids = []

    # 使用正则表达式匹配所有的频道设置语句
    channel_pattern = r"Authentication\.CUSetConfig\('Channel','(.*?)'\)"
    channel_matches = re.findall(channel_pattern, html_content)

    log_info(f"找到频道配置语句数量: {len(channel_matches)}")

    for channel_config in channel_matches:
        try:
            user_channel_id = re.search(r'UserChannelID="(.*?)"', channel_config)
            if user_channel_id:
                channel_ids.append(user_channel_id.group(1))
        except Exception as e:
            log_error(f"解析频道配置时出错: {e}")
            continue

    return channel_ids

def get_channel_list(session):
    """获取频道列表"""
    # 获取频道列表的表单数据
    channel_form_data = {
        'conntype': 'dhcp',
        'UserToken': USER_TOKEN_SERVICE,
        'tempKey': TEMP_KEY,
        'stbid': STB_ID_SHORT,
        'SupportHD': '1',
        'UserID': USER_ID,
        'Lang': '1'
    }

    try:
        response = session.post(f'{IPTVhost}/EPG/jsp/getchannellistHWCU.jsp', data=channel_form_data, timeout=15)
        log_info(f"获取频道列表响应状态: {response.status_code}")

        # 使用新的解析方法提取频道ID
        channel_ids = extract_channel_ids_from_js(response.text)

        if not channel_ids:
            # 如果新方法没有找到，回退到旧方法
            log_info("使用新方法未找到频道ID，尝试旧方法")
            channel_ids = re.findall(r'UserChannelID="(.*?)"', response.text)

        # 去重
        channel_ids = list(set(channel_ids))
        log_info(f"找到去重后的频道数量: {len(channel_ids)}")

        # 按数字排序
        try:
            channel_ids = sorted(channel_ids, key=lambda x: int(x))
        except ValueError:
            # 如果不能转换为数字，按字符串排序
            channel_ids.sort()

        return channel_ids

    except Exception as e:
        log_error(f"获取频道列表失败: {e}")
        return []

def get_logo_url(session, userchannelID, today_zero):
    """获取指定频道的logo URL"""
    try:
        #构造用于查询频道logo的文件头
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest"
        }
        #构造提交的表单数据，抓包获得
        data = {
            "queryChannel": {
                "channelNOs": [userchannelID],
                "count": 1
            },
            "queryPlaybillContext": {
                "date": today_zero,
                "type": 1,
                "preNumber": 1,
                "nextNumber": 1
            }
        }
        response = session.post(f'{IPTVhost}/VSP/V3/QueryPlaybillContext', headers=headers, json=data, timeout=15)

        #通过正则表达式筛选出logo地址
        logo_str = re.search(r'(http://[^"^\s]*\.(png|jpg|jpeg))', response.text, re.IGNORECASE)
        if logo_str:
            logo_url = logo_str.group(1)
            log_info(f"频道 {userchannelID} 获取到的图片链接：{logo_url}")
            return logo_url
        else:
            log_info(f"频道 {userchannelID} 未找到logo链接")
            return None

    except Exception as e:
        log_error(f"获取频道 {userchannelID} 的logo URL时出错: {e}")
        return None

# 线程安全的计数器
class Counter:
    def __init__(self):
        self._value = 0
        self._lock = threading.Lock()

    def increment(self):
        with self._lock:
            self._value += 1
            return self._value

    @property
    def value(self):
        return self._value

def download_single_logo(args):
    """下载单个频道的logo（供线程池调用）"""
    userchannelID, session, today_zero = args

    # 检查是否已存在该logo文件
    logo_filename = os.path.join(logo_path, f"{userchannelID}.png")
    if os.path.exists(logo_filename):
        file_size = os.path.getsize(logo_filename)
        if file_size > 0:
            return ('skip', userchannelID, f"Logo已存在({file_size}字节)")
        else:
            os.remove(logo_filename)

    try:
        # 获取logo URL
        logo_url = get_logo_url(session, userchannelID, today_zero)

        if logo_url:
            # 下载logo
            if download_logo(session, logo_url, logo_filename):
                if os.path.exists(logo_filename) and os.path.getsize(logo_filename) > 0:
                    return ('success', userchannelID, "下载成功")
                else:
                    if os.path.exists(logo_filename):
                        os.remove(logo_filename)
                    return ('fail', userchannelID, "文件无效")
            else:
                return ('fail', userchannelID, "下载失败")
        else:
            return ('fail', userchannelID, "无logo链接")

    except Exception as e:
        return ('fail', userchannelID, str(e))

#获取logo台标
def getlogo():
    """获取所有频道的logo（并发版本）"""
    # 确保logo目录存在
    ensure_logo_directory()

    today_zero = int(round(time.mktime(datetime.date.today().timetuple()) * 1000)) #获取今日0点时间戳毫秒
    session = getValidAuthenticationHWCU()

    # 获取频道列表
    userchannel_IDs = get_channel_list(session)
    if not userchannel_IDs:
        log_error("无法获取频道列表，程序退出")
        return

    log_info(f"开始下载 {len(userchannel_IDs)} 个频道的logo")

    success_count = 0
    skip_count = 0
    fail_count = 0

    # 准备任务参数
    tasks = [(channel_id, session, today_zero) for channel_id in userchannel_IDs]

    # 使用线程池并发下载
    max_workers = 5
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(download_single_logo, task): task[0] for task in tasks}

        for future in as_completed(futures):
            try:
                status, channel_id, message = future.result()
                if status == 'success':
                    success_count += 1
                    log_info(f"频道 {channel_id}: {message}")
                elif status == 'skip':
                    skip_count += 1
                else:
                    fail_count += 1
                    log_error(f"频道 {channel_id}: {message}")
            except Exception as e:
                fail_count += 1
                log_error(f"处理异常: {e}")

            # 进度日志
            total_done = success_count + skip_count + fail_count
            if total_done % 10 == 0:
                log_info(f"处理进度: {total_done}/{len(userchannel_IDs)} - 成功: {success_count}, 跳过: {skip_count}, 失败: {fail_count}")

    log_info(f"Logo下载完成！统计: 成功 {success_count}, 跳过 {skip_count}, 失败 {fail_count}, 总计 {len(userchannel_IDs)}")

    # 显示前10个频道ID示例
    if userchannel_IDs:
        log_info(f"前10个频道ID示例: {userchannel_IDs[:10]}")

if __name__ == '__main__':
    try:
        log_info("开始执行Logo获取程序")
        getlogo()
        log_info("Logo获取程序执行完成")
    except Exception as e:
        log_error(f"程序执行出错: {e}")
        import traceback
        traceback.print_exc()
