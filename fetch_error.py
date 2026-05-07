import urllib.request
from urllib.error import HTTPError

try:
    response = urllib.request.urlopen("http://localhost:8000/")
    print(response.read().decode('utf-8'))
except HTTPError as e:
    print("HTTP ERROR:", e.code)
    print(e.read().decode('utf-8'))
except Exception as e:
    print("OTHER ERROR:", str(e))
