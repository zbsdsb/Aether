# Gunicorn configuration file

import gc

# max-requests 触发 worker 轮换时，旧 worker 的最大存活时间（秒）
# 超过此时间后旧 worker 会被 SIGKILL 强制回收，防止因长 streaming 连接导致僵尸进程
graceful_timeout = 120


def when_ready(server):
    """
    Called just after the server is started.
    Freeze GC before forking workers to optimize Copy-on-Write memory sharing.
    """
    gc.freeze()
    server.log.info("GC frozen for Copy-on-Write optimization")
    server.log.info(f"Objects in permanent generation: {gc.get_freeze_count()}")


def post_fork(server, worker):
    try:
        import resource

        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        server.log.info(f"Worker {worker.pid} RSS after fork: {rss} KB")
    except ImportError:
        pass  # Windows 不支持 resource 模块
