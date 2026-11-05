# tcli — CLI для Tinkoff Invest API

Полноценный CLI-инструмент для работы с **Tinkoff Invest API**. Поддержка песочницы (**SANDBOX**) и боевого контура (**LIVE**) с раздельными токенами.

## 📋 Все команды

| № | Команда | Описание |
|---|---------|----------|
| 1 | `check` | Самопроверка: `.env`, сертификат НУЦ, доступ к API |
| 2 | `change-mode` | Переключение контура (SANDBOX ↔ LIVE) |
| 3 | `status` | Счета и сводка портфеля |
| 4 | `positions` | Позиции: тикер, количество, средняя/текущая цена, P&L |
| 5 | `orders` | Активные заявки |
| 6 | `payin` | Пополнить счёт песочницы (только SANDBOX) |
| 7 | `reset` | Сбросить песочницу (устарело) |
| 8 | `account-list` | Список всех счетов |
| 9 | `account-new` | Создать новый счёт (только SANDBOX) |
| 10 | `account-rm` | Удалить счёт (только SANDBOX) |
| 11 | `account-show` | Показать детали счёта |
| 12 | `account-select` | Интерактивный выбор активного счёта |
| 13 | `order-buy` | Купить инструмент |
| 14 | `order-sell` | Продать инструмент |
| 15 | `order-cancel` | Отменить заявку |
| 16 | `ops` | История операций |
| 17 | `quote` | Текущая цена инструмента |
| 18 | `candles` | История свечей |
| 19 | `find` | Поиск инструментов |
| 20 | `instruments` | Фильтрация инструментов по типу, цене, валюте и др. |
| 21 | `info` | Детальная информация об инструменте |
| 22 | `id-info` | Определить тип идентификатора (FIGI/UID/ISIN) |
| 23 | `export` | Экспорт данных в CSV/JSON |
| 24 | `watchlist` | Управление избранными инструментами |
| 25 | `orderbook` | Стакан заявок (bid/ask) |
| 26 | `trading-status` | Статус торгов инструментом |
| 27 | `sessions` | Расписание торговых сессий |
| 28 | `close` | Закрытие позиции рыночной заявкой |
| 29 | `close-all` | Закрытие всех открытых позиций |
| 30 | `cancel-all` | Отмена всех открытых заявок |
| 31 | `order-info` | Информация о заявке |
| 32 | `stop-order-list` | Список стоп-заявок |
| 33 | `stop-order-cancel` | Отмена стоп-заявки |
| 34 | `free-cash` | Свободные средства на счёте |
| 35 | `has-position` | Проверка наличия позиции |
| 36 | `is-market-open` | Проверка статуса рынка |
| 37 | `stop-order-place` | Размещение стоп-заявки |
| 38 | `stop-order-cancel-all` | Отмена всех стоп-заявок |

---

## 1. 🔍 `check` — Самопроверка

Проверяет корректность конфигурации: наличие `.env`, токен, сертификат НУЦ Минцифры, доступ к API.

```bash
# Проверка конфигурации
tcli check
```

**Вывод:**
```
[1/4] .env (/home/user/tcli/.env): токен t.V6***sEHg
[2/4] сертификат: /home/user/tcli/certs/russian-trusted-root.pem (1234 байт)
[3/4] GRPC_DEFAULT_SSL_ROOTS_FILE_PATH: /home/user/tcli/certs/russian-trusted-root.pem
[4/4] API (SANDBOX): OK, счетов: 2 (Main, Test)
check: OK — всё готово
```

---

## 2. 🔄 `change-mode` — Переключение контура

Переключает между SANDBOX и LIVE контурами. Токен выбирается автоматически:
- **SANDBOX** → использует `INVEST_SANDBOX_TOKEN`
- **LIVE** → использует `INVEST_TOKEN`

**Параметры:**
- `contour` (обязательный) — `sandbox` или `live`
- `--yes`, `-y` — не запрашивать подтверждение для LIVE
- `--no-prompt` — неинтерактивный режим (то же, что `--yes`)

```bash
# Переключить на песочницу
tcli change-mode sandbox
# контур: LIVE → SANDBOX
# токен: t.V6***sEHg → t.sJ***tYyw

# Переключить на боевой контур (с подтверждением)
tcli change-mode live
# ВНИМАНИЕ: Переключение на LIVE контур
# Все операции будут выполняться с реальными деньгами!
# Введите 'LIVE' для подтверждения: LIVE
# контур: SANDBOX → LIVE
# токен: t.sJ***tYyw → t.V6***sEHg

# Переключить на LIVE без подтверждения (для скриптов)
tcli change-mode live --yes
tcli change-mode live --no-prompt
```

---

## 3. 📊 `status` — Счета и сводка портфеля

Показывает все счета и сводку портфеля: деньги, бумаги, итого, P&L.

**Параметры:**
- `--json` — вывод в JSON формате

```bash
# Человекочитаемый вывод
tcli status

# JSON вывод (для интеграции с торговым агентом)
tcli status --json
```

**JSON вывод:**
```json
{
  "contour": "SANDBOX",
  "accounts": [
    {"id": "acc-1", "name": "Main", "type": "TINKOFF", "status": "OPEN"}
  ],
  "portfolio": [
    {
      "account": "Main",
      "cash": 100000.0,
      "securities": 50000.0,
      "total": 150000.0,
      "pnl": 5000.0
    }
  ]
}
```

---

## 4. 💼 `positions` — Позиции портфеля

Показывает все позиции: тикер, тип, количество, средняя/текущая цена, стоимость, P&L.

**Параметры:**
- `--json` — вывод в JSON формате

```bash
# Человекочитаемый вывод
tcli positions

# JSON вывод
tcli positions --json
```

**JSON вывод:**
```json
[
  {
    "ticker": "SBER",
    "type": "SHARE",
    "quantity": 10,
    "avg": "290.50",
    "current": "300.00",
    "value": 3000.0,
    "pnl": 95.0
  }
]
```

