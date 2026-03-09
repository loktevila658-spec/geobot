"""
Геологический бот для MAX
Финальная версия с кнопками
"""

import logging
import asyncio
import os
import sys
import json
from dotenv import load_dotenv
from maxapi import Bot, Dispatcher
from maxapi import types

from utils.storage import (
    add_user, get_all_users, set_state, get_state, clear_state,
    set_data, get_data, clear_data, UserState
)
from utils.feedback import add_feedback, get_feedback_stats
from utils.dictionary import GeologicalDictionary

# Загружаем переменные из .env файла (для локальной разработки)
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
    logger.error("Добавьте BOT_TOKEN в настройках Bothost → Environment Variables")
    sys.exit(1)

try:
    ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
    if ADMIN_ID == 0:
        logger.warning("⚠️ ADMIN_ID не задан, команды /stats и /broadcast будут недоступны")
except ValueError:
    logger.error("❌ ADMIN_ID должен быть числом!")
    sys.exit(1)

# Настройки словаря
DICTIONARY_FILE = os.environ.get('DICTIONARY_FILE', 'dictionary.xlsx')
FUZZY_THRESHOLD = float(os.environ.get('FUZZY_THRESHOLD', 0.7))
MAX_SUGGESTIONS = int(os.environ.get('MAX_SUGGESTIONS', 5))

logger.info("✅ Переменные окружения загружены")
logger.info(f"👑 ADMIN_ID: {ADMIN_ID}")
logger.info(f"📚 DICTIONARY_FILE: {DICTIONARY_FILE}")

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
    # Формат для MAX API
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


# ==================== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ ОТПРАВКИ ====================

