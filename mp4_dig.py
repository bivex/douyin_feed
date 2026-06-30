"""
Докапываемся до .mp4: aweme/detail с a_bogus + X-Bogus + _signature.
"""
import hashlib, time, requests, json
from urllib.parse import urlencode, parse_qsl, urlencode

CID = "d9ba8ae07d955b83c3b04280f3dc5a4a"; HOST = "https://api2.52jan.com"
SOCKS = "socks5://jAGome9inQjtByd:iGoQn4cIBkteq3R@89.32.126.116:43438"
proxies = {"http": SOCKS, "https": SOCKS}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
APPKEY = hashlib.sha256((CID + "5c6b8r9a").encode()).hexdigest()
def sign(ts): return hashlib.md5(("1005" + CID + ts + APPKEY).encode()).hexdigest()

def api_form(path, payload):
    ts = str(int(time.time()))
    d = dict(payload); d["sign"] = sign(ts)
    return requests.post(HOST + path, data=d, headers={"cid": CID, "timestamp": ts}, proxies=proxies, timeout=25)
def api_json(path, payload):
    ts = str(int(time.time()))
    d = dict(payload); d["sign"] = sign(ts)
    return requests.post(HOST + path, json=d, headers={"cid": CID, "timestamp": ts, "content-type": "application/json"}, proxies=proxies, timeout=25)

s = requests.Session()
s.headers.update({"User-Agent": UA, "Accept-Language": "zh-CN,zh;q=0.9", "Referer": "https://www.douyin.com/"})
s.proxies.update(proxies)
s.post("https://ttwid.bytedance.com/ttwid/union/register/",
       json={"region": "cn", "aid": 1768, "needFid": False, "service": "https://www.douyin.com",
             "migrate_info": {"ticket": "", "source": "node"}, "cbUrlProtocol": "https", "union": True, "fid": ""}, timeout=25)
ttwid = s.cookies.get("ttwid") or ""
msToken = api_json("/dyapi/web/get_msToken", {"msToken": "", "headers": {"User-Agent": UA, "Cookie": f"ttwid={ttwid}"}, "uuid": ""}).json().get("msToken", "")

AID = "7656047929158210831"  # тренд #1
params = {"device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
          "aweme_id": AID, "cookie_enabled": "true", "screen_width": "1920", "screen_height": "1080",
          "browser_language": "zh-CN", "browser_platform": "Win32", "browser_name": "Chrome",
          "browser_version": "149.0.0.0", "browser_online": "true", "msToken": msToken}
url1 = "https://www.douyin.com/aweme/v1/web/aweme/detail/?" + urlencode(params)

a_bogus = api_json("/dyapi/web/abogus", {"url": url1, "ua": UA, "data": "", "t": ""}).json().get("abogus", "")
url2 = url1 + "&a_bogus=" + a_bogus

# X-Bogus + _signature
xb = api_form("/dyapi/v2/web/signature", {"url": url1, "body": ""}).json().get("result", "")
# xb выглядит как '&X-Bogus=...&_signature=...'
xb_params = dict(parse_qsl(xb.lstrip("&")))
print("X-Bogus:", xb_params.get("X-Bogus"))
print("_signature:", xb_params.get("_signature"))

url3 = url2 + "&" + urlencode(xb_params)
# продублируем X-Bogus в заголовке на всякий случай
hdrs = {"Accept": "application/json", "X-Bogus": xb_params.get("X-Bogus", "")}

r = s.get(url3, headers=hdrs, timeout=30)
print("\nHTTP", r.status_code, "| bytes", len(r.content), "| ctype", r.headers.get("content-type"))
try:
    j = r.json()
    aw = j.get("aweme_detail") or {}
    print("status_code:", j.get("status_code"), "| keys:", list(j.keys())[:8])
    print("desc:", (aw.get("desc") or "")[:60])
    v = (aw.get("video") or {})
    pa = v.get("play_addr") or {}
    urls = pa.get("url_list") or []
    print("duration:", v.get("duration"), "мс | play url count:", len(urls))
    for u in urls[:2]:
        print("  play:", u[:160])
    if not aw:
        print("RAW:", r.text[:300])
except Exception as e:
    print("не JSON:", e, "| тело:", r.text[:300])
