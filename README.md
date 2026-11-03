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

### Рыночные данные и история

| Команда | Описание |
| --- | --- |
| `tcli ops [--from YYYY-MM-DD] [--to YYYY-MM-DD]` | История операций |
| `tcli quote <тикер>` | Последние цены инструмента |
| `tcli candles <тикер> [--interval 1min\|5min\|15min\|1hour\|1day] [--days N]` | История свечей |
| `tcli find <запрос>` | Поиск инструментов по тикеру/названию |

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
├── cli.py      # typer-команды (19 команд)
├── client.py   # Broker: поддержка SANDBOX/LIVE, ретраи, классификация ошибок
├── config.py   # .env → Settings, Contour/TokenMode, маскировка токена
├── ssl.py      # подкладка корня НУЦ в gRPC
└── render.py   # таблицы rich
```

## Ограничения

- Бэктестов, стратегий и LLM нет — это осознанный минимум.
- В режиме LIVE некоторые операции недоступны (создание/удаление счёта, пополнение) — они выполняются через приложение Т-Банка.
