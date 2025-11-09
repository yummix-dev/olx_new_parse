from dataclasses import dataclass
from environs import Env

env = Env()
# Загрузите переменные окружения из файла .env
env.read_env(path=".env")


@dataclass
class Proxy:
    ips: list
    login: str
    password: str
    port: int


@dataclass
class ParserSettings:
    # Таймаут для запросов (в секундах)
    request_timeout: int
    # Максимальное количество попыток retry
    max_retries: int
    # URL полигонального сервиса
    polygon_service_url: str
    # Whitelist доменов для парсинга
    allowed_domains: list


@dataclass
class RabbitMQ:
    host: str
    port: int
    username: str
    password: str
    vhost: str


@dataclass
class DB:
    user: str
    password: str
    hostname: str
    port: int
    db_name: str
    db_echo: bool


@dataclass
class Config:
    db: DB
    proxy: Proxy
    parser: ParserSettings
    rabbitmq: RabbitMQ


def load_config() -> Config:
    return Config(
        db=DB(
            user=env.str("DB_USER"),
            password=env.str("DB_PASSWORD"),
            hostname=env.str("DB_HOST", "localhost"),
            port=env.int("DB_PORT", 3306),
            db_name=env.str("DB_NAME"),
            db_echo=env.bool("DB_ECHO", False),
        ),
        proxy=Proxy(
            ips=env.list("PROXIES_IP"),
            login=env.str("PROXY_LOGIN"),
            password=env.str("PROXY_PASSWORD"),
            port=env.int("PROXY_PORT"),
        ),
        parser=ParserSettings(
            request_timeout=env.int("REQUEST_TIMEOUT", 10),
            max_retries=env.int("MAX_RETRIES", 3),
            polygon_service_url=env.str("POLYGON_SERVICE_URL", "http://194.87.56.245/search"),
            allowed_domains=env.list("ALLOWED_DOMAINS", ["olx.uz", "www.olx.uz"]),
        ),
        rabbitmq=RabbitMQ(
            host=env.str("RABBITMQ_HOST"),
            port=env.int("RABBITMQ_PORT", 5672),
            username=env.str("RABBITMQ_USERNAME"),
            password=env.str("RABBITMQ_PASSWORD"),
            vhost=env.str("RABBITMQ_VHOST", "/"),
        ),
    )
