# Отчёт по tcli: что надо исправить

**Репозиторий:** https://github.com/metrag/tcli (MIT)
**Проверено на коммите:** `315dfad fix(watchlist): разделить логику поиска инструмента и получения цены`
**Окружение проверки:** VPS Ubuntu 26.04, Python 3.13.18, `tinkoff-investments 0.2.0b117`, контур SANDBOX, счёт «Скальп» (10 000 ₽ виртуальных).
**Дата:** 2026-11-04

Статусы: **[FIXED]** — патч применён, **[OPEN]** — не исправлено, **[DESIGN]** — вопрос дизайна, **[PLATFORM]** — ограничение биржи/SDK, не баг tcli.

---

## Критические (ломают работу)

### 1. **[OPEN]** `GetInstrumentBy` без `class_code` → `INVALID_ARGUMENT 30013`

**Симптом:**
```
$ tcli quote SBER
080d1a5add447307008b0743525c638b GetInstrumentBy INVALID_ARGUMENT 30013
SBER (FIGI: TCS019029540)
  Последняя цена: 0 ₽
  Время: 1970-01-01 00:00:00+00:00
```

**Причина (ответ сервера, verbatim):**
```
`class_code` require for `id_type` = `ticker`
```


### 2. **[OPEN]** Фолбэк по тикеру выбирает класс без рыночных данных

**Симптом:** цена `0 ₽`, время `1970-01-01`, при этом команда «успешна» (exit 0).

**Причина:** один тикер существует в нескольких классах — `TQBR`, `SMAL`, `SPEQ`, `37M` и др.
Старый код возвращал **первое точное совпадение** из `find_instrument`:

```python
instruments = self.find_instrument(ticker)
for inst in instruments:
    if getattr(inst, "ticker", "") == ticker:
        return inst
```

Для SBER первым приходил псевдо-FIGI `TCS019029540` класса `37M` **без данных по котировкам**.
Получается худший вид ошибки: команда отработала, а данных нет — молча.


## Ломают скрипты / автоматизацию

### 3. [OPEN] `positions --json` падает

```
$ tcli positions --json
Ошибка: TypeError: Object of type Quotation is not JSON serializable
```

Причина: в рендерере объект `Quotation` (protobuf) уходит в `json.dumps` как есть.

### 4. [OPEN] `orders --json` падает

```
$ tcli orders --json
Ошибка: TypeError: Object of type MoneyValue is not JSON serializable
```

Тот же класс дефекта, что и №3. `status --json` при этом работает.

**Общий фикс для №3–4:** ввести единый сериализатор protobuf-типов
(`Quotation`, `MoneyValue`, `Timestamp`, `Decimal`) — одна функция `to_jsonable()`,
применяемая на выходе всех `--json`-команд. Сейчас `--json` у позиций и заявок
фактически недоступен, а это основной способ потребления данных из скриптов.

---

### 5. [OPEN] У `order-cancel` нет флага `--no-prompt` / `--yes`

```
$ tcli order-cancel <id> --no-prompt
exit=2   # неизвестный опция
```

При этом `order-buy` / `order-sell` этот флаг **принимают**.
Для автоматизации (движок отменяет лимитки по расписанию в 18:35 / 23:50)
это блокер: команда требует интерактивного подтверждения.

**Фикс:** добавить `--yes/--no-prompt` в `order-cancel`, как в `order-buy`.
То же проверить у `account-rm` (он закрывает позиции и заявки — подтверждение там оправдано,
но флаг для скриптов нужен).

---

## Дизайнерские проблемы (важно для нашей архитектуры)

### 6. [DESIGN] `change-mode` и `account-select` мутят общий `.env`

Обе команды пишут через `dotenv.set_key` в `ENV_PATH = PROJECT_ROOT / ".env"`:

| Команда | Ключ | Файл |
|---|---|---|
| `change-mode` | `TCLI_CONTOUR` | `tcli/cli.py` (`set_env_value("TCLI_CONTOUR", ...)`) |
| `account-select` | `SANDBOX_ACCOUNT_NAME` | `tcli/cli.py:1201` |

**Опасность:** `.env` — это ещё и хранилище токенов. Любая команда, меняющая контур,
перезаписывает файл целиком (`dotenv.set_key`). Два процесса, работающих с одним профилем,
могут затереть токены друг друга.

**Что делаем в проекте:** два физически изолированных профиля (`~/tcli-manual`, `~/tcli-bot`),
каждый со своим `.env` (mode 600). В профиле бота `change-mode`/`account-select` **запрещены**.

**Рекомендация для tcli:** вынести контур/счёт в отдельный файл состояния
(например. `~/.config/tcli/state.json`) и не трогать `.env` с токенами.

---

### 7. [DESIGN] `account-select` пишет `SANDBOX_ACCOUNT_NAME` даже в LIVE

`account-select` безусловно пишет `SANDBOX_ACCOUNT_NAME` — ветки на контур нет.
Если выполнить в `TCLI_CONTOUR=LIVE`, ключ с «sandbox» в имени молча устанавливает
боевой счёт. Название ключа вводит в заблуждение (см. №8).

---

### 8. [DESIGN] В LIVE нет отдельной переменной счёта

`Broker.pick_account()` (`tcli/client.py`) **не ветвится по контуру** — он всегда читает
`Settings.sandbox_account_name`:

```python
name = self._settings.sandbox_account_name
if name:
    matched = [a for a in accounts if a.name == name]
    ...
if len(accounts) == 1:
    return accounts[0]
available = ", ".join(a.name or a.id for a in accounts)
raise AmbiguousAccountError(
    f"несколько счетов — задайте SANDBOX_ACCOUNT_NAME в .env; варианты: {available}"
)
```

