import logging
import os
import sys
import time
from http import HTTPStatus
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telegram import Bot

from exceptions import APIError, TokenNotFound

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s -- %(lineno)s -- %(levelname)s -- %(message)s'
)

logger = logging.getLogger(__name__)
handler = StreamHandler(stream=sys.stdout)
logger.addHandler(handler)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PTOKEN')
TELEGRAM_TOKEN = os.getenv('TTOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверить доступность переменных окружения."""
    logging.info('Начало проверки доступности токенов')
    all_tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    if not all(all_tokens):
        logging.critical('Токен не найден в виртуальном окружении!')
        raise TokenNotFound('Токен не найден в виртуальном окружении!')
    logging.info('Токены проверены')
    return True


def send_message(bot, message):
    """Отправка сообщений в Telegram-чат."""
    logging.info('Начало отправки сообщения пользователю')
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug('Отправлено сообщение пользователю')


def get_api_answer(timestamp):
    """Запрос к API."""
    logging.info('Начало запроса к API')
    paramload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=paramload)
    except requests.RequestException:
        raise APIError('Кажется, запрос к API кривой(')
    if response.status_code != HTTPStatus.OK:
        raise APIError('Кажется, запрос к API кривой(')
    logging.info('Запрос к API успешен!')
    return response.json()


def check_response(response):
    """Проверить ответ API."""
    logging.info('Начало проверки ответа API')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является "dict"')
    if 'homeworks' not in response:
        raise KeyError('Ответ API не содержит список проектов')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Список проектов не является "list"')
    for index in range(len(response.get('homeworks'))):
        if 'homework_name' not in response['homeworks'][index]:
            raise KeyError('Ответ API не содержит ключ "homework_name"!')
        if 'status' not in response.get('homeworks')[index]:
            raise KeyError('Ответ API не содержит ключ "status"!')
    logging.info('Проверка ответа API прошла успешно!')
    return response


def parse_status(homework):
    """Проверяется статус домашней работы."""
    logging.info('Начало проверки статуса проекта')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if not homework_status or not homework_name:
        raise KeyError('Не найдено имя или статус проекта в ответе API')
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError('Не найден статус последнего проекта')
    verdict = HOMEWORK_VERDICTS[homework_status]
    logging.info('Проверка статуса проекта успешна!')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    logging.info('Бот запущен.')

    if not check_tokens():
        err_msg = ('Критические переменные'
                   ' не существуют либо повреждены!'
                   ' Бот остановлен.')
        logger.critical(err_msg)
        raise SystemExit(err_msg)

    bot = Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status = ''

    while True:
        try:
            response_hwk = get_api_answer(timestamp)
            timestamp = response_hwk.get('current_date')
            homeworks = check_response(response_hwk)['homeworks']
            last_hwork = homeworks[0]
            message = parse_status(last_hwork)
            if last_status == last_hwork.get('status'):
                message = 'Статус проекта не поменялся'
                logging.info(message)
            try:
                send_message(bot, message)
            except Exception as err:
                logging.error(f'Ошибка отправки сообщения: {err}')
        except IndexError:
            message = 'Статус проекта не поменялся'
            send_message(bot, message)
            logging.info(message)

        except Exception as err:
            msg_error = f'Сбой в работе программы: {err}'
            logging.error(msg_error)
            if str(msg_error) != str(last_status):
                send_message(bot, msg_error)
            last_status = msg_error
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
