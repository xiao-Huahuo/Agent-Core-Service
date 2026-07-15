import requests, time

urls = [
    'http://127.0.0.1:8002/health',
    'http://127.0.0.1:8002/agent/tools',
    'http://127.0.0.1:8002/sessions',
    'http://127.0.0.1:8002/settings',
    'http://127.0.0.1:8002/knowledge/files',
    'http://127.0.0.1:8002/knowledge/libraries',
]

for url in urls:
    times = []
    for _ in range(5):
        start = time.time()
        try:
            resp = requests.get(url, timeout=5)
            status = resp.status_code
        except Exception as e:
            status = f'ERR:{e}'
        times.append(round((time.time()-start)*1000, 1))
    print(f'{url}')
    print(f'  times={times}, avg={round(sum(times)/len(times), 1)}ms')
