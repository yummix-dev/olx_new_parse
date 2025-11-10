import asyncio
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import and_

from ..exception import ParserError
from ..schemas.post_apartment import PostApartment as PostApartmentSchemas
from ..core.config import load_config
from ..models.post_sale_apartment import BuildingMaterial, Repair
from ..models.post import TypeOfProperty
from .parse_post import BaseParser
from ..misc.convert_to_usd import convert_uzs_to_usd

# Загружаем конфигурацию
config = load_config()


class ApartmentParse(BaseParser):
    type_of_property = TypeOfProperty.APARTMENT.value

    def __init__(self, url: str, soup: BeautifulSoup, session: aiohttp.ClientSession):
        super().__init__(url, soup, session)

        self.rooms: int | None = None
        self.floor: int | None = None
        self.total_floor: int | None = None
        self.total_area_sqm: int | None = None
        self.total_price: int | None = None
        self.is_new_building: bool = False
        self.has_furniture: bool = False
        self.repair: Repair | None = None
        self.building_material: BuildingMaterial | None = None

    def __extract_rooms(self):
        rooms_match = re.search(r"Количество комнат: (\d+)", self.html)

        if not rooms_match:
            raise ParserError('Не найден элемент "Количество комнат"')

        self.rooms = int(rooms_match.group(1))

    def __extract_floor(self):
        floor_match = re.search(r"Этаж: (\d+)", self.html)

        if not floor_match:
            raise ParserError('Не найден элемент "Этаж"')

        self.floor = int(floor_match.group(1))

    def __extract_total_floor(self):
        total_floor_match = re.search(r"Этажность дома: (\d+)", self.html)

        if not total_floor_match:
            raise ParserError('Не найден элемент "Этажность дома"')

        self.total_floor = int(total_floor_match.group(1))

    def __extract_total_area(self):
        total_area_matches = re.search(r">Общая площадь: ([\d\s]+)", self.html)
        if not total_area_matches:
            raise ParserError('Не найден элемент "Общая площадь"')

        total_area_str = total_area_matches.group(1).replace(" ", "")

        try:
            self.total_area_sqm = round(float(total_area_str))
        except ValueError as e:
            raise ParserError(f"Не удалось преобразовать площадь в число: {total_area_str}") from e

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

    def __extract_type_flat(self):
        flat_match = re.search(r"Тип жилья: \s*([А-Я]{1,}[^А-Я]+)", self.html)

        if not flat_match:
            logger.warning('Не удалось получить элемент "Тип жилья"')
            return

        type_flat = re.sub(r"<[^>]+>", "", flat_match.group(1)).strip()
        self.is_new_building = False if type_flat == "Вторичный рынок" else True

    def __extract_building_material(self):
        building_material_match = re.search(r">Тип строения:\s*([А-Я]{1,}[^А-Я]+)<", self.html)

        if not building_material_match:
            logger.warning('Не удалось получить элемент "Тип строения"')
            return

        building_material_clean = re.sub(r"<[^>]+>", "", building_material_match.group(1))
        building_material_text = " ".join(building_material_clean.split()).strip()

        match building_material_text:
            case "Кирпичный":
                self.building_material = BuildingMaterial.brick
            case "Панельный":
                self.building_material = BuildingMaterial.panel
            case "Монолитный":
                self.building_material = BuildingMaterial.monolith
            case "Блочный":
                self.building_material = BuildingMaterial.block
            case "Деревянный":
                self.building_material = BuildingMaterial.wood
            case _:
                raise ParserError(f'Неизвестный тип строения: "{building_material_text}"')

    def __extract_furniture(self):
        furniture_match = re.search(r"Меблирована:\s*([А-Я]{1,}[^А-Я]+)", self.html)

        if not furniture_match:
            raise ParserError('Не удалось найти элемент "Меблирована"')

        self.has_furniture = True if furniture_match.group(1) == "Да" else False

    async def __extract_total_price(self):
        # Нормализуем HTML, заменяя неразрывные пробелы на обычные
        html_normalized = self.html.replace("\xa0", " ")

        # Поиск цены в формате "850 000 у.е."
        total_price_match = re.search(r"([\d\s]+)\sу\.е\.", html_normalized)

        if total_price_match:
            total_price_str = total_price_match.group(1)
            total_price_str = re.search(r"\d+", total_price_str).group(0).replace(" ", "")
            try:
                self.total_price = int(total_price_str)
                return
            except Exception as e:
                raise ParserError(f"Не удалось преобразовать цену в int: {total_price_str}") from e

        # Поиск цены в формате "850 000 $" или "850 000 сум"
        total_price_match = re.search(r"([\d\s]+)\sсум", html_normalized)
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

    async def execute(self) -> PostApartmentSchemas:
        """
        Выполняет парсинг специфичных данных квартиры.
        Базовые данные уже спарсены в BaseParser.parse()
        """
        self.__extract_rooms()
        self.__extract_floor()
        self.__extract_total_floor()
        self.__extract_total_area()
        self.__extract_repair()
        self.__extract_type_flat()
        self.__extract_building_material()
        self.__extract_furniture()
        await self.__extract_total_price()

    async def send_db(self):
        """Сохраняет спарсенные данные в базу данных"""
        from sqlalchemy import select
        from ..models.db_helper import db_helper
        from ..models.post import Post, Source, TypeOfService
        from ..models.post_sale_apartment import PostSaleApartment
        from ..models.post_rent_apartment import PostRentApartment
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
                    is_broker=self.is_broker if hasattr(self, "is_broker") else False,
                )
                session.add(organization)
                await session.flush()  # Получаем ID организации
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
            await session.flush()  # Получаем ID поста

            # 4. Создаем запись в таблице квартир (sale или rent)
            if self.type_of_service == TypeOfService.SALE.value:
                apartment_details = PostSaleApartment(
                    post_id=new_post.id,
                    rooms=self.rooms,
                    floor=self.floor,
                    total_floor=self.total_floor,
                    total_area_sqm=self.total_area_sqm,
                    total_price=self.total_price,
                    is_new_building=self.is_new_building,
                    has_furniture=self.has_furniture,
                    repair=self.repair,
                    building_material=self.building_material,
                )
            else:  # RENT
                apartment_details = PostRentApartment(
                    post_id=new_post.id,
                    rooms=self.rooms,
                    floor=self.floor,
                    total_floor=self.total_floor,
                    total_area_sqm=self.total_area_sqm,
                    total_price=self.total_price,
                    is_new_building=self.is_new_building,
                    has_furniture=self.has_furniture,
                    repair=self.repair,
                    building_material=self.building_material,
                )

            session.add(apartment_details)
            await session.commit()
            logger.success(f"Квартира {self.external_id} успешно сохранена в БД")

        except Exception as e:
            await session.rollback()
            logger.error(f": Ошибка при сохранении квартиры в БД: {e}")
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
            "https://www.olx.uz/d/obyavlenie/27-mkr-da-5-etazhda-zhaylaskan-3-komnataly-kvartira-ID4a2ig.html"
        ) as response:
            page = await response.text()
            soup = BeautifulSoup(page, "lxml")

            # Создаем базовый парсер - он сам определит тип и вызовет ApartmentParse
            result = await BaseParser(
                url="https://www.olx.uz/d/obyavlenie/27-mkr-da-5-etazhda-zhaylaskan-3-komnataly-kvartira-ID4a2ig.html",
                soup=soup,
                session=session,
            ).execute()

            for row in result.__dict__:
                print(row, getattr(result, row))


if __name__ == "__main__":
    asyncio.run(main())
