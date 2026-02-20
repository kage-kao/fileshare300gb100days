# GigaFile便 (gigafile.nu) — Полная техническая документация API

**Версия:** 2.0  
**Дата:** Февраль 2026  
**Автор:** Reverse Engineering Documentation

---

## Содержание

1. [Общая информация о сервисе](#1-общая-информация-о-сервисе)
2. [Архитектура и серверы](#2-архитектура-и-серверы)
3. [API Endpoints — Полный список](#3-api-endpoints--полный-список)
4. [Загрузка файлов (Upload API)](#4-загрузка-файлов-upload-api)
5. [Скачивание файлов (Download API)](#5-скачивание-файлов-download-api)
6. [Получение прямой ссылки на скачивание](#6-получение-прямой-ссылки-на-скачивание)
7. [Удаление файлов (Delete API)](#7-удаление-файлов-delete-api)
8. [Проверка пароля (DLKey API)](#8-проверка-пароля-dlkey-api)
9. [Объединение файлов в ZIP (Matomete)](#9-объединение-файлов-в-zip-matomete)
10. [Отслеживание прогресса](#10-отслеживание-прогресса)
11. [Антивирусная проверка](#11-антивирусная-проверка)
12. [Жалоба на файл (Report API)](#12-жалоба-на-файл-report-api)
13. [Email уведомления](#13-email-уведомления)
14. [Структура страницы скачивания (Парсинг HTML)](#14-структура-страницы-скачивания-парсинг-html)
15. [Лимиты и ограничения](#15-лимиты-и-ограничения)
16. [Примеры кода](#16-примеры-кода)
17. [CLI инструменты](#17-cli-инструменты)
18. [Cookies и сессии](#18-cookies-и-сессии)
19. [Обработка ошибок](#19-обработка-ошибок)
20. [Правовая информация](#20-правовая-информация)

---

## 1. Общая информация о сервисе

### Описание
**GigaFile便 (ギガファイル便)** — бесплатный японский файлообменный сервис для передачи больших файлов без регистрации.

### Основные характеристики

| Параметр | Значение |
|----------|----------|
| **Официальный сайт** | https://gigafile.nu/ |
| **Компания** | 株式会社ギガファイル (GigaFile Inc.) |
| **Регистрация** | Не требуется |
| **Максимальный размер файла** | 300 ГБ (300G) |
| **Максимальное количество файлов** | Без ограничений |
| **Срок хранения** | 3, 5, 7, 14, 30, 60, 100 дней |
| **Пароль** | 4 символа (a-z, 0-9) |
| **Антивирусная проверка** | Да |
| **HTTPS** | Да |

### Дополнительные возможности
- ✅ Drag & Drop загрузка (включая целые папки)
- ✅ Защита паролем для скачивания
- ✅ Защита паролем для удаления (Delete Key)
- ✅ Email уведомления о скачивании
- ✅ Объединение нескольких файлов в ZIP
- ✅ QR-код для ссылки
- ✅ Сертификация файлов (для правообладателей)
- ✅ Проверка прогресса скачивания
- ✅ WEB-альбомы (GigaFile FLY)

---

## 2. Архитектура и серверы

### Структура URL

```
https://{SERVER_NUMBER}.gigafile.nu/{FILE_ID}
```

- **SERVER_NUMBER** — номер сервера (например: 60, 66, 95, 99)
- **FILE_ID** — формат: `{MMDD}-{32-символьный-hash}`

### Получение номера сервера

При загрузке файла сервер определяется динамически. Номер извлекается из главной страницы:

```javascript
// В HTML https://gigafile.nu/ найти:
var server = "XX.gigafile.nu";
```

**Python пример:**
```python
import re
import requests

response = requests.get('https://gigafile.nu/')
server = re.search(r'var server = "(.+?)"', response.text).group(1)
# Результат: "60.gigafile.nu" или подобное
```

### Формат FILE_ID

```
{MMDD}-{HASH}

Где:
- MMDD = месяц и день (например: 0530 для 30 мая)
- HASH = 32 символа hex (a-f, 0-9)

Пример: 0530-b529348ab72d51706f22da1e7ed1910c2
```

---

## 3. API Endpoints — Полный список

### Основные endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/` | GET | Главная страница (получение server ID) |
| `/upload_chunk.php` | POST | Загрузка чанка файла |
| `/download.php` | GET | **Прямое скачивание файла** |
| `/check_dlkey.php` | GET | Проверка пароля скачивания |
| `/remove.php` | GET | Удаление файла |
| `/get_download_prog.php` | GET | Прогресс скачивания |
| `/get_av_status.php` | GET | Статус антивирусной проверки |
| `/tsuho_file.php` | POST | Жалоба на незаконный файл |
| `/report.php` | GET | Форма жалобы |
| `/bypass_dl.php` | GET | Альтернативное скачивание (bypass) |

### Дополнительные endpoints

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/support.php` | GET | Страница поддержки/FAQ |
| `/privacy.php` | GET | Политика конфиденциальности |
| `/contact-us.php` | GET | Форма обратной связи |
| `/optout.php` | GET | Настройки cookies |

---

## 4. Загрузка файлов (Upload API)

### Алгоритм загрузки

```
1. GET https://gigafile.nu/ → Извлечь "var server" из HTML
2. Сгенерировать уникальный token (UUID v1 без дефисов)
3. Разбить файл на чанки (рекомендуется 10-100 МБ)
4. Последовательно/параллельно: POST /upload_chunk.php для каждого чанка
5. Из последнего ответа получить URL скачивания
```

### POST /upload_chunk.php

**URL:** `https://{server}/upload_chunk.php`

**Content-Type:** `multipart/form-data`

**Параметры формы:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `id` | string | ✅ | Уникальный token (UUID v1 hex, 32 символа) |
| `name` | string | ✅ | Имя файла (с расширением) |
| `chunk` | string | ✅ | Номер текущего чанка (начиная с 0) |
| `chunks` | string | ✅ | Общее количество чанков |
| `lifetime` | string | ✅ | Срок хранения: `3`, `5`, `7`, `14`, `30`, `60`, `100` |
| `file` | binary | ✅ | Данные чанка (Content-Type: application/octet-stream) |

### Пример запроса cURL

```bash
# Генерация UUID
TOKEN=$(python3 -c "import uuid; print(uuid.uuid1().hex)")

# Загрузка файла одним чанком
curl -X POST "https://60.gigafile.nu/upload_chunk.php" \
  -F "id=${TOKEN}" \
  -F "name=document.pdf" \
  -F "chunk=0" \
  -F "chunks=1" \
  -F "lifetime=100" \
  -F "file=@document.pdf;type=application/octet-stream"
```

### Ответ API

**Успешная загрузка промежуточного чанка:**
```json
{
    "status": 0
}
```

**Успешная загрузка последнего чанка:**
```json
{
    "status": 0,
    "url": "https://60.gigafile.nu/0530-b529348ab72d51706f22da1e7ed1910c2"
}
```

**Ошибка:**
```json
{
    "status": 1,
    "error": "Error description"
}
```

### Важные замечания

1. **Первый чанк** должен быть загружен отдельно для установки cookies
2. **Последующие чанки** могут загружаться параллельно (до 8 потоков)
3. **Порядок** чанков важен — они должны обрабатываться последовательно на сервере
4. **Рекомендуемый размер чанка:** 10 МБ для надёжности, до 100 МБ для скорости

---

## 5. Скачивание файлов (Download API)

### Типы URL

GigaFile предоставляет два типа URL:

| Тип | Формат | Описание |
|-----|--------|----------|
| **Страница** | `https://XX.gigafile.nu/{file_id}` | HTML страница с информацией и кнопкой |
| **Прямая ссылка** | `https://XX.gigafile.nu/download.php?file={file_id}` | Прямое скачивание файла |

### GET /download.php

**URL:** `https://{server}/download.php`

**Параметры:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `file` | string | ✅ | ID файла (например: `0530-abc123...`) |
| `dlkey` | string | ❌ | Пароль скачивания (4 символа) |
| `dlnotify` | string | ❌ | `0` — отключить уведомление о скачивании |

### Примеры

```bash
# Без пароля
curl -L -O -J "https://60.gigafile.nu/download.php?file=0530-b529348ab72d51706f22da1e7ed1910c2"

# С паролем
curl -L -O -J "https://60.gigafile.nu/download.php?file=0530-b529348ab72d51706f22da1e7ed1910c2&dlkey=1234"

# Без уведомления владельцу
curl -L -O -J "https://60.gigafile.nu/download.php?file=0530-xxx&dlnotify=0"
```

### Headers ответа

```http
HTTP/1.1 200 OK
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="original_filename.ext"
Content-Length: 12345678
```

---

## 6. Получение прямой ссылки на скачивание

### Формула преобразования

```
Страница скачивания:  https://XX.gigafile.nu/{file_id}
Прямая ссылка:        https://XX.gigafile.nu/download.php?file={file_id}
```

### Примеры

**Вход:**
```
https://60.gigafile.nu/0530-b529348ab72d51706f22da1e7ed1910c2
```

**Выход (прямая ссылка):**
```
https://60.gigafile.nu/download.php?file=0530-b529348ab72d51706f22da1e7ed1910c2
```

### Код преобразования

**Python:**
```python
def get_direct_download_url(page_url, password=None):
    """
    Преобразует URL страницы GigaFile в прямую ссылку на скачивание.
    
    Args:
        page_url: URL страницы (https://XX.gigafile.nu/XXXX-hash)
        password: Пароль для скачивания (опционально)
    
    Returns:
        Прямая ссылка на скачивание
    """
    parts = page_url.rsplit('/', 1)
    base_url = parts[0]
    file_id = parts[1]
    
    direct_url = f"{base_url}/download.php?file={file_id}"
    
    if password:
        direct_url += f"&dlkey={password}"
    
    return direct_url

# Примеры использования
page = "https://60.gigafile.nu/0530-b529348ab72d51706f22da1e7ed1910c2"

# Без пароля
print(get_direct_download_url(page))
# https://60.gigafile.nu/download.php?file=0530-b529348ab72d51706f22da1e7ed1910c2

# С паролем
print(get_direct_download_url(page, "1234"))
# https://60.gigafile.nu/download.php?file=0530-b529348ab72d51706f22da1e7ed1910c2&dlkey=1234
```

**JavaScript:**
```javascript
function getDirectDownloadUrl(pageUrl, password = null) {
    const lastSlash = pageUrl.lastIndexOf('/');
    const baseUrl = pageUrl.substring(0, lastSlash);
    const fileId = pageUrl.substring(lastSlash + 1);
    
    let directUrl = `${baseUrl}/download.php?file=${fileId}`;
    
    if (password) {
        directUrl += `&dlkey=${encodeURIComponent(password)}`;
    }
    
    return directUrl;
}
```

**Bash:**
```bash
#!/bin/bash
PAGE_URL="https://60.gigafile.nu/0530-b529348ab72d51706f22da1e7ed1910c2"
FILE_ID="${PAGE_URL##*/}"
BASE_URL="${PAGE_URL%/*}"
DIRECT_URL="${BASE_URL}/download.php?file=${FILE_ID}"

echo "Прямая ссылка: $DIRECT_URL"

# Скачивание
curl -L -O -J "$DIRECT_URL"

# С aria2 (многопоточно)
aria2c "$DIRECT_URL"

# С wget
wget "$DIRECT_URL"
```

---

## 7. Удаление файлов (Delete API)

### GET /remove.php

**URL:** `https://{server}/remove.php`

**Параметры:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `file` | string | ✅ | ID файла |
| `delkey` | string | ✅ | Ключ удаления (4 символа: a-z, 0-9) |

### Пример запроса

```bash
curl "https://60.gigafile.nu/remove.php?file=0530-abc123...&delkey=abcd"
```

### Ответ

**Успех:**
```json
{
    "status": 0
}
```

**Ошибка (неверный ключ):**
```json
{
    "status": 1
}
```

### Важно
- Delete Key генерируется при загрузке файла
- Delete Key **НЕ** восстанавливается — если потеряли, ждите автоудаления
- Формат: 4 символа `[a-zA-Z0-9]`

---

## 8. Проверка пароля (DLKey API)

### GET /check_dlkey.php

Проверяет правильность пароля **перед** скачиванием.

**URL:** `https://{server}/check_dlkey.php`

**Параметры:**

| Параметр | Тип | Обязательный | Описание |
|----------|-----|--------------|----------|
| `file` | string | ✅ | ID файла |
| `dlkey` | string | ✅ | Пароль для проверки |
| `is_zip` | int | ❌ | `0` — обычный файл, `1` — ZIP архив |

### Пример

```bash
curl "https://60.gigafile.nu/check_dlkey.php?file=0530-abc123...&dlkey=1234&is_zip=0"
```

### Коды ответа

| status | Описание |
|--------|----------|
| `0` | Пароль верный |
| `1` | Пароль неверный |
| `3` | Превышен лимит попыток (заблокировано) |

---

## 9. Объединение файлов в ZIP (Matomete)

### Функция "まとめる" (Matomete)

Позволяет объединить несколько загруженных файлов в один ZIP-архив.

**Элементы интерфейса:**
- `#zip_file_name` — имя ZIP файла
- `#zip_dlkey` — пароль для ZIP (4 символа)
- `#matomete_btn` — кнопка объединения
- `#matomete_url` — результирующий URL

### Страница с множественными файлами

При скачивании нескольких файлов страница содержит:
- `#contents_matomete` — контейнер
- `.matomete_file` — каждый файл
- `.matomete_file_info` — информация о файле

---

## 10. Отслеживание прогресса

### GET /get_download_prog.php

Отслеживание прогресса скачивания в реальном времени.

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `file` | string | ID файла |
| `key` | string | Уникальный ключ сессии (из cookie `prog_key`) |

### Ответ

```json
{
    "status": 0,
    "prog": 45
}
```

- `prog` — процент скачивания (0-100)

---

## 11. Антивирусная проверка

### GET /get_av_status.php

Проверка статуса антивирусного сканирования файла.

### Индикаторы на странице
- `#av_status` — статус проверки
- При проверке отображается: "ウイルスチェック中です" (Проверка на вирусы...)
- Анимированный GIF: `av_stat.gif`

---

## 12. Жалоба на файл (Report API)

### POST /tsuho_file.php

Отправка жалобы на незаконный файл.

**Параметры:**

| Параметр | Тип | Описание |
|----------|-----|----------|
| `file` | string | ID файла |

### Форма жалобы

```
GET /report.php?host={server}&uri={file_id}
```

---

## 13. Email уведомления

### Функции email

1. **Отправка информации о загрузке** — отправляет URL, имя файла, Delete Key
2. **Уведомление о скачивании** — оповещает когда файл скачан

### Элементы интерфейса
- `#email_addr` — email адрес
- `#memoarea` — заметка/сообщение
- `#send_email` — кнопка отправки
- `#dlnotify_set_btn` — включить уведомления о скачивании

### Ограничения
- Можно вводить **только свой** email адрес
- Множественные адреса не поддерживаются

---

## 14. Структура страницы скачивания (Парсинг HTML)

### CSS селекторы для парсинга

| Селектор | Содержимое |
|----------|------------|
| `#dl` | Имя файла |
| `.dl_size` | Размер файла (например: "18.96KB") |
| `.download_term_value` | Дата истечения |
| `#dlkey` | Поле ввода пароля |
| `.download_panel_btn_dl` | Кнопка скачивания |

### Для множественных файлов (Matomete)

| Селектор | Содержимое |
|----------|------------|
| `#contents_matomete` | Контейнер множественных файлов |
| `.matomete_file` | Каждый файл |
| `.matomete_file_info > span:nth-child(2)` | Имя файла |
| `.matomete_file_info > span:nth-child(3)` | Размер (в скобках) |

### Извлечение file_id из onclick

```javascript
// В атрибуте onclick кнопки:
onclick="download('0530-abc123...', false, false);"

// Regex для извлечения:
/download\(\d+, *'(.+?)'/
```

### Python пример парсинга

```python
from bs4 import BeautifulSoup
import requests
import re

def parse_download_page(url):
    """Парсит страницу скачивания GigaFile"""
    session = requests.Session()
    response = session.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    files = []
    
    # Проверка на множественные файлы
    if soup.select_one('#contents_matomete'):
        for elem in soup.select('.matomete_file'):
            name = elem.select_one('.matomete_file_info > span:nth-child(2)').text.strip()
            size_text = elem.select_one('.matomete_file_info > span:nth-child(3)').text.strip()
            size = re.search(r'（(.+?)）', size_text).group(1)
            onclick = elem.select_one('.download_panel_btn_dl')['onclick']
            file_id = re.search(r"download\(\d+, *'(.+?)'", onclick).group(1)
            files.append({'name': name, 'size': size, 'file_id': file_id})
    else:
        # Одиночный файл
        file_id = url.split('/')[-1]
        name = soup.select_one('#dl').text.strip()
        size = soup.select_one('.dl_size').text.strip()
        files.append({'name': name, 'size': size, 'file_id': file_id})
    
    return files
```

---

## 15. Лимиты и ограничения

### Технические лимиты

| Параметр | Значение |
|----------|----------|
| Максимальный размер файла | 300 ГБ |
| Максимальное количество файлов | Без ограничений |
| Длина пароля (dlkey) | 4 символа |
| Длина ключа удаления (delkey) | 4 символа |
| Символы пароля | a-z, A-Z, 0-9 |
| Минимальный срок хранения | 3 дня |
| Максимальный срок хранения | 100 дней |
| Рекомендуемый размер чанка | 10-100 МБ |
| Рекомендуемое количество потоков | 4-8 |

### Сроки хранения

| Значение lifetime | Период |
|-------------------|--------|
| `3` | 3 дня |
| `5` | 5 дней |
| `7` | 7 дней |
| `14` | 14 дней |
| `30` | 30 дней |
| `60` | 60 дней |
| `100` | 100 дней |

### Время удаления
- Файлы удаляются **после полуночи** (JST) следующего дня после истечения срока
- Не в момент истечения времени, а при ночной очистке

---

## 16. Примеры кода

### Python — Полная реализация

```python
import requests
import uuid
import math
import re
import os
from pathlib import Path

class GigaFileClient:
    """Клиент для работы с GigaFile API"""
    
    def __init__(self, chunk_size=10*1024*1024, threads=4):
        self.session = requests.Session()
        self.chunk_size = chunk_size
        self.threads = threads
        self.server = None
    
    def _get_server(self):
        """Получить текущий сервер"""
        if not self.server:
            resp = self.session.get('https://gigafile.nu/')
            match = re.search(r'var server = "(.+?)"', resp.text)
            self.server = match.group(1)
        return self.server
    
    def upload(self, filepath, lifetime=100):
        """
        Загрузить файл на GigaFile
        
        Args:
            filepath: Путь к файлу
            lifetime: Срок хранения (3, 5, 7, 14, 30, 60, 100)
        
        Returns:
            URL страницы скачивания
        """
        server = self._get_server()
        token = uuid.uuid1().hex
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        total_chunks = math.ceil(filesize / self.chunk_size)
        
        result = None
        
        with open(filepath, 'rb') as f:
            for chunk_no in range(total_chunks):
                chunk_data = f.read(self.chunk_size)
                
                files = {
                    'file': ('blob', chunk_data, 'application/octet-stream')
                }
                data = {
                    'id': token,
                    'name': filename,
                    'chunk': str(chunk_no),
                    'chunks': str(total_chunks),
                    'lifetime': str(lifetime)
                }
                
                resp = self.session.post(
                    f'https://{server}/upload_chunk.php',
                    files=files,
                    data=data
                )
                response_data = resp.json()
                
                if 'url' in response_data:
                    result = response_data['url']
                
                print(f"Чанк {chunk_no + 1}/{total_chunks} загружен")
        
        return result
    
    def get_direct_url(self, page_url, password=None):
        """Получить прямую ссылку на скачивание"""
        parts = page_url.rsplit('/', 1)
        base_url = parts[0]
        file_id = parts[1]
        
        direct_url = f"{base_url}/download.php?file={file_id}"
        if password:
            direct_url += f"&dlkey={password}"
        
        return direct_url
    
    def download(self, url, output_path=None, password=None):
        """
        Скачать файл
        
        Args:
            url: URL страницы или прямая ссылка
            output_path: Путь для сохранения (опционально)
            password: Пароль (опционально)
        """
        # Если это страница — преобразовать в прямую ссылку
        if '/download.php' not in url:
            url = self.get_direct_url(url, password)
        elif password and 'dlkey=' not in url:
            url += f"&dlkey={password}"
        
        resp = self.session.get(url, stream=True)
        resp.raise_for_status()
        
        # Получить имя файла
        if not output_path:
            cd = resp.headers.get('Content-Disposition', '')
            match = re.search(r'filename="(.+?)"', cd)
            output_path = match.group(1) if match else 'downloaded_file'
        
        # Скачать
        total_size = int(resp.headers.get('Content-Length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=1024*1024):
                f.write(chunk)
                downloaded += len(chunk)
                if total_size:
                    print(f"Скачано: {downloaded}/{total_size} ({downloaded*100//total_size}%)")
        
        return output_path
    
    def delete(self, url, delete_key):
        """
        Удалить файл
        
        Args:
            url: URL страницы или file_id
            delete_key: Ключ удаления (4 символа)
        """
        if '/' in url:
            file_id = url.split('/')[-1]
            server = url.split('/')[2]
        else:
            file_id = url
            server = self._get_server()
        
        resp = self.session.get(
            f'https://{server}/remove.php',
            params={'file': file_id, 'delkey': delete_key}
        )
        return resp.json()['status'] == 0
    
    def check_password(self, url, password):
        """Проверить пароль без скачивания"""
        if '/' in url:
            file_id = url.split('/')[-1]
            server = url.split('/')[2]
        else:
            file_id = url
            server = self._get_server()
        
        resp = self.session.get(
            f'https://{server}/check_dlkey.php',
            params={'file': file_id, 'dlkey': password, 'is_zip': 0}
        )
        return resp.json()['status'] == 0


# Примеры использования
if __name__ == "__main__":
    client = GigaFileClient()
    
    # Загрузка
    url = client.upload('myfile.pdf', lifetime=100)
    print(f"Загружено: {url}")
    
    # Получение прямой ссылки
    direct = client.get_direct_url(url)
    print(f"Прямая ссылка: {direct}")
    
    # Скачивание
    client.download(url, 'downloaded.pdf')
```

### JavaScript/Node.js

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');
const path = require('path');
const { v1: uuidv1 } = require('uuid');

class GigaFileClient {
    constructor() {
        this.server = null;
    }
    
    async getServer() {
        if (!this.server) {
            const resp = await axios.get('https://gigafile.nu/');
            const match = resp.data.match(/var server = "(.+?)"/);
            this.server = match[1];
        }
        return this.server;
    }
    
    async upload(filepath, lifetime = 100) {
        const server = await this.getServer();
        const token = uuidv1().replace(/-/g, '');
        const filename = path.basename(filepath);
        const stats = fs.statSync(filepath);
        const filesize = stats.size;
        const chunkSize = 10 * 1024 * 1024;
        const totalChunks = Math.ceil(filesize / chunkSize);
        
        const fileBuffer = fs.readFileSync(filepath);
        let result = null;
        
        for (let i = 0; i < totalChunks; i++) {
            const start = i * chunkSize;
            const end = Math.min(start + chunkSize, filesize);
            const chunk = fileBuffer.slice(start, end);
            
            const form = new FormData();
            form.append('id', token);
            form.append('name', filename);
            form.append('chunk', i.toString());
            form.append('chunks', totalChunks.toString());
            form.append('lifetime', lifetime.toString());
            form.append('file', chunk, {
                filename: 'blob',
                contentType: 'application/octet-stream'
            });
            
            const resp = await axios.post(
                `https://${server}/upload_chunk.php`,
                form,
                { headers: form.getHeaders() }
            );
            
            if (resp.data.url) {
                result = resp.data.url;
            }
            
            console.log(`Chunk ${i + 1}/${totalChunks} uploaded`);
        }
        
        return result;
    }
    
    getDirectUrl(pageUrl, password = null) {
        const lastSlash = pageUrl.lastIndexOf('/');
        const baseUrl = pageUrl.substring(0, lastSlash);
        const fileId = pageUrl.substring(lastSlash + 1);
        
        let directUrl = `${baseUrl}/download.php?file=${fileId}`;
        if (password) {
            directUrl += `&dlkey=${encodeURIComponent(password)}`;
        }
        
        return directUrl;
    }
}

// Использование
(async () => {
    const client = new GigaFileClient();
    
    // Загрузка
    const url = await client.upload('./myfile.pdf', 100);
    console.log('Uploaded:', url);
    
    // Прямая ссылка
    const direct = client.getDirectUrl(url);
    console.log('Direct URL:', direct);
})();
```

---

## 17. CLI инструменты

### Библиотека gfile (Python)

**Установка:**
```bash
pip install -U gigafile
```

**Команды:**

```bash
# Загрузка
gfile upload path/to/file

# Загрузка с параметрами
gfile upload path/to/file -n 8 -s 100MB

# Скачивание
gfile download https://60.gigafile.nu/0530-abc123...

# Скачивание с паролем
gfile download https://60.gigafile.nu/0530-abc123... -k 1234

# Скачивание через aria2 (быстрее)
gfile download https://60.gigafile.nu/0530-abc123... --aria2
```

**Параметры CLI:**

| Флаг | Описание | По умолчанию |
|------|----------|--------------|
| `-n THREAD_NUM` | Количество потоков | 8 |
| `-s CHUNK_SIZE` | Размер чанка | 100MB |
| `-k KEY` | Пароль скачивания | - |
| `--aria2` | Использовать aria2 | False |
| `--mute` | Тихий режим | False |
| `--no-verify` | Не проверять размер | False |

---

## 18. Cookies и сессии

### Используемые cookies

| Cookie | Описание |
|--------|----------|
| `prog_key` | Ключ для отслеживания прогресса скачивания |
| (сессионные) | Стандартные cookies для поддержания сессии |

### Установка cookie prog_key

```javascript
document.cookie = "prog_key=" + prog_key + "; domain=gigafile.nu";
```

### Важно для aria2

При использовании aria2 для скачивания необходимо передавать cookies:

```python
cookie_str = "; ".join([f"{c.name}={c.value}" for c in session.cookies])
cmd = ['aria2c', url, '--header', f'Cookie: {cookie_str}', '-o', filename]
```

---

## 19. Обработка ошибок

### Коды статуса API

| status | Описание |
|--------|----------|
| `0` | Успех |
| `1` | Общая ошибка / Неверные данные |
| `3` | Заблокировано (превышен лимит попыток) |

### Типичные ошибки

1. **Файл не найден** — истёк срок хранения или неверный URL
2. **Неверный пароль** — status: 1 от check_dlkey.php
3. **Заблокировано** — status: 3, слишком много неверных попыток пароля
4. **Размер не совпадает** — ошибка загрузки, нужна повторная попытка

### Retry логика

```python
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

retry = Retry(total=5, backoff_factor=0.2)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

---

## 20. Правовая информация

### Запрещённые файлы

1. Нарушающие законодательство или общественную мораль
2. Связанные с преступной деятельностью
3. Мешающие работе сервиса
4. Причиняющие ущерб пользователям

### Запрещённые действия

1. Загрузка/скачивание запрещённых файлов
2. Массовое размещение ссылок на форумах (нагрузка на сервер)
3. Ввод чужих email адресов
4. Нестандартное использование, создающее нагрузку
5. Попытки несанкционированного доступа

### Хранение данных

- Файлы не просматриваются администрацией (кроме подозрительных)
- Логи могут быть переданы правоохранительным органам при необходимости
- Файлы автоматически удаляются после истечения срока хранения

### Контакты

- **Сайт поддержки:** https://gigafile.nu/support.php
- **FAQ:** https://faq.gigafile.nu/
- **Форма обратной связи:** https://gigafile.nu/contact-us.php

---

## Ссылки и ресурсы

- **Официальный сайт:** https://gigafile.nu/
- **Правила использования:** https://gigafile.nu/privacy.php
- **Python библиотека gfile:** https://github.com/fireattack/gfile
- **PyPI:** https://pypi.org/project/gigafile/
- **Компания:** https://gigafile.ltd/

---

*Документация создана на основе reverse engineering. API может измениться без предупреждения. GigaFile не предоставляет официальной API документации.*

**Версия документации:** 2.0  
**Последнее обновление:** Февраль 2026
