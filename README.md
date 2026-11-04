# tcli

CLI-инструмент для **Tinkoff Invest API**. Поддерживает работу с **песочницей (SANDBOX)** и **боевым контуром (LIVE)**.

## Возможности

### Базовые команды

| Команда | Описание |
| --- | --- |
| `tcli check` | Самопроверка: `.env`, сертификат НУЦ, доступ к API |
| `tcli change-mode sandbox` | Переключить на песочницу |
| `tcli change-mode live` | Переключить на боевой контур (требует подтверждения) |
| `tcli status` | Счета и сводка портфеля (деньги, бумаги, P&L) |
| `tcli positions` | Позиции: тикер, количество, средняя/текущая цена, P&L |
| `tcli orders` | Активные заявки |
| `tcli payin <сумма>` | Пополнить счёт песочницы (рубли, только SANDBOX) |

### Управление счетами

| Команда | Описание |
| --- | --- |
| `tcli account-list` | Список всех счетов |
| `tcli account-new [имя]` | Создать новый счёт (только SANDBOX) |
| `tcli account-rm <имя\|id>` | Удалить счёт (только SANDBOX) |
| `tcli account-show <имя\|id>` | Показать детали счёта |

### Торговые операции

| Команда | Описание |
| --- | --- |
| `tcli order-buy <тикер> <лоты> [--price <цена>]` | Купить инструмент |
| `tcli order-sell <тикер> <лоты> [--price <цена>]` | Продать инструмент |
| `tcli order-cancel <order_id>` | Отменить заявку |

**`order-buy`** — покупка акций, облигаций, ETF или фьючерсов.
Без `--price` выставляется рыночная заявка (исполнение по текущей цене биржи).
С `--price` — лимитная заявка (исполнение только по указанной цене или лучше).
Перед исполнением запрашивает подтверждение (отключается через `--yes`).

```bash
# Купить 1 лот Сбер по рыночной цене
tcli order-buy SBER 1

# Купить 10 лотов Сбер лимитной заявкой по 290 ₽
tcli order-buy SBER 10 --price 290
```

**`order-sell`** — продажа инструмента из портфеля. Аналогично:
рыночная или лимитная заявка, подтверждение перед исполнением.

```bash
# Продать 5 лотов Сбер по рыночной цене
tcli order-sell SBER 5

# Продать 5 лотов Сбер не дешевле 310 ₽
tcli order-sell SBER 5 --price 310
```

**`order-cancel`** — отмена ранее выставленной заявки по её `order_id`.
ID заявки можно узнать через `tcli orders`.

```bash
tcli order-cancel 12345678-abcd-efgh-1234-567890abcdef
```

### Рыночные данные и история

| Команда | Описание |
| --- | --- |
| `tcli ops [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--ticker ТИКЕР]` | История операций |
| `tcli quote <тикер>` | Текущая цена инструмента |
| `tcli candles <тикер> [--interval 1min\|5min\|15min\|1hour\|1day] [--days N]` | История свечей |
| `tcli find <запрос>` | Поиск инструментов по тикеру/названию/ISIN |

**`ops`** — история операций по счёту: покупки, продажи, зачисление денег,
дивиденды, купоны, удержания комиссий. Фильтрация по дате и тикеру.

```bash
# Все операции с начала года
tcli ops --from 2026-01-01

# Операции по Сберу за ноябрь
tcli ops --from 2026-11-01 --to 2026-11-30 --ticker SBER
```

**`quote`** — последняя цена инструмента на бирже.

```bash
tcli quote SBER
# SBER (FIGI: BBG004730N88)
#   Последняя цена: 300.50 ₽
#   Время: 2026-11-03 18:50:00
```

**`candles`** — исторические свечи OHLCV (Open/High/Low/Close/Volume)
для технического анализа. Интервалы: 1min, 5min, 15min, 1hour, 1day.

```bash
# Дневные свечи за 90 дней
tcli candles SBER --interval 1day --days 90

# Часовые свечи за 5 дней
tcli candles SBER --interval 1hour --days 5

# Пятиминутные свечи за 1 день
tcli candles SBER --interval 5min --days 1
```

**`find`** — поиск инструментов по тикеру, названию или ISIN.
Возвращает таблицу с тикером, FIGI, названием, типом и классом инструмента.

