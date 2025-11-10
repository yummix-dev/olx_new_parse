import asyncio
import re

import aiohttp
from bs4 import BeautifulSoup
from loguru import logger
from sqlalchemy import and_

from ..exception import ParserError
from ..schemas.post_house import PostHouse as PostHouseSchemas
from ..core.config import load_config
from ..models.post import TypeOfProperty
from ..models.post_sale_apartment import Repair, BuildingMaterial
from ..models.post_sale_house import HouseType
from .parse_post import BaseParser
from ..misc.convert_to_usd import convert_uzs_to_usd

# Загружаем конфигурацию
config = load_config()


class HouseParse(BaseParser):
    type_of_property = TypeOfProperty.HOUSE.value

    def __init__(self, url: str, soup: BeautifulSoup, session: aiohttp.ClientSession):
        super().__init__(url, soup, session)

        self.rooms: int | None = None
        self.total_floor: int | None = None
        self.total_area_sqm: int | None = None
        self.land_area_sqm: int | None = None
        self.total_price: int | None = None
        self.has_furniture: bool = False
        self.repair: Repair | None = None
        self.building_material: BuildingMaterial | None = None
        self.house_type: HouseType | None = None

    def __extract_rooms(self):
        rooms_match = re.search(r"Количество комнат: (\d+)", self.html)

        if not rooms_match:
            logger.warning('Не найден элемент "Количество комнат"')
            return

        self.rooms = int(rooms_match.group(1))

    def __extract_total_floor(self):
        total_floor_match = re.search(r"Этажность дома: (\d+)", self.html)

        if not total_floor_match:
            logger.warning('Не найден элемент "Этажность дома"')
            return

        self.total_floor = int(total_floor_match.group(1))

    def __extract_total_area(self):
        total_area_matches = re.search(r"Общая площадь: ([\d\s]+(?:\.\d+)?)", self.html)
        if not total_area_matches:
            logger.warning('Не найден элемент "Общая площадь"')
            return

        total_area_str = total_area_matches.group(1).replace(" ", "")

        try:
            self.total_area_sqm = round(float(total_area_str))
        except ValueError as e:
            logger.error(f"Не удалось преобразовать площадь в число: {total_area_str}, ошибка: {e}")

    def __extract_land_area(self):
        land_area_match = re.search(r"Площадь участка: ([\d\s]+(?:\.\d+)?)", self.html)

        if not land_area_match:
            logger.warning('Не найден элемент "Площадь участка"')
            return

        land_area_str = land_area_match.group(1).replace(" ", "")

        try:
            self.land_area_sqm = round(float(land_area_str) * 100)
        except ValueError as e:
            logger.error(f"Не удалось преобразовать площадь участка в число: {land_area_str}, ошибка: {e}")

    def __extract_repair(self):
        repair_match = re.search(r"Ремонт:\s*([А-Я]{1,}[^А-Я]+)", self.html)

        if repair_match:
            repair_clean = re.sub(r"<[^>]+>", "", repair_match.group(1))
            repair_text = " ".join(repair_clean.split()).strip().lower()

            if "авторский проект" in repair_text:
                self.repair = Repair.designer
            elif "евроремонт" in repair_text:
                self.repair = Repair.euro
            elif "евро" in repair_text:
                self.repair = Repair.euro
            elif "средний ремонт" in repair_text:
                self.repair = Repair.average
            elif "средний" in repair_text:
                self.repair = Repair.average
            elif "не достроен" in repair_text:
                self.repair = Repair.needs_repair
            elif "под снос" in repair_text:
                self.repair = Repair.needs_repair
            elif "требует ремонта" in repair_text:
                self.repair = Repair.needs_repair
            elif "коробка" in repair_text:
                self.repair = Repair.needs_repair
            elif "черновая отделка" in repair_text:
                self.repair = Repair.rough_finish
            elif "предчистовая отделка" in repair_text:
                self.repair = Repair.pre_finish
            else:
                logger.error(f'Неизвестный тип ремонта: "{repair_text}"')
        else:
            logger.warning('Не найден элемент "Ремонт" или "Состояние дома"')

        # Альтернативный вариант - "Состояние дома"
        repair_match = re.search(r"Состояние дома:\s*([А-Я]{1,}[^А-Я]+)", self.html)
        if repair_match:
            repair_clean = re.sub(r"<[^>]+>", "", repair_match.group(1))
            repair_text = " ".join(repair_clean.split()).strip().lower()

            if "авторский проект" in repair_text:
                self.repair = Repair.designer
            elif "евроремонт" in repair_text:
                self.repair = Repair.euro
            elif "евро" in repair_text:
                self.repair = Repair.euro
            elif "средний ремонт" in repair_text:
                self.repair = Repair.average
            elif "средний" in repair_text:
                self.repair = Repair.average
            elif "не достроен" in repair_text:
                self.repair = Repair.needs_repair
            elif "под снос" in repair_text:
                self.repair = Repair.needs_repair
            elif "требует ремонта" in repair_text:
                self.repair = Repair.needs_repair
            elif "коробка" in repair_text:
                self.repair = Repair.needs_repair
            elif "черновая отделка" in repair_text:
                self.repair = Repair.rough_finish
            elif "предчистовая отделка" in repair_text:
                self.repair = Repair.pre_finish
            else:
                logger.error(f'Неизвестный тип ремонта: "{repair_text}"')
        else:
            logger.warning('Не найден элемент "Ремонт" или "Состояние дома"')

    def __extract_building_material(self):
        building_material_match = re.search(r">Тип строения:\s*([А-Я]{1,}[^А-Я]+)<", self.html)

        if not building_material_match:
            logger.warning('Не найден элемент "Тип строения"')
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

    def __extract_house_type(self):
        house_type_match = re.search(r">Тип дома:\s*([А-Яа-я\s]+)<", self.html)

        if not house_type_match:
            logger.warning('Не найден элемент "Тип дома"')
            return

        house_type_clean = re.sub(r"<[^>]+>", "", house_type_match.group(1))
        house_type_text = " ".join(house_type_clean.split()).strip().lower()

        match house_type_text:
            case "дом":
                self.house_type = HouseType.house
            case "флигель":
                self.house_type = HouseType.wing
            case "коттедж":
                self.house_type = HouseType.cottage
            case "часть дома":
                self.house_type = HouseType.part_of_house
            case "дача":
                self.house_type = HouseType.dacha
            case "таунхаус":
                self.house_type = HouseType.townhouse
            case _:
                raise ParserError(f'Неизвестный тип дома: "{house_type_text}"')

    def __extract_furniture(self):
        furniture_match = re.search(r"Меблирована:\s*([А-Я]{1,}[^А-Я]+)", self.html)

        if not furniture_match:
            logger.warning('Не найден элемент "Меблирована"')
            return

        self.has_furniture = True if furniture_match.group(1) == "Да" else False

    async def __extract_total_price(self):
        # Нормализуем HTML, заменяя неразрывные пробелы на обычные
        html_normalized = self.html.replace("\xa0", " ")

        # Поиск цены в формате "850 000 у.е."
        total_price_match = re.search(r"([\d\s]+)\s*у\.е\.", html_normalized)
        if total_price_match:
            total_price_str = total_price_match.group(1).replace(" ", "")
            try:
                self.total_price = int(total_price_str)
                self.__calculate_price_per_square()
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
                self.__calculate_price_per_square()
                return
            except Exception as e:
                raise ParserError(f"Не удалось преобразовать цену в int: {total_price_str}") from e

        raise ParserError('Не удалось получить элемент "Цена"')

    def __calculate_price_per_square(self):
        """Вычисляет цену за квадратный метр"""
        if self.total_price and self.total_area_sqm:
            try:
                self.price_per_square = round(float(self.total_price) / float(self.total_area_sqm), 2)
            except (ValueError, TypeError, ZeroDivisionError) as e:
                logger.warning(
                    f"Не удалось вычислить цену за квадратный метр: "
                    f"price={self.total_price}, area={self.total_area_sqm}, ошибка: {e}"
                )
                self.price_per_square = None

    async def execute(self) -> PostHouseSchemas:
        """
        Выполняет парсинг специфичных данных дома.
        Базовые данные уже спарсены в BaseParser.parse()
        """
        self.__extract_rooms()
        self.__extract_total_floor()
        self.__extract_total_area()
        self.__extract_land_area()
        self.__extract_repair()
        self.__extract_building_material()
        self.__extract_house_type()
        self.__extract_furniture()
        await self.__extract_total_price()

    async def send_db(self):
        """Сохраняет спарсенные данные в базу данных"""
        from sqlalchemy import select
        from ..models.db_helper import db_helper
        from ..models.post import Post, Source, TypeOfService
        from ..models.post_sale_house import PostSaleHouse
        from ..models.post_rent_house import PostRentHouse
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

            # 4. Создаем запись в таблице домов (sale или rent)
            if self.type_of_service == TypeOfService.SALE.value:
                house_details = PostSaleHouse(
                    post_id=new_post.id,
                    rooms=self.rooms,
                    total_floor=self.total_floor,
                    total_area_sqm=self.total_area_sqm,
                    land_area_sqm=self.land_area_sqm,
                    total_price=self.total_price,
                    has_furniture=self.has_furniture,
                    building_material=self.building_material,
                    repair=self.repair,
                    house_type=self.house_type,
                )
            else:  # RENT
                house_details = PostRentHouse(
                    post_id=new_post.id,
                    rooms=self.rooms,
                    total_floor=self.total_floor,
                    total_area_sqm=self.total_area_sqm,
                    land_area_sqm=self.land_area_sqm,
                    total_price=self.total_price,
                    has_furniture=self.has_furniture,
                    building_material=self.building_material,
                    repair=self.repair,
                    house_type=self.house_type,
                )

            session.add(house_details)
            await session.commit()
            logger.success(f"Дом {self.external_id} успешно сохранен в БД")

        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при сохранении дома в БД: {e}")
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
            "https://www.olx.uz/d/obyavlenie/ipoteka-sotiladi-dacha-hovli-5-25sot-bstonli-tumani-bayt-uron-ID48x54.html"
        ) as response:
            page = await response.text()
            soup = BeautifulSoup(page, "lxml")

            # Создаем базовый парсер - он сам определит тип и вызовет HouseParse
            url = (
                "https://www.olx.uz/d/obyavlenie/"
                "ipoteka-sotiladi-dacha-hovli-5-25sot-bstonli-tumani-bayt-uron-ID48x54.html"
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