async def send_message_with_keyboard(chat_id: int, text: str, keyboard: dict = None):
    """Отправка сообщения с клавиатурой"""
    try:
        # Базовый запрос
        data = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        # Добавляем клавиатуру, если есть
        if keyboard:
            data["reply_markup"] = json.dumps(keyboard)

        # Отправляем через прямой API запрос
        url = f"https://botapi.max.ru/bot{BOT_TOKEN}/sendMessage"
        import aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=data) as response:
                if response.status != 200:
                    logger.error(f"Ошибка отправки: {response.status}")
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения: {e}")


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

        # Получаем chat_id из recipient
        recipient = message.recipient
        chat_id = recipient.chat_id

        logger.info(f"📨 ВХОДЯЩЕЕ: от {first_name} (ID:{user_id}) в чат {chat_id}: '{text[:50]}...'")

        # Сохраняем пользователя
        add_user(user_id, chat_id, username, first_name)

        # Если словарь не загружен - сообщаем об ошибке
        if not dictionary:
            await send_message_with_keyboard(
                chat_id,
                "❌ Ошибка: словарь не загружен. Обратитесь к администратору."
            )
            return

        # Получаем состояние пользователя
        state = get_state(user_id)

        # ===== ОБРАБОТКА КОМАНДЫ START =====
        if text == '/start':
            welcome = f"👋 Добро пожаловать, {first_name}!\n\nЯ геологический словарь. Выберите действие:"
            await send_message_with_keyboard(chat_id, welcome, get_main_keyboard())
            return

        # ===== ОБРАБОТКА КНОПОК =====
        if text == "🔍 Найти термин":
            set_state(user_id, UserState.AWAITING_TERM)
            await send_message_with_keyboard(
                chat_id,
                "🔍 Введите геологический термин:",
                get_main_keyboard()
            )
            return

        elif text == "💬 Обратная связь":
            set_state(user_id, UserState.AWAITING_FEEDBACK)
            await send_message_with_keyboard(
                chat_id,
                "📝 Напишите ваше сообщение. Я передам его разработчикам:",
                get_main_keyboard()
            )
            return

        elif text == "📚 О словаре":
            await send_message_with_keyboard(chat_id, SOURCE_INFO, get_main_keyboard())
            return

        elif text == "❓ Помощь":
            help_text = HELP_TEXT.format(count=len(dictionary.terms))
            await send_message_with_keyboard(chat_id, help_text, get_main_keyboard())
            return

        # ===== ОБРАБОТКА КОМАНД АДМИНА =====
        if text.startswith('/stats'):
            if user_id != ADMIN_ID:
                await send_message_with_keyboard(
                    chat_id,
                    "⛔ Команда доступна только администратору.",
                    get_main_keyboard()
                )
                return

            users = get_all_users()
            stats = get_feedback_stats()

            response = f"""
📊 *СТАТИСТИКА БОТА*

👥 **Пользователи:** {len(users)}
📚 **Словарь:** {len(dictionary.terms)} терминов
📬 **Обратная связь:** {stats['total']} всего, {stats['unread']} новых
            """
            await send_message_with_keyboard(chat_id, response, get_main_keyboard())
            return

        if text.startswith('/broadcast'):
            if user_id != ADMIN_ID:
                await send_message_with_keyboard(
                    chat_id,
                    "⛔ Команда доступна только администратору.",
                    get_main_keyboard()
                )
                return

            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                await send_message_with_keyboard(
                    chat_id,
                    "❌ Используйте: /broadcast [текст рассылки]",
                    get_main_keyboard()
                )
                return

            broadcast_text = parts[1].strip()
            users = get_all_users()

            if not users:
                await send_message_with_keyboard(chat_id, "⚠️ Нет пользователей для рассылки.")
                return

            await send_message_with_keyboard(chat_id, f"📤 Начинаю рассылку на {len(users)} пользователей...")

            success = 0
            failed = 0

            for user_id_str, user_data in users.items():
                try:
                    user_chat_id = user_data.get('chat_id')
                    if not user_chat_id:
                        continue

                    await send_message_with_keyboard(
                        user_chat_id,
                        f"📢 *Сообщение от администратора:*\n\n{broadcast_text}"
                    )
                    success += 1
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error(f"Ошибка рассылки: {e}")
                    failed += 1

            await send_message_with_keyboard(
                chat_id,
                f"✅ *Рассылка завершена!*\n\n• Успешно: {success}\n• Ошибок: {failed}",
                get_main_keyboard()
            )
            return

        # ===== ОБРАБОТКА СОСТОЯНИЙ =====

        # Поиск термина
        if state == UserState.AWAITING_TERM:
            result = dictionary.search(text, FUZZY_THRESHOLD, MAX_SUGGESTIONS)

            if result['found']:
                response = f"""
🔍 *{result['term']}*

{result['definition']}

---
{SOURCE_INFO}
                """
                await send_message_with_keyboard(chat_id, response, get_main_keyboard())

            elif result['suggestions']:
                suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
                response = f"""
🤔 Термин *"{text}"* не найден.

Возможно, вы имели в виду:
{suggestions}
                """
                await send_message_with_keyboard(chat_id, response, get_main_keyboard())

            else:
                response = f"""
❌ Термин *"{text}"* не найден в словаре.
                """
                await send_message_with_keyboard(chat_id, response, get_main_keyboard())

            clear_state(user_id)

        # Обратная связь
        elif state == UserState.AWAITING_FEEDBACK:
            user = get_user(user_id)
            user_name = user['name'] if user else first_name
            feedback_id = add_feedback(user_id, user_name, text)

            await send_message_with_keyboard(
                chat_id,
                f"✅ Спасибо! Сообщение #{feedback_id} отправлено разработчикам.",
                get_main_keyboard()
            )
            clear_state(user_id)

        # Если нет состояния и это не кнопка и не команда
        else:
            await send_message_with_keyboard(
                chat_id,
                "Используйте кнопки для навигации 👇",
                get_main_keyboard()
            )

    except Exception as e:
        logger.error(f"❌ Ошибка обработки сообщения: {e}")
        import traceback
        traceback.print_exc()


# ==================== ЗАПУСК БОТА ====================

async def main():
    """Главная функция запуска"""
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ ДЛЯ MAX (ФИНАЛЬНАЯ ВЕРСИЯ)")
    logger.info("=" * 60)
    logger.info(f"📚 Терминов в словаре: {len(dictionary.terms) if dictionary else 0}")
    logger.info(f"👑 Администратор ID: {ADMIN_ID}")
    logger.info("=" * 60)

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        import traceback

        traceback.print_exc()