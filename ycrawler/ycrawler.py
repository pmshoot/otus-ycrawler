import argparse
import asyncio
import collections
import json
import logging
import time
from hashlib import sha256
from pathlib import Path

import aiofiles
import aiohttp
from aiofiles import os as aios
from aiofiles import ospath as aiospath
from aiohttp import ClientTimeout
from bs4 import BeautifulSoup

ycomb_url = 'https://news.ycombinator.com/'
encoding = 'utf-8'


async def read_url(url, session, semafor, proxy=None):
    """Загрузка страницы по url c ограничением одновременных загрузок"""
    response = content_type = status = None
    async with semafor:
        try:
            async with session.get(url, proxy=proxy) as r:
                if r.status == 200:
                    response = await r.read()
                    content_type = r.content_type
                    status = r.status
        except Exception as e:
            msg = '' if e is None else str(e)
            status = msg if msg else 'timeout connect'
    return response, content_type, status


async def write_file(fp: Path, content, mode='wb'):
    """Запись данных в файл"""
    if not await aiospath.exists(fp.parent):
        await aios.makedirs(fp.parent, exist_ok=True)
    async with aiofiles.open(fp, mode=mode) as f:
        await f.write(content)


async def handle_record(id, record, session, semafor, options):
    """Обработчик новости - парсинг и загрузка по ссылкам из комментариев"""
    url = f'{ycomb_url}item?id={id}'
    response, content_type, status = await read_url(url, session, semafor)
    if not response:
        logging.info(f'{url} status code - {status}')
        return
    # write record to file
    fp = Path(options.output) / id / 'index.html'
    await write_file(fp, response)
    # текст новости и ссылка на ресурс
    a = record.find_all(attrs={'class': 'titleline'})[0].a
    name = a.text.strip()
    href = a['href']
    logging.info(f'News: {id}\t{name}\t{href}')
    # комментарии к новости
    bs = BeautifulSoup(response, features="html.parser")
    st = bs.table.find(attrs={'class': 'comment-tree'})
    items = st.find_all('tr', attrs={'class': 'athing'})  #
    if not items:  # no comments block
        return
    comm_index = collections.defaultdict(list)
    comm_index_dir = Path(options.output) / id / 'comments'
    comm_index_file = comm_index_dir / 'index.json'

    for tr in items:
        comm_id = tr['id']
        commtext = tr.find('span', attrs={'class': 'commtext'})
        if commtext is None:  # no commtext
            continue
        comm_urls = [a['href'] for a in commtext.find_all('a') if a]
        if not comm_urls:  # no links in comment
            continue
        for comm_url in comm_urls:
            # download html by comment link
            response, content_type, status = await read_url(comm_url, session, semafor)
            msg = f'Comm: {comm_id}\t{comm_url}'
            if not response:
                logging.info(msg + f' status code - {status}')
                continue
            logging.info(msg)
            suffix = sha256(time.time_ns().to_bytes(8, 'little')).hexdigest()[:10]
            if content_type == 'text/html':
                fname = f'{comm_id}_{suffix}.html'
            else:
                fname = f'{comm_id}_{suffix}_{Path(comm_url).name.split("?")[0]}'
            fp = comm_index_dir / fname
            await write_file(fp, response)
            comm_index[comm_id].append([fname, comm_url])
    if comm_index:
        await write_file(comm_index_file, json.dumps(comm_index).encode(encoding=encoding))
    return name, url


async def main(options):
    """Разбор страницы новостей"""
    semafor = asyncio.Semaphore(options.max_tasks)  # ограничение кол-ва загрузок в одной сессии
    parsed_fp = Path(options.output) / 'parsed.json'
    timeout = ClientTimeout(total=options.timeout)
    try:
        with parsed_fp.open(encoding=encoding) as fp:
            parsed = json.loads(fp.read())
    except FileNotFoundError:
        parsed = {}
    logging.info(f'Root: {ycomb_url}')
    while True:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            response, _, status = await read_url(ycomb_url, session, semafor)
            if not response:
                logging.error(f'Error - {status}')
                break
            bs = BeautifulSoup(response, features="html.parser")
            records = bs.table.find_all(attrs={'class': 'athing'})
            if not records:
                logging.info('Hе найдены новости')
                break
            for record in records[:options.numbers]:
                try:
                    id = record['id']
                    if id in parsed:  # no repeat
                        continue
                    name_url_tpl: tuple = await handle_record(id, record, session, semafor, options)
                    if not name_url_tpl:
                        continue
                    parsed[id] = name_url_tpl
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    logging.error(f'main: {e}')
                    continue
            # fix parsed
            await write_file(parsed_fp, json.dumps(parsed).encode(encoding=encoding))
            logging.info('--- End cycle ------------------------')
        if options.once:  # no cycle repeat
            break
        logging.info(f'Waiting for {options.sleep} sec...')
        await asyncio.sleep(options.sleep)
        logging.info('Repeat')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-s', '--sleep', type=int, default=30, action='store', help='Период ожидания перед повтором '
                                                                                    'опроса в секундах')
    parser.add_argument('-m', '--max_tasks', type=int, default=5, action='store', help='Максимальное количество '
                                                                                       'одновременных загрузок')
    parser.add_argument('-n', '--numbers', type=int, default=30, action='store', help='Количество обрабатываемых '
                                                                                      'новостей на главной странице')
    parser.add_argument('-t', '--timeout', type=int, default=5, action='store', help='Таймаут соединения')
    parser.add_argument('-o', '--output', default='downloads', action='store', help='Путь выгрузки файлов')
    parser.add_argument('-d', '--debug', action='store_true')
    parser.add_argument('--proxy', default=None, action='store', help='Прокси-сервер')
    parser.add_argument('--once', default=False, action='store_true', help='Один проход без цикла повторов')
    options = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if options.debug else logging.INFO,
                        format="%(levelname)-.1s:%(message)s"
                        )
    #
    try:
        asyncio.run(main(options))
    except KeyboardInterrupt:
        logging.info('End up')