---

## 5. 📋 `orders` — Активные заявки

Показывает все активные заявки: тикер, направление, статус, лоты, цена, ID.

**Параметры:**
- `--json` — вывод в JSON формате

```bash
tcli orders
tcli orders --json
```

**JSON вывод:**
```json
[
  {
    "ticker": "SBER",
    "direction": "BUY",
    "status": "FILL",
    "lots": 5,
    "price": "290.00",
    "order_id": "12345678-abcd-efgh"
  }
]
```

---

## 6. 💰 `payin` — Пополнить счёт (только SANDBOX)

Пополняет счёт песочницы на указанную сумму в рублях.

**Параметры:**
- `amount` (обязательный) — сумма пополнения в рублях

```bash
# Пополнить на 100000 рублей
tcli payin 100000
# пополнено на 100 000 ₽ · счёт Main · денег теперь: 200 000 ₽

# Пополнить на 50000 рублей
tcli payin 50000
```

---

## 7. 🔄 `reset` — Сбросить песочницу

**Устарело.** Метод `reset` отсутствует в `tinkoff-investments 0.2.0-beta117`. Используйте приложение Т-Банка для закрытия/открытия счёта.

```bash
tcli reset
# Ошибка: метод reset отсутствует в tinkoff-investments 0.2.0-beta117
```

---

## 8. 📋 `account-list` — Список всех счетов

Показывает все доступные счета: имя, ID, тип, статус.

```bash
tcli account-list
```

**Вывод:**
```
Счета (SANDBOX)
┌──────────┬──────────┬───────────┬────────┐
│ Имя      │ ID       │ Тип       │ Статус │
├──────────┼──────────┼───────────┼────────┤
│ Main     │ acc-1    │ TINKOFF   │ OPEN   │
│ Test     │ acc-2    │ TINKOFF   │ OPEN   │
└──────────┴──────────┴───────────┴────────┘
```

---

## 9. ➕ `account-new` — Создать новый счёт (только SANDBOX)

Создаёт новый счёт в песочнице.

**Параметры:**
- `name` (опциональный) — имя нового счёта

```bash
# Создать счёт с именем
tcli account-new "Основной"
# счёт создан: 2001234567

# Создать счёт без имени
tcli account-new
# счёт создан: 2007654321
```

---

## 10. 🗑️ `account-rm` — Удалить счёт (только SANDBOX)

Удаляет счёт в песочнице. Все позиции и заявки будут закрыты.

**Параметры:**
- `account` (обязательный) — имя или ID счёта для удаления
- `--yes`, `-y` — не запрашивать подтверждение
- `--no-prompt` — неинтерактивный режим

```bash
# Удалить счёт с подтверждением
tcli account-rm Main
# ВНИМАНИЕ: Удаление счёта Main
# Все позиции и заявки будут закрыты!
# Введите имя счёта для подтверждения: Main
# счёт удалён: Main

# Удалить без подтверждения (для скриптов)
tcli account-rm Main --yes
tcli account-rm Main --no-prompt

# Удалить по ID
tcli account-rm 2001234567
```

---

## 11. 🔍 `account-show` — Показать детали счёта

Показывает детальную информацию о счёте: ID, тип, статус, портфель, позиции.

**Параметры:**
- `account` (обязательный) — имя или ID счёта

```bash
# Показать детали по имени
tcli account-show Main

# Показать детали по ID
tcli account-show 2001234567
```

**Вывод:**
```
Счёт: Main
  ID: 2001234567
  Тип: TINKOFF
  Статус: OPEN

Портфель:
  Деньги: 100 000 ₽
  Бумаги: 50 000 ₽
  Итого: 150 000 ₽
  P&L: 5 000 ₽

Позиции (2):
┌────────┬───────┬─────────┬───────────┬─────────┬──────────┬──────┐
│ Тикер  │ Тип   │ Кол-во  │ Средняя   │ Текущая │ Стоимость│ P&L  │
├────────┼───────┼─────────┼───────────┼─────────┼──────────┼──────┤
│ SBER   │ SHARE │ 10      │ 290.50 ₽  │ 300.00 ₽│ 3 000 ₽  │ 95 ₽ │
│ GAZP   │ SHARE │ 5       │ 150.00 ₽  │ 155.00 ₽│ 775 ₽    │ 25 ₽ │
└────────┴───────┴─────────┴───────────┴─────────┴──────────┴──────┘
```

---

## 12. ✅ `account-select` — Интерактивный выбор счёта

Показывает список всех счетов и позволяет выбрать активный. Сохраняет выбор в `.env`.

```bash
tcli account-select
# Доступные счета:
#   1. Main (2001234567)
#   2. Test (2007654321)
# Выберите номер счёта: 1
# выбран счёт: Main
# сохранено в .env как SANDBOX_ACCOUNT_NAME
```

---

## 13. 🛒 `order-buy` — Купить инструмент

Покупает акции, облигации, ETF или фьючерсы.

**Параметры:**
- `ticker` (обязательный) — тикер инструмента (например, `SBER`)
- `lots` (обязательный) — количество лотов
- `--price` (опциональный) — лимитная цена (без неё — рыночная заявка)
- `--yes`, `-y` — не запрашивать подтверждение
- `--no-prompt` — неинтерактивный режим

```bash
# Купить 1 лот Сбер по рыночной цене
tcli order-buy SBER 1

# Купить 10 лотов Сбер лимитной заявкой по 290 ₽
tcli order-buy SBER 10 --price 290

# Купить без подтверждения (для скриптов)
tcli order-buy SBER 1 --yes
tcli order-buy SBER 1 --no-prompt --price 290
```

**Вывод:**
```
заявка выставлена
  order_id: 12345678-abcd-efgh-1234-567890abcdef
  figi: BBG004730N88
```

---

## 14. 💸 `order-sell` — Продать инструмент

Продаёт инструмент из портфеля.

