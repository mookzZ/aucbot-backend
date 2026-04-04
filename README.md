# AUC BOT — Backend

## Структура
```
main.py              — FastAPI app + scheduler + bot
bot.py               — /start handler
app/
  config.py          — настройки из .env
  database.py        — async SQLAlchemy session
  models.py          — таблицы: users, items, alerts
  routers/api.py     — все HTTP эндпоинты
  services/
    stalcraft.py     — обёртка над Stalcraft API
    auth.py          — валидация Telegram initData
    worker.py        — проверка алертов каждые 30 сек
scripts/
  sync_items.py      — синхронизация предметов из GitHub репо
```

## Запуск

### 1. Настрой окружение
```bash
cp .env.example .env
# заполни .env
```

### 2. Установи зависимости
```bash
pip install -r requirements.txt
```

### 3. Синхронизируй предметы (один раз)
```bash
python scripts/sync_items.py
```

### 4. Запусти сервер
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API эндпоинты

Все запросы (кроме `/regions`, `/health`) требуют заголовок:
```
X-Init-Data: <Telegram WebApp initData>
```

| Метод | URL | Описание |
|-------|-----|----------|
| GET | /api/regions | Список регионов |
| GET | /api/users/me | Получить юзера |
| POST | /api/users/me | Создать/обновить юзера (регион) |
| GET | /api/items/search?q=... | Поиск предмета |
| GET | /api/auction/{item_id}/lots | Активные лоты |
| GET | /api/auction/{item_id}/history | История цен |
| GET | /api/alerts | Мои алерты |
| POST | /api/alerts | Создать алерт |
| DELETE | /api/alerts/{id} | Удалить алерт |
