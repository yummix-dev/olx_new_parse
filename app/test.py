import aio_pika
import aiohttp
import asyncio
from bs4 import BeautifulSoup
from core.config import load_config

config = load_config()

urls = [
    "https://www.olx.uz/nedvizhimost/kvartiry/?page=2",
    "https://www.olx.uz/nedvizhimost/kvartiry/?page=3",
    "https://www.olx.uz/nedvizhimost/kvartiry/?page=4",
    "https://www.olx.uz/nedvizhimost/kvartiry/?page=5",
]


async def fetch_links(session, url):
    async with session.get(url) as response:
        html = await response.text()
        soup = BeautifulSoup(html, "lxml")

        # находим все ссылки внутри блока с data-cy="ad-card-title"
        links = []
        for div in soup.select('div[data-cy="ad-card-title"] a'):
            href = div.get("href")
            if href and href.startswith("/d/obyavlenie/"):
                links.append("https://www.olx.uz" + href)
        return links


async def main():
    async with aiohttp.ClientSession() as session:
        # Формируем URL для подключения к RabbitMQ из конфигурации
        rabbitmq_url = (
            f"amqp://{config.rabbitmq.username}:{config.rabbitmq.password}@"
            f"{config.rabbitmq.host}:{config.rabbitmq.port}/{config.rabbitmq.vhost}"
        )
        connection = await aio_pika.connect_robust(rabbitmq_url)
        channel = await connection.channel()

        queue_name = "post"
        await channel.declare_queue(queue_name, durable=True)

        tasks = [fetch_links(session, url) for url in urls]
        results = await asyncio.gather(*tasks)

        all_links = [link for page_links in results for link in page_links]
        print(f"Найдено {len(all_links)} объявлений:")
        for link in all_links:
            await channel.default_exchange.publish(
                aio_pika.Message(body=link.encode()),
                routing_key=queue_name,
            )

        await connection.close()


asyncio.run(main())