**Параметры:**
- `ticker` (обязательный) — тикер инструмента
- `lots` (обязательный) — количество лотов
- `--price` (опциональный) — лимитная цена
- `--yes`, `-y` — не запрашивать подтверждение
- `--no-prompt` — неинтерактивный режим

```bash
# Продать 5 лотов Сбер по рыночной цене
tcli order-sell SBER 5

# Продать 5 лотов Сбер не дешевле 310 ₽
tcli order-sell SBER 5 --price 310

# Продать без подтверждения
tcli order-sell SBER 5 --yes
```

**Вывод:**
```
заявка выставлена
  order_id: 87654321-dcba-hgfe-4321-0987654321fe
  figi: BBG004730N88
```

---

## 15. ❌ `order-cancel` — Отменить заявку

Отменяет ранее выставленную заявку по её `order_id`.

**Параметры:**
- `order_id` (обязательный) — ID заявки (узнать через `tcli orders`)

```bash
tcli order-cancel 12345678-abcd-efgh-1234-567890abcdef
# заявка отменена: 12345678-abcd-efgh-1234-567890abcdef
```

---

## 16. 📜 `ops` — История операций

Показывает историю операций: покупки, продажи, зачисление денег, дивиденды, купоны, комиссии.

**Параметры:**
- `--from YYYY-MM-DD` — дата начала
- `--to YYYY-MM-DD` — дата окончания
- `--ticker ТИКЕР` — фильтр по тикеру

```bash
# Все операции с начала года
tcli ops --from 2026-01-01

# Операции за ноябрь
tcli ops --from 2026-11-01 --to 2026-11-30

# Операции по Сберу за ноябрь
tcli ops --from 2026-11-01 --to 2026-11-30 --ticker SBER

# Все операции без фильтров
tcli ops
```

**Вывод:**
```
Операции
┌───────────┬──────────┬───────┬────────┬──────────┬──────────┬────────┐
│ Дата      │ Тип      │ Тикер │ Кол-во │ Цена     │ Сумма    │ Валюта │
├───────────┼──────────┼───────┼────────┼──────────┼──────────┼────────┤
│ 2026-11-01│ BUY      │ SBER  │ 10     │ 290.50 ₽ │ 2 905 ₽  │ RUB    │
│ 2026-11-05│ SELL     │ GAZP  │ 5      │ 155.00 ₽ │ 775 ₽    │ RUB    │
│ 2026-11-10│ DIVIDEND │ SBER  │        │          │ 50 ₽     │ RUB    │
└───────────┴──────────┴───────┴────────┴──────────┴──────────┴────────┘
```

---

## 17. 💹 `quote` — Текущая цена инструмента

Показывает последнюю цену инструмента на бирже.

**Параметры:**
- `ticker` (обязательный) — тикер, FIGI или UID инструмента
- `--json` — вывод в JSON формате

```bash
# По тикеру
tcli quote SBER
# SBER (FIGI: BBG004730N88)
#   Последняя цена: 300.50 ₽
#   Время: 2026-11-03 18:50:00

# По FIGI
tcli quote BBG004730N88

# JSON вывод
tcli quote SBER --json
```

**JSON вывод:**
```json
{
  "ticker": "SBER",
  "figi": "BBG004730N88",
  "price": "300.50",
  "time": "2026-11-03 18:50:00"
}
```

---

## 18. 📈 `candles` — История свечей

Показывает исторические свечи OHLCV (Open/High/Low/Close/Volume) для технического анализа.

**Параметры:**
- `ticker` (обязательный) — тикер инструмента
- `--interval`, `-i` — интервал: `1min`, `5min`, `15min`, `1hour`, `1day` (по умолчанию `1day`)
- `--days`, `-d` — количество дней истории (по умолчанию `30`)
- `--json` — вывод в JSON формате

```bash
# Дневные свечи за 90 дней
tcli candles SBER --interval 1day --days 90

# Часовые свечи за 5 дней
tcli candles SBER -i 1hour -d 5

# Пятиминутные свечи за 1 день
tcli candles SBER -i 5min -d 1

# JSON вывод
tcli candles SBER --json
```

**JSON вывод:**
```json
{
  "ticker": "SBER",
  "interval": "1day",
  "days": 30,
  "candles": [
    {
      "time": "2026-10-01 00:00:00",
      "open": "285.00",
      "high": "290.50",
      "low": "283.00",
      "close": "289.00",
      "volume": 1000000
    }
  ]tcli instruments --type share --price-min 100 --price-max 1000
}
```

---

## 19. 🔍 `find` — Поиск инструментов

Ищет инструменты по тикеру, названию, ISIN, FIGI или UID. Автоматически определяет тип идентификатора.

**Параметры:**
- `query` (обязательный) — поисковый запрос (тикер, название, ISIN, FIGI, UID)
- `--json` — вывод в JSON формате

```bash
# Поиск по тикеру
tcli find SBER
tcli find Сбер

# Поиск по ISIN
tcli find RU000A0ZY7C3

# Поиск по FIGI
tcli find BBG004730N88

# Поиск по UID (внутренний ID Т-Банка)
tcli find TCS019029540

# JSON вывод
tcli find SBER --json
```

**JSON вывод:**
```json
[
  {
    "ticker": "SBER",
    "figi": "BBG004730N88",
    "name": "Сбербанк",
    "type": "share",
    "class": "TQBR"
  }
]
```

---

## 20. 🎯 `instruments` — Фильтрация инструментов

Фильтрует инструменты по типу, цене, валюте, бирже и другим параметрам. Возвращает все доступные инструменты с возможностью детальной фильтрации.

