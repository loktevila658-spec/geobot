"""
Геологический бот для MAX
Добавлена команда для просмотра обратной связи
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
from utils.feedback import add_feedback, get_feedback_stats, load_feedback, mark_as_read
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

📚 *О словаре*
/источник - информация об авторах и издании.

📋 *Эта справка*
/помощь - показать это сообщение.

👑 *Команды администратора:*
/feed - просмотр обратной связи

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


# ==================== ГЛАВНЫЙ ОБРАБОТЧИК СООБЩЕНИЙ ====================

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
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Ошибка: словарь не загружен. Обратитесь к администратору."
            )
            return

        # Получаем состояние пользователя
        state = get_state(user_id)

        # ===== ОБРАБОТКА КОМАНД ПО ТЕКСТУ =====

        # Команда /start
        if text == '/start':
            await bot.send_message(
                chat_id=chat_id,
                text=WELCOME_TEXT.format(name=first_name)
            )
            return

        # Команда /помощь
        elif text == '/помощь':
            await bot.send_message(chat_id=chat_id, text=HELP_TEXT)
            return

        # Команда /источник
        elif text == '/источник':
            await bot.send_message(chat_id=chat_id, text=SOURCE_INFO)
            return

        # Команда /поиск
        elif text == '/поиск':
            if state == UserState.AWAITING_TERM:
                # Уже в режиме поиска - выходим
                clear_state(user_id)
                await bot.send_message(chat_id=chat_id, text=EXIT_SEARCH_TEXT)
            else:
                # Входим в режим поиска
                set_state(user_id, UserState.AWAITING_TERM)
                await bot.send_message(chat_id=chat_id, text=SEARCH_MODE_TEXT)
            return

        # Команда /связь
        elif text == '/связь':
            if state == UserState.AWAITING_FEEDBACK:
                # Уже в режиме связи - выходим
                clear_state(user_id)
                await bot.send_message(
                    chat_id=chat_id,
                    text="✅ Вы вышли из режима обратной связи."
                )
            else:
                # Входим в режим связи
                set_state(user_id, UserState.AWAITING_FEEDBACK)
                await bot.send_message(
                    chat_id=chat_id,
                    text="📝 *Напишите ваше сообщение*\n\n"
                         "Я передам его разработчикам.\n\n"
                         "Чтобы выйти, снова введите /связь"
                )
            return

        # ===== КОМАНДЫ ДЛЯ АДМИНА =====

        # Команда /stats - статистика
        elif text == '/stats':
            if user_id == ADMIN_ID:
                users = get_all_users()
                stats = get_feedback_stats()
                response = f"""
📊 *Статистика бота*

👥 Пользователей: {len(users)}
📚 Терминов: {len(dictionary.terms) if dictionary else 0}
📬 Сообщений: {stats['total']} всего, {stats['unread']} новых
                """
                await bot.send_message(chat_id=chat_id, text=response)
            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text="⛔ Эта команда только для администратора."
                )
            return

        # Команда /feed - просмотр обратной связи
        elif text == '/feed':
            if user_id != ADMIN_ID:
                await bot.send_message(chat_id=chat_id, text="⛔ Эта команда только для администратора.")
                return

            # Загружаем все сообщения
            feedback = load_feedback()

            if not feedback:
                await bot.send_message(chat_id=chat_id, text="📭 Нет сообщений обратной связи.")
                return

            # Сортируем по дате (сначала новые)
            feedback.sort(key=lambda x: x['created_at'], reverse=True)

            # Берем последние 5 сообщений
            recent = feedback[:5]

            response = "📬 *Последние сообщения:*\n\n"
            for msg in recent:
                status = "🆕" if not msg['is_read'] else "✅"
                response += f"{status} *#{msg['id']}* от {msg['user_name']} ({msg['created_at']}):\n"
                response += f"_{msg['message'][:100]}{'...' if len(msg['message']) > 100 else ''}_\n\n"

            response += f"Всего сообщений: {len(feedback)}, непрочитано: {len([m for m in feedback if not m['is_read']])}\n"
            response += "Для просмотра конкретного сообщения: /view [id]"

            await bot.send_message(chat_id=chat_id, text=response)
            return

        # Команда /view [id] - просмотр конкретного сообщения
        elif text.startswith('/view'):
            if user_id != ADMIN_ID:
                await bot.send_message(chat_id=chat_id, text="⛔ Эта команда только для администратора.")
                return

            parts = text.split()
            if len(parts) < 2:
                await bot.send_message(chat_id=chat_id, text="❌ Используйте: /view [id сообщения]")
                return

            try:
                msg_id = int(parts[1])
            except ValueError:
                await bot.send_message(chat_id=chat_id, text="❌ ID должен быть числом")
                return

            feedback = load_feedback()
            msg = next((m for m in feedback if m['id'] == msg_id), None)

            if not msg:
                await bot.send_message(chat_id=chat_id, text=f"❌ Сообщение #{msg_id} не найдено")
                return

            # Отмечаем как прочитанное
            mark_as_read(msg_id)

            response = f"""
📝 *Сообщение #{msg['id']}*

👤 От: {msg['user_name']} (ID: {msg['user_id']})
📅 Дата: {msg['created_at']}
📌 Статус: {'✅ Прочитано' if msg['is_read'] else '🆕 Новое'}

💬 *Текст:*
{msg['message']}
            """

            if msg.get('reply'):
                response += f"\n\n✉️ *Ответ:*\n{msg['reply']} (от {msg['replied_at']})"

            await bot.send_message(chat_id=chat_id, text=response)
            return

        # ===== ОБРАБОТКА РЕЖИМОВ =====

        # Если в режиме поиска
        if state == UserState.AWAITING_TERM:
            # Ищем термин
            result = dictionary.search(text, FUZZY_THRESHOLD, MAX_SUGGESTIONS)

            if result['found']:
                response = f"""
🔍 *{result['term']}*

{result['definition']}

---
{SOURCE_INFO}
                """
                await bot.send_message(chat_id=chat_id, text=response)

            elif result['suggestions']:
                suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
                response = f"""
🤔 Термин *"{text}"* не найден.

Возможно, вы имели в виду:
{suggestions}
                """
                await bot.send_message(chat_id=chat_id, text=response)

            else:
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Термин *{text}* не найден в словаре."
                )

            return

        # Если в режиме обратной связи
        elif state == UserState.AWAITING_FEEDBACK:
            user = get_user(user_id)
            user_name = user['name'] if user else first_name
            feedback_id = add_feedback(user_id, user_name, text)
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Спасибо! Сообщение #{feedback_id} отправлено разработчикам."
            )
            return

        # Если нет активного режима и это не команда
        else:
            await bot.send_message(
                chat_id=chat_id,
                text="❓ *Неизвестная команда*\n\n"
                     "Используйте:\n"
                     "/поиск - найти термин\n"
                     "/связь - написать нам\n"
                     "/помощь - список команд"
            )

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ (С ПРОСМОТРОМ FEEDBACK)")
    logger.info("=" * 60)
    logger.info(f"📚 Терминов: {len(dictionary.terms) if dictionary else 0}")
    logger.info(f"👑 ADMIN_ID: {ADMIN_ID}")
    logger.info("=" * 60)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())