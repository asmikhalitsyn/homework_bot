import logging
from logging import StreamHandler
import os
import requests
import time

from dotenv import load_dotenv
import telegram

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
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.info('Сообщение успешно отправлено пользователю')
    except Exception as error:
        logger.error(f'Произошел сбой при отправке сообщения пользователю: {error}')


def get_api_answer(current_timestamp):
    """Отпрвка запроса к API-сервису Яндекс.Практикум"""
    timestamp = current_timestamp or int(time.time())
    try:
        homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params={'from_date': timestamp})
    except Exception as error:
        logger.error(f'Ошибка при запросе к основному API: {error}')
    else:
        return homework_statuses.json()


def check_response(response):
    """Проверка ответа от API-сервиса Яндекс.Практикум на коррректность"""
    try:
        response['homeworks']
    except KeyError as error:
        logger.error(f'В ответе API отсутсвует ключ: {error}')
    else:
        return response['homeworks']


def parse_status(homework):
    """Парсинг ответа от API-сервиса Яндекс.Практикум"""
    homework_status = homework['status']
    try:
        HOMEWORK_STATUSES[homework_status]
    except KeyError as error:
        logger.error(f'Недокументированный статус домашней работы: {error}')
    else:
        logger.debug(f'В ответе отсутствуют новые статусы домашней работы')
        return (f'Изменился статус проверки работы "{homework["homework_name"]}".'
                f'{HOMEWORK_STATUSES[homework_status]}')


def check_tokens(token_of_practicum, token_of_telegram):
    if all([token_of_practicum, token_of_telegram]):
        return True
    return False


def main():
    """Основная логика работы бота."""
    dictionary_help = {}
    try:
        if check_tokens(PRACTICUM_TOKEN, TELEGRAM_TOKEN):
            logger.debug('Переменные окружения настроены корректно')
        else:
            logger.critical('Переменная окружения имеет пустое значение')
    except Exception as error:
        logger.critical(f'Не хватает обязательной переменной окружения: {error}')
    else:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        while True:
            try:
                response = get_api_answer(current_timestamp)
                if not check_response(response):
                    current_timestamp = response['current_date']
                    time.sleep(RETRY_TIME)
                    continue
            except Exception as error:
                logger.error(f'Сбой в работе программы: {error}')
                time.sleep(RETRY_TIME)
            else:
                for homework in check_response(response):
                    if homework['homework_name'] not in dictionary_help:
                        dictionary_help[homework['homework_name']] = homework['status']
                    if homework['status'] != dictionary_help[homework['homework_name']]:
                        send_message(bot, parse_status(homework))


if __name__ == '__main__':
    main()
