"""
Геологический бот для MAX
Версия с кнопками - не нужно вводить команды вручную
"""

import logging
import asyncio
import os
import sys
from dotenv import load_dotenv
from maxapi import Bot, Dispatcher
from maxapi import types
from maxapi.keyboards import ReplyKeyboardMarkup, KeyboardButton

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
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("🔍 Найти термин"),
        KeyboardButton("💬 Обратная связь")
    )
    keyboard.add(
        KeyboardButton("📚 О словаре"),
        KeyboardButton("❓ Помощь")
    )
    return keyboard


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


# ==================== ОБРАБОТЧИК КОМАНДЫ START ====================

@dp.message_created(commands=['start'])
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "Пользователь"

    # Сохраняем пользователя
    add_user(user_id, chat_id, None, first_name)

    # Отправляем приветствие с клавиатурой
    await message.answer(
        f"👋 Добро пожаловать, {first_name}!\n\n"
        "Я геологический словарь. Выберите действие:",
        reply_markup=get_main_keyboard()
    )


# ==================== ОБРАБОТЧИКИ КНОПОК ====================

@dp.message_created(lambda message: message.text == "🔍 Найти термин")
async def handle_search_button(message: types.Message):
    """Обработчик кнопки поиска термина"""
    user_id = message.from_user.id
    set_state(user_id, UserState.AWAITING_TERM)

    await message.answer(
        "🔍 Введите геологический термин:",
        reply_markup=get_main_keyboard()
    )


@dp.message_created(lambda message: message.text == "💬 Обратная связь")
async def handle_feedback_button(message: types.Message):
    """Обработчик кнопки обратной связи"""
    user_id = message.from_user.id
    set_state(user_id, UserState.AWAITING_FEEDBACK)

    await message.answer(
        "📝 Напишите ваше сообщение. Я передам его разработчикам:",
        reply_markup=get_main_keyboard()
    )


@dp.message_created(lambda message: message.text == "📚 О словаре")
async def handle_info_button(message: types.Message):
    """Обработчик кнопки информации о словаре"""
    await message.answer(
        SOURCE_INFO,
        reply_markup=get_main_keyboard()
    )


@dp.message_created(lambda message: message.text == "❓ Помощь")
async def handle_help_button(message: types.Message):
    """Обработчик кнопки помощи"""
    help_text = HELP_TEXT.format(count=len(dictionary.terms) if dictionary else 0)
    await message.answer(
        help_text,
        reply_markup=get_main_keyboard()
    )


# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================

@dp.message_created()
async def handle_text(message: types.Message):
    """Обработчик всех текстовых сообщений"""
    try:
        user_id = message.from_user.id
        text = message.text

        # Если это команда /start (уже обработана выше, но на всякий случай)
        if text == '/start':
            return

        # Получаем состояние пользователя
        state = get_state(user_id)

        # Если нет состояния - отправляем на кнопки
        if not state:
            await message.answer(
                "Используйте кнопки для навигации 👇",
                reply_markup=get_main_keyboard()
            )
            return

        # ===== ПОИСК ТЕРМИНА =====
        if state == UserState.AWAITING_TERM:
            if not dictionary:
                await message.answer(
                    "❌ Ошибка: словарь не загружен. Обратитесь к администратору.",
                    reply_markup=get_main_keyboard()
                )
                clear_state(user_id)
                return

            result = dictionary.search(text, FUZZY_THRESHOLD, MAX_SUGGESTIONS)

            if result['found']:
                response = f"""
🔍 *{result['term']}*

{result['definition']}

---
{SOURCE_INFO}
                """
                await message.answer(response, reply_markup=get_main_keyboard())

            elif result['suggestions']:
                suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
                response = f"""
🤔 Термин *"{text}"* не найден.

Возможно, вы имели в виду:
{suggestions}
                """
                await message.answer(response, reply_markup=get_main_keyboard())

            else:
                response = f"""
❌ Термин *"{text}"* не найден в словаре.
                """
                await message.answer(response, reply_markup=get_main_keyboard())

            clear_state(user_id)

        # ===== ОБРАТНАЯ СВЯЗЬ =====
        elif state == UserState.AWAITING_FEEDBACK:
            user = get_user(user_id)
            user_name = user['name'] if user else "Пользователь"
            feedback_id = add_feedback(user_id, user_name, text)

            await message.answer(
                f"✅ Спасибо! Сообщение #{feedback_id} отправлено разработчикам.",
                reply_markup=get_main_keyboard()
            )
            clear_state(user_id)

    except Exception as e:
        logger.error(f"❌ Ошибка обработки сообщения: {e}")
        await message.answer(
            "Произошла ошибка. Попробуйте позже.",
            reply_markup=get_main_keyboard()
        )


# ==================== КОМАНДЫ ДЛЯ АДМИНА ====================

@dp.message_created(commands=['stats'])
async def cmd_stats(message: types.Message):
    """Обработка /stats (только админ)"""
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id != ADMIN_ID:
        await message.answer(
            "⛔ Команда доступна только администратору.",
            reply_markup=get_main_keyboard()
        )
        return

    users = get_all_users()
    stats = get_feedback_stats()

    response = f"""
📊 *СТАТИСТИКА БОТА*

👥 **Пользователи:** {len(users)}
📚 **Словарь:** {len(dictionary.terms) if dictionary else 0} терминов
📬 **Обратная связь:** {stats['total']} всего, {stats['unread']} новых
    """

    await message.answer(response, reply_markup=get_main_keyboard())


@dp.message_created(commands=['broadcast'])
async def cmd_broadcast(message: types.Message):
    """Обработка /broadcast (только админ)"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text

    if user_id != ADMIN_ID:
        await message.answer(
            "⛔ Команда доступна только администратору.",
            reply_markup=get_main_keyboard()
        )
        return

    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "❌ Используйте: /broadcast [текст рассылки]",
            reply_markup=get_main_keyboard()
        )
        return

    broadcast_text = parts[1].strip()
    users = get_all_users()

    if not users:
        await message.answer(
            "⚠️ Нет пользователей для рассылки.",
            reply_markup=get_main_keyboard()
        )
        return

    await message.answer(f"📤 Начинаю рассылку на {len(users)} пользователей...")

    success = 0
    failed = 0

    for user_id_str, user_data in users.items():
        try:
            user_chat_id = user_data.get('chat_id')
            if not user_chat_id:
                continue

            await bot.send_message(
                chat_id=user_chat_id,
                text=f"📢 *Сообщение от администратора:*\n\n{broadcast_text}"
            )
            success += 1
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Ошибка рассылки пользователю {user_id_str}: {e}")
            failed += 1

    await message.answer(
        f"✅ *Рассылка завершена!*\n\n"
        f"• Успешно: {success}\n"
        f"• Ошибок: {failed}",
        reply_markup=get_main_keyboard()
    )


# ==================== ЗАПУСК БОТА ====================

async def main():
    """Главная функция запуска"""
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ ДЛЯ MAX (ВЕРСИЯ С КНОПКАМИ)")
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