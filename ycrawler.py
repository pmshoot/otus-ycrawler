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
from bs4 import BeautifulSoup

#############################################
# URL адрес сайта для обкачки
# url = 'https://news.ycombinator.com/'
ycomb_url = 'https://news.ycombinator.com/'
# Кол-во обрабатываемых новостей
ntop = 30
# Время ожидания между обкачками в секундах
nsleep = 30
store_path = "./downloads"
proxy = r'http://10.66.2.130:8118/'  # or None
encoding = 'utf-8'


#############################################


async def read_url(url, session, semafor):
    async with semafor:
        async with session.get(url, proxy=proxy) as r:
            try:
                if r.status == 200:
                    response = await r.read()
                    content_type = r.content_type
                else:
                    response = content_type = None
                    logging.error(f'Error download url {url}: status {r.status}')
            except Exception as e:
                logging.error(e)
                response = content_type = None
    return response, content_type


async def write_file(fp: Path, content, mode='wb'):
    """"""
    if not await aiospath.exists(fp.parent):
        await aios.makedirs(fp.parent, exist_ok=True)
    async with aiofiles.open(fp, mode=mode) as f:
        await f.write(content)


async def handle_record(id, record, session, semafor):
    url = f'{ycomb_url}item?id={id}'
    response, content_type = await read_url(url, session, semafor)
    if not response:
        return
    # write record to file
    fp = Path(store_path) / id / 'index.html'
    await write_file(fp, response)

    a = record.find_all(attrs={'class': 'titleline'})[0].a
    name = a.text.strip()
    href = a['href']
    logging.info(f'Item: {id}\t{name}\t{href}')

    bs = BeautifulSoup(response, features="html.parser")
    st = bs.table.find(attrs={'class': 'comment-tree'})
    items = st.find_all('tr', attrs={'class': 'athing'})  #
    if not items:
        return
    comm_index = collections.defaultdict(list)
    comm_index_dir = Path(store_path) / id / 'comments'
    comm_index_file = comm_index_dir / 'index.json'

    for tr in items:
        comm_id = tr['id']
        commtext = tr.find('span', attrs={'class': 'commtext'})
        if commtext is None:  # no comments
            continue
        comm_urls = [a['href'] for a in commtext.find_all('a') if a]
        if not comm_urls:  # no links in comment
            continue
        for comm_url in comm_urls:
            # download html by comment link
            response, content_type = await read_url(comm_url, session, semafor)
            logging.info(f'Comm: {comm_id}\t{comm_url}')
            if not response:
                logging.debug(f'{id}::{comm_id}: error get data from comment url {comm_url}')
                continue
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
    """"""
    semafor = asyncio.Semaphore(options.max_tasks)  # ограничение кол-ва загрузок в одной сессии
    parsed_fp = Path('parsed.json')
    try:
        with parsed_fp.open(encoding=encoding) as fp:
            parsed = json.loads(fp.read())
    except Exception:
        parsed = {}
    while True:
        async with aiohttp.ClientSession() as session:
            try:
                response, _ = await read_url(ycomb_url, session, semafor)
                logging.info(f'Root: {ycomb_url}')
                if not response:
                    break
                bs = BeautifulSoup(response, features="html.parser")
                records = bs.table.find_all(attrs={'class': 'athing'})
                if not records:
                    logging.info('Root: не найдены новости')
                    break
                for record in records[:options.numbers]:
                    try:
                        id = record['id']
                        if id in parsed:  # no repeat
                            continue
                        name_url = await handle_record(id, record, session, semafor)
                        if not name_url:
                            continue
                        parsed[id] = name_url
                    except KeyboardInterrupt:
                        break
                    except Exception as e:
                        logging.error(f'main: {e}')
                        continue
            finally:
                with parsed_fp.open('wt', encoding=encoding) as fp:
                    json.dump(parsed, fp)
            logging.info('--- End cycle ------------------------')

        logging.info(f'Waiting for {options.period} sec...')
        await asyncio.sleep(options.period)
        logging.info('Repeat')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--period', type=int, default=30, action='store', help='Период повтора опроса в секундах')
    parser.add_argument('-t', '--max_tasks', type=int, default=5, action='store', help='Максимальное количество '
                                                                                       'одновременных загрузок')
    parser.add_argument('-n', '--numbers', type=int, default=30, action='store', help='Количество обрабатываемых '
                                                                                    'новостей на главной странице')
    parser.add_argument('-d', '--debug', action='store_true')
    options = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if options.debug else logging.INFO)
    #
    asyncio.run(main(options))