```bash
tcli find Сбер
tcli find SBER
tcli find RU000A0JSKN0
```

### Дополнительные возможности

| Команда | Описание |
| --- | --- |
| `tcli export <тип> [--format csv\|json] [--output файл]` | Экспорт данных в CSV/JSON |
| `tcli watchlist [add\|remove\|list] [тикер]` | Управление избранными инструментами |
| `tcli account-select` | Интерактивный выбор активного счёта |
| `tcli info <тикер\|figi\|uid>` | Детальная информация об инструменте |

**`export`** — экспорт позиций, операций или заявок в CSV или JSON формат.
Удобно для анализа в Excel или других инструментах.

```bash
# Экспорт текущих позиций в CSV
tcli export positions --format csv --output positions.csv

# Экспорт операций за год в JSON
tcli export operations --format json --from 2026-01-01 --output ops.json

# Экспорт активных заявок в CSV
tcli export orders --format csv --output orders.csv
```

**`watchlist`** — управление списком отслеживаемых инструментов (избранное).
Список хранится в `~/.tcli/watchlist.json` и сохраняется между сессиями.

```bash
# Добавить инструмент в избранное
tcli watchlist add SBER
tcli watchlist add GAZP

# Показать текущие цены всех избранных инструментов
tcli watchlist list

# Удалить инструмент из избранного
tcli watchlist remove SBER
```

**`account-select`** — интерактивный выбор активного счёта.
Показывает список всех доступных счетов и сохраняет выбор в `.env`.

```bash
tcli account-select
# Доступные счета:
#   1. Основной (2001234567)
#   2. ИИС (2007654321)
# Выберите номер счёта: 1
# выбран счёт: Основной
# сохранено в .env как SANDBOX_ACCOUNT_NAME
```

**`info`** — детальная информация об инструменте.
Поддерживает поиск по тикеру, FIGI или внутреннему UID Т-Банка.

```bash
# Информация по тикеру
tcli info SBER

# Информация по FIGI
tcli info BBG004730N88

# Информация по UID Т-Банка
tcli info TCS019029540
```

Показывает: название, FIGI, ISIN, тип инструмента, валюту, лотность, биржу, класс, статус торгов.

### Универсальный поиск инструментов

Команды `tcli info`, `tcli quote`, `tcli candles` и другие поддерживают **универсальный поиск** через метод `find_instrument_smart()`, который автоматически определяет тип идентификатора:

- **FIGI** (формат `BBG*`) — поиск через `instrument_by_figi()`
- **UID/TCS** (внутренние ID Т-Банка, формат `TCS*` или длинные ID) — поиск через `instrument_by_uid()`
- **Тикеры** (всё остальное) — поиск через `instrument_by_ticker()` с fallback через `find_instrument()`

Это означает что вы можете использовать любой из этих идентификаторов в командах, и tcli автоматически найдёт нужный инструмент.

## Режимы работы

### Контуры (TCLI_CONTOUR)

- **SANDBOX** (по умолчанию) — работа с песочницей через `sandbox-invest-public-api.tinkoff.ru`
- **LIVE** — работа с боевым контуром через `invest-public-api.tinkoff.ru`

Переключение требует ввода кода `LIVE` для подтверждения.

### Токены

- **SANDBOX** — используется `INVEST_SANDBOX_TOKEN` (только для песочницы)
- **LIVE** — используется `INVEST_TOKEN` (только для боевого контура)

Токены не взаимозаменяемы — каждый работает только в своём контуре.

## Установка

Требуется Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate

# Шаг 1: рантайм-зависимости SDK + приложение
pip install -r requirements.txt

# Шаг 2: сам SDK (пакет удалён с PyPI, ставится из git без его зависимостей —
# они уже установлены на шаге 1)
pip install --no-deps "tinkoff-investments @ git+https://github.com/RussianInvestments/invest-python.git@0.2.0-beta117"

