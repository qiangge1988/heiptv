import re
import time
import datetime
import requests
import gzip
import os
import shutil
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# 配置日志
def setup_logging():
    """配置日志系统"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('iptv.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# 配置参数类
class Config:
    """应用配置参数类"""
    # 服务器配置
    IPTVServer = os.getenv('IPTV_SERVER', 'http://REDACTED_IPTV_SERVER')
    RTSPServerIP = os.getenv('RTSP_SERVER_IP', 'REDACTED_RTSP_SERVER')
    LivePort = os.getenv('LIVE_PORT', '5140')
    ReplayPort = os.getenv('REPLAY_PORT', '554')
    WebPort = os.getenv('WEB_PORT', '2000')
    LanServer = os.getenv('LAN_SERVER', 'REDACTED_LAN_SERVER')
    BofangServer = os.getenv('BOFANG_SERVER', 'REDACTED_BOFANG_SERVER')
    NetServer = os.getenv('NET_SERVER', 'REDACTED_NET_SERVER')

    # 文件路径配置
    web_path = os.getenv('WEB_PATH', r'/app/output/lighttps/root/')
    playlist = 'PL.xml'
    playlistgz = 'PL.xml.gz'

    # 输出文件配置
    LanReplay_name = 'LanReplay.m3u'
    LanLive_name = 'LanLive.m3u'
    iptv_name = 'iptv.m3u'
    NetLive_name = 'NetLive.m3u'
    NetReplay_name = 'NetReplay.m3u'

    # 鉴权参数
    USER_ID = os.getenv('USER_ID', 'REDACTED_USER_ID')
    AUTHENTICATOR = os.getenv('AUTHENTICATOR', '')
    USER_TOKEN = os.getenv('USER_TOKEN', '')
    STB_ID = os.getenv('STB_ID', '')
    MAC = os.getenv('MAC', '')
    STB_VERSION = os.getenv('STB_VERSION', 'REDACTED_STB_VERSION')
    AREA_ID = os.getenv('AREA_ID', 'REDACTED_AREA_ID')

    # 服务入口参数
    USER_TOKEN_SERVICE = os.getenv('USER_TOKEN_SERVICE', '')
    TEMP_KEY = os.getenv('TEMP_KEY', '')
    STB_ID_SHORT = os.getenv('STB_ID_SHORT', 'REDACTED_STB_ID_SHORT')

class IPTVService:
    """IPTV服务类，封装核心业务逻辑"""

    def __init__(self, config):
        self.config = config
        self.session = None

    def create_session_with_retry(self, retries=3, backoff_factor=0.3):
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

    def check_disk_space(self, min_space_gb=0.1):
        """检查磁盘空间是否充足"""
        try:
            stat = shutil.disk_usage(self.config.web_path)
            free_space_gb = stat.free / (1024**3)
            logging.info(f"磁盘剩余空间: {free_space_gb:.2f} GB")
            return free_space_gb > min_space_gb
        except Exception as e:
            logging.error(f"检查磁盘空间失败: {e}")
            return True  # 检查失败时继续执行

    def cleanup_temp_files(self):
        """清理临时M3U文件"""
        try:
            temp_files = [
                os.path.join(self.config.web_path, self.config.LanReplay_name),
                os.path.join(self.config.web_path, self.config.LanLive_name),
                os.path.join(self.config.web_path, self.config.iptv_name),
                os.path.join(self.config.web_path, self.config.NetLive_name),
                os.path.join(self.config.web_path, self.config.NetReplay_name)
            ]

            for file_path in temp_files:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logging.info(f"已清理临时文件: {file_path}")

        except Exception as e:
            logging.error(f"清理临时文件失败: {e}")

    def authenticate(self):
        """进行鉴权并返回有效的会话"""
        try:
            session = self.create_session_with_retry()

            # 第一步：GET请求获取初始页面
            get_url = f'{self.config.IPTVServer}/EPG/jsp/AuthenticationURL?UserID={self.config.USER_ID}&Action=Login'
            session.get(get_url, timeout=10)

            # 第二步：POST请求进行基础认证
            auth_data = {
                'UserID': self.config.USER_ID,
                'VIP': ''
            }
            session.post(f'{self.config.IPTVServer}/EPG/jsp/authLoginHWCU.jsp', data=auth_data, timeout=10)

            # 第三步：POST请求进行详细鉴权验证
            form_data = {
                'UserID': self.config.USER_ID,
                'Lang': '',
                'SupportHD': '1',
                'NetUserID': f'{self.config.USER_ID}@iptv',
                'Authenticator': self.config.AUTHENTICATOR,
                'STBType': 'HG680-L',
                'STBVersion': self.config.STB_VERSION,
                'conntype': 'dhcp',
                'STBID': self.config.STB_ID,
                'templateName': 'defaultnew1_v6',
                'areaId': self.config.AREA_ID,
                'userToken': self.config.USER_TOKEN,
                'userGroupId': '',
                'productPackageId': '',
                'mac': self.config.MAC,
                'SoftwareVersion': self.config.STB_VERSION,
                'VIP': ''
            }
            session.post(f'{self.config.IPTVServer}/EPG/jsp/ValidAuthenticationHWCU.jsp', data=form_data, timeout=10)
            logging.info("鉴权验证成功")

            self.session = session
            return session

        except requests.exceptions.Timeout:
            logging.error("鉴权请求超时")
            raise
        except requests.exceptions.RequestException as e:
            logging.error(f"鉴权请求失败: {e}")
            raise

    def get_channel_list(self):
        """获取并解析频道列表"""
        try:
            if not self.session:
                self.authenticate()

            # 获取频道列表
            channel_form_data = {
                'conntype': 'dhcp',
                'UserToken': self.config.USER_TOKEN_SERVICE,
                'tempKey': self.config.TEMP_KEY,
                'stbid': self.config.STB_ID_SHORT,
                'SupportHD': '1',
                'UserID': self.config.USER_ID,
                'Lang': '1'
            }

            response = self.session.post(
                f'{self.config.IPTVServer}/EPG/jsp/getchannellistHWCU.jsp',
                data=channel_form_data,
                timeout=15
            )
            logging.info(f"频道列表响应状态: {response.status_code}")

            return self.parse_channel_data(response.text)

        except Exception as e:
            logging.error(f"获取频道列表失败: {e}")
            return []

    def parse_channel_data(self, html_content):
        """解析频道数据"""
        channeldata = []
        channel_pattern = r"Authentication\.CUSetConfig\('Channel','(.*?)'\)"
        channel_matches = re.findall(channel_pattern, html_content)

        logging.info(f"找到频道配置语句数量: {len(channel_matches)}")

        index = 1
        for channel_config in channel_matches:
            try:
                # 解析频道配置字段
                channel_id = re.search(r'ChannelID="(.*?)"', channel_config)
                channel_name = re.search(r'ChannelName="(.*?)"', channel_config)
                user_channel_id = re.search(r'UserChannelID="(.*?)"', channel_config)
                channel_url = re.search(r'ChannelURL="(.*?)"', channel_config)
                timeshift_url = re.search(r'TimeShiftURL="(.*?)"', channel_config)

                if not all([channel_id, channel_name, user_channel_id, channel_url, timeshift_url]):
                    logging.debug(f"频道配置不完整: {channel_config[:100]}...")
                    continue

                # 提取IGMP地址
                igmp_match = re.search(r'igmp://([^\s"]+)', channel_url.group(1))
                igmp_url = igmp_match.group(1) if igmp_match else ""

                # 提取RTSP地址
                rtsp_match = re.search(r'(rtsp://[^\s"]+\.smil\?[^\s"]+)', timeshift_url.group(1))
                if not rtsp_match:
                    rtsp_match = re.search(r'(rtsp://[^\s"]+\.smil)', timeshift_url.group(1))

                rtsp_url = rtsp_match.group(1) if rtsp_match else ""

                if igmp_url and rtsp_url:
                    # 替换RTSP地址中的IP
                    rtsp_url_replaced = self.replace_rtsp_ip(rtsp_url)

                    # 确保RTSP地址格式正确
                    if not rtsp_url_replaced.startswith('rtsp://'):
                        rtsp_url_replaced = f'rtsp://{rtsp_url_replaced}'

                    group_title = self.get_group_title(
                        user_channel_id.group(1),
                        channel_name.group(1)
                    )

                    channeldata.append((
                        index,
                        channel_id.group(1),
                        channel_name.group(1),
                        user_channel_id.group(1),
                        group_title,
                        rtsp_url_replaced,
                        igmp_url
                    ))
                    index += 1
                    logging.debug(f"成功解析频道: {channel_name.group(1)}")
                else:
                    logging.debug(f"跳过频道 {channel_name.group(1)}: 未找到有效的播放地址")

            except Exception as e:
                logging.error(f"解析频道配置时出错: {e}")
                continue

        return channeldata

    def replace_rtsp_ip(self, rtsp_url):
        """替换RTSP地址中的IP"""
        if not rtsp_url:
            return rtsp_url

        try:
            if rtsp_url.startswith('rtsp://'):
                parts = rtsp_url.split('://', 1)
                protocol = parts[0]
                rest = parts[1]

                # 查找IP地址结束位置
                ip_end = rest.find('/')
                if ip_end == -1:
                    ip_end = rest.find('?')
                if ip_end == -1:
                    ip_end = len(rest)

                # 替换为新的IP
                return f"{protocol}://{self.config.RTSPServerIP}{rest[ip_end:]}"
            else:
                # 非标准格式处理
                ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
                match = re.search(ip_pattern, rtsp_url)
                if match:
                    return rtsp_url.replace(match.group(), self.config.RTSPServerIP)

            return rtsp_url

        except Exception as e:
            logging.error(f"替换RTSP IP地址失败: {e}, URL: {rtsp_url[:100]}...")
            return rtsp_url

    def get_group_title(self, userchannelID, channelname):
        """根据台号和名称确定频道分组"""
        try:
            channel_no = int(userchannelID)

            # 基础分组规则
            if channel_no < 20:
                group_title = '央视台'
            elif channel_no < 30:
                group_title = '河北省台'
            elif channel_no < 62:
                group_title = '全国卫视'
            elif channel_no < 112:
                group_title = '购物台'
            elif channel_no < 113:
                group_title = '数字节目'
            elif channel_no < 119:
                group_title = '购物台'
            elif channel_no < 121:
                group_title = '其他'
            elif channel_no < 183:
                group_title = '河北市级台'
            elif channel_no < 245:
                group_title = '全国卫视'
            elif channel_no < 265:
                group_title = '超高清4K'
            elif channel_no < 520:
                group_title = '数字节目'
            elif channel_no < 558:
                group_title = '央视台'
            elif channel_no < 628:
                group_title = '慢直播'
            elif channel_no < 685:
                group_title = '香港台'
            elif channel_no < 900:
                group_title = '县级台'
            else:
                group_title = '其他'

            # 根据频道名称调整分组
            if ('4K' in channelname or '超高清' in channelname) and channel_no < 800:
                group_title = '超高清4K'

            return group_title
        except ValueError:
            return '其他'

    def get_playlist_data(self, channeldata):
        """获取所有频道的节目单数据"""
        if not channeldata:
            logging.error("频道数据为空，无法获取节目单")
            return []

        # 使用已有的会话，如果没有则重新鉴权
        if not self.session:
            session = self.authenticate()
        else:
            session = self.session

        # 计算起始时间（六天前的凌晨）
        limittime = int(round(time.mktime(
            datetime.date.today().timetuple()) * 1000)) - 518400000

        logging.info(f"开始获取所有{len(channeldata)}个频道的节目单")

        # 使用线程池处理
        max_workers = min(5, len(channeldata))
        playlistdata = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_channel = {
                executor.submit(
                    self.get_single_channel_playlist,
                    session, channelID, channelname, limittime
                ): (index, channelID, channelname, userchannelID)
                for index, (_, channelID, channelname, userchannelID, _, _, _)
                in enumerate(channeldata, 1)
            }

            for future in as_completed(future_to_channel):
                index, channelID, channelname, userchannelID = future_to_channel[future]
                try:
                    result = future.result()
                    playlistdata.append((result[0], userchannelID, result[1], result[2]))

                    if index % 10 == 0:
                        logging.info(f"已处理 {index}/{len(channeldata)} 个频道的节目单")
                except Exception as e:
                    logging.error(f"获取频道 {channelname} 节目单失败: {e}")

        return playlistdata

    def get_single_channel_playlist(self, session, channelID, channelname, limittime):
        """获取单个频道的节目单数据"""
        Tendaysdata = []
        headers = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        starttime = limittime

        # 获取8天的节目单
        for _ in range(8):
            data = {
                "queryChannel": {"channelIDs": [channelID]},
                "queryPlaybill": {
                    "type": "0",
                    "startTime": starttime,
                    "endTime": starttime + 86400000,
                    "count": "100",
                    "offset": "0",
                    "isFillProgram": "0",
                    "mustIncluded": "0"
                },
                "needChannel": "0"
            }

            try:
                response = session.post(
                    f'{self.config.IPTVServer}/VSP/V3/QueryPlaybillList',
                    headers=headers,
                    json=data,
                    timeout=15
                )
                starttime += 86400000
                dayplaydata = self.format_day_play_data(response.text)
                Tendaysdata.append(dayplaydata)
            except Exception as e:
                logging.error(f"获取频道 {channelname} 节目单失败: {e}")
                Tendaysdata.append([])

        return (channelID, channelname, Tendaysdata)

    def format_day_play_data(self, playlisttext):
        """格式化单日节目单数据"""
        dayplaydata = []
        clean_text = re.findall(r'(startTime":".*?endTime":".*?)"', playlisttext)
        trantab = str.maketrans({'<': '《', '>': '》'})  # 替换特殊符号

        for playlist_text in clean_text:
            try:
                channelID = re.search(r'channelID":"(.*?)"', playlist_text)
                starttime_str = re.search(r'startTime":"(.*?)"', playlist_text)
                name_str = re.search(r'name":"(.*?)"', playlist_text)
                endtime_str = re.search(r'endTime":"(.*)', playlist_text)

                if not all([channelID, starttime_str, name_str, endtime_str]):
                    continue

                # 处理节目名称
                playname = name_str.group(1).translate(trantab)

                # 转换时间格式
                startTime = time.strftime(
                    "%Y%m%d%H%M%S +0800",
                    time.localtime(int(starttime_str.group(1))/1000)
                )
                endTime = time.strftime(
                    "%Y%m%d%H%M%S +0800",
                    time.localtime(int(endtime_str.group(1))/1000)
                )

                dayplaydata.append((channelID.group(1), startTime, playname, endTime))
            except Exception as e:
                logging.error(f"格式化节目单数据出错: {e}")
                continue

        return dayplaydata

    def generate_all_files(self, channeldata, playlistdata):
        """生成所有输出文件"""
        # 生成M3U文件
        self.generate_LanReplaym3u(channeldata)
        self.generate_LanLivem3u(channeldata)
        self.generate_iptvm3u(channeldata)
        self.generate_NetLivem3u(channeldata)
        self.generate_NetReplaym3u(channeldata)

        # 生成节目单文件
        self.generate_playlist(playlistdata)
        self.generate_playlistgz()

    # M3U文件生成方法
    def generate_LanLivem3u(self, channeldata):
        """生成内网直播M3U文件"""
        file_path = os.path.join(self.config.web_path, self.config.LanLive_name)
        epg_url = f'http://{self.config.LanServer}:{self.config.WebPort}/{self.config.playlistgz}'
        self._write_m3u_file(
            file_path,
            self._generate_m3u_content(channeldata, epg_url, is_replay=False),
            "内网直播"
        )

    def generate_LanReplaym3u(self, channeldata):
        """生成内网回看M3U文件"""
        file_path = os.path.join(self.config.web_path, self.config.LanReplay_name)
        epg_url = f'http://{self.config.LanServer}:{self.config.WebPort}/{self.config.playlistgz}'
        self._write_m3u_file(
            file_path,
            self._generate_m3u_content(channeldata, epg_url, is_replay=True),
            "内网回看"
        )

    def generate_iptvm3u(self, channeldata):
        """生成IPTV M3U文件"""
        file_path = os.path.join(self.config.web_path, self.config.iptv_name)
        epg_url = f'http://{self.config.LanServer}:{self.config.WebPort}/{self.config.playlistgz}'

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f'#EXTM3U name="河北联通IPTV" x-tvg-url="{epg_url}"\n')
                for _, _, channelname, userchannelID, group_title, _, igmpurl in channeldata:
                    if igmpurl:
                        lanliveurl = f"rtp://{igmpurl}"
                        channellogo = f"http://{self.config.LanServer}:{self.config.WebPort}/logo/{userchannelID}.png"
                        f.write(f'#EXTINF:-1 tvg-id="{userchannelID}" tvg-name="{channelname}" tvg-logo="{channellogo}" group-title="{group_title}", {channelname}\n')
                        f.write(f'{lanliveurl}\n')
            logging.info(f'M3U文件已生成：{file_path}')
        except Exception as e:
            logging.error(f"生成IPTV M3U文件失败: {e}")

    def generate_NetLivem3u(self, channeldata):
        """生成外网直播M3U文件"""
        file_path = os.path.join(self.config.web_path, self.config.NetLive_name)
        epg_url = f'http://{self.config.NetServer}:{self.config.WebPort}/{self.config.playlistgz}'

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f'#EXTM3U name="河北联通IPTV" x-tvg-url="{epg_url}"\n')
                for _, _, channelname, userchannelID, group_title, _, igmpurl in channeldata:
                    if igmpurl:
                        netliveurl = f"http://{self.config.NetServer}:{self.config.LivePort}/udp/{igmpurl}"
                        channellogo = f"http://{self.config.NetServer}:{self.config.WebPort}/logo/{userchannelID}.png"
                        f.write(f'#EXTINF:-1 tvg-id="{userchannelID}" tvg-name="{channelname}" tvg-logo="{channellogo}" group-title="{group_title}", {channelname}\n')
                        f.write(f'{netliveurl}\n')
            logging.info(f'M3U文件已生成：{file_path}')
        except Exception as e:
            logging.error(f"生成外网直播M3U文件失败: {e}")

    def generate_NetReplaym3u(self, channeldata):
        """生成外网回看M3U文件"""
        file_path = os.path.join(self.config.web_path, self.config.NetReplay_name)
        epg_url = f'http://{self.config.NetServer}:{self.config.WebPort}/{self.config.playlistgz}'

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f'#EXTM3U name="河北联通IPTV" x-tvg-url="{epg_url}" catchup="append" catchup-source="?playseek=${{(b)yyyyMMddHHmmss}}-${{(e)yyyyMMddHHmmss}}"\n')
                for _, _, channelname, userchannelID, group_title, rtspurl, _ in channeldata:
                    channellogo = f"http://{self.config.NetServer}:{self.config.WebPort}/logo/{userchannelID}.png"

                    # 确保RTSP地址格式正确
                    if not rtspurl.startswith('rtsp://'):
                        rtspurl = 'rtsp://' + rtspurl
                    if 'REDACTED_RTSP_SERVER' in rtspurl:
                        rtspurl = rtspurl.replace('REDACTED_RTSP_SERVER', self.config.RTSPServerIP)

                    f.write(f'#EXTINF:-1 tvg-id="{userchannelID}" tvg-name="{channelname}" tvg-logo="{channellogo}" group-title="{group_title}", {channelname}\n')
                    f.write(f'{rtspurl}\n')
            logging.info(f'M3U文件已生成：{file_path}')
        except Exception as e:
            logging.error(f"生成外网回看M3U文件失败: {e}")

    def generate_playlist(self, playlistdata):
        """生成EPG节目单XML文件"""
        if not self.check_disk_space():
            logging.error("错误：磁盘空间不足，跳过生成节目单")
            return

        file_path = os.path.join(self.config.web_path, self.config.playlist)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
                f.write('<tv info-name="河北联通" info-url="">\n')

                # 写入频道信息
                channels_written = set()
                for _, userchannelID, channelname, _ in playlistdata:
                    if userchannelID not in channels_written:
                        f.write(f'<channel id="{userchannelID}">\n<display-name lang="zh">{channelname}</display-name>\n</channel>\n')
                        channels_written.add(userchannelID)

                # 写入节目单信息
                program_count = 0
                for _, userchannelID, _, Tendaysdata in playlistdata:
                    for dayplaydata in Tendaysdata:
                        for _, startTime, playname, endTime in dayplaydata:
                            f.write(f'<programme channel="{userchannelID}" start="{startTime}" stop="{endTime}">\n<title lang="zh">{playname}</title>\n</programme>\n')
                            program_count += 1

                            if program_count % 1000 == 0:
                                f.flush()
                                logging.info(f"已写入 {program_count} 个节目信息")

                f.write('</tv>')
            logging.info(f'节目单XML文件已生成：{file_path}，共 {program_count} 个节目')

        except OSError as e:
            if "No space left on device" in str(e):
                logging.error("错误：磁盘空间不足，无法生成节目单文件")
                self.cleanup_temp_files()
            else:
                raise e

    def generate_playlistgz(self):
        """生成压缩的节目单文件"""
        src_path = os.path.join(self.config.web_path, self.config.playlist)
        dest_path = os.path.join(self.config.web_path, self.config.playlistgz)

        if not os.path.exists(src_path):
            logging.error("节目单文件不存在，跳过压缩")
            return

        try:
            with open(src_path, 'r', encoding='utf-8') as f_in:
                data = f_in.read()

            with gzip.open(dest_path, "wb") as f_out:
                f_out.write(data.encode('utf-8'))

            logging.info(f'压缩节目单文件已生成：{dest_path}')

        except Exception as e:
            logging.error(f"压缩文件失败: {e}")

    # 内部辅助方法
    def _write_m3u_file(self, filepath, content_generator, description):
        """写入M3U文件的通用方法"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for line in content_generator:
                    f.write(line)
            logging.info(f'{description} M3U文件已生成：{filepath}')
        except Exception as e:
            logging.error(f"生成{description} M3U文件失败: {e}")

    def _generate_m3u_content(self, channeldata, epg_url, is_replay=False):
        """生成M3U文件内容的生成器"""
        if is_replay:
            yield f'#EXTM3U name="河北联通IPTV" x-tvg-url="{epg_url}" catchup="append" catchup-source="?playseek=${{(b)yyyyMMddHHmmss}}-${{(e)yyyyMMddHHmmss}}"\n'
        else:
            yield f'#EXTM3U name="河北联通IPTV" x-tvg-url="{epg_url}"\n'

        for _, _, channelname, userchannelID, group_title, rtspurl, igmpurl in channeldata:
            channellogo = f"http://{self.config.LanServer}:{self.config.WebPort}/logo/{userchannelID}.png"
            if igmpurl:
                if is_replay:
                    # 处理回看地址
                    if 'REDACTED_RTSP_SERVER' in rtspurl:
                        rtspurl = rtspurl.replace('REDACTED_RTSP_SERVER', self.config.RTSPServerIP)
                    yield f'#EXTINF:-1 tvg-id="{userchannelID}" tvg-name="{channelname}" tvg-logo="{channellogo}" group-title="{group_title}", {channelname}\n'
                    yield f'{rtspurl}\n'
                else:
                    # 处理直播地址
                    lanliveurl = f"http://{self.config.BofangServer}:{self.config.LivePort}/udp/{igmpurl}"
                    yield f'#EXTINF:-1 tvg-id="{userchannelID}" tvg-name="{channelname}" tvg-logo="{channellogo}" group-title="{group_title}", {channelname}\n'
                    yield f'{lanliveurl}\n'

