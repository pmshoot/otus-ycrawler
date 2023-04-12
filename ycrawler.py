import asyncio
import json
from asyncio.log import logger
from pathlib import Path, PurePath

import aiofiles
import aiohttp
from aiofiles import os as aios
from aiofiles import ospath as aiospath
from aiohttp import ClientHttpProxyError
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
fnmain = 'main.html'
fncomm = 'comments.html'


async def read_url(url):
    async with aiohttp.ClientSession() as s:
        try:
            async with s.get(url, proxy=proxy) as r:
                # print(r.status)
                if r.status == 200:
                    response = await r.text()
                else:
                    response = ''
                    msg = f'url {url}: status {r.status}'
                    logger.error(msg)
                    print(msg)
        except ClientHttpProxyError as e:
            logger.error(e)
            print(e)
            response = ''
    return response


async def parse_html(html):
    """"""
    bs_obj = BeautifulSoup(html, features="html.parser")
    return bs_obj


async def write_file(fp: Path, html):
    """"""
    if not await aiospath.exists(fp.parent):
        await aios.makedirs(fp.parent, exist_ok=True)
    async with aiofiles.open(fp, mode='w', encoding=encoding) as f:
        await f.write(html)


async def handle_record(id, record):
    url = f'{ycomb_url}item?id={id}'
    record_html = await read_url(url)
    if not record_html:
        return
    logger.debug('got main page')
    # write record to file
    fp = PurePath(store_path) / id / 'index.html'
    await write_file(fp, record_html)

    a = record.find_all(attrs={'class': 'titleline'})[0].a
    name = a.text.strip()
    href = a['href']
    logger.info(f'{id}\t{name}\t{href}')

    bs = await parse_html(record_html)
    st = bs.table.find(attrs={'class': 'comment-tree'})
    items = st.find_all('tr', attrs={'class': 'athing'})

    logger.debug(f'{id}\tparsing comments')
    for tr in items:
        comm_id = tr['id']
        commtext = tr.find('span', attrs={'class': 'commtext'})
        if commtext is None:  # no comments
            continue
        comm_urls = [a['href'] for a in commtext.find_all('a') if a]
        if not comm_urls:  # no links
            continue
        logger.debug(f'{id}\tparsed comment\'s urls')

        for comm_url in comm_urls:
            # download html by comment link
            fp = Path(store_path) / id / 'comments' / f'{comm_id}.html'.lower()
            html = await read_url(comm_url)
            if not html:
                logger.debug(f'error get data from comment url {comm_url}')
            else:
                logger.debug(f'got data from comment url {comm_url}')

            await write_file(fp, html)
            logger.info(f'got {str(fp)}')


async def main(parsed):
    """"""
    mpage_html = await read_url(ycomb_url)
    if not mpage_html:
        return
    bs = await parse_html(mpage_html)
    records = bs.table.find_all(attrs={'class': 'athing'})
    for record in records:
        id = record['id']
        if id in parsed:
            continue
        name = await handle_record(id, record)
        if not name:
            continue
        parsed[id] = name


if __name__ == '__main__':
    parsed_fp = Path('parsed.json')
    if not parsed_fp.exists():
        parsed = {}
    else:
        parsed = json.loads(parsed_fp.read_text(encoding=encoding))
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(main(parsed))
    try:
        asyncio.run(main(parsed), debug=True)
    except Exception as e:
        print(e)
        raise
    # end up
    with parsed_fp.open('w', encoding=encoding) as fp:
        json.dump(parsed, fp)

# @TODO логирование
# @TODO парсинг имени файла скачанного html из url комментария из url (-http:// и прочее)
