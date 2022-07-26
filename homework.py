from http import HTTPStatus
import logging
import os
import requests
import time

from dotenv import load_dotenv
import telegram

from exceptions import APIResponseStatusCodeException, CheckResponseException

load_dotenv()

PRACTICUM_TOKEN = os.getenv('TOKEN_OF_PRACTICUM')
TELEGRAM_TOKEN = os.getenv('TOKEN_OF_TELEGRAM')
TELEGRAM_CHAT_ID = os.getenv('ID_OF_CHAT')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(message)s'
)
handler = logging.StreamHandler()
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщений в telegram-чат."""

    try:
        result = bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение успешно отправлено пользователю')
    except Exception as error:
        logger.error(
            f'Произошел сбой при отправке сообщения пользователю: {error}'
        )
    return result


def get_api_answer(current_timestamp):
    """Отпрвка запроса к API-сервису Яндекс.Практикум"""

    timestamp = current_timestamp or int(time.time())
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise APIResponseStatusCodeException(
                f'Ошибка при запросе к основному API'
            )
    except Exception as error:
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    else:
        return homework_statuses.json()


def check_response(response):
    """Проверка ответа от API-сервиса Яндекс.Практикум на коррректность"""

    if response is None:
        raise CheckResponseException('В ответе от API нет словаря')
    if not isinstance(response, dict):
        raise TypeError('Ответ от API не является словарем')
    if 'homeworks' not in response:
        raise KeyError('В ответе от API нет ключа homeworks')
    if not response.get('homeworks'):
        return {}
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение ключа homeworks не является списком')
    return response['homeworks']


def parse_status(homework):
    """Парсинг ответа от API-сервиса Яндекс.Практикум"""

    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise ValueError(
            f'Неизвестный статус домашней работы: {homework_status}'
        )
    if 'homework_name' not in homework:
        raise KeyError('Нет ключа homework_name в словаре')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка переменных окружения"""

    if all([PRACTICUM_TOKEN, TELEGRAM_TOKEN]):
        return True
    return False


def main():
    """Основная логика работы бота."""

    if not check_tokens():
        logger.critical('Не хватает обязательной переменной окружения')
    else:
        logger.debug('Переменные окружения настроены корректно')
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        old_status = ''
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homework = check_response(response)
                status = parse_status(homework[0])
                if old_status != status:
                    send_message(bot, status)
                    old_status = status
                current_timestamp = response.get('current_date')
            except Exception as error:
                logger.error(f'Сбой в работе программы: {error}')
            finally:
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
