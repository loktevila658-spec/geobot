"""
Геологический бот для MAX
Версия для Render
"""

import logging
import asyncio
import os
from maxapi import Bot, Dispatcher
from maxapi import types

# Импортируем настройки, но позволяем переопределить через переменные окружения
import config
from utils.storage import (
    add_user, get_all_users, set_state, get_state, clear_state,
    set_data, get_data, clear_data, UserState
)
from utils.feedback import add_feedback, get_feedback_stats
from utils.dictionary import GeologicalDictionary

# Настройка логирования для Render
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Проверяем, что токен есть в окружении (приоритет у переменных окружения)
BOT_TOKEN = os.environ.get('BOT_TOKEN') or config.BOT_TOKEN
if not BOT_TOKEN or BOT_TOKEN == "ваш_токен_сюда":
    raise ValueError(
        "BOT_TOKEN не задан! Укажите в переменных окружения Render.\n"
        "Перейдите в Dashboard → ваш сервис → Environment → Add Environment Variable"
    )

try:
    ADMIN_ID = int(os.environ.get('ADMIN_ID', config.ADMIN_ID))
except ValueError:
    raise ValueError("ADMIN_ID должен быть числом! Проверьте переменные окружения.")

logger.info(f"✅ Бот запускается с ADMIN_ID: {ADMIN_ID}")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Инициализация словаря
dictionary = GeologicalDictionary(config.DICTIONARY_FILE)

# ==================== ИНФОРМАЦИОННЫЕ ТЕКСТЫ ====================

SOURCE_INFO = """
📚 *Краткий геологический словарь для школьников*
Под ред. Г. И. Немкова — М.: Недра, 1989. — 176 с.

👥 *Авторы:*
Г. И. НЕМКОВ, Б. Е. КАРСКИЙ, Н. Г. ЛИН, 
И. Ф. РОМАНОВИЧ, В. Р. ЛОЗОВСКИЙ, А. А. АНУФРИЕВ
"""

HELP_TEXT = """
❓ *ДОСТУПНЫЕ КОМАНДЫ:*

/start - начало работы
/help - эта справка
/info - информация о словаре
/search [термин] - поиск термина
/feedback [текст] - отправить сообщение
/stats - статистика (только админ)
/broadcast [текст] - рассылка (только админ)

📚 Всего в словаре: {count} терминов
"""


# ==================== ОБРАБОТЧИКИ СООБЩЕНИЙ ====================

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

        # ===== ОБРАБОТКА КОМАНД =====

        if text == '/start':
            await cmd_start(chat_id, first_name)

        elif text == '/help':
            await cmd_help(chat_id)

        elif text == '/info':
            await cmd_info(chat_id)

        elif text.startswith('/search'):
            await cmd_search(chat_id, text)

        elif text.startswith('/feedback'):
            await cmd_feedback(chat_id, user_id, first_name, text)

        elif text == '/stats':
            await cmd_stats(chat_id, user_id)

        elif text.startswith('/broadcast'):
            await cmd_broadcast(chat_id, user_id, text)

        elif text.startswith('/'):
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Неизвестная команда. Напишите /help"
            )

        else:
            # Если это не команда - предлагаем поиск
            await bot.send_message(
                chat_id=chat_id,
                text=f"Используйте команды:\n"
                     f"/search {text} - поиск этого термина\n"
                     f"/feedback {text} - отправить как сообщение\n"
                     f"/help - все команды"
            )

        logger.info(f"✅ Обработка сообщения от {first_name} завершена")

    except Exception as e:
        logger.error(f"❌ Ошибка обработки сообщения: {e}")
        import traceback
        traceback.print_exc()


# ==================== ОБРАБОТЧИКИ КОМАНД ====================

async def cmd_start(chat_id: int, first_name: str):
    """Обработка /start"""
    try:
        welcome = f"👋 Добро пожаловать, {first_name}!\n\nЯ геологический словарь.\nНапишите /help для списка команд."
        await bot.send_message(chat_id=chat_id, text=welcome)
        logger.info(f"✅ Отправлен /start в чат {chat_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки /start: {e}")


async def cmd_help(chat_id: int):
    """Обработка /help"""
    try:
        text = HELP_TEXT.format(count=len(dictionary.terms))
        await bot.send_message(chat_id=chat_id, text=text)
        logger.info(f"✅ Отправлен /help в чат {chat_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки /help: {e}")