# Установка приложения (консольная команда tcli)
pip install -e .
```

## Настройка

Скопируйте `.env.example` в `.env` и заполните:

- `INVEST_TOKEN` — токен T-Invest (полный доступ).
  Создаётся в [настройках Т-Инвестиций](https://invest.tbank.ru/settings/token).
- `INVEST_SANDBOX_TOKEN` — альтернативный токен (используется если `TCLI_TOKEN=sandbox`).
- `SANDBOX_ACCOUNT_NAME` — имя счёта, если счетов несколько (необязательно).
- `TCLI_CONTOUR` — режим работы: `SANDBOX` или `LIVE` (по умолчанию `SANDBOX`).
- `TCLI_TOKEN` — какой токен использовать: `main` или `sandbox` (по умолчанию `main`).

Проверка:

```bash
tcli check
```

## Сертификат НУЦ Минцифры

API Tinkoff использует цепочку сертификатов ГУ «НУЦ Минцифры России», которой нет
в стандартном хранилище Mozilla. Без неё gRPC падает с `CERTIFICATE_VERIFY_FAILED`.
Файл `certs/russian-trusted-root.pem` подкладывается автоматически при импорте
пакета `tcli` (переменная `GRPC_DEFAULT_SSL_ROOTS_FILE_PATH`) — отдельных действий
не требуется.

## Разработка

```bash
ruff check .          # линтер
pytest                # тесты (без сети, на моках)
python -m tcli --help # альтернативный запуск без установки скрипта
```

## Структура

```
tcli/
├── cli.py              # typer-команды (24 команды)
├── client.py           # Broker: поддержка SANDBOX/LIVE, ретраи, универсальный поиск
├── config.py           # .env → Settings, контуры, маскировка токена
├── render.py           # таблицы rich (включая watchlist и info)
├── ssl.py              # подкладка корня НУЦ в gRPC
└── watchlist_utils.py  # утилиты для работы с избранным (watchlist.json)

skills/
├── __init__.py         # экспорты всех функций
├── base.py             # базовая инфраструктура (run_tcli_command)
├── market_data.py      # рыночные данные (котировки, свечи, портфель)
├── trading.py          # торговые операции (заявки)
├── account.py          # управление счетами
└── analytics.py        # аналитика и инструменты
```

## Skills модуль (Python API для торгового агента)

Модуль `skills/` предоставляет высокоуровневый Python API для взаимодействия с `tcli`. Все функции принимают Python-словари и возвращают структурированные данные, автоматически вызывая соответствующие команды `tcli` с флагами `--json` и `--no-prompt`.

### Установка и использование

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

### Функции по категориям

#### Market Data (рыночные данные)

```python
from skills import get_quote, get_candles, get_portfolio, get_status, get_orders

# Текущая цена инструмента
quote = get_quote('SBER')
# Возвращает: {'ticker': str, 'figi': str, 'price': str, 'time': str}

# История свечей
candles = get_candles('SBER', interval='1hour', days=7)
# Возвращает: {'ticker': str, 'interval': str, 'days': int, 'candles': list[dict]}
# Каждая свеча: {'time': str, 'open': str, 'high': str, 'low': str, 'close': str, 'volume': int}

# Позиции портфеля
portfolio = get_portfolio()
# Возвращает: {'positions': list[dict]}
# Каждая позиция: {'ticker': str, 'figi': str, 'quantity': str, 'average_price': str, 
#                   'current_price': str, 'value': str, 'pnl': str, 'pnl_percent': str}

# Статус счетов и сводка портфеля
status = get_status()
# Возвращает: {'contour': str, 'accounts': list[dict], 'portfolio': dict}

# Активные заявки
orders = get_orders()
# Возвращает: {'orders': list[dict]}
```

#### Trading (торговые операции)

```python
from skills import place_order, cancel_order, get_order_info

# Размещение заявки (лимитная)
result = place_order('SBER', 'buy', 1, price=285.50)
# Возвращает: {'order_id': str, 'figi': str, 'status': str}

# Размещение заявки (рыночная)
result = place_order('SBER', 'sell', 1)  # без price
# Возвращает: {'order_id': str, 'figi': str, 'status': str}

# Отмена заявки
result = cancel_order('12345')
# Возвращает: {'status': 'cancelled', 'order_id': str}

# Информация о заявке
order = get_order_info('12345')
# Возвращает: {'order_id': str, 'ticker': str, 'direction': str, 'quantity': str, 
#               'price': str, 'status': str, 'created_at': str}
```

#### Account (управление счетами)

```python
from skills import get_accounts, select_account, get_current_account, get_account_info

