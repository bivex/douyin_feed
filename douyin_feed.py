#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Douyin (китайский TikTok) — безлогиновый фид + ссылки на видео.

Пайплайн:  ttwid -> msToken -> aBogus (+X-Bogus для detail) -> эндпоинт Douyin.
Зависимости:  pip install requests "requests[socks]"

Запуск:
    python3 douyin_feed.py                 # тренды в консоль
    python3 douyin_feed.py --save          # + снимок в douyin_feed_trending_<дата>.txt
    python3 douyin_feed.py --limit 20      # топ-20
    python3 douyin_feed.py --mp4 <aweme_id># попробовать вытащить play URL (НУЖЕН прокси в КНР!)

ВАЖНО: метаданные видео (aweme/detail, play URL) Douyin отдаёт ТОЛЬКО китайским IP.
Прокси по умолчанию — США, поэтому --mp4 вернёт пусто; для .mp4 нужен CN-прокси.
"""
import argparse
import hashlib
import time
from datetime import datetime
from urllib.parse import urlencode, parse_qsl, quote

import requests

# ─────────────────────────── КОНФИГ ───────────────────────────
CID = "d9ba8ae07d955b83c3b04280f3dc5a4a"          # тестовый cid api2.52jan.com
SIGN_HOST = "https://api2.52jan.com"
APPKEY_SALT = "5c6b8r9a"

# SOCKS5-прокси. Для .mp4 требуется прокси В КИТАЕ — замените на CN-узел.
SOCKS5 = "socks5://jAGome9inQjtByd:iGoQn4cIBkteq3R@89.32.126.116:43438"

# UA должен быть Chrome 149 — этого требует эндпоинт msToken
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36")
# ────────────────────────────────────────────────────────────────


class DouyinClient:
    def __init__(self, cid=CID, sign_host=SIGN_HOST, socks5=SOCKS5, ua=UA):
        self.cid = cid
        self.sign_host = sign_host
        self.ua = ua
        self.appkey = hashlib.sha256((cid + APPKEY_SALT).encode()).hexdigest()
        proxies = {"http": socks5, "https": socks5} if socks5 else None

        self.s = requests.Session()
        self.s.headers.update({"User-Agent": ua, "Accept-Language": "zh-CN,zh;q=0.9",
                               "Referer": "https://www.douyin.com/"})
        if proxies:
            self.s.proxies.update(proxies)
        self._proxies = proxies
        self.ttwid = ""
        self.ms_token = ""

    # подпись для api2.52jan.com: md5('1005' + cid + ts + AppKey)
    def _sign(self, ts):
        return hashlib.md5(("1005" + self.cid + ts + self.appkey).encode("utf8")).hexdigest()

    def _api_form(self, path, payload):
        ts = str(int(time.time()))
        d = dict(payload); d["sign"] = self._sign(ts)
        return requests.post(self.sign_host + path, data=d,
                             headers={"cid": self.cid, "timestamp": ts},
                             proxies=self._proxies, timeout=25)

    def _api_json(self, path, payload):
        ts = str(int(time.time()))
        d = dict(payload); d["sign"] = self._sign(ts)
        return requests.post(self.sign_host + path, json=d,
                             headers={"cid": self.cid, "timestamp": ts, "content-type": "application/json"},
                             proxies=self._proxies, timeout=25)

    def init_tokens(self):
        """Свежие ttwid + msToken без логина."""
        self.s.post("https://ttwid.bytedance.com/ttwid/union/register/",
                    json={"region": "cn", "aid": 1768, "needFid": False,
                          "service": "https://www.douyin.com",
                          "migrate_info": {"ticket": "", "source": "node"},
                          "cbUrlProtocol": "https", "union": True, "fid": ""},
                    timeout=25)
        self.ttwid = self.s.cookies.get("ttwid") or ""
        r = self._api_json("/dyapi/web/get_msToken",
                           {"msToken": "", "headers": {"User-Agent": self.ua, "Cookie": f"ttwid={self.ttwid}"}, "uuid": ""})
        self.ms_token = r.json().get("msToken", "")
        return bool(self.ttwid and self.ms_token)

    def _x_bogus(self, url):
        """X-Bogus + _signature через /dyapi/v2/web/signature. Возвращает dict."""
        res = self._api_form("/dyapi/v2/web/signature", {"url": url, "body": ""}).json().get("result", "")
        return dict(parse_qsl(res.lstrip("&")))

    def _signed_get(self, url, params, with_xbogus=False):
        """GET к Douyin с a_bogus (+опц. X-Bogus/_signature)."""
        if not (self.ttwid and self.ms_token):
            self.init_tokens()
        p = dict(params); p["msToken"] = self.ms_token
        full = url + ("&" if "?" in url else "?") + urlencode(p)
        abogus = self._api_json("/dyapi/web/abogus", {"url": full, "ua": self.ua, "data": "", "t": ""}).json().get("abogus", "")
        full += "&a_bogus=" + abogus
        headers = {"Accept": "application/json"}
        if with_xbogus:
            xb = self._x_bogus(url + ("&" if "?" in url else "?") + urlencode(p))
            full += "&" + urlencode(xb)
            headers["X-Bogus"] = xb.get("X-Bogus", "")
        return self.s.get(full, headers=headers, timeout=30)

    # ── эндпоинты ──
    def get_trending(self, limit=46):
        """Тренды Douyin + прямые ссылки на видео (group_id)."""
        resp = self._signed_get("https://www.douyin.com/aweme/v1/web/hot/search/list/",
                                {"device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
                                 "detail": "1", "source": "6", "cookie_enabled": "true", "screen_width": "1920",
                                 "screen_height": "1080", "browser_language": "zh-CN", "browser_platform": "Win32",
                                 "browser_name": "Chrome", "browser_version": "149.0.0.0", "browser_online": "true"})
        data = resp.json()
        wl = (data.get("data") or {}).get("word_list") or []
        return {
            "status_code": data.get("status_code"),
            "items": [{
                "position": w.get("position"),
                "word": w.get("word"),
                "hot_value": w.get("hot_value"),
                "sentence_id": w.get("sentence_id"),
                "aweme_id": w.get("group_id"),
                "video_url": (f"https://www.douyin.com/video/{w['group_id']}" if w.get("group_id") else None),
                "search_url": f"https://www.douyin.com/search/{quote(w.get('word', ''))}",
            } for w in wl[:limit]],
        }

    def get_video_detail(self, aweme_id):
        """Play URL видео. ТРЕБУЕТ прокси в КНР (иначе пустой ответ)."""
        resp = self._signed_get("https://www.douyin.com/aweme/v1/web/aweme/detail/",
                                {"device_platform": "webapp", "aid": "6383", "channel": "channel_pc_web",
                                 "aweme_id": str(aweme_id), "cookie_enabled": "true", "screen_width": "1920",
                                 "screen_height": "1080", "browser_language": "zh-CN", "browser_platform": "Win32",
                                 "browser_name": "Chrome", "browser_version": "149.0.0.0", "browser_online": "true"},
                                with_xbogus=True)
        if not resp.content:
            return {"status_code": None, "note": "пустой ответ — нужен прокси в КНР", "play_urls": []}
        j = resp.json()
        aw = j.get("aweme_detail") or {}
        urls = (((aw.get("video") or {}).get("play_addr") or {}).get("url_list")) or []
        return {
            "status_code": j.get("status_code"),
            "aweme_id": aw.get("aweme_id"),
            "desc": aw.get("desc"),
            "author": (aw.get("author") or {}).get("nickname"),
            "play_urls": urls,
        }


def _format_trending(feed):
    lines = [f"Douyin тренды — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
             f"status_code: {feed['status_code']} | тем: {len(feed['items'])}", "=" * 70, ""]
    for it in feed["items"]:
        lines.append(f"#{it['position']:>2}  [{it['hot_value']:,}🔥]  {it['word']}  (sentence_id={it['sentence_id']})")
        if it.get("video_url"):
            lines.append(f"     видео : {it['video_url']}")
        lines.append(f"     поиск : {it['search_url']}")
        lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Douyin безлогиновый фид")
    ap.add_argument("--limit", type=int, default=15, help="сколько трендов показать")
    ap.add_argument("--save", action="store_true", help="сохранить снимок в douyin_feed_trending_<дата>.txt")
    ap.add_argument("--mp4", metavar="AWEME_ID", help="получить play URL видео (нужен прокси в КНР)")
    args = ap.parse_args()

    cli = DouyinClient()
    if not cli.init_tokens():
        print("Не удалось получить ttwid/msToken"); return

    if args.mp4:
        print(f"aweme/detail для {args.mp4} ...")
        d = cli.get_video_detail(args.mp4)
        print("status:", d.get("status_code"))
        if d.get("note"):
            print("⚠", d["note"])
        if d.get("desc") is not None:
            print("desc  :", d.get("desc"))
            print("author:", d.get("author"))
            for u in d.get("play_urls", [])[:2]:
                print("  play:", u[:160])
            if not d.get("play_urls"):
                print("play URLs пусто (гео/логин).")
        return

    feed = cli.get_trending(limit=args.limit)
    out = _format_trending(feed)
    print(out)
    if args.save:
        fn = f"douyin_feed_trending_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.txt"
        with open(fn, "w", encoding="utf-8") as fh:
            fh.write(out)
        print(f"\n[сохранено] {fn}")


if __name__ == "__main__":
    main()
