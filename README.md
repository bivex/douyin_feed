# Douyin безлогиновый фид

Рабочий пайплайн получения фида Douyin (китайский TikTok) **без логина**:
`ttwid → msToken → aBogus → эндпоинт Douyin`.

Подпись (aBogus/msToken) считается внешним сервисом `api2.52jan.com` (тестовый
`cid` из публичного репозитория [Superheroff/TikTokApi_aBogus_Test]). К Douyin
запросы идут через SOCKS5-прокси.

## Файлы
- `douyin_feed.py` — клиент `DouyinClient` + запуск (`main`).
- `requirements.txt` — зависимости.

## Установка / запуск
```bash
pip install -r requirements.txt
python3 douyin_feed.py
```

## Как это работает
1. **ttwid** — `POST https://ttwid.bytedance.com/ttwid/union/register/` (Set-Cookie).
2. **msToken** — сервис `52jan` `/dyapi/web/get_msToken`. Требует `headers` с
   `cookie` и **User-Agent Chrome 149**.
3. **sign** (для `52jan`) — `md5('1005' + cid + ts + AppKey)`,
   где `AppKey = sha256(cid + '5c6b8r9a')`.
4. **aBogus** — сервис `52jan` `/dyapi/web/abogus`, считается над полным URL.
5. **Эндпоинт** — `/aweme/v1/web/hot/search/list/` (тренды), `GET` с `&a_bogus=`.
   Работает без логина.

## Использование как модуль
```python
from douyin_feed import DouyinClient

cli = DouyinClient()
cli.init_tokens()
feed = cli.get_trending(limit=20)
for it in feed["items"]:
    print(it["position"], it["hot_value"], it["word"])
```

## Конфиг
Вверху `douyin_feed.py`:
- `CID`, `SIGN_HOST`, `APPKEY_SALT` — учётка сервиса подписей.
- `SOCKS5` — прокси.
- `UA` — должен быть Chrome 149.

## Лимиты / ограничения
- `cid` — тестовый аккаунт `52jan`, **200 запросов/день**. Не для нагрузки.
- `/hot/search/list/` отдаёт **тренды (темы + hot-значения)**; `aweme_info` в
  ответе пустой.
- Полные метаданные видео (play-URL) без логина — через `/aweme/v1/web/aweme/post/`
  (нужен `sec_user_id`) или `/aweme/v1/web/aweme/detail/` (нужен `aweme_id`).
  Главная Douyin под антиботом `ac_signature` эти ID напрямую не отдаёт.
- Поиск `/web/general/search/single/` требует логина (`status 2483 请先登录`).