**Параметры:**
- `--type`, `-t` — тип инструмента: `share`, `bond`, `etf`, `future`, `currency`
- `--price-min` — минимальная цена
- `--price-max` — максимальная цена
- `--name` — поиск по названию (содержит)
- `--ticker` — поиск по тикеру (содержит)
- `--currency` — валюта: `RUB`, `USD`, `EUR`
- `--exchange` — биржа: `MOEX`, `SPB`
- `--lot-min` — минимальная лотность
- `--lot-max` — максимальная лотность
- `--available` — только доступные для торговли
- `--maturity-from` — дата погашения от (YYYY-MM-DD, для облигаций)
- `--maturity-to` — дата погашения до (YYYY-MM-DD, для облигаций)
- `--coupon-min` — минимальный купон (%)
- `--coupon-max` — максимальный купон (%)
- `--market-cap-min` — минимальная капитализация
- `--market-cap-max` — максимальная капитализация
- `--management-fee-max` — максимальная комиссия ETF (%)
- `--json` — вывод в JSON формате

```bash
# Все акции
tcli instruments --type share

# Акции с ценой от 100 до 1000 ₽
tcli instruments --type share --price-min 100 --price-max 1000

# Облигации с погашением в 2025 году
tcli instruments --type bond --maturity-from 2025-01-01 --maturity-to 2025-12-31

# ETF на Мосбирже
tcli instruments --type etf --exchange MOEX

# Акции в рублях, доступные для торговли
tcli instruments --type share --currency RUB --available

# Поиск по названию
tcli instruments --name "Сбер"

# Поиск по тикеру
tcli instruments --ticker "SBER"

# Акции с лотностью от 1 до 10
tcli instruments --type share --lot-min 1 --lot-max 10

# Комбинация фильтров
tcli instruments --type share --currency RUB --exchange MOEX --price-min 200 --available

# JSON вывод
tcli instruments --type share --json
```

**JSON вывод:**
```json
[
  {
    "ticker": "SBER",
    "figi": "BBG004730N88",
    "name": "Сбербанк",
    "type": "share",
    "lot": 10,
    "currency": "RUB",
    "min_price_step": 0.01,
    "exchange": "MOEX"
  }
]
```

---

## 21. ℹ️ `info` — Детальная информация об инструменте

Показывает полную информацию об инструменте: название, FIGI, ISIN, тип, валюта, лотность, биржа, класс, статус торгов.

**Параметры:**
- `ticker` (обязательный) — тикер, FIGI или UID инструмента
- `--json` — вывод в JSON формате

```bash
# По тикеру
tcli info SBER

# По FIGI
tcli info BBG004730N88

# По UID Т-Банка
tcli info TCS019029540

# По ISIN
tcli info RU000A0ZY7C3

# JSON вывод
tcli info SBER --json
```

**Вывод:**
```
Инструмент: SBER
  Название:    Сбербанк
  FIGI:        BBG004730N88
  ISIN:        RU000A0ZY7C3
  Тип:         share
  Валюта:      RUB
  Лот:         10
  Биржа:       MOEX
  Класс:       TQBR
  Статус:      NORMAL_TRADING
```

**JSON вывод:**
```json
{
  "name": "Сбербанк",
  "ticker": "SBER",
  "figi": "BBG004730N88",
  "isin": "RU000A0ZY7C3",
  "type": "share",
  "currency": "RUB",
  "lot": 10,
  "exchange": "MOEX",
  "class_code": "TQBR",
  "trading_status": "NORMAL_TRADING"
}
```

---

## 22. 🔎 `id-info` — Определить тип идентификатора

Определяет тип идентификатора (FIGI, UID, ISIN, тикер) и показывает информацию из кэша.

**Параметры:**
- `identifier` (обязательный) — идентификатор (тикер, FIGI, UID, ISIN)

```bash
# Определить тип FIGI
tcli id-info BBG004730N88
# Идентификатор: BBG004730N88
# Определённый тип: FIGI
# Кэшированный тип: FIGI

# Определить тип UID
tcli id-info TCS019029540
# Идентификатор: TCS019029540
# Определённый тип: UID
# Кэшированный тип: UID

# Определить тип ISIN
tcli id-info RU000A0ZY7C3
# Идентификатор: RU000A0ZY7C3
# Определённый тип: ISIN
# Кэшированный тип: ISIN

# Определить тип тикера
tcli id-info SBER
# Идентификатор: SBER
# Определённый тип: TICKER
# Кэшированный тип: (не найден в кэше)
```

---

## 23. 📤 `export` — Экспорт данных в CSV/JSON

Экспортирует позиции, операции или заявки в CSV или JSON формат.

**Параметры:**
- `data_type` (обязательный) — тип данных: `positions`, `operations`, `orders`
- `--format`, `-f` — формат: `csv`, `json` (по умолчанию `csv`)
- `--output`, `-o` — путь к файлу (по умолчанию stdout)
- `--from YYYY-MM-DD` — дата начала (для `operations`)
- `--to YYYY-MM-DD` — дата окончания (для `operations`)

```bash
# Экспорт позиций в CSV (stdout)
tcli export positions

# Экспорт позиций в CSV (файл)
tcli export positions --format csv --output positions.csv

# Экспорт позиций в JSON
tcli export positions --format json --output positions.json

# Экспорт операций за год в CSV
tcli export operations --from 2026-01-01 --output ops.csv

# Экспорт операций за период в JSON
tcli export operations --from 2026-01-01 --to 2026-11-30 --format json --output ops.json

# Экспорт активных заявок в CSV
tcli export orders --format csv --output orders.csv
```

**CSV вывод:**
```csv
ticker,type,quantity,avg,current,value,pnl
SBER,SHARE,10,290.50,300.00,3000.0,95.0
GAZP,SHARE,5,150.00,155.00,775.0,25.0
```

---

## 24. ⭐ `watchlist` — Управление избранными инструментами

Управляет списком отслеживаемых инструментов (избранное). Список хранится в `~/.tcli/watchlist.json`.

**Параметры:**
- `action` (опциональный) — действие: `add`, `remove`, `list` (по умолчанию `list`)
- `ticker` (опциональный) — тикер для `add`/`remove`
- `--json` — вывод в JSON формате

