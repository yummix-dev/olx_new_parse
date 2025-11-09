import aiohttp


async def convert_uzs_to_usd(amount: int | float) -> int:
    """
    Конвертирует сумму из узбекских сумов в доллары США.

    Args:
        amount: Сумма в сумах

    Returns:
        Сумма в долларах США

    Raises:
        RuntimeError: Если не удалось получить курс валюты
    """
    target_currency = 'USD'
    url = f'https://open.er-api.com/v6/latest/{target_currency}'
    async with aiohttp.ClientSession() as session:
        response = await session.get(url)
        if response.status != 200:
            raise RuntimeError(f'Failed to convert currency: HTTP {response.status}')
        data = await response.json()

        if 'rates' not in data or 'UZS' not in data['rates']:
            raise RuntimeError('Invalid response from currency API: missing rates data')

        exchange_rate = data['rates']['UZS']
        converted_amount = amount / exchange_rate
        return int(round(converted_amount))
