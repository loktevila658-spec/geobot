"""
Геологический бот для MAX
Универсальная версия - работает с любым API
"""

import logging
import asyncio
import os
import sys
import json
import aiohttp
from dotenv import load_dotenv
from maxapi import Bot, Dispatcher
from maxapi import types

from utils.storage import (
    add_user, get_all_users, set_state, get_state, clear_state,
    set_data, get_data, clear_data, UserState
)
from utils.feedback import add_feedback, get_feedback_stats
from utils.dictionary import GeologicalDictionary

# Загружаем переменные из .env файла
load_dotenv()

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ==================== ПРОВЕРКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ====================

BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан в переменных окружения!")
    sys.exit(1)

try:
    ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
except ValueError:
    ADMIN_ID = 0
    logger.warning("⚠️ ADMIN_ID не задан или некорректен")

# Настройки словаря
DICTIONARY_FILE = os.environ.get('DICTIONARY_FILE', 'dictionary.xlsx')
FUZZY_THRESHOLD = float(os.environ.get('FUZZY_THRESHOLD', 0.7))
MAX_SUGGESTIONS = int(os.environ.get('MAX_SUGGESTIONS', 5))

logger.info("✅ Переменные окружения загружены")
logger.info(f"👑 ADMIN_ID: {ADMIN_ID}")
logger.info(f"📚 Терминов в словаре: загружается...")

# ==================== ИНИЦИАЛИЗАЦИЯ ====================

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Инициализация словаря
try:
    dictionary = GeologicalDictionary(DICTIONARY_FILE)
    logger.info(f"✅ Загружено {len(dictionary.terms)} терминов")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки словаря: {e}")
    dictionary = None


# ==================== КЛАВИАТУРА ====================

def get_main_keyboard():
    """Главная клавиатура с кнопками"""
    return {
        "keyboard": [
            [{"text": "🔍 Найти термин"}, {"text": "💬 Обратная связь"}],
            [{"text": "📚 О словаре"}, {"text": "❓ Помощь"}]
        ],
        "resize_keyboard": True
    }


# ==================== ИНФОРМАЦИОННЫЕ ТЕКСТЫ ====================

SOURCE_INFO = """
📚 *Краткий геологический словарь для школьников*
Под ред. Г. И. Немкова — М.: Недра, 1989. — 176 с.

👥 *Авторы:*
Г. И. НЕМКОВ, Б. Е. КАРСКИЙ, Н. Г. ЛИН, 
И. Ф. РОМАНОВИЧ, В. Р. ЛОЗОВСКИЙ, А. А. АНУФРИЕВ
"""

HELP_TEXT = """
❓ *КАК ПОЛЬЗОВАТЬСЯ*

1️⃣ Нажмите "🔍 Найти термин"
2️⃣ Введите геологический термин
3️⃣ Получите определение

💬 Если термина нет в словаре - напишите нам через "💬 Обратная связь"

📚 Всего в словаре: {count} терминов
"""


# ==================== ФУНКЦИЯ ОТПРАВКИ СООБЩЕНИЙ ====================

