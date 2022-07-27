from http import HTTPStatus
import logging
import os
import requests
import time

from dotenv import load_dotenv
import telegram

from exceptions import APIResponseStatusCodeError
from exceptions import MissingRequiredTokenError
from exceptions import ServerResponseError
from exceptions import TelegramError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('TOKEN_OF_PRACTICUM')
TELEGRAM_TOKEN = os.getenv('TOKEN_OF_TELEGRAM')
TELEGRAM_CHAT_ID = os.getenv('ID_OF_CHAT')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
FORMAT_OF_LOGS = ('%(asctime)s - %(name)s - %(lineno)s - '
                  '%(levelname)s - %(funcName)s()- %(message)s')

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

PARSE_STATUS_MESSAGE_ERROR = 'Неизвестный статус домашней работы: {status}'
PARSE_STATUS_MESSAGE_RESULT = 'Изменился статус проверки работы "{name}". {verdict}'

CHECK_RESPONSE_MESSAGE_ERROR = 'В ответе от API нет словаря'
CHECK_RESPONSE_MESSAGE_ERROR_2 = ('Ответ от API не является словарем'
                                  'Полученный тип: {}')
CHECK_RESPONSE_MESSAGE_ERROR_3 = 'В ответе от API нет ключа homeworks'
CHECK_RESPONSE_MESSAGE_ERROR_4 = ('Значение ключа homeworks не является списком. '
                                  'Полученный тип ключа: {}.')

CHECK_TOKENS_LOG_ERROR = 'Не хватает обязательной переменной окружения {name}'

SEND_MESSAGE_LOG_INFO = 'Сообщение {message} успешно отправлено пользователю'
SEND_MESSAGE_MESSAGE_ERROR = ('Произошла ошибка во время отправки сообщения'
                              ' {message} в чат: {error}')

GET_API_ANSWER_MESSAGE_ERROR = ('Ошибка подключении к основному API '
                                'с параметрами: '
                                '{HEADERS}, {current_timestamp}. '
                                'Эндпоинт {ENDPOINT}. '
                                'Ошибка: {error}. ')

GET_API_ANSWER_MESSAGE_ERROR_2 = ('Ошибка при запросе к основному API '
                                  'с параметрами: '
                                  '{HEADERS}, {current_timestamp}. '
                                  'Эндпоинт {ENDPOINT}. '
                                  'Получен ответ: {homework_statuses}')

GET_API_ANSWER_MESSAGE_ERROR_3 = ('Обнаружена проблема с сервером. '
                                  'Код ошибки: {server_error}. ')

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
formatter = logging.Formatter(FORMAT_OF_LOGS)
file_handler = logging.FileHandler(__file__ + '.log')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(FORMAT_OF_LOGS))
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.addHandler(file_handler)


def send_message(bot, message):
    """Отправка сообщений в telegram-чат."""
    try:
        result = bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.info(SEND_MESSAGE_LOG_INFO.format(message=message))
    except telegram.error.TelegramError as error:
        raise TelegramError(SEND_MESSAGE_MESSAGE_ERROR.format(
            message=message, error=error
        ))
    return result


def get_api_answer(current_timestamp):
    """Отпрвка запроса к API-сервису Яндекс.Практикум."""
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': current_timestamp}
        )
    except requests.exceptions.RequestException as error:
        raise ConnectionError(GET_API_ANSWER_MESSAGE_ERROR.format(
            HEADERS=HEADERS,
            current_timestamp=current_timestamp,
            ENDPOINT=ENDPOINT,
            error=error
        ))

    if 'error' in homework_statuses.json():
        raise ServerResponseError(GET_API_ANSWER_MESSAGE_ERROR_3.format(
            server_error=homework_statuses.json().get('error')
        ))

    if homework_statuses.status_code != HTTPStatus.OK:
        raise APIResponseStatusCodeError(GET_API_ANSWER_MESSAGE_ERROR_2.format(
            HEADERS=HEADERS,
            current_timestamp=current_timestamp,
            ENDPOINT=ENDPOINT,
            homework_statuses=homework_statuses.status_code
        ))
    return homework_statuses.json()


def check_response(response):
    """Проверка ответа от API-сервиса Яндекс.Практикум на коррректность."""
    if response is None:
        raise TypeError(CHECK_RESPONSE_MESSAGE_ERROR)
    if not isinstance(response, dict):
        raise TypeError(CHECK_RESPONSE_MESSAGE_ERROR_2.format(type(response)))
    if 'homeworks' not in response:
        raise KeyError(CHECK_RESPONSE_MESSAGE_ERROR_3)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(CHECK_RESPONSE_MESSAGE_ERROR_4.format({type(response["homeworks"])}))
    return homeworks


def parse_status(homework):
    """Парсинг ответа от API-сервиса Яндекс.Практикум."""
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            PARSE_STATUS_MESSAGE_ERROR.format(status=status)
        )
    verdict = HOMEWORK_VERDICTS[status]
    return PARSE_STATUS_MESSAGE_RESULT.format(name=name, verdict=verdict)


def check_tokens():
    """Проверка переменных окружения."""
    for name in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN']:
        if name not in globals() or not globals()[name]:
            logger.critical(CHECK_TOKENS_LOG_ERROR.format(name=name))
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise MissingRequiredTokenError('Отсутствует переменная окружения')
    logger.debug('Переменные окружения настроены корректно')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    old_status = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                status = parse_status(homework[0])
                if old_status != status:
                    send_message(bot, status)
                    old_status = status
            current_timestamp = response.get('current_date', current_timestamp)
        except Exception as error:
            error_message = f'Проблема с ботом: {error}'
            send_message(bot, error_message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