def main():
    """程序主入口"""
    try:
        setup_logging()
        logging.info("开始执行IPTV数据获取程序")

        config = Config()
        iptv_service = IPTVService(config)

        # 清理临时文件
        iptv_service.cleanup_temp_files()

        # 检查磁盘空间
        if not iptv_service.check_disk_space():
            logging.error("警告：磁盘空间不足，程序可能无法完成")

        # 获取频道数据
        channeldata = iptv_service.get_channel_list()
        if not channeldata:
            logging.error("错误：未获取到任何频道数据")
            return

        # 显示部分频道信息
        logging.info("前3个频道信息示例:")
        for i in range(min(3, len(channeldata))):
            _, _, channelname, _, _, rtspurl, _ = channeldata[i]
            logging.info(f"频道{i+1}: {channelname}")
            logging.info(f"  RTSP地址: {rtspurl[:200]}")

        # 获取节目单数据
        playlistdata = iptv_service.get_playlist_data(channeldata)

        # 生成所有文件
        iptv_service.generate_all_files(channeldata, playlistdata)

        # 输出结果信息
        logging.info("所有文件生成完成！")
        logging.info(f"生成的节目单文件:")
        logging.info(f"  - 原始XML文件: {os.path.join(config.web_path, config.playlist)}")
        logging.info(f"  - 压缩文件: {os.path.join(config.web_path, config.playlistgz)}")
        logging.info(f"生成的M3U文件:")
        logging.info(f"  - 内网回看: {os.path.join(config.web_path, config.LanReplay_name)}")
        logging.info(f"  - 内网直播: {os.path.join(config.web_path, config.LanLive_name)}")
        logging.info(f"  - 外网直播: {os.path.join(config.web_path, config.NetLive_name)}")
        logging.info(f"  - 外网回看: {os.path.join(config.web_path, config.NetReplay_name)}")

    except Exception as e:
        logging.error(f"程序执行出错: {e}")
        traceback.print_exc()

if __name__ == '__main__':
    main()
