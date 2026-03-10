"""
Геологический бот для MAX
Исправленная версия с правильными атрибутами
"""

import logging
import asyncio
import os
import sys
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
    logger.error("❌ КРИТИЧЕСКАЯ ОШИБКА: BOT_TOKEN не задан!")
    sys.exit(1)

try:
    ADMIN_ID = int(os.environ.get('ADMIN_ID', 0))
except ValueError:
    ADMIN_ID = 0

# Настройки словаря
DICTIONARY_FILE = os.environ.get('DICTIONARY_FILE', 'dictionary.xlsx')
FUZZY_THRESHOLD = float(os.environ.get('FUZZY_THRESHOLD', 0.7))
MAX_SUGGESTIONS = int(os.environ.get('MAX_SUGGESTIONS', 5))

# ==================== ИНИЦИАЛИЗАЦИЯ ====================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Инициализация словаря
try:
    dictionary = GeologicalDictionary(DICTIONARY_FILE)
    logger.info(f"✅ Загружено {len(dictionary.terms)} терминов")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки словаря: {e}")
    dictionary = None

# ==================== ТЕКСТЫ ====================

WELCOME_TEXT = """
👋 *Здравствуйте, {name}!*

Я геологический словарь. Помогу найти определение любого геологического термина.

📋 *Доступные команды:*
/поиск - найти термин
/связь - написать разработчикам
/помощь - список команд
/источник - информация о словаре

Просто выберите команду 👇
"""

HELP_TEXT = """
❓ *Команды бота:*

🔍 *Поиск термина*
/поиск - активировать режим поиска.
После команды просто вводите слова, и я буду искать их в словаре.

✉️ *Обратная связь*
/связь - отправить сообщение разработчикам.
Напишите, если нашли ошибку или хотите предложить новый термин.

📚 *О словаре*
/источник - информация об авторах и издании.

📋 *Эта справка*
/помощь - показать это сообщение.

Чтобы выйти из режима поиска, просто введите /поиск еще раз.
"""

SOURCE_INFO = """
📚 *Краткий геологический словарь для школьников*
Под ред. Г. И. Немкова — М.: Недра, 1989. — 176 с.

Авторы: Г. И. НЕМКОВ, Б. Е. КАРСКИЙ, Н. Г. ЛИН, 
И. Ф. РОМАНОВИЧ, В. Р. ЛОЗОВСКИЙ, А. А. АНУФРИЕВ
"""

SEARCH_MODE_TEXT = """
🔍 *Режим поиска активирован!*

Теперь просто вводите геологические термины одним словом, и я буду показывать их определения.

Например: *базальт*, *гранит*, *известняк*

Чтобы выйти из режима поиска, снова введите /поиск
"""

EXIT_SEARCH_TEXT = """
✅ Вы вышли из режима поиска.

Используйте /поиск, чтобы снова искать термины.
"""


# ==================== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ====================

def get_user_info(message):
    """Получает информацию о пользователе из сообщения"""
    try:
        from_user = message.from_user

        # Получаем user_id
        if hasattr(from_user, 'user_id'):
            user_id = from_user.user_id
        elif hasattr(from_user, 'id'):
            user_id = from_user.id
        else:
            user_id = 0
            logger.warning("⚠️ Не удалось получить user_id")

        first_name = getattr(from_user, 'first_name', 'Пользователь')
        username = getattr(from_user, 'username', '')

        return user_id, first_name, username
    except Exception as e:
        logger.error(f"❌ Ошибка в get_user_info: {e}")
        return 0, "Пользователь", ""


def get_chat_id(message):
    """Получает chat_id из сообщения"""
    try:
        # Пробуем разные варианты получения chat_id
        if hasattr(message, 'chat'):
            chat = message.chat
            if hasattr(chat, 'chat_id'):
                return chat.chat_id
            elif hasattr(chat, 'id'):
                return chat.id

        # Если ничего не нашли, пробуем из recipient
        if hasattr(message, 'recipient') and hasattr(message.recipient, 'chat_id'):
            return message.recipient.chat_id

        logger.warning("⚠️ Не удалось получить chat_id")
        return 0
    except Exception as e:
        logger.error(f"❌ Ошибка в get_chat_id: {e}")
        return 0


# ==================== ОБРАБОТЧИК КОМАНДЫ /start ====================

@dp.message_created(commands=['start'])
async def cmd_start(message: types.Message):
    """Приветствие"""
    try:
        user_id, first_name, username = get_user_info(message)
        chat_id = get_chat_id(message)

        logger.info(f"📨 /start от {first_name} (ID:{user_id}) в чат {chat_id}")

        # Сохраняем пользователя
        if user_id and chat_id:
            add_user(user_id, chat_id, username, first_name)
            await message.answer(WELCOME_TEXT.format(name=first_name))
        else:
            await message.answer("👋 Добро пожаловать! (не удалось идентифицировать пользователя)")

    except Exception as e:
        logger.error(f"❌ Ошибка в /start: {e}")


