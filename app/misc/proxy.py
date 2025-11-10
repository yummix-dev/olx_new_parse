import aiohttp
import logging

from ..core.config import load_config

config = load_config()
logger = logging.getLogger(__name__)


class Proxy:
    def __init__(self):
        self.proxies = {}

    def load(self):
        for ip in config.proxy.ips:
            self.proxies[ip] = {"count": 0, "is_blocked": False}

    def get(self):
        available_proxies = {ip: data for ip, data in self.proxies.items() if not data["is_blocked"]}
        if not available_proxies:
            logger.error("No available proxies - all proxies are blocked")
            raise RuntimeError("No available proxies")

        # Сортируем по count и берём минимально использованный
        least_used_ip = min(available_proxies, key=lambda ip: available_proxies[ip]["count"])

        # Увеличиваем счётчик использования
        self.proxies[least_used_ip]["count"] += 1

        logger.info(f"Selected proxy: {least_used_ip} (used {self.proxies[least_used_ip]['count']} times)")

        return least_used_ip

    def block(self, ip: str):
        """Блокирует прокси (например, при обнаружении бана)"""
        if ip in self.proxies:
            self.proxies[ip]["is_blocked"] = True
            logger.warning(f"Proxy {ip} has been blocked (used {self.proxies[ip]['count']} times)")
        else:
            logger.error(f"Attempted to block unknown proxy: {ip}")

    def unblock(self, ip: str):
        """Разблокирует прокси"""
        if ip in self.proxies:
            self.proxies[ip]["is_blocked"] = False
            logger.info(f"Proxy {ip} has been unblocked")
        else:
            logger.error(f"Attempted to unblock unknown proxy: {ip}")

    def reset_counters(self):
        """Сбрасывает счётчики использования всех прокси"""
        for ip in self.proxies:
            self.proxies[ip]["count"] = 0
        logger.info("All proxy usage counters have been reset")

    def get_stats(self):
        """Возвращает статистику по прокси"""
        stats = {
            "total": len(self.proxies),
            "available": sum(1 for data in self.proxies.values() if not data["is_blocked"]),
            "blocked": sum(1 for data in self.proxies.values() if data["is_blocked"]),
            "proxies": self.proxies.copy(),
        }
        return stats

    @staticmethod
    def authenticate():
        return aiohttp.BasicAuth(login=config.proxy.login, password=config.proxy.password)
