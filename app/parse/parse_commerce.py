import asyncio
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import and_

from ..exception import ParserError
from ..models.post_sale_apartment import Repair
from ..models.post_sale_commerce import Purpose
from ..schemas.post_commerce import PostCommerce as PostCommerceSchemas
from ..core.config import load_config
from ..models.post import TypeOfProperty
from .parse_post import BaseParser
from ..misc.convert_to_usd import convert_uzs_to_usd

# Загружаем конфигурацию
config = load_config()


class CommerceParse(BaseParser):
    type_of_property = TypeOfProperty.COMMERCE.value

    def __init__(self, url: str, soup: BeautifulSoup, session: aiohttp.ClientSession):
        super().__init__(url, soup, session)

        self.floor: int | None = None
        self.total_floor: int | None = None
        self.total_area_sqm: int | None = None
        self.land_area_sqm: int | None = None
        self.total_price: int | None = None
        self.repair: Repair | None = None
        self.purpose: Purpose | None = None

    def __extract_floor(self):
        floor_match = re.search(r"Этаж: (\d+)", self.html)

        if not floor_match:
            logger.warning('Не найден элемент "Этаж"')
            return

        self.floor = int(floor_match.group(1))

    def __extract_total_floor(self):
        total_floor_match = re.search(r"Этажность дома: (\d+)", self.html)

        if not total_floor_match:
            logger.warning('Не найден элемент "Этажность дома"')
            return

        self.total_floor = int(total_floor_match.group(1))

    def __extract_total_area(self):
        area_matches = re.search(r"Общая площадь: ([\d\s]+(?:\.\d+)?)", self.html)
        if not area_matches:
            logger.warning('Не найден элемент "Общая площадь"')
            return

        total_area_str = area_matches.group(1).replace(" ", "")

        try:
            self.total_area_sqm = round(float(total_area_str))
        except ValueError as e:
            logger.error(f"Не удалось преобразовать площадь в число: {total_area_str}, ошибка: {e}")

    def __extract_repair(self):
        repair_match = re.search(r">Ремонт:\s*([А-Яа-я\s]+)<", self.html)

        if not repair_match:
            logger.warning('Не найден элемент "Ремонт"')
            return

        repair_clean = re.sub(r"<[^>]+>", "", repair_match.group(1))
        repair_text = " ".join(repair_clean.split()).strip()

        match repair_text:
            case "Авторский проект":
                self.repair = Repair.designer
            case "Евроремонт":
                self.repair = Repair.euro
            case "Средний":
                self.repair = Repair.average
            case "Требует ремонта":
                self.repair = Repair.needs_repair
            case "Черновая отделка":
                self.repair = Repair.rough_finish
            case "Предчистовая отделка":
                self.repair = Repair.pre_finish
            case _:
                raise ParserError(f'Неизвестный тип ремонта: "{repair_text}"')

    def __extract_purpose(self):
        purpose_match = re.search(r">Тип недвижимости:\s*([А-Яа-я/\(\)\s]+)<", self.html)

        if not purpose_match:
            logger.warning('Не найден элемент "Тип недвижимости"')
            return

        purpose_clean = re.sub(r"<[^>]+>", "", purpose_match.group(1))
        purpose_text = " ".join(purpose_clean.split()).strip().lower()
        print(purpose_text)

        match purpose_text:
            case "магазины/бутики":
                self.purpose = Purpose.shop
            case "базы отдыха":
                self.purpose = Purpose.recreation_base
            case "салоны":
                self.purpose = Purpose.salon
            case "помещения промышленного назначения":
                self.purpose = Purpose.industrial
            case "рестораны/кафе/бары":
                self.purpose = Purpose.restaurant_cafe_bar
            case "помещения свободного назначения":
                self.purpose = Purpose.free_purpose
            case "офисы":
                self.purpose = Purpose.office
            case "маф (малая архитектурная форма)":
                self.purpose = Purpose.small_architectural_form
            case "склады":
                self.purpose = Purpose.warehouse
            case "часть здания":
                self.purpose = Purpose.part_of_building
            case "отдельно стоящие здания":
                self.purpose = Purpose.standalone_building
            case "нежилое помещение":
                self.purpose = Purpose.uninhabitable
            case "другое":
                self.purpose = Purpose.other
            case _:
                raise ParserError(f'Неизвестный тип недвижимости: "{purpose_text}"')

    def __extract_land_area(self):
        land_area_match = re.search(r"Участок: ([\d\s]+(?:\.\d+)?)", self.html)

        if not land_area_match:
            logger.warning('Не найден элемент "Участок"')
            return

        land_area_str = land_area_match.group(1).replace(" ", "")

        try:
            self.land_area_sqm = round(float(land_area_str)) * 100
        except ValueError as e:
            logger.error(f"Не удалось преобразовать площадь участка в число: {land_area_str}, ошибка: {e}")

    async def __extract_total_price(self):
        # Нормализуем HTML, заменяя неразрывные пробелы на обычные
        html_normalized = self.html.replace("\xa0", " ")

        # Поиск цены в формате "850 000 у.е."
        total_price_match = re.search(r"([\d\s]+)\s*у\.е\.", html_normalized)
        if total_price_match:
            total_price_str = total_price_match.group(1).replace(" ", "")
            try:
                self.total_price = int(total_price_str)
                return
            except Exception as e:
                raise ParserError(f"Не удалось преобразовать цену в int: {total_price_str}") from e

        # Поиск цены в формате "850 000 $" или "850 000 сум"
        total_price_match = re.search(r"([\d\s]+)\s*(?:\$|сум)", html_normalized)
        if total_price_match:
            total_price_str = total_price_match.group(1).replace(" ", "")
            try:
                price = int(total_price_str)
                if "сум" in total_price_match.group(0):
                    self.total_price = await convert_uzs_to_usd(price)
                else:
                    self.total_price = price
                return
            except Exception as e:
                raise ParserError(f"Не удалось преобразовать цену в int: {total_price_str}") from e

        raise ParserError('Не удалось получить элемент "Цена"')

    async def execute(self) -> PostCommerceSchemas:
        """
        Выполняет парсинг специфичных данных коммерческой недвижимости.
        Базовые данные уже спарсены в BaseParser.parse()
        """
        self.__extract_floor()
        self.__extract_total_floor()
        self.__extract_total_area()
        self.__extract_repair()
        self.__extract_land_area()
        self.__extract_purpose()
        await self.__extract_total_price()

    async def send_db(self):
        """Сохраняет спарсенные данные в базу данных"""
        from sqlalchemy import select
        from ..models.db_helper import db_helper
        from ..models.post import Post, Source, TypeOfService
        from ..models.post_sale_commerce import PostSaleCommerce
        from ..models.post_rent_commerce import PostRentCommerce
        from ..models.organization import Organization, Platform

        session = db_helper.get_scope_session()

        try:
            # 1. Проверяем/создаем организацию
            stmt = select(Organization).where(
                and_(Organization.url == self.organization_url, Organization.platform == Platform.OLX)
            )
            result = await session.execute(stmt)
            organization = result.scalar_one_or_none()

            if not organization:
                organization = Organization(
                    url=self.organization_url,
                    platform=Platform.OLX,
                    is_broker=getattr(self, "is_broker", False),
                )
                session.add(organization)
                await session.flush()
                logger.info(f"Создана новая организация: {organization.url}")

            # 2. Проверяем существование поста по external_id
            stmt = select(Post).where(Post.external_id == self.external_id, Post.source == Source.OLX)
            result = await session.execute(stmt)
            existing_post = result.scalar_one_or_none()

            if existing_post:
                logger.info(f"Пост {self.external_id} уже существует в БД, пропускаем")
                await session.remove()
                return

            # 3. Создаем новый пост
            new_post = Post(
                type_of_property=self.type_of_property,
                type_of_service=self.type_of_service,
                url=self.url,
                title=self.title,
                description=self.description,
                source=Source.OLX,
                external_id=self.external_id,
                phone_number=getattr(self, "phone_number", None),
                polygon_id=self.polygon_id,
                organization_id=organization.id,
                is_broker=getattr(self, "is_broker", False),
            )
            session.add(new_post)
            await session.flush()

            # 4. Создаем запись в таблице коммерческой недвижимости (sale или rent)
            if self.type_of_service == TypeOfService.SALE.value:
                commerce_details = PostSaleCommerce(
                    post_id=new_post.id,
                    rooms=getattr(self, "rooms", None),
                    floor=self.floor,
                    total_floor=self.total_floor,
                    total_area_sqm=self.total_area_sqm,
                    land_area_sqm=self.land_area_sqm,
                    total_price=self.total_price,
                    has_furniture=getattr(self, "has_furniture", None),
                    repair=self.repair,
                    purpose=self.purpose,
                )
            else:  # RENT
                commerce_details = PostRentCommerce(
                    post_id=new_post.id,
                    rooms=getattr(self, "rooms", None),
                    floor=self.floor,
                    total_floor=self.total_floor,
                    total_area_sqm=self.total_area_sqm,
                    land_area_sqm=self.land_area_sqm,
                    total_price=self.total_price,
                    has_furniture=getattr(self, "has_furniture", None),
                    repair=self.repair,
                    purpose=self.purpose,
                )

            session.add(commerce_details)
            await session.commit()
            logger.success(f"Коммерческая недвижимость {self.external_id} успешно сохранена в БД")

        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при сохранении коммерческой недвижимости в БД: {e}")
            raise
        finally:
            await session.remove()


async def main():
    """
    Пример использования: создаем BaseParser, он автоматически определяет
    тип недвижимости и вызывает нужный специализированный парсер
    """
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://www.olx.uz/d/obyavlenie/assalomu-aleykum-kimga-taer-ishlab-turgan-biznes-kizik-bulsa-ID4cTue.html"
        ) as response:
            page = await response.text()
            soup = BeautifulSoup(page, "lxml")

            # Создаем базовый парсер - он сам определит тип и вызовет CommerceParse
            url = (
                "https://www.olx.uz/d/obyavlenie/"
                "assalomu-aleykum-kimga-taer-ishlab-turgan-biznes-kizik-bulsa-ID4cTue.html"
            )
            result = await BaseParser(
                url=url,
                soup=soup,
                session=session,
            ).execute()

            for row in result.__dict__:
                print(row, getattr(result, row))


if __name__ == "__main__":
    asyncio.run(main())