# ==================== ОБРАБОТЧИК КОМАНДЫ /поиск ====================

@dp.message_created(commands=['поиск'])
async def cmd_search_mode(message: types.Message):
    """Вход/выход из режима поиска"""
    try:
        user_id, first_name, username = get_user_info(message)

        if not user_id:
            await message.answer("❌ Ошибка идентификации пользователя")
            return

        current_state = get_state(user_id)

        if current_state == UserState.AWAITING_TERM:
            clear_state(user_id)
            await message.answer(EXIT_SEARCH_TEXT)
        else:
            set_state(user_id, UserState.AWAITING_TERM)
            await message.answer(SEARCH_MODE_TEXT)

    except Exception as e:
        logger.error(f"❌ Ошибка в /поиск: {e}")


# ==================== ОБРАБОТЧИК КОМАНДЫ /связь ====================

@dp.message_created(commands=['связь'])
async def cmd_feedback(message: types.Message):
    """Режим обратной связи"""
    try:
        user_id, first_name, username = get_user_info(message)

        if not user_id:
            await message.answer("❌ Ошибка идентификации пользователя")
            return

        set_state(user_id, UserState.AWAITING_FEEDBACK)

        await message.answer(
            "📝 *Напишите ваше сообщение*\n\n"
            "Я передам его разработчикам.\n\n"
            "Чтобы выйти, снова введите /связь"
        )
    except Exception as e:
        logger.error(f"❌ Ошибка в /связь: {e}")


# ==================== ОБРАБОТЧИК КОМАНДЫ /помощь ====================

@dp.message_created(commands=['помощь'])
async def cmd_help(message: types.Message):
    """Справка"""
    try:
        await message.answer(HELP_TEXT)
    except Exception as e:
        logger.error(f"❌ Ошибка в /помощь: {e}")


# ==================== ОБРАБОТЧИК КОМАНДЫ /источник ====================

@dp.message_created(commands=['источник'])
async def cmd_source(message: types.Message):
    """Информация о словаре"""
    try:
        await message.answer(SOURCE_INFO)
    except Exception as e:
        logger.error(f"❌ Ошибка в /источник: {e}")


# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================

@dp.message_created()
async def handle_text(message: types.Message):
    """Обработка текста в зависимости от режима"""
    try:
        user_id, first_name, username = get_user_info(message)
        text = message.text

        if not user_id:
            return

        # Пропускаем команды
        if text.startswith('/'):
            return

        # Получаем состояние
        state = get_state(user_id)

        # ===== РЕЖИМ ПОИСКА ТЕРМИНА =====
        if state == UserState.AWAITING_TERM:
            if not dictionary:
                await message.answer("❌ Словарь не загружен")
                return

            result = dictionary.search(text, FUZZY_THRESHOLD, MAX_SUGGESTIONS)

            if result['found']:
                response = f"""
🔍 *{result['term']}*

{result['definition']}

---
{SOURCE_INFO}
                """
                await message.answer(response)

            elif result['suggestions']:
                suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
                response = f"""
🤔 Термин *"{text}"* не найден.

Возможно, вы имели в виду:
{suggestions}
                """
                await message.answer(response)

            else:
                await message.answer(f"❌ Термин *{text}* не найден")

            return

        # ===== РЕЖИМ ОБРАТНОЙ СВЯЗИ =====
        elif state == UserState.AWAITING_FEEDBACK:
            user = get_user(user_id)
            user_name = user['name'] if user else first_name
            feedback_id = add_feedback(user_id, user_name, text)
            await message.answer(f"✅ Спасибо! Сообщение #{feedback_id} отправлено")
            return

        # ===== НЕТ АКТИВНОГО РЕЖИМА =====
        else:
            await message.answer(
                "❓ *Неизвестная команда*\n\n"
                "Используйте:\n"
                "/поиск - найти термин\n"
                "/связь - написать нам\n"
                "/помощь - список команд"
            )

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")


# ==================== КОМАНДЫ ДЛЯ АДМИНА ====================

@dp.message_created(commands=['stats'])
async def cmd_stats(message: types.Message):
    """Статистика (только для админа)"""
    try:
        user_id, first_name, username = get_user_info(message)

        if user_id != ADMIN_ID:
            await message.answer("⛔ Эта команда только для администратора")
            return

        users = get_all_users()
        stats = get_feedback_stats()

        response = f"""
📊 *Статистика бота*

👥 Пользователей: {len(users)}
📚 Терминов: {len(dictionary.terms) if dictionary else 0}
📬 Сообщений: {stats['total']} всего, {stats['unread']} новых
        """
        await message.answer(response)
    except Exception as e:
        logger.error(f"❌ Ошибка в /stats: {e}")


# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ")
    logger.info("=" * 60)
    logger.info(f"📚 Терминов: {len(dictionary.terms) if dictionary else 0}")
    logger.info(f"👑 ADMIN_ID: {ADMIN_ID}")
    logger.info("=" * 60)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())