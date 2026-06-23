# HEIPTV 项目规范

## 项目概述
- **项目名称**：HEIPTV（河北联通IPTV工具）
- **功能定位**：Docker 化的 IPTV 工具集
- **核心能力**：频道列表获取、节目单生成、Logo 下载、RTSP 代理、定时任务调度

## 技术栈
- **语言**：Python 3
- **基础镜像**：Ubuntu 22.04
- **容器化**：Docker + docker-compose
- **依赖库**：python-dotenv, requests, schedule
- **进程管理**：supervisord
- **Web 服务**：lighttpd

## 目录结构
```
/workspace/projects/
├── .coze                    # Coze 项目配置
├── Dockerfile               # Docker 镜像定义
├── docker-compose.yml       # 容器编排配置
├── supervisord.conf         # 进程管理配置
├── lighttpd.conf            # Web 服务器配置
├── .env.example              # 环境变量模板
├── iptv.py                  # IPTV 频道和节目单获取
├── getlogo.py               # 频道 Logo 下载
├── rtspproxy.py             # RTSP 代理服务器
├── starttask.py             # 定时任务调度器
├── extract_auth.py          # 抓包参数提取脚本
├── config/                   # 配置目录（挂载到容器 /app/config）
└── output/                  # 输出目录（挂载到容器 /app/output）
```

## 关键入口 / 核心模块

### 核心脚本
| 文件 | 功能 | 定时任务 |
|------|------|----------|
| `iptv.py` | 从 IPTV 服务器获取频道列表和节目单 | 每天 01:00、13:00 |
| `getlogo.py` | 并发下载频道 Logo（5线程） | 每天 01:01、13:01 |
| `rtspproxy.py` | RTSP 代理服务器，处理地址转换和流转发 | 常驻 |
| `starttask.py` | 定时任务调度器 | 常驻 |
| `extract_auth.py` | 从抓包文件中自动提取鉴权参数 | 手动执行 |

### 端口说明
| 端口 | 协议 | 说明 |
|------|------|------|
| 554 | TCP | RTSP 代理端口 |
| 8080 | HTTP | Lighttpd Web 服务端口（映射到 2000） |

### 服务地址
- Web 目录：`http://IP:2000/`
- 组播源：`http://IP:2000/iptv.m3u`
- 内网直播：`http://IP:2000/LanLive.m3u`
- 内网回看：`http://IP:2000/LanReplay.m3u`
- 外网直播：`http://IP:2000/NetLive.m3u`
- 外网回看：`http://IP:2000/NetReplay.m3u`
- EPG 节目单：`http://IP:2000/PL.xml.gz`

## 运行与预览
- **运行方式**：Docker Compose
  ```bash
  docker compose up -d
  docker compose logs -f
  docker compose restart
  ```
- **预览**：不支持（无前端界面，纯后端工具）

## 环境变量说明
核心环境变量（需在 `config/.env` 中配置）：
- `IPTV_SERVER` - IPTV 服务器地址
- `RTSP_SERVER_IP` - RTSP 服务器 IP
- `USER_ID` / `AUTHENTICATOR` / `USER_TOKEN` - 鉴权参数
- `STB_ID` / `MAC` / `STB_VERSION` - 机顶盒信息
- `AREA_ID` / `USER_TOKEN_SERVICE` / `TEMP_KEY` - 区域和服务参数
- `LAN_SERVER` - 内网服务器地址（需手动修改）
- `BOFANG_SERVER` - 组播转单播服务器 IP
- `NET_SERVER` - 外网服务器域名

## 初始化步骤
1. 克隆项目后，先运行 `extract_auth.py` 提取鉴权参数
2. 复制环境变量文件并修改 `LAN_SERVER`、`BOFANG_SERVER`、`NET_SERVER`
3. 执行 `docker compose up -d` 启动服务

## 用户偏好与长期约束
- 项目使用 docker-compose 独立部署，不走 Coze 平台
- 脚本通过 volume 挂载，便于更新维护
- 定时任务由容器内 supervisord 管理

## 常见问题和预防
- **鉴权参数过期**：需要重新抓包提取参数
- **频道无法播放**：检查 `LAN_SERVER` 和 `BOFANG_SERVER` 配置
- **Logo 下载失败**：检查网络连接和 Logo URL 是否有效