```bash
# Добавить инструмент в избранное
tcli watchlist add SBER
# добавлено в watchlist: SBER

tcli watchlist add GAZP
# добавлено в watchlist: GAZP

tcli watchlist add LKOH
# добавлено в watchlist: LKOH

# Показать текущие цены всех избранных инструментов
tcli watchlist list
tcli watchlist  # то же самое

# JSON вывод
tcli watchlist --json

# Удалить инструмент из избранного
tcli watchlist remove SBER
# удалено из watchlist: SBER

# JSON вывод для add/remove
tcli watchlist add SBER --json
tcli watchlist remove SBER --json
```

**Вывод watchlist:**
```
Избранные инструменты (3)
┌────────┬──────────────┬──────────┬────────┐
│ Тикер  │ FIGI         │ Цена     │ Изм.   │
├────────┼──────────────┼──────────┼────────┤
│ SBER   │ BBG004730N88 │ 300.50 ₽ │ 0.00%  │
│ GAZP   │ BBG004731X10 │ 155.00 ₽ │ 0.00%  │
│ LKOH   │ BBG000VLTH35 │ 7500.00 ₽│ 0.00%  │
└────────┴──────────────┴──────────┴────────┘
```

**JSON вывод:**
```json
[
  {"ticker": "SBER", "figi": "BBG004730N88", "price": "300.50", "change": 0.0},
  {"ticker": "GAZP", "figi": "BBG004731X10", "price": "155.00", "change": 0.0}
]
```

---

## 25. 📊 `orderbook` — Стакан заявок

Показывает стакан заявок (bid/ask) для инструмента.

**Параметры:**
- `ticker` — тикер или FIGI инструмента
- `--depth` (опциональный) — глубина стакана (по умолчанию 10)
- `--json` — вывод в JSON формате

```bash
# Стакан заявок для SBER с глубиной 20
tcli orderbook SBER --depth 20

# JSON вывод
tcli orderbook GAZP --json

# Стандартная глубина 10
tcli orderbook LKOH
```

**Вывод:**
```
Стакан заявок: SBER (BBG004730N88)
┌─────────────────────────────────────────────────────────────┐
│ BIDS (Покупка)                         │ ASKS (Продажа)     │
├──────────────┬─────────────────────────┼──────────────┬─────┤
│ Цена         │ Объём                   │ Цена         │ Объём│
├──────────────┼─────────────────────────┼──────────────┼─────┤
│ 300.50 ₽     │ 100                     │ 300.60 ₽     │ 150 │
│ 300.45 ₽     │ 200                     │ 300.65 ₽     │ 120 │
│ 300.40 ₽     │ 150                     │ 300.70 ₽     │ 180 │
└──────────────┴─────────────────────────┴──────────────┴─────┘
```

**JSON вывод:**
```json
{
  "ticker": "SBER",
  "figi": "BBG004730N88",
  "bids": [
    {"price": "300.50", "quantity": 100},
    {"price": "300.45", "quantity": 200}
  ],
  "asks": [
    {"price": "300.60", "quantity": 150},
    {"price": "300.65", "quantity": 120}
  ]
}
```

---

## 26. 📈 `trading-status` — Статус торгов инструментом

Показывает текущий статус торгов для инструмента (открыт/закрыт, тип торгов).

**Параметры:**
- `ticker` — тикер или FIGI инструмента
- `--json` — вывод в JSON формате

```bash
# Статус торгов для SBER
tcli trading-status SBER

# JSON вывод
tcli trading-status GAZP --json
```

**Вывод:**
```
Статус торгов: SBER (BBG004730N88)
  Статус: NORMAL_TRADING
  Ограничения: нет
  API торгов: включены
```

**JSON вывод:**
```json
{
  "ticker": "SBER",
  "figi": "BBG004730N88",
  "trading_status": "NORMAL_TRADING",
  "limit_types": "NONE",
  "api_trade_available": true
}
```

---

## 27. 📅 `sessions` — Расписание торговых сессий

Показывает расписание торговых сессий для биржи.

**Параметры:**
- `--exchange` (опциональный) — код биржи (по умолчанию MOEX)
- `--days` (опциональный) — количество дней вперёд (по умолчанию 7)
- `--json` — вывод в JSON формате

```bash
# Расписание MOEX на 7 дней
tcli sessions

# Расписание для SPBEX на 14 дней
tcli sessions --exchange SPBEX --days 14

# JSON вывод
tcli sessions --json
```

**Вывод:**
```
Расписание торговых сессий (MOEX, 2024-01-15 - 2024-01-21)
┌────────────┬───────────────────┬───────────────────┐
│ Дата       │ Начало            │ Окончание         │
├────────────┼───────────────────┼───────────────────┤
│ 2024-01-15 │ 10:00:00          │ 23:50:00          │
│ 2024-01-16 │ 10:00:00          │ 23:50:00          │
│ 2024-01-17 │ 10:00:00          │ 23:50:00          │
└────────────┴───────────────────┴───────────────────┘
```

**JSON вывод:**
```json
{
  "exchange": "MOEX",
  "sessions": [
    {
      "date": "2024-01-15",
      "start": "2024-01-15T10:00:00+03:00",
      "end": "2024-01-15T23:50:00+03:00"
    }
  ]
}
```

---

## 28. 🔄 `close` — Закрытие позиции рыночной заявкой

Закрывает открытую позицию по инструменту рыночной заявкой.

**Параметры:**
- `ticker` — тикер или FIGI инструмента
- `--yes`, `-y` — пропустить подтверждение
- `--no-prompt` — неинтерактивный режим
- `--json` — вывод в JSON формате

```bash
# Закрыть позицию по SBER (с подтверждением)
tcli close SBER

# Закрыть без подтверждения
tcli close GAZP --yes

# Неинтерактивный режим
tcli close LKOH --no-prompt

# JSON вывод
tcli close SBER --yes --json
```

