# YCrawler

### Асинхронный краулер для новостного сайта news.ycombinator.com

```shell
usage: ycrawler.py [-h] [-s SLEEP] [-m MAX_TASKS] [-n NUMBERS] [-t TIMEOUT] [-o OUTPUT] [-d] [--proxy PROXY] [--once]

optional arguments:
  -h, --help            show this help message and exit
  -s SLEEP, --sleep SLEEP
                        Период ожидания перед повтором опроса в секундах
  -m MAX_TASKS, --max_tasks MAX_TASKS
                        Максимальное количество одновременных загрузок
  -n NUMBERS, --numbers NUMBERS
                        Количество обрабатываемых новостей на главной странице
  -t TIMEOUT, --timeout TIMEOUT
                        Таймаут соединения
  -o OUTPUT, --output OUTPUT
                        Путь выгрузки файлов
  -d, --debug
  --proxy PROXY         Прокси-сервер
  --once                Один проход без цикла повторов
```
Дефолтные значения:

    SLEEP       = 30
    NUMBERS     = 30
    MAX_TASKS   = 5
    TIMEOUT     = 5
    OUTPUT      = './downloads'
    
Все файлы загружаются в папку `OUTPUT`. В корне файл `parsed.json` с данными оо обработанных записях формата:

```json
{
  "ID": [
    "NEWS TITLE",
    "https://news.ycombinator.com/item?id=ID"
  ],
  ...
}
``` 

Страницы новостей сохраняются в `OUTPUT/ID/index.html` 

Файлы по ссылкам в комментариях сохраняются в `OUTPUT/ID/comments/COMMID_HASH.html`

В корне каждой папки `comments` генерируется файл `index.json` с информацией о загруженных файлах по ссылкам в 
комментариях формата:

```json
{
  "COMMID": [
    [
      "COMMID_HASH.html",
      "DOWNLOADED FILE URL"
    ]
  ],
  ...
}
```

, где 

- ID      - id новости на сайте
- COMMID  - id комментария к новости
- HASH    - сгенерированный суффикс