async def send_max_message(chat_id: int, text: str, keyboard: dict = None):
    """Универсальная отправка сообщений в MAX"""

    # Пробуем разные варианты URL
    api_urls = [
        f"https://botapi.max.ru/bot{BOT_TOKEN}/sendMessage",
        f"https://api.max.ru/bot{BOT_TOKEN}/sendMessage",
        f"https://botapi.max.ru/v1/bot{BOT_TOKEN}/sendMessage",
        f"https://botapi.max.ru/bot{BOT_TOKEN}/sendMessage"
    ]

    # Формируем данные
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }

    if keyboard:
        data["reply_markup"] = json.dumps(keyboard)

    # Пробуем отправить через все URL
    async with aiohttp.ClientSession() as session:
        for url in api_urls:
            try:
                logger.info(f"🔄 Пробую отправить через {url}")
                async with session.post(url, json=data, timeout=10) as response:
                    if response.status == 200:
                        logger.info(f"✅ Сообщение отправлено через {url}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.warning(f"❌ URL {url} вернул статус {response.status}: {response_text[:100]}")
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при отправке через {url}: {e}")
                continue

    logger.error("❌ НЕ УДАЛОСЬ ОТПРАВИТЬ СООБЩЕНИЕ НИ ЧЕРЕЗ ОДИН URL")
    return False


# ==================== ОБРАБОТЧИК СООБЩЕНИЙ ====================

@dp.message_created()
async def handle_message(event):
    """Главный обработчик всех сообщений"""
    try:
        message = event.message
        if not message:
            return

        # Получаем текст сообщения
        if not hasattr(message, 'body') or not message.body:
            return

        text = message.body.text
        if not text:
            return

        # Получаем информацию об отправителе
        sender = message.sender
        user_id = sender.user_id
        first_name = sender.first_name or "Пользователь"
        username = sender.username

        # Получаем chat_id
        recipient = message.recipient
        chat_id = recipient.chat_id

        logger.info(f"📨 ВХОДЯЩЕЕ: от {first_name} (ID:{user_id}) в чат {chat_id}: '{text[:50]}...'")

        # Сохраняем пользователя
        add_user(user_id, chat_id, username, first_name)

        # Если словарь не загружен
        if not dictionary:
            await send_max_message(chat_id, "❌ Ошибка: словарь не загружен")
            return

        # Получаем состояние пользователя
        state = get_state(user_id)

        # ===== ОБРАБОТКА /start =====
        if text == '/start':
            welcome = f"👋 Добро пожаловать, {first_name}!\n\nЯ геологический словарь. Выберите действие:"
            await send_max_message(chat_id, welcome, get_main_keyboard())
            return

        # ===== ОБРАБОТКА КНОПОК =====
        if text == "🔍 Найти термин":
            set_state(user_id, UserState.AWAITING_TERM)
            await send_max_message(chat_id, "🔍 Введите геологический термин:", get_main_keyboard())
            return

        elif text == "💬 Обратная связь":
            set_state(user_id, UserState.AWAITING_FEEDBACK)
            await send_max_message(chat_id, "📝 Напишите ваше сообщение:", get_main_keyboard())
            return

        elif text == "📚 О словаре":
            await send_max_message(chat_id, SOURCE_INFO, get_main_keyboard())
            return

        elif text == "❓ Помощь":
            help_text = HELP_TEXT.format(count=len(dictionary.terms))
            await send_max_message(chat_id, help_text, get_main_keyboard())
            return

        # ===== ОБРАБОТКА КОМАНД АДМИНА =====
        if text.startswith('/stats'):
            if user_id != ADMIN_ID:
                await send_max_message(chat_id, "⛔ Команда только для админа", get_main_keyboard())
                return

            users = get_all_users()
            stats = get_feedback_stats()
            response = f"📊 Статистика:\n👥 Пользователи: {len(users)}\n📚 Терминов: {len(dictionary.terms)}\n📬 Feedback: {stats['total']} всего, {stats['unread']} новых"
            await send_max_message(chat_id, response, get_main_keyboard())
            return

        # ===== ОБРАБОТКА СОСТОЯНИЙ =====

        # Поиск термина
        if state == UserState.AWAITING_TERM:
            result = dictionary.search(text, FUZZY_THRESHOLD, MAX_SUGGESTIONS)

            if result['found']:
                response = f"🔍 *{result['term']}*\n\n{result['definition']}\n\n---{SOURCE_INFO}"
                await send_max_message(chat_id, response, get_main_keyboard())
            elif result['suggestions']:
                suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
                response = f"🤔 Термин не найден. Возможно, вы имели в виду:\n{suggestions}"
                await send_max_message(chat_id, response, get_main_keyboard())
            else:
                await send_max_message(chat_id, "❌ Термин не найден в словаре.", get_main_keyboard())

            clear_state(user_id)

        # Обратная связь
        elif state == UserState.AWAITING_FEEDBACK:
            user = get_user(user_id)
            user_name = user['name'] if user else first_name
            feedback_id = add_feedback(user_id, user_name, text)
            await send_max_message(chat_id, f"✅ Спасибо! Сообщение #{feedback_id} отправлено.", get_main_keyboard())
            clear_state(user_id)

        # Если нет состояния
        else:
            await send_max_message(chat_id, "Используйте кнопки для навигации 👇", get_main_keyboard())

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ (УНИВЕРСАЛЬНАЯ ВЕРСИЯ)")
    logger.info("=" * 60)
    logger.info(f"📚 Терминов: {len(dictionary.terms) if dictionary else 0}")
    logger.info(f"👑 ADMIN_ID: {ADMIN_ID}")
    logger.info("=" * 60)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())