**Вывод:**
```
Закрытие позиции: SBER (10 лотов)
Заявка выставлена: order_id=123456789
```

**JSON вывод:**
```json
{
  "ticker": "SBER",
  "figi": "BBG004730N88",
  "lots": 10,
  "order_id": "123456789"
}
```

---

## 29. 🔄 `close-all` — Закрытие всех открытых позиций

Закрывает все открытые позиции рыночными заявками.

**Параметры:**
- `--yes`, `-y` — пропустить подтверждение
- `--no-prompt` — неинтерактивный режим
- `--json` — вывод в JSON формате

```bash
# Закрыть все позиции (с подтверждением)
tcli close-all

# Закрыть без подтверждения
tcli close-all --yes

# Неинтерактивный режим
tcli close-all --no-prompt

# JSON вывод
tcli close-all --yes --json
```

**Вывод:**
```
Закрытие всех позиций (3)
✓ SBER: 10 лотов (order_id=123456789)
✓ GAZP: 5 лотов (order_id=123456790)
✓ LKOH: 2 лота (order_id=123456791)
```

**JSON вывод:**
```json
{
  "closed": [
    {"ticker": "SBER", "lots": 10, "order_id": "123456789"},
    {"ticker": "GAZP", "lots": 5, "order_id": "123456790"},
    {"ticker": "LKOH", "lots": 2, "order_id": "123456791"}
  ]
}
```

---

## 30. ❌ `cancel-all` — Отмена всех открытых заявок

Отменяет все открытые заявки для текущего счёта.

**Параметры:**
- `--yes`, `-y` — пропустить подтверждение
- `--no-prompt` — неинтерактивный режим
- `--json` — вывод в JSON формате

```bash
# Отменить все заявки (с подтверждением)
tcli cancel-all

# Отменить без подтверждения
tcli cancel-all --yes

# Неинтерактивный режим
tcli cancel-all --no-prompt

# JSON вывод
tcli cancel-all --yes --json
```

**Вывод:**
```
Отмена всех заявок (2)
✓ Заявка 123456789 отменена
✓ Заявка 123456790 отменена
```

**JSON вывод:**
```json
{
  "cancelled": ["123456789", "123456790"]
}
```

---

## 31. ℹ️ `order-info` — Информация о заявке

Показывает детальную информацию о заявке по ID.

**Параметры:**
- `order_id` — ID заявки
- `--json` — вывод в JSON формате

```bash
# Информация о заявке
tcli order-info 123456789

# JSON вывод
tcli order-info 123456789 --json
```

**Вывод:**
```
Заявка: 123456789
  Тикер: SBER
  FIGI: BBG004730N88
  Направление: BUY
  Статус: EXECUTED
  Количество: 10
  Исполнено: 10
  Цена: 300.50 ₽
  Дата: 2024-01-15 10:30:45
```

**JSON вывод:**
```json
{
  "order_id": "123456789",
  "ticker": "SBER",
  "figi": "BBG004730N88",
  "direction": "BUY",
  "status": "EXECUTED",
  "lots_requested": 10,
  "lots_executed": 10,
  "price": "300.50",
  "date": "2024-01-15T10:30:45+03:00"
}
```

---

## 32. 📋 `stop-order-list` — Список стоп-заявок

Показывает список активных стоп-заявок.

**Параметры:**
- `--json` — вывод в JSON формате

```bash
# Список стоп-заявок
tcli stop-order-list

# JSON вывод
tcli stop-order-list --json
```

**Вывод:**
```
Стоп-заявки (2)
┌────────────┬────────┬───────────┬──────────┬──────────┬──────────┐
│ ID         │ Тикер  │ Направление│ Стоп-цена│ Количество│ Статус   │
├────────────┼────────┼───────────┼──────────┼──────────┼──────────┤
│ 123456789  │ SBER   │ SELL      │ 290.00 ₽ │ 10       │ ACTIVE   │
│ 123456790  │ GAZP   │ BUY       │ 160.00 ₽ │ 5        │ ACTIVE   │
└────────────┴────────┴───────────┴──────────┴──────────┴──────────┘
```

**JSON вывод:**
```json
[
  {
    "stop_order_id": "123456789",
    "ticker": "SBER",
    "direction": "SELL",
    "stop_price": "290.00",
    "quantity": 10,
    "status": "ACTIVE"
  }
]
```

---

## 33. ❌ `stop-order-cancel` — Отмена стоп-заявки

Отменяет стоп-заявку по ID.

**Параметры:**
- `stop_order_id` — ID стоп-заявки
- `--yes`, `-y` — пропустить подтверждение
- `--no-prompt` — неинтерактивный режим
- `--json` — вывод в JSON формате

```bash
# Отменить стоп-заявку (с подтверждением)
tcli stop-order-cancel 123456789

# Отменить без подтверждения
tcli stop-order-cancel 123456789 --yes

# Неинтерактивный режим
tcli stop-order-cancel 123456789 --no-prompt

# JSON вывод
tcli stop-order-cancel 123456789 --yes --json
```

**Вывод:**
```
Стоп-заявка 123456789 отменена
```

**JSON вывод:**
```json
{
  "stop_order_id": "123456789",
  "cancelled": true
}
```

---

## 34. 💰 `free-cash` — Свободные средства на счёте

Показывает свободные средства на текущем счёте.

**Параметры:**
- `--json` — вывод в JSON формате

```bash
# Свободные средства
tcli free-cash

# JSON вывод
tcli free-cash --json
```

**Вывод:**
```
Свободные средства: 100 000.00 ₽
```

**JSON вывод:**
```json
{
  "free_cash": "100000.00",
  "currency": "RUB"
}
```

---

## 35. ✅ `has-position` — Проверка наличия позиции

Проверяет наличие открытой позиции по инструменту.

**Параметры:**
- `ticker` — тикер или FIGI инструмента
- `--json` — вывод в JSON формате

