from http import HTTPStatus
import logging
import os
import requests
import time

from dotenv import load_dotenv
import telegram

from exceptions import APIResponseStatusCodeError
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

UNKNOWN_HOMEWORK = 'Неизвестный статус домашней работы: {status}'
CHECK_CHANGE_STATUS = ('Изменился статус проверки работы "{name}".'
                       ' {verdict}')

ANSWER_WITHOUT_DICT = 'В ответе от API нет словаря'
NO_DICT = ('Ответ от API не является словарем'
           'Полученный тип: {}')
NO_HOMEWORKS = 'В ответе от API нет ключа homeworks'
HOMEWORKS_NO_LIST = ('Значение ключа homeworks'
                     ' не является списком. '
                     'Полученный тип ключа: {}.')

NO_TOKEN = 'Не хватает обязательной переменной окружения {name}'

SUCCESS_MESSAGE = 'Сообщение {message} успешно отправлено пользователю'
ERROR_MESSAGE = ('Произошла ошибка во время отправки сообщения'
                 ' {message} в чат: {error}')

FAIL_CONNECTION = ('Ошибка подключении к основному API '
                   'с параметрами: '
                   '{HEADERS}, {params}. '
                   'Эндпоинт: {ENDPOINT}. '
                   'Ошибка: {error}. ')

FAIL_STATUS = ('Ошибка при запросе к основному API '
               'с параметрами: '
               '{HEADERS}, {params}. '
               'Эндпоинт: {ENDPOINT}. '
               'Получен ответ: {homework_statuses}')

FAIL_SERVER = ('Обнаружена проблема с сервером. '
               'с параметрами: '
               'Эндпоинт: {ENDPOINT}. '
               '{HEADERS}, {params}. '
               'Код ошибки: {server_error}.'
               )
BOT_ERROR = 'Проблема с ботом: {error}'
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']
KEY_OF_SERVER_ERROR = ['error', 'code']

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
        logger.info(SUCCESS_MESSAGE.format(message=message))
    except Exception as error:
        logger.exception(ERROR_MESSAGE.format(
            message=message, error=error
        ))
    return result


def get_api_answer(current_timestamp):
    """Отпрвка запроса к API-сервису Яндекс.Практикум."""
    params = {'from_date': current_timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except requests.exceptions.RequestException as error:
        raise ConnectionError(FAIL_CONNECTION.format(
            HEADERS=HEADERS,
            params=params,
            ENDPOINT=ENDPOINT,
            error=error
        ))
    homework = homework_statuses.json()
    for key in KEY_OF_SERVER_ERROR:
        if key in homework:
            raise ServerResponseError(FAIL_SERVER.format(
                server_error=homework.get(key),
                ENDPOINT=ENDPOINT,
                HEADERS=HEADERS,
                params=params
            ))

    if homework_statuses.status_code != HTTPStatus.OK:
        raise APIResponseStatusCodeError(FAIL_STATUS.format(
            HEADERS=HEADERS,
            params=params,
            ENDPOINT=ENDPOINT,
            homework_statuses=homework_statuses.status_code
        ))
    return homework


def check_response(response):
    """Проверка ответа от API-сервиса Яндекс.Практикум на коррректность."""
    if response is None:
        raise TypeError(ANSWER_WITHOUT_DICT)
    if not isinstance(response, dict):
        raise TypeError(NO_DICT.format(type(response)))
    if 'homeworks' not in response:
        raise KeyError(NO_HOMEWORKS)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(HOMEWORKS_NO_LIST.format(
            {type(homeworks)}
        ))
    return homeworks


def parse_status(homework):
    """Парсинг ответа от API-сервиса Яндекс.Практикум."""
    name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(
            UNKNOWN_HOMEWORK.format(status=status)
        )
    verdict = HOMEWORK_VERDICTS[status]
    return CHECK_CHANGE_STATUS.format(name=name, verdict=verdict)


def check_tokens():
    """Проверка переменных окружения."""
    for token in TOKENS:
        if token not in globals() or not globals()[token]:
            logger.critical(NO_TOKEN.format(name=token))
            return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise KeyError('Отсутствует переменная окружения')
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
            logger.exception(BOT_ERROR.format(error=error))
            try:
                send_message(bot, BOT_ERROR.format(error=error))
            except Exception:
                pass
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
