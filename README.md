# HEIPTV - 河北联通IPTV工具

Docker 化的 IPTV 工具集，包含频道列表获取、节目单生成、Logo 下载、RTSP 代理等功能。

> 本项目基于恩山论坛的 IPTV 获取器项目修改而来，原项目 Docker 镜像：`xinjiawei1/heiptv:4.1.38`

## 功能

- **iptv.py** - 从 IPTV 服务器获取频道列表和节目单，生成多种 M3U 文件
- **getlogo.py** - 并发下载频道 Logo（5线程）
- **rtspproxy.py** - RTSP 代理服务器，处理地址转换和流转发
- **starttask.py** - 定时任务调度器（每天 01:00/13:00 执行）
- **港澳台直播源** - 自动从远程 M3U 提取港澳台频道

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/qiangge1988/heiptv.git
cd heiptv
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 IPTV 服务器信息和鉴权参数
vim .env
```

### 3. 启动服务

```bash
docker compose up -d
```

### 4. 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| Web 目录 | http://your-ip:2000/ | 文件列表 |
| 组播源 | http://your-ip:2000/iptv.m3u | IGMP 组播地址 |
| 组播转单播 | http://your-ip:2000/LanLive.m3u | 内网直播（组播转单播） |
| 单播源 | http://your-ip:2000/LanReplay.m3u | 内网回看（单播） |
| 外网直播 | http://your-ip:2000/NetLive.m3u | 外网直播 |
| 外网回看 | http://your-ip:2000/NetReplay.m3u | 外网回看 |
| EPG 节目单 | http://your-ip:2000/PL.xml.gz | 节目单（gzip） |

## 定时任务

- `iptv.py` - 每天 01:00、13:00 执行
- `getlogo.py` - 每天 01:01、13:01 执行

## 常用命令

```bash
# 查看日志
docker compose logs -f

# 重启服务
docker compose restart

# 重新构建
docker compose build && docker compose up -d

# 停止服务
docker compose down
```

## 目录结构

```
heiptv/
├── Dockerfile           # Docker 镜像定义
├── docker-compose.yml   # 容器编排配置
├── supervisord.conf     # 进程管理配置
├── lighttpd.conf        # Web 服务器配置
├── .env.example         # 环境变量模板
├── iptv.py              # IPTV 频道和节目单获取
├── getlogo.py           # 频道 Logo 下载
├── rtspproxy.py         # RTSP 代理服务器
└── starttask.py         # 定时任务调度器
```

## 环境变量说明

| 变量 | 说明 |
|------|------|
| `IPTV_SERVER` | IPTV 服务器地址 |
| `RTSP_SERVER_IP` | RTSP 服务器 IP |
| `USER_ID` | 用户 ID |
| `AUTHENTICATOR` | 鉴权令牌 |
| `USER_TOKEN` | 用户 Token |
| `LAN_SERVER` | 内网服务器地址 |
| `NET_SERVER` | 外网服务器域名 |

## 改进说明

本项目在原版基础上进行了以下改进：

1. **配置管理** - 硬编码参数改为 `.env` 文件管理，便于维护
2. **代码结构** - 使用面向对象重构，提高可维护性
3. **并发下载** - Logo 下载改为多线程并发，提升效率
4. **错误修复** - 修复了 IP 替换、RTSP 代理等多项 Bug
5. **容器化** - 使用 Dockerfile + docker-compose 简化部署
6. **进程管理** - 使用 supervisord 替代 shell 脚本管理进程

## 免责声明

> 由于本人没有 RTSP 代理的需求，关于 `rtspproxy.py` 的部分仅供参考，需自行研究适配。

## 参考与致谢

- 原始项目来自 [恩山论坛 IPTV 获取器](https://www.right.com.cn/forum/thread-8438394-1-1.html)
- 原 Docker 镜像：`xinjiawei1/heiptv:4.1.38`
- 感谢原作者的辛勤开发和无私分享

## License

MIT
