FROM ubuntu:22.04

ENV TZ=Asia/Shanghai
ENV DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    python3 python3-pip lighttpd supervisor curl \
    && pip3 install python-dotenv requests schedule \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && echo "Asia/Shanghai" > /etc/timezone

# 复制 supervisord 配置
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# 复制 lighttpd 配置
COPY lighttpd.conf /etc/lighttpd/lighttpd.conf

WORKDIR /app

EXPOSE 8080 554

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
