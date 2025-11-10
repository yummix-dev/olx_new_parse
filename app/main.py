import asyncio
import gc
from random import randint
from urllib.parse import urlparse
import aio_pika

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from pydantic import BaseModel, field_validator

from .core.config import load_config
from .exception import ParserError
from .misc.proxy import Proxy
from fake_useragent import UserAgent
import cloudscraper

from .parse.parse_post import BaseParser

# Import parse subclasses to register them in BaseParser.registry
from . import parse  # noqa: F401

# Загружаем конфигурацию
config = load_config()

_proxy = Proxy()

ua = UserAgent()


class URLValidator(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("Невалидный URL")

        # Проверяем, что домен в whitelist
        domain = parsed.netloc.lower()
        if domain not in config.parser.allowed_domains:
            raise ValueError(f"Домен {domain} не разрешен для парсинга")

        return v


def get_headers() -> dict:
    """Генерирует заголовки с случайным User-Agent"""
    return {
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.olx.uz/",
        "Connection": "keep-alive",
    }


async def fetch_with_cloudscraper(url: str, proxy_ip: str, headers: dict, timeout: int) -> tuple[int, str]:
    """
    Выполняет синхронный запрос через cloudscraper в отдельном потоке
    Возвращает (status_code, response_text)
    """

    def _fetch():
        scraper = None
        try:
            if config.proxy.login and config.proxy.password:
                proxy_with_auth = f"http://{config.proxy.login}:{config.proxy.password}@{proxy_ip}:{config.proxy.port}"
            else:
                proxy_with_auth = f"http://{proxy_ip}:{config.proxy.port}"

            proxies = {"http": proxy_with_auth, "https": proxy_with_auth}

            scraper = cloudscraper.create_scraper(browser={"browser": "chrome", "platform": "windows", "mobile": False})
            scraper.proxies = proxies

            response = scraper.get(url, headers=headers, timeout=timeout)
            return response.status_code, response.text
        finally:
            # Явно закрываем scraper для освобождения ресурсов
            if scraper is not None:
                try:
                    scraper.close()
                except Exception:
                    pass

    # Выполняем синхронный код в отдельном потоке, чтобы не блокировать event loop
    return await asyncio.to_thread(_fetch)


async def process_message(message: aio_pika.IncomingMessage, session: aiohttp.ClientSession):
    """Обрабатывает одно сообщение из очереди"""
    url = message.body.decode()
    soup = None
    post = None

    try:
        URLValidator(url=url)
    except ValueError as e:
        logger.error(f"Невалидный URL: {url}, ошибка: {e}")
        await message.ack()  # Удаляем невалидные URL из очереди
        return

    max_retries = min(config.parser.max_retries, len(_proxy.proxies))
    headers = get_headers()

    proxy_ip = _proxy.get()

    try:
        for attempt in range(max_retries):
            logger.info(f"Используется прокси {proxy_ip} (попытка {attempt + 1}/{max_retries})")

            try:
                status_code, response_text = await fetch_with_cloudscraper(
                    url, proxy_ip, headers, config.parser.request_timeout
                )

                logger.debug(f"Получен статус код: {status_code}")

                if status_code == 200:
                    logger.info(f"Успешно получена страница: {url}")
                    soup = BeautifulSoup(response_text, "lxml")
                    post = await BaseParser(url, soup, session).execute()
                    await post.send_db()

                    logger.success(f"Парсинг завершен успешно для {url}")
                    await message.ack()
                    await asyncio.sleep(randint(1, 2))
                    return
                elif status_code == 403:
                    logger.warning(f"Прокси {proxy_ip} заблокирован (403), пробуем следующий...")
                    proxy_ip = _proxy.get()
                    continue
                elif status_code == 404:
                    logger.error(f"Страница не найдена: {url}")
                    await message.ack()  # Удаляем из очереди, т.к. страница не существует
                    return
                elif status_code == 410:
                    logger.info(f"Страница {url} удалена")
                    await message.ack()  # Удаляем из очереди, т.к. страница не существует
                    return
                else:
                    logger.warning(f"Получен статус {status_code} от {proxy_ip}, пробуем следующий...")
                    proxy_ip = _proxy.get()
                    continue

            except ParserError as e:
                logger.error(f"Ошибка парсера: {e}")
                await message.nack(requeue=True)
                return
            except RuntimeError:
                logger.error("Все прокси заблокированы или недоступны")
                await message.nack(requeue=True)
                return
            except asyncio.TimeoutError:
                logger.warning(f"Таймаут при запросе через прокси {proxy_ip}")
                proxy_ip = _proxy.get()
                continue
            except ConnectionError as e:
                logger.warning(f"Ошибка соединения с прокси {proxy_ip}: {e}")
                proxy_ip = _proxy.get()
                continue
            except Exception as e:
                logger.warning(f"Неожиданная ошибка с прокси {proxy_ip}: {type(e).__name__}: {e}")
                proxy_ip = _proxy.get()
                continue

        # Если все попытки исчерпаны
        logger.error(f"Не удалось обработать URL после {max_retries} попыток: {url}")
        await message.nack(requeue=True)
    finally:
        # Явно очищаем объекты для освобождения памяти
        if soup is not None:
            soup.decompose()
            del soup
        if post is not None:
            del post
        # Принудительная сборка мусора каждые N сообщений
        gc.collect()


async def main():
    """Основная функция для обработки сообщений из RabbitMQ"""
    _proxy.load()
    logger.info("Подключение к RabbitMQ...")

    # Формируем URL для подключения к RabbitMQ из конфигурации
    rabbitmq_url = (
        f"amqp://{config.rabbitmq.username}:{config.rabbitmq.password}@"
        f"{config.rabbitmq.host}:{config.rabbitmq.port}/{config.rabbitmq.vhost}"
    )
    connection = await aio_pika.connect_robust(rabbitmq_url)

    # Создаем одну долгоживущую aiohttp сессию для всех запросов
    connector = aiohttp.TCPConnector(
        limit=10,  # Максимум 10 одновременных соединений
        limit_per_host=5,  # Максимум 5 соединений на хост
        ttl_dns_cache=300,  # Кэшируем DNS на 5 минут
        force_close=True  # Закрываем соединения после каждого запроса
    )
    timeout = aiohttp.ClientTimeout(total=config.parser.request_timeout)

    try:
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=1)  # Обрабатываем по одному сообщению за раз
            queue = await channel.declare_queue("post", durable=True)

            logger.info("Ожидание сообщений из очереди...")

            async with queue.iterator(no_ack=False) as queue_iter:
                async for message in queue_iter:
                    try:
                        await process_message(message, session)
                    except Exception as e:
                        logger.error(f"Критическая ошибка при обработке сообщения: {e}")
                        try:
                            await message.nack(requeue=True)
                        except Exception as nack_error:
                            logger.error(f"Не удалось вернуть сообщение в очередь: {nack_error}")

    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"Критическая ошибка в main: {e}")
    finally:
        await connection.close()
        logger.info("Соединение с RabbitMQ закрыто")


asyncio.run(main())
