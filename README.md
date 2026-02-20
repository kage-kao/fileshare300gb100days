# GigaFile.nu Telegram Bot & Proxy API

Telegram-бот + веб-интерфейс для загрузки, скачивания и проксирования файлов через [GigaFile.nu](https://gigafile.nu/) (до 300 ГБ, до 100 дней хранения).

## Возможности

### Telegram Bot
- **GigaFile ссылка** -> мгновенно получить 3 типа ссылок (страница, прямая, прокси)
- **Любой URL** -> скачать и перезалить на GigaFile -> 3 ссылки
- **Файл/документ** -> загрузить на GigaFile -> 3 ссылки (до 20 МБ через Telegram API)
- Выбор срока хранения: 3, 5, 7, 14, 30, 60, 100 дней
- Мультиязычность: EN, RU, ES, DE, FR, ZH, JA, PT (автоопределение по Telegram)
- Inline-кнопки для удобной навигации
- Отмена операций через `/cancel`

### Web API
- `POST /api/upload` - загрузка файла или URL на GigaFile
- `GET /api/proxy?url=...` - проксирование скачивания с GigaFile (без куки)

### Web-интерфейс
- Drag & Drop загрузка файлов
- Загрузка по URL
- Выбор срока хранения
- Прокси-скачивание без куки
- Мультиязычный интерфейс

## Архитектура

```
Backend (FastAPI + aiogram 3)
├── server.py           # FastAPI + webhook endpoint + proxy + upload API
├── bot.py              # Telegram bot handlers (aiogram 3)
├── gigafile_client.py  # GigaFile.nu async client (оптимизированный)
├── i18n.py             # Мультиязычная поддержка
└── .env                # Конфигурация

Frontend (React)
├── src/App.js          # UI компоненты
└── src/App.css         # Стили
```

## Оптимизации производительности

- **Параллельная загрузка чанков** - до 4 одновременных потоков на GigaFile
- **Увеличенный размер чанков** - 50 МБ (вместо 10 МБ) для меньшего числа запросов
- **Кэширование сервера** - номер сервера GigaFile кэшируется на 5 минут
- **Защита от зависаний** - `sock_read` таймаут 120с для обнаружения остановки передачи данных
- **Retry-логика** - до 3 повторных попыток для чанков и скачивания с экспоненциальной задержкой
- **Увеличенный буфер чтения** - 2 МБ для скачивания
- **Прогресс без Content-Length** - корректное отображение прогресса даже когда сервер не отправляет размер файла

## Настройка

### Переменные окружения (.env)

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=test_database
CORS_ORIGINS=*
TELEGRAM_BOT_TOKEN=your_bot_token_here
BACKEND_URL=https://your-domain.com
```

### Установка зависимостей

```bash
# Backend
cd backend
pip install -r requirements.txt

# Frontend
cd frontend
yarn install
```

### Запуск

```bash
# Backend (FastAPI + Uvicorn)
cd backend
uvicorn server:app --host 0.0.0.0 --port 8001

# Frontend (React)
cd frontend
yarn start
```

## Telegram Bot - Команды

| Команда | Описание |
|---------|----------|
| `/start` | Приветственное сообщение |
| `/help` | Справка по использованию |
| `/cancel` | Отменить текущую операцию |
| `/lang` | Выбрать язык |

## API Использование

### Загрузка файла
```bash
curl -X POST -F "file=@yourfile.zip" -F "duration=100" https://your-domain.com/api/upload
```

### Загрузка по URL
```bash
curl -X POST -F "url=https://example.com/file.zip" -F "duration=7" https://your-domain.com/api/upload
```

### Прокси-скачивание
```bash
curl -L -O -J "https://your-domain.com/api/proxy?url=https://XX.gigafile.nu/XXXX-hash"
```

## Технологии

- **Backend:** Python, FastAPI, aiogram 3, aiohttp, MongoDB (Motor)
- **Frontend:** React, Axios
- **File hosting:** GigaFile.nu API
- **Deployment:** Heroku / любой сервер с Python 3.11+

## Лицензия

MIT
