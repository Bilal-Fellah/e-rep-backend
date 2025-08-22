import multiprocessing, os
bind = "0.0.0.0:8000"
workers = multiprocessing.cpu_count() * 2 + 1
threads = 2
timeout = 60
graceful_timeout = 30
accesslog = "-"   # stdout
errorlog  = "-"   # stderr
loglevel  = "info"
