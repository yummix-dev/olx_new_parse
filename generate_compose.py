import yaml

# === Настройки ===
PROXIES_PER_CONTAINER = 10  # сколько прокси на 1 контейнер
PROXY_PORT = 3000
PROXY_LOGIN = "mSx81Xtb"
PROXY_PASSWORD = "HUmetwMO"

# === Читаем прокси из файла ===
with open("proxies.txt") as f:
    proxies = [line.strip() for line in f if line.strip()]

# Проверим, что файл не пустой
if not proxies:
    raise ValueError("❌ Файл proxies.txt пуст или не найден!")

# === Разделяем по 10 штук на контейнер ===
chunks = [proxies[i : i + PROXIES_PER_CONTAINER] for i in range(0, len(proxies), PROXIES_PER_CONTAINER)]

# === Базовая структура compose ===
compose = {"version": "3.8", "services": {}}

# === Генерируем сервисы ===
for i, chunk in enumerate(chunks, start=1):
    service_name = f"parser_{i}"
    compose["services"][service_name] = {
        "build": {"context": ".", "dockerfile": "Dockerfile"},
        "container_name": service_name,
        "environment": {
            "PROXIES_IP": ",".join(chunk),
            "PROXY_PORT": PROXY_PORT,
            "PROXY_LOGIN": PROXY_LOGIN,
            "PROXY_PASSWORD": PROXY_PASSWORD,
        },
        "restart": "unless-stopped",
    }

# === Записываем результат ===
with open("docker-compose.generated.yml", "w") as f:
    yaml.dump(compose, f, sort_keys=False)

print(f"✅ Успешно создан docker-compose.generated.yml с {len(chunks)} контейнерами.")
