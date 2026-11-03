# tcli

CLI-инструмент для **Tinkoff Invest API**. Работает **только с песочницей (SANDBOX)** —
боевой контур в коде не используется и недоступен по построению.

## Возможности

| Команда | Описание |
| --- | --- |
| `tcli check` | Самопроверка: `.env`, сертификат НУЦ, доступ к API песочницы |
| `tcli status` | Счета песочницы и сводка портфеля (деньги, бумаги, P&L) |
| `tcli positions` | Позиции: тикер, количество, средняя/текущая цена, P&L |
| `tcli orders` | Активные заявки песочницы |
| `tcli payin <сумма>` | Пополнить счёт песочницы (рубли) |
| `tcli reset` | Сброс песочницы (недоступен в текущем SDK — см. сообщение) |

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

- `INVEST_TOKEN` — токен T-Invest (полный доступ; работает и в песочнице).
  Создаётся в [настройках Т-Инвестиций](https://invest.tbank.ru/settings/token).
- `INVEST_SANDBOX_TOKEN` — запасной токен, используется, если `INVEST_TOKEN` пуст.
- `SANDBOX_ACCOUNT_NAME` — имя счёта, если песочниц несколько (необязательно).

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
├── cli.py      # typer-команды
├── client.py   # SandboxClient: ретраи, классификация ошибок, выбор счёта
├── config.py   # .env → Settings, маскировка токена
├── ssl.py      # подкладка корня НУЦ в gRPC
└── render.py   # таблицы rich
```

## Ограничения

- Только песочница: все операции идут через `SandboxClient` (sandbox-хост API).
- Бэктестов, стратегий и LLM нет — это осознанный минимум.
- Рыночные данные и заявки в живом контуре не используются.