```bash
# Проверить наличие позиции по SBER
tcli has-position SBER

# JSON вывод
tcli has-position SBER --json
```

**Вывод:**
```
Позиция SBER: ДА (10 лотов)
```

**JSON вывод:**
```json
{
  "ticker": "SBER",
  "has_position": true,
  "quantity": 10
}
```

---

## 36. 🏦 `is-market-open` — Проверка статуса рынка

Проверяет, открыт ли рынок для торгов по инструменту.

**Параметры:**
- `ticker` — тикер или FIGI инструмента
- `--json` — вывод в JSON формате

```bash
# Проверить статус рынка для SBER
tcli is-market-open SBER

# JSON вывод
tcli is-market-open SBER --json
```

**Вывод:**
```
Рынок SBER: ОТКРЫТ
```

**JSON вывод:**
```json
{
  "ticker": "SBER",
  "market_open": true
}
```

---

## 37. 🛑 `stop-order-place` — Размещение стоп-заявки

Размещает стоп-заявку для защиты позиции. Стоп-заявка активируется при достижении стоп-цены и исполняется как рыночная или лимитная заявка.

**Параметры:**
- `ticker` — тикер или FIGI инструмента
- `lots` — количество лотов
- `--stop-price` — стоп-цена активации (обязательный)
- `--price` — лимитная цена исполнения (опционально, по умолчанию рыночная)
- `--direction` — направление: BUY или SELL (обязательный)
- `--yes`, `-y` — пропустить подтверждение
- `--no-prompt` — неинтерактивный режим
- `--json` — вывод в JSON формате

```bash
# Разместить стоп-лосс на продажу SBER при цене 280₽
tcli stop-order-place SBER 10 --stop-price 280 --direction SELL

# Стоп-заявка с лимитной ценой исполнения
tcli stop-order-place SBER 10 --stop-price 280 --price 279.50 --direction SELL

# Без подтверждения
tcli stop-order-place SBER 10 --stop-price 280 --direction SELL --yes

# Неинтерактивный режим
tcli stop-order-place SBER 10 --stop-price 280 --direction SELL --no-prompt

# JSON вывод
tcli stop-order-place SBER 10 --stop-price 280 --direction SELL --json
```

**Вывод:**
```
Стоп-заявка (SELL): SBER × 10 лот(ов)
  Счёт: Main
  Стоп-цена: 280.00 ₽
  Цена исполнения: рыночная после активации
  Контур: SANDBOX

стоп-заявка размещена
  stop_order_id: 123456789
  figi: BBG004730N88
```

**JSON вывод:**
```json
{
  "stop_order_id": "123456789",
  "ticker": "SBER",
  "figi": "BBG004730N88",
  "direction": "SELL",
  "lots": 10,
  "stop_price": "280.00",
  "price": "market"
}
```

**Примечание:**
- Стоп-заявки используются для установки стоп-лоссов
- При активации стоп-заявки создаётся обычная заявка
- Без указания `--price` заявка исполняется по рыночной цене
- С `--price` создаётся лимитная заявка после активации стопа

---

## 38. ❌ `stop-order-cancel-all` — Отмена всех стоп-заявок

Отменяет все активные стоп-заявки одним вызовом. Полезно для массовой очистки стоп-лоссов перед изменением стратегии или закрытием позиций.

**Параметры:**
- `--yes`, `-y` — пропустить подтверждение
- `--no-prompt` — неинтерактивный режим
- `--json` — вывод в JSON формате

```bash
# Отменить все стоп-заявки (с подтверждением)
tcli stop-order-cancel-all

# Отменить без подтверждения
tcli stop-order-cancel-all --yes

# Неинтерактивный режим
tcli stop-order-cancel-all --no-prompt

# JSON вывод
tcli stop-order-cancel-all --yes --json
```

**Вывод:**
```
Отмена всех стоп-заявок: 3 шт.
  Счёт: Main
  Контур: SANDBOX

отменено стоп-заявок: 3 из 3
  ✓ 123456789
  ✓ 123456790
  ✓ 123456791
```

**JSON вывод:**
```json
{
  "cancelled_count": 3,
  "cancelled_ids": ["123456789", "123456790", "123456791"]
}
```

**Примечание:**
- Команда отменяет все активные стоп-заявки для текущего счёта
- Если активных стоп-заявок нет, выводит сообщение "активных стоп-заявок нет"
- Возвращает количество успешно отменённых заявок
- Рекомендуется использовать `--yes` для автоматизации

---

## 🔧 Глобальные флаги

### `--json` — JSON вывод

Большинство команд с выводом данных поддерживают флаг `--json` для структурированного вывода:

**Основные команды:**
- `status --json`
- `positions --json`
- `orders --json`
- `quote --json`
- `candles --json`
- `find --json`
- `info --json`
- `instruments --json`
- `watchlist --json`

**P0 команды (стакан, статусы, заявки):**
- `orderbook --json`
- `trading-status --json`
- `sessions --json`
- `order-info --json`
- `stop-order-list --json`

**P0 команды (управление позициями):**
- `close --json`
- `close-all --json`
- `cancel-all --json`
- `stop-order-cancel --json`
- `free-cash --json`
- `has-position --json`
- `is-market-open --json`

### `--no-prompt` — Неинтерактивный режим

Команды с подтверждениями поддерживают флаг `--no-prompt` для работы в скриптах:

**Основные команды:**
- `change-mode live --no-prompt`
- `order-buy SBER 1 --no-prompt`
- `order-sell SBER 1 --no-prompt`
- `account-rm Main --no-prompt`

**P0 команды:**
- `close SBER --no-prompt`
- `close-all --no-prompt`
- `cancel-all --no-prompt`
- `stop-order-cancel ID --no-prompt`

### `--yes`, `-y` — Пропустить подтверждение

Альтернатива `--no-prompt` для некоторых команд:

**Основные команды:**
- `change-mode live --yes`
- `order-buy SBER 1 --yes`
- `order-sell SBER 1 --yes`
- `account-rm Main --yes`