# Список всех счетов
accounts = get_accounts()
# Возвращает: {'accounts': list[dict]}
# Каждый счет: {'id': str, 'name': str, 'type': str, 'status': str}

# Выбор активного счета
result = select_account('account-name')
# Возвращает: {'status': 'selected', 'account_id': str, 'account_name': str}

# Текущий активный счет
current = get_current_account()
# Возвращает: {'account_id': str, 'account_name': str}

# Информация о счете
info = get_account_info('account-id')
# Возвращает: {'id': str, 'name': str, 'type': str, 'status': str, 'portfolio': dict}
```

#### Analytics (аналитика и инструменты)

```python
from skills import (
    search_instruments, get_instrument_info, 
    get_instrument_by_figi, get_instrument_by_isin,
    search_by_type, get_watchlist, 
    add_to_watchlist, remove_from_watchlist
)

# Поиск инструментов
results = search_instruments('SBER')
# Возвращает: {'instruments': list[dict]}
# Каждый инструмент: {'ticker': str, 'figi': str, 'name': str, 'type': str, 'class_code': str}

# Информация об инструменте
info = get_instrument_info('SBER')
# Возвращает: {'ticker': str, 'figi': str, 'name': str, 'isin': str, 
#               'lot': int, 'currency': str, 'type': str, 'exchange': str}

# Поиск по FIGI
info = get_instrument_by_figi('BBG004730N88')
# Возвращает: {'ticker': str, 'figi': str, 'name': str, ...}

# Поиск по ISIN
info = get_instrument_by_isin('RU000A0ZY7C3')
# Возвращает: {'ticker': str, 'figi': str, 'name': str, ...}

# Поиск по типу инструмента
results = search_by_type('share')
# Возвращает: {'instruments': list[dict]}

# Список отслеживаемых инструментов
watchlist = get_watchlist()
# Возвращает: {'watchlist': list[dict]}
# Каждый элемент: {'ticker': str, 'figi': str, 'added_at': str}

# Добавить в watchlist
result = add_to_watchlist('SBER')
# Возвращает: {'status': 'added', 'ticker': str}

# Удалить из watchlist
result = remove_from_watchlist('SBER')
# Возвращает: {'status': 'removed', 'ticker': str}
```

### Обработка ошибок

Все функции могут выбрасывать исключение `TcliError` при ошибке выполнения команды:

```python
from skills import get_quote
from skills.base import TcliError

try:
    quote = get_quote('INVALID_TICKER')
except TcliError as e:
    print(f"Ошибка: {e.message}")
    print(f"Код ошибки: {e.exit_code}")
```

### Особенности реализации

- Все функции автоматически добавляют флаги `--json` и `--no-prompt` к командам
- Таймаут выполнения: 30 секунд
- Работает только в неинтерактивном режиме (без подтверждений)
- Возвращает только структурированные данные (JSON)
- Все цены и суммы возвращаются как строки (для точности)

### Интеграция с торговым агентом

Модуль `skills/` разработан для интеграции с торговым агентом. Все функции:

1. **Детерминированы** — одинаковые входные данные дают одинаковый результат
2. **Безопасны** — требуют явного подтверждения только для опасных операций
3. **Структурированы** — возвращают Python-словари вместо текста
4. **Логируются** — все операции записываются в структурированные JSON логи

Пример полного торгового сценария:

```python
from skills import get_quote, place_order, get_portfolio

# Анализ
quote = get_quote('SBER')
current_price = float(quote['price'])

# Торговое решение (упрощённо)
if current_price < 280.0:
    # Покупка
    result = place_order('SBER', 'buy', 1, price=279.50)
    print(f"Заявка размещена: {result['order_id']}")

# Проверка портфеля
portfolio = get_portfolio()
for pos in portfolio['positions']:
    pnl_percent = float(pos['pnl_percent'])
    if pnl_percent > 10.0:
        print(f"{pos['ticker']}: прибыль {pnl_percent}%")
```

## Ограничения

- Бэктестов, стратегий и LLM нет — это осознанный минимум.
- В режиме LIVE некоторые операции недоступны (создание/удаление счёта, пополнение) — они выполняются через приложение Т-Банка.
- В песочнице FIGI может отображаться как внутренний UID (TCS*) — это особенность API песочницы.
