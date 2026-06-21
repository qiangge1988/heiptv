import subprocess
import time
import os
import logging
import threading

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/starttask.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 任务锁，防止重复执行
_task_locks = {
    'iptv': threading.Lock(),
    'logo': threading.Lock(),
}

def run_task(name, script_path):
    """执行任务，带锁防止重复执行"""
    lock = _task_locks[name]
    if not lock.acquire(blocking=False):
        logging.warning(f"[{name}] 上一次任务还在执行，跳过本次")
        return

    try:
        logging.info(f"[{name}] 开始执行 {script_path}")
        # 不捕获输出，让子进程的日志直接输出到 docker logs
        result = subprocess.run(
            ['python3', script_path],
            timeout=1800  # 30分钟超时
        )
        if result.returncode == 0:
            logging.info(f"[{name}] 执行完成")
        else:
            logging.error(f"[{name}] 执行失败 (code={result.returncode})")
    except subprocess.TimeoutExpired:
        logging.error(f"[{name}] 执行超时（30分钟）")
    except Exception as e:
        logging.error(f"[{name}] 执行异常: {e}")
    finally:
        lock.release()

def playtask():
    run_task('iptv', '/app/iptv.py')

def logotask():
    run_task('logo', '/app/getlogo.py')

if __name__ == "__main__":
    import schedule

    logging.info("=== 定时任务调度器启动 ===")

    # 立即执行一次
    playtask()
    logotask()

    # 定时任务：每天 01:00 和 13:00 执行 iptv.py
    schedule.every().day.at("01:00").do(playtask)
    schedule.every().day.at("13:00").do(playtask)

    # 定时任务：每天 01:01 和 13:01 执行 getlogo.py（错开1分钟避免并发）
    schedule.every().day.at("01:01").do(logotask)
    schedule.every().day.at("13:01").do(logotask)

    logging.info("定时任务已设置: iptv=01:00/13:00, logo=01:01/13:01")

    while True:
        schedule.run_pending()
        time.sleep(1)