**P0 команды:**
- `close SBER --yes`
- `close-all --yes`
- `cancel-all --yes`
- `stop-order-cancel ID --yes`

---

## 🔑 Архитектура токенов

**ВАЖНО:** Токены не взаимозаменяемы — каждый работает только в своём контуре.

- **SANDBOX** → использует `INVEST_SANDBOX_TOKEN` (свои счета песочницы)
- **LIVE** → использует `INVEST_TOKEN` (боевые счета)

При переключении контура через `tcli change-mode` токен выбирается автоматически.

---

## 📦 Установка

Требуется Python 3.10+.

```bash
# Создание виртуального окружения
python3 -m venv .venv
source .venv/bin/activate

# Установка зависимостей
pip install -r requirements.txt

# Установка SDK (пакет удалён с PyPI, ставится из git)
pip install --no-deps "tinkoff-investments @ git+https://github.com/RussianInvestments/invest-python.git@0.2.0-beta117"

# Установка приложения (консольная команда tcli)
pip install -e .
```

---

## ⚙️ Настройка

Скопируйте `.env.example` в `.env` и заполните:

```bash
# Токен для LIVE контура (боевой)
INVEST_TOKEN=your_live_token_here

# Токен для SANDBOX контура (песочница)
INVEST_SANDBOX_TOKEN=your_sandbox_token_here

# Имя счёта (если счетов несколько)
SANDBOX_ACCOUNT_NAME=Main

# Контур (SANDBOX или LIVE)
TCLI_CONTOUR=SANDBOX
```

Проверка:

```bash
tcli check
```

---

## 🔐 Сертификат НУЦ Минцифры

API Tinkoff использует цепочку сертификатов ГУ «НУЦ Минцифры России», которой нет в стандартном хранилище Mozilla. Без неё gRPC падает с `CERTIFICATE_VERIFY_FAILED`.

Файл `certs/russian-trusted-root.pem` подкладывается автоматически при импорте пакета `tcli` (переменная `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH`) — отдельных действий не требуется.

---

## 🛠️ Разработка

```bash
# Линтер
ruff check .

# Тесты (без сети, на моках)
pytest

# Альтернативный запуск без установки скрипта
python -m tcli --help
```

---

## 📁 Структура проекта

```
tcli/
├── cli.py              # typer-команды (24 команды)
├── client.py           # Broker: поддержка SANDBOX/LIVE, ретраи, универсальный поиск
├── config.py           # .env → Settings, контуры, маскировка токена
├── render.py           # таблицы rich (включая watchlist и info)
├── ssl.py              # подкладка корня НУЦ в gRPC
├── watchlist_utils.py  # утилиты для работы с избранным (watchlist.json)
└── id_utils.py         # утилиты для определения типов ID

skills/
├── __init__.py         # экспорты всех функций
├── base.py             # базовая инфраструктура (run_tcli_command)
├── market_data.py      # рыночные данные (котировки, свечи, портфель)
├── trading.py          # торговые операции (заявки)
├── account.py          # управление счетами
└── analytics.py        # аналитика и инструменты

tests/
├── test_cli.py         # тесты CLI
├── test_client.py      # тесты клиента
├── test_config.py      # тесты конфигурации
└── test_new_features.py # тесты новых функций
```

---

## 🤖 Skills модуль (Python API для торгового агента)

Модуль `skills/` предоставляет высокоуровневый Python API для взаимодействия с `tcli`. Все функции автоматически вызывают соответствующие команды `tcli` с флагами `--json` и `--no-prompt`.

### Пример использования

```python
from skills import get_quote, place_order, get_portfolio

# Получение котировки
quote = get_quote('SBER')
print(quote['price'])  # '285.50'

# Получение портфеля
portfolio = get_portfolio()
for pos in portfolio['positions']:
    print(f"{pos['ticker']}: {pos['quantity']} @ {pos['current_price']}")

# Размещение заявки
result = place_order('SBER', 'buy', 1, price=285.50)
print(result['order_id'])
```

### Основные функции

**Market Data:**
- `get_quote(ticker)` — текущая цена
- `get_candles(ticker, interval, days)` — история свечей
- `get_portfolio()` — позиции портфеля
- `get_status()` — счета и сводка
- `get_orders()` — активные заявки

**Trading:**
- `place_order(ticker, side, quantity, price)` — разместить заявку
- `cancel_order(order_id)` — отменить заявку
- `get_order_info(order_id)` — информация о заявке

**Account:**
- `get_accounts()` — список счетов
- `select_account(account_id)` — выбрать счёт
- `get_current_account()` — текущий счёт
- `get_account_info(account_id)` — информация о счёте

**Analytics:**
- `search_instruments(query)` — поиск инструментов
- `get_instrument_info(ticker)` — информация об инструменте
- `add_to_watchlist(ticker)` — добавить в избранное
- `remove_from_watchlist(ticker)` — удалить из избранного
- `get_watchlist()` — список избранного

---

## ⚠️ Ограничения

- **Бэктестов, стратегий и LLM нет** — это осознанный минимум.
- **В режиме LIVE** некоторые операции недоступны (создание/удаление счёта, пополнение) — они выполняются через приложение Т-Банка.
- **В песочнице** FIGI может отображаться как внутренний UID (TCS*) — это особенность API песочницы.
- **Метод `reset`** отсутствует в `tinkoff-investments 0.2.0-beta117` — используйте приложение Т-Банка для закрытия/открытия счёта.

---

## 📝 Лицензия

MIT

---

## 🙏 Благодарности

- [Tinkoff Invest API](https://github.com/Tinkoff/investAPI) — официальный API Т-Инвестиций
- [invest-python](https://github.com/RussianInvestments/invest-python) — Python SDK для Tinkoff Invest API

---

**Версия:** 1.0.0  
**Последнее обновление:** Ноябрь 2026
