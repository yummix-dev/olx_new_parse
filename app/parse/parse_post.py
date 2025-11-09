import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from fastapi import HTTPException
from loguru import logger

from exception import ParserError
from misc.clean_text import clean_text
from models.post import TypeOfProperty, TypeOfService
from core.config import load_config

config = load_config()


class BaseParser:
    registry = {}

    def __init_subclass__(cls, type_of_property=None, **kwargs):
        """Регистрирует дочерние парсеры по типу недвижимости"""
        super().__init_subclass__(**kwargs)
        if type_of_property:
            BaseParser.registry[type_of_property] = cls

        logger.debug(BaseParser.registry)

    def __init__(
        self,
        url: str,
        soup: BeautifulSoup,
        session: aiohttp.ClientSession,
    ):
        self.url = url
        self.soup = soup
        self.session = session
        self.html = str(soup)

        self.type_of_property = None
        self.type_of_service = None
        self.organization_url = None
        self.external_id = None
        self.title = None
        self.description = None
        self.polygon_id = None

    def __extract_properties(self):
        breadcrumbs = self.soup.find("ol", {"data-testid": "breadcrumbs"})
        if not breadcrumbs:
            raise ParserError("Не удалось найти структуру breadcrumbs")

        ad_attr = breadcrumbs.find_all("li", {"data-testid": "breadcrumb-item"})
        if len(ad_attr) < 4:
            raise ParserError(f"Слишком мало элементов в breadcrumbs: {len(ad_attr)}")

        type_of_property = ad_attr[2].get_text(strip=True).lower()
        type_of_service = ad_attr[3].get_text(strip=True).lower()

        match type_of_service:
            case "продажа":
                self.type_of_service = TypeOfService.SALE.value
            case "аренда долгосрочная":
                self.type_of_service = TypeOfService.RENT.value
            case "обмен":
                self.type_of_service = TypeOfService.SALE.value
            case _:
                raise ParserError('Не удалось получить "Вид услуги"')

        match type_of_property:
            case "квартиры":
                self.type_of_property = TypeOfProperty.APARTMENT.value
            case "коммерческие помещения":
                self.type_of_property = TypeOfProperty.COMMERCE.value
            case "дома":
                self.type_of_property = TypeOfProperty.HOUSE.value
            case _:
                raise ParserError('Не удалось получить "Тип недвижимости"')

    def __extract_organization_url(self):
        profile_element = self.soup.find("a", {"name": "user_ads"})

        if profile_element is None or not hasattr(profile_element, "href"):
            raise ParserError("Не удалось найти URL пользователя")

        href = profile_element.get("href")
        if href.startswith("/list/user/"):
            self.organization_url = f"https://www.olx.uz{href}"
        else:
            self.organization_url = href.replace("http://", "https://")

    def __extract_title(self):
        title_match = self.soup.find("title")

        if title_match is None:
            raise ParserError('Не удалось получить элемент "Заголовок"')

        self.title = title_match.get_text().strip()

    def __extract_description(self):
        description_match = self.soup.find(string="Описание").parent.parent.find("div")

        if description_match is None:
            raise ParserError('Не удалось получить элемент "Описание"')

        self.description = description_match.text

    def __extract_external_id(self):
        external_id_element = self.soup.find(string="ID: ").parent

        if external_id_element is None:
            raise ParserError('Не удалось получить элемент "External ID"')

        external_match = re.search(r"(\d+)", external_id_element.text)
        self.external_id = external_match.group(0)

    async def __get_polygon(self):
        url_polygon = config.parser.polygon_service_url
        text = clean_text(f"{self.title} - {self.description}")
        data = {
            "text": text,
        }
        try:
            async with self.session.post(url_polygon, json=data, timeout=config.parser.request_timeout) as response:
                if response.status != 200:
                    logger.error(f"Ошибка polygon сервиса: статус {response.status}")
                    raise HTTPException(status_code=response.status, detail=f"Polygon error: {data}")

                result = await response.json()
                self.polygon_id = result.get("polygon_id")
                self.polygon_keyword = result.get("key")
                logger.debug(f"Получен polygon_id: {self.polygon_id}, keyword: {self.polygon_keyword}")
        except asyncio.TimeoutError:
            logger.warning(f"Таймаут при обращении к polygon сервису: {url_polygon}")
            self.polygon_id = None
            self.polygon_keyword = None

    async def parse(self):
        """Парсит общие данные для всех типов недвижимости"""
        self.__extract_properties()
        self.__extract_organization_url()
        self.__extract_title()
        self.__extract_description()
        self.__extract_external_id()
        await self.__get_polygon()

    async def execute(self):
        """
        Главный метод: определяет тип недвижимости и вызывает нужный парсер.
        Используется только для BaseParser, дочерние классы переопределяют этот метод.
        """
        # Сначала парсим базовые данные, чтобы определить type_of_property
        await self.parse()

        # Проверяем, есть ли специализированный парсер для этого типа
        if self.type_of_property in self.registry:
            # Создаем экземпляр специализированного парсера
            specialized_parser = self.registry[self.type_of_property](
                url=self.url, soup=self.soup, session=self.session
            )
            # Копируем уже спарсенные базовые данные
            specialized_parser.type_of_property = self.type_of_property
            specialized_parser.type_of_service = self.type_of_service
            specialized_parser.organization_url = self.organization_url
            specialized_parser.external_id = self.external_id
            specialized_parser.title = self.title
            specialized_parser.description = self.description
            specialized_parser.polygon_id = self.polygon_id
            specialized_parser.polygon_keyword = getattr(self, "polygon_keyword", None)

            await specialized_parser.execute()
            return specialized_parser
        else:
            raise ValueError(f"Нет парсера для типа недвижимости: {self.type_of_property}")