async def cmd_info(chat_id: int):
    """Обработка /info"""
    try:
        await bot.send_message(chat_id=chat_id, text=SOURCE_INFO)
        logger.info(f"✅ Отправлен /info в чат {chat_id}")
    except Exception as e:
        logger.error(f"❌ Ошибка отправки /info: {e}")


async def cmd_search(chat_id: int, full_text: str):
    """Обработка /search"""
    try:
        parts = full_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Используйте: /search [термин]\nНапример: /search базальт"
            )
            return

        query = parts[1].strip()
        result = dictionary.search(query, config.FUZZY_THRESHOLD, config.MAX_SUGGESTIONS)

        if result['found']:
            response = f"""
🔍 *{result['term']}*

{result['definition']}

---
{SOURCE_INFO}
            """
            await bot.send_message(chat_id=chat_id, text=response)
            logger.info(f"✅ Найден термин '{result['term']}' для чата {chat_id}")

        elif result['suggestions']:
            suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
            response = f"""
🤔 Термин *"{query}"* не найден.

Возможно, вы имели в виду:
{suggestions}

Используйте: /search [термин]
            """
            await bot.send_message(chat_id=chat_id, text=response)
            logger.info(f"💡 Предложены варианты для чата {chat_id}: {result['suggestions']}")

        else:
            response = f"""
❌ Термин *"{query}"* не найден в словаре.

Проверьте написание или используйте /feedback
            """
            await bot.send_message(chat_id=chat_id, text=response)
            logger.info(f"❌ Термин не найден для чата {chat_id}: {query}")

    except Exception as e:
        logger.error(f"❌ Ошибка в /search: {e}")


async def cmd_feedback(chat_id: int, user_id: int, first_name: str, full_text: str):
    """Обработка /feedback"""
    try:
        parts = full_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Используйте: /feedback [текст сообщения]\nНапример: /feedback Опечатка в слове базальт"
            )
            return

        text = parts[1].strip()
        feedback_id = add_feedback(user_id, first_name, text)

        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ Спасибо! Сообщение #{feedback_id} отправлено разработчикам."
        )
        logger.info(f"✅ Сохранен feedback #{feedback_id} для чата {chat_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка в /feedback: {e}")


async def cmd_stats(chat_id: int, user_id: int):
    """Обработка /stats (только админ)"""
    try:
        if user_id != ADMIN_ID:
            await bot.send_message(
                chat_id=chat_id,
                text="⛔ Команда доступна только администратору."
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

        await bot.send_message(chat_id=chat_id, text=response)
        logger.info(f"✅ Отправлена статистика админу в чат {chat_id}")

    except Exception as e:
        logger.error(f"❌ Ошибка в /stats: {e}")


async def cmd_broadcast(chat_id: int, user_id: int, full_text: str):
    """Обработка /broadcast (только админ)"""
    try:
        if user_id != ADMIN_ID:
            await bot.send_message(
                chat_id=chat_id,
                text="⛔ Команда доступна только администратору."
            )
            return

        parts = full_text.split(maxsplit=1)
        if len(parts) < 2:
            await bot.send_message(
                chat_id=chat_id,
                text="❌ Используйте: /broadcast [текст рассылки]"
            )
            return

        broadcast_text = parts[1].strip()
        users = get_all_users()

        if not users:
            await bot.send_message(chat_id=chat_id, text="⚠️ Нет пользователей для рассылки.")
            return

        await bot.send_message(
            chat_id=chat_id,
            text=f"📤 Начинаю рассылку на {len(users)} пользователей..."
        )

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

        await bot.send_message(
            chat_id=chat_id,
            text=f"✅ *Рассылка завершена!*\n\n"
                 f"• Успешно: {success}\n"
                 f"• Ошибок: {failed}"
        )
        logger.info(f"✅ Рассылка завершена: {success} успешно, {failed} ошибок")

    except Exception as e:
        logger.error(f"❌ Ошибка в /broadcast: {e}")


# ==================== ЗАПУСК БОТА ====================

async def main():
    """Главная функция запуска"""
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ ДЛЯ MAX НА RENDER")
    logger.info("=" * 60)
    logger.info(f"📚 Терминов в словаре: {len(dictionary.terms)}")
    logger.info(f"👑 Администратор ID: {ADMIN_ID}")
    logger.info("=" * 60)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())