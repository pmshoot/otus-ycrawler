import aiohttp
import asyncio


#############################################
# URL адрес сайта для обкачки
url = 'https://news.ycombinator.com/'
# Кол-во обрабатываемых новостей
ntop = 30
# Время ожидания между обкачками в секундах
nsleep = 30
store_path = "./downloads"
proxy = r'http://10.66.2.130:8118/'  # or None
#############################################


async def main():
    """"""
    async with aiohttp.ClientSession() as s:
        async with s.get(url, proxy=proxy) as r:
            print(r.status)
            print(await r.text())


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
