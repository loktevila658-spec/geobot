"""
Геологический бот для MAX

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


# ==================== ОБРАБОТЧИК КОМАНДЫ /start ====================

@dp.message_created(commands=['start'])
async def cmd_start(message: types.Message):
    """Приветствие"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    first_name = message.from_user.first_name or "Пользователь"

    # Сохраняем пользователя
    add_user(user_id, chat_id, None, first_name)

    # Отправляем приветствие
    await message.answer(WELCOME_TEXT.format(name=first_name))


# ==================== ОБРАБОТЧИК КОМАНДЫ /поиск ====================

@dp.message_created(commands=['поиск'])
async def cmd_search_mode(message: types.Message):
    """Вход/выход из режима поиска"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    current_state = get_state(user_id)

    if current_state == UserState.AWAITING_TERM:
        # Уже в режиме поиска - выходим
        clear_state(user_id)
        await message.answer(EXIT_SEARCH_TEXT)
    else:
        # Входим в режим поиска
        set_state(user_id, UserState.AWAITING_TERM)
        await message.answer(SEARCH_MODE_TEXT)


# ==================== ОБРАБОТЧИК КОМАНДЫ /связь ====================

@dp.message_created(commands=['связь'])
async def cmd_feedback(message: types.Message):
    """Режим обратной связи"""
    user_id = message.from_user.id
    set_state(user_id, UserState.AWAITING_FEEDBACK)

    await message.answer(
        "📝 *Напишите ваше сообщение*\n\n"
        "Я передам его разработчикам. Можно писать несколько сообщений подряд.\n\n"
        "Чтобы выйти, снова введите /связь"
    )


# ==================== ОБРАБОТЧИК КОМАНДЫ /помощь ====================

@dp.message_created(commands=['помощь'])
async def cmd_help(message: types.Message):
    """Справка"""
    await message.answer(HELP_TEXT)


# ==================== ОБРАБОТЧИК КОМАНДЫ /источник ====================

@dp.message_created(commands=['источник'])
async def cmd_source(message: types.Message):
    """Информация о словаре"""
    await message.answer(SOURCE_INFO)


# ==================== ОБРАБОТЧИК ТЕКСТОВЫХ СООБЩЕНИЙ ====================

@dp.message_created()
async def handle_text(message: types.Message):
    """Обработка текста в зависимости от режима"""
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        text = message.text

        # Пропускаем команды (они уже обработаны выше)
        if text.startswith('/'):
            return

        # Получаем состояние
        state = get_state(user_id)

        # ===== РЕЖИМ ПОИСКА ТЕРМИНА =====
        if state == UserState.AWAITING_TERM:
            if not dictionary:
                await message.answer("❌ Словарь не загружен. Попробуйте позже.")
                return

            # Ищем термин
            result = dictionary.search(text, FUZZY_THRESHOLD, MAX_SUGGESTIONS)

            if result['found']:
                # Термин найден
                response = f"""
🔍 *{result['term']}*

{result['definition']}

---
{SOURCE_INFO}
                """
                await message.answer(response)

            elif result['suggestions']:
                # Есть похожие
                suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
                response = f"""
🤔 Термин *"{text}"* не найден.

Возможно, вы имели в виду:
{suggestions}
                """
                await message.answer(response)

            else:
                # Ничего не найдено
                await message.answer(f"❌ Термин *{text}* не найден в словаре.")

            return

        # ===== РЕЖИМ ОБРАТНОЙ СВЯЗИ =====
        elif state == UserState.AWAITING_FEEDBACK:
            user = get_user(user_id)
            user_name = user['name'] if user else "Пользователь"
            feedback_id = add_feedback(user_id, user_name, text)
            await message.answer(f"✅ Спасибо! Сообщение #{feedback_id} отправлено разработчикам.")
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
    user_id = message.from_user.id
    chat_id = message.chat.id

    if user_id != ADMIN_ID:
        await message.answer("⛔ Эта команда только для администратора.")
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


# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ (РУССКИЕ КОМАНДЫ)")
    logger.info("=" * 60)
    logger.info(f"📚 Терминов: {len(dictionary.terms) if dictionary else 0}")
    logger.info(f"👑 ADMIN_ID: {ADMIN_ID}")
    logger.info("=" * 60)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())