`grep -rn "ACCOUNT_NAME\|ACCOUNT_ID\|LIVE_ACCOUNT" tcli/*.py` → 3 совпадения, все `SANDBOX_ACCOUNT_NAME`.
**`INVEST_ACCOUNT_ID` / `ACCOUNT_ID` не существуют.**

Следствия:
- ключ один и тот же для обоих контуров (имя невезучее, но это так);
- **автовыбор «единственного счёта» ненадёжен** — как только в LIVE появится второй счёт,
  поведение молча изменится. Мы **пиним счёт явно**: `SANDBOX_ACCOUNT_NAME=Скальп`.

**Рекомендация:** ввести `ACCOUNT_NAME` (общий) и оставить `SANDBOX_ACCOUNT_NAME`
как алиас с предупреждением о депрекации; убрать автовыбор при `len(accounts)==1`
в пользу явной ошибки.

---

### 9. [DESIGN] Токены контуров не взаимозаменяемы — легко перепутать

```python
# tcli/config.py
sandbox_token = (values.get("INVEST_SANDBOX_TOKEN") or "").strip()
main_token    = (values.get("INVEST_TOKEN") or "").strip()
...
@property
def token(self) -> str:
    return self.sandbox_token if self.contour == Contour.SANDBOX else self.main_token
```

Проверено на практике: подставление LIVE-токена в SANDBOX-контур (и наоборот) даёт
```
GetAccounts UNAUTHENTICATED 40003 — Authentication token is missing or invalid
```
Ошибку выдаёт сервер, выглядит как «токен битый», хотя на самом деле он от другого контура.

**Рекомендация:** `tcli check` должен на шаге `[4/4]` при 40003 явно писать
«проверьте, что токен от контура X, а не Y», а не «токен недействителен или отозван».

---

## Ограничения платформы (не баги tcli, но критично для плана)

### 10. [PLATFORM] Лимиты истории свечей в SANDBOX

| Интервал | Максимум (SANDBOX) |
|---|---|
| **1min** | **1 день** (2 дня → `30014`) |
| 5min | ~7 дней |
| 15min | ~6 дней |
| 1hour | ~90 дней |
| 1day | ~85 дней |

**Следствие для Фазы 3 (бэктест):** накопить 1min-историю через SANDBOX **невозможно**.
Варианты: (а) пагинация day-by-day, (б) LIVE-контур (другие лимиты), (в) внешний источник
MOEX. Решение вынести в задачу Фазы 3.

### 11. [PLATFORM] Лимит цены заявки ≈ −3.6% от последней

```
30099 "The price is outside the limits for this instrument"
```
253.50 (−13%) и 280.00 отклонены; рабочая глубина — **281.00** при bid 290.04.
Для стопов и «глубоких» лимиток это ограничение надо учитывать в `execution.py`.

### 12. [PLATFORM] Часть классов запрещена для торгов через API

```
30052 "Instrument forbidden for trading by API"   (класс SMAL у GAZP)
```
Псевдо-FIGI `TCS*` классов `SMAL/SPEQ/37M` возвращают устаревшие или нулевые котировки.
**Всегда требовать `class_code=TQBR`.**

### 13. [PLATFORM] В SANDBOX нет `reset`

Метод `reset` отсутствует в SDK `0.2.0-beta117` (в README tcli это отмечено).
Сбросить песочницу нельзя — для повторных экспериментов нужен отдельный счёт
(`account-new`, но это уже изменение состояния).

### 14. [PLATFORM] SDK старше сервера

Бенign-лог при работе: `unknown enum InstrumentType=11`.
`protobuf` зажат `<5` в `requirements.txt` — на Python 3.14 это ещё и фатально
(см. ниже), на 3.13 работает.

---

## Проблемы окружения (не tcli, но заблокировало установку)

### 15. [OPEN] Python 3.14 несовместим с `protobuf 4.25.9`

```
File ".../google/protobuf/internal/api_implementation.py", line 41, in _CanImport
    mod = importlib.import_module(mod_name)
File "/usr/lib/python3.14/importlib/__init__.py", line 88, in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
TypeError: Metaclasses with custom tp_new are not supported.
```

Причина: `protobuf-4.25.9` (пин `>=4.25.1,<5` в `requirements.txt`) тянет `upb` C-расширение
`cp37-abi3`, чей трюк с метаклассом CPython 3.14 отвергает.
Установка пакетов при этом **проходит** — падает только запуск.

В Ubuntu 26.04 в репозиториях **только Python 3.14** (`apt-cache policy python3.12/3.13/3.11`
→ нет кандидатов). Решение, применённое у нас: `uv` + **CPython 3.13.18** в
`/home/operator/.local`, системный Python не тронут.

**Рекомендация tcli:** объявить `requires-python = ">=3.10,<3.14"` или поднять пин `protobuf` до 5.x.

### 16. [OPEN] `pip install -e .` требует отдельного шага для SDK

README предписывает:
```
pip install -r requirements.txt
pip install --no-deps "tinkoff-investments @ git+https://github.com/RussianInvestments/invest-python.git@0.2.0-beta117"
pip install -e .
```
SDK не в `requirements.txt` — шаг легко пропустить, ошибка тогда невнятная
(`ModuleNotFoundError: No module named 'tinkoff'`).
**Рекомендация:** добавить SDK в `requirements.txt` или в `[project.dependencies]` `pyproject.toml`.
