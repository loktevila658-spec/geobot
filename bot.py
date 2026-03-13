"""
Геологический бот для MAX
Полная версия с поддержкой нового словаря (7 колонок)
ИСПРАВЛЕНО: правильный формат для клавиатур
"""

import logging
import asyncio
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv
from maxapi import Bot, Dispatcher
from maxapi import types
from maxapi.types import CallbackButton, ButtonsPayload, Attachment
from maxapi.enums.intent import Intent

from utils.storage import (
    add_user, get_all_users, set_state, get_state, clear_state,
    set_data, get_data, clear_data, UserState
)
from utils.feedback import add_feedback, get_feedback_stats, load_feedback, mark_as_read, save_feedback
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
    logger.info(f"✅ Загружено {len(dictionary.terms)} терминов из нового словаря")

    # Дополнительная статистика по новым полям
    stats = dictionary.get_stats()
    logger.info(f"📊 Статистика словаря: {stats['total']} терминов, "
                f"с синонимами: {stats['with_synonym']}, "
                f"с формулами: {stats['with_formula']}, "
                f"с классификацией: {stats['with_classification']}")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки словаря: {e}")
    dictionary = None

# Глобальные переменные для админ-режимов
admin_states = {}  # {user_id: "awaiting_broadcast" / "awaiting_term_add" и т.д.}
admin_data = {}  # временные данные для админ-операций


# ==================== ФУНКЦИИ ДЛЯ СОЗДАНИЯ КНОПОК ====================

def get_main_keyboard():
    """Главная клавиатура с кнопками (для reply_markup)"""
    return {
        "keyboard": [
            [{"text": "🔍 Найти термин"}, {"text": "💬 Обратная связь"}],
            [{"text": "📚 О словаре"}, {"text": "❓ Помощь"}]
        ],
        "resize_keyboard": True
    }


def get_exit_keyboard():
    """Клавиатура с кнопкой выхода"""
    return {
        "keyboard": [
            [{"text": "❌ Выйти из режима"}]
        ],
        "resize_keyboard": True
    }


def create_main_menu():
    """Главное меню для пользователей (inline-кнопки)"""
    btn_search = CallbackButton(
        text="🔍 Найти термин",
        payload="user_search",
        intent=Intent.DEFAULT
    )
    btn_feedback = CallbackButton(
        text="💬 Обратная связь",
        payload="user_feedback",
        intent=Intent.POSITIVE
    )
    btn_info = CallbackButton(
        text="📚 О словаре",
        payload="user_info",
        intent=Intent.DEFAULT
    )
    btn_help = CallbackButton(
        text="❓ Помощь",
        payload="user_help",
        intent=Intent.DEFAULT
    )

    buttons_payload = ButtonsPayload(buttons=[
        [btn_search, btn_feedback],
        [btn_info, btn_help]
    ])

    return Attachment(type="inline_keyboard", payload=buttons_payload)


def create_admin_menu():
    """Админ-меню с кнопками"""
    btn_stats = CallbackButton(
        text="📊 Статистика",
        payload="admin_stats",
        intent=Intent.DEFAULT
    )
    btn_feed = CallbackButton(
        text="📬 Сообщения",
        payload="admin_feed",
        intent=Intent.DEFAULT
    )
    btn_broadcast = CallbackButton(
        text="📢 Рассылка",
        payload="admin_broadcast",
        intent=Intent.POSITIVE
    )
    btn_add_term = CallbackButton(
        text="➕ Добавить термин",
        payload="admin_add_term",
        intent=Intent.DEFAULT
    )
    btn_del_term = CallbackButton(
        text="➖ Удалить термин",
        payload="admin_del_term",
        intent=Intent.NEGATIVE
    )
    btn_export = CallbackButton(
        text="📁 Экспорт",
        payload="admin_export",
        intent=Intent.DEFAULT
    )
    btn_logs = CallbackButton(
        text="📋 Логи",
        payload="admin_logs",
        intent=Intent.DEFAULT
    )
    btn_find_user = CallbackButton(
        text="🔍 Найти пользователя",
        payload="admin_find_user",
        intent=Intent.DEFAULT
    )
    btn_dict_stats = CallbackButton(
        text="📚 Статистика словаря",
        payload="admin_dict_stats",
        intent=Intent.DEFAULT
    )

    buttons_payload = ButtonsPayload(buttons=[
        [btn_stats, btn_feed],
        [btn_broadcast, btn_add_term],
        [btn_del_term, btn_export],
        [btn_logs, btn_find_user],
        [btn_dict_stats]
    ])

    return Attachment(type="inline_keyboard", payload=buttons_payload)


def create_exit_button():
    """Кнопка для выхода из режима"""
    btn_exit = CallbackButton(
        text="❌ Выйти",
        payload="exit_mode",
        intent=Intent.NEGATIVE
    )
    buttons_payload = ButtonsPayload(buttons=[[btn_exit]])
    return Attachment(type="inline_keyboard", payload=buttons_payload)


def create_back_button():
    """Кнопка возврата в админ-меню"""
    btn_back = CallbackButton(
        text="◀️ Назад",
        payload="admin_back",
        intent=Intent.DEFAULT
    )
    buttons_payload = ButtonsPayload(buttons=[[btn_back]])
    return Attachment(type="inline_keyboard", payload=buttons_payload)


# ==================== ТЕКСТЫ ====================

WELCOME_TEXT = """
👋 *Здравствуйте, {name}!*

Я геологический словарь. Помогу найти определение любого геологического термина.

Нажмите на кнопку ниже, чтобы начать 👇
"""

HELP_TEXT = """
❓ *Как пользоваться ботом:*

🔍 *Поиск термина*
Нажмите кнопку "Найти термин", затем просто вводите слова.

✉️ *Обратная связь*
Нажмите кнопку "Обратная связь", напишите сообщение разработчикам.

📚 *О словаре*
Нажмите кнопку "О словаре" - информация об авторах.

👑 *Для администратора*
После /admin откроется панель управления.
"""

SOURCE_INFO = """
📚 *Краткий геологический словарь для школьников*
Под ред. Г. И. Немкова — М.: Недра, 1989. — 176 с.

Авторы: Г. И. НЕМКОВ, Б. Е. КАРСКИЙ, Н. Г. ЛИН, 
И. Ф. РОМАНОВИЧ, В. Р. ЛОЗОВСКИЙ, А. А. АНУФРИЕВ
"""

SEARCH_MODE_TEXT = """
🔍 *Режим поиска активирован!*

Теперь просто вводите геологические термины одним словом.

Например: *базальт*, *гранит*, *известняк*

Чтобы выйти, нажмите кнопку ниже 👇
"""

EXIT_SEARCH_TEXT = """
✅ Вы вышли из режима поиска.

Используйте меню, чтобы выбрать действие.
"""

FEEDBACK_MODE_TEXT = """
📝 *Режим обратной связи*

Напишите ваше сообщение. Я передам его разработчикам.

Чтобы выйти, нажмите кнопку ниже 👇
"""

ADMIN_WELCOME = """
👑 *Панель администратора*

Выберите действие:

📊 Статистика - общая информация о боте
📬 Сообщения - просмотр обратной связи
📢 Рассылка - отправить сообщение всем пользователям
➕ Добавить термин - пополнить словарь
➖ Удалить термин - убрать термин из словаря
📁 Экспорт - выгрузить данные пользователей/сообщений
📋 Логи - последние события
🔍 Найти пользователя - поиск по имени или ID
📚 Статистика словаря - информация о наполнении словаря
"""

BROADCAST_MODE_TEXT = """
📢 *Режим рассылки*

Отправьте сообщение, которое будет доставлено ВСЕМ пользователям бота.

Напишите текст сообщения:
"""

ADD_TERM_TEXT = """
➕ *Добавление термина*

Введите термин и определение в формате:
`термин | определение`

Например:
`Магма | Расплавленная масса в недрах Земли`
"""

DEL_TERM_TEXT = """
➖ *Удаление термина*

Введите название термина, который нужно удалить:
"""

FIND_USER_TEXT = """
🔍 *Поиск пользователя*

Введите имя пользователя или ID:
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

        # Получаем chat_id из recipient
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

        # Получаем состояния
        state = get_state(user_id)
        admin_state = admin_states.get(user_id)

        # ===== ОБРАБОТКА КОМАНД =====

        # Команда /start
        if text == '/start':
            main_menu = create_main_menu()
            await bot.send_message(
                chat_id=chat_id,
                text=WELCOME_TEXT.format(name=first_name),
                attachments=[main_menu]
            )
            return

        # Команда /admin (только для админа)
        if text == '/admin':
            if user_id != ADMIN_ID:
                await bot.send_message(
                    chat_id=chat_id,
                    text="⛔ Эта команда только для администратора."
                )
                return

            admin_menu = create_admin_menu()
            await bot.send_message(
                chat_id=chat_id,
                text=ADMIN_WELCOME,
                attachments=[admin_menu]
            )
            return

        # ===== ОБРАБОТКА АДМИН-РЕЖИМОВ =====

        # Режим рассылки
        if admin_state == "awaiting_broadcast":
            users = get_all_users()
            if not users:
                await bot.send_message(chat_id=chat_id, text="⚠️ Нет пользователей для рассылки.")
                admin_states.pop(user_id, None)
                return

            success = 0
            failed = 0
            await bot.send_message(chat_id=chat_id, text=f"📤 Начинаю рассылку {len(users)} пользователям...")

            for user_id_str, user_data in users.items():
                try:
                    user_chat_id = user_data.get('chat_id')
                    if user_chat_id:
                        await bot.send_message(
                            chat_id=user_chat_id,
                            text=f"📢 *Сообщение от администратора:*\n\n{text}"
                        )
                        success += 1
                        await asyncio.sleep(0.1)
                except:
                    failed += 1

            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Рассылка завершена!\n✓ Успешно: {success}\n✗ Ошибок: {failed}"
            )
            admin_states.pop(user_id, None)
            return

        # Режим добавления термина
        if admin_state == "awaiting_term_add":
            if '|' not in text:
                await bot.send_message(
                    chat_id=chat_id,
                    text="❌ Неверный формат. Используйте: `термин | определение`"
                )
                return

            term, definition = text.split('|', 1)
            term = term.strip()
            definition = definition.strip()

            # Сохраняем новый термин в отдельный файл
            new_terms_file = "new_terms.txt"
            with open(new_terms_file, 'a', encoding='utf-8') as f:
                f.write(f"{term}|{definition}\n")

            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Термин *{term}* добавлен в очередь на утверждение."
            )
            admin_states.pop(user_id, None)
            return

        # Режим удаления термина
        if admin_state == "awaiting_term_del":
            term = text.strip()
            await bot.send_message(
                chat_id=chat_id,
                text=f"❌ Функция удаления временно недоступна. Термин *{term}* не был удален."
            )
            admin_states.pop(user_id, None)
            return

        # Режим поиска пользователя
        if admin_state == "awaiting_find_user":
            users = get_all_users()
            found = []

            # Поиск по ID или имени
            for uid, data in users.items():
                if text == uid or text.lower() in data.get('name', '').lower():
                    found.append((uid, data))

            if not found:
                await bot.send_message(chat_id=chat_id, text="❌ Пользователь не найден.")
            else:
                response = "🔍 *Найденные пользователи:*\n\n"
                for uid, data in found:
                    response += f"👤 {data.get('name', '—')} (ID: {uid})\n"
                    response += f"📅 Регистрация: {data.get('created_at', '—')}\n"
                    response += f"📊 Запросов: {data.get('total_requests', 0)}\n\n"
                await bot.send_message(chat_id=chat_id, text=response)

            admin_states.pop(user_id, None)
            return

        # ===== ОБРАБОТКА РЕЖИМОВ ПОЛЬЗОВАТЕЛЯ =====

        # Если в режиме поиска
        if state == UserState.AWAITING_TERM:
            # Ищем в словаре
            result = dictionary.search(text, FUZZY_THRESHOLD, MAX_SUGGESTIONS)

            if result['found']:
                # Формируем информационный блок
                info_lines = []

                # Синоним
                if result.get('synonym') and result['synonym'] and result['synonym'] != 'nan':
                    info_lines.append(f"📝 *Синоним:* {result['synonym']}")

                # Происхождение
                if result.get('origin') and result['origin'] and result['origin'] != 'nan':
                    info_lines.append(f"📚 *Происхождение:* {result['origin']}")

                # Формула
                if result.get('formula') and result['formula'] and result['formula'] != 'nan':
                    info_lines.append(f"🧪 *Формула:* {result['formula']}")

                # Описание
                if result.get('definition') and result['definition'] and result['definition'] != 'nan':
                    info_lines.append(f"📖 *Описание:* {result['definition']}")

                # Классификация
                if result.get('classification') and result['classification'] and result['classification'] != 'nan':
                    info_lines.append(f"🏷️ *Классификация:* {result['classification']}")

                info_block = '\n'.join(info_lines) if info_lines else "Информация отсутствует"

                response = f"""
🔍 *{result['term']}*

{info_block}

---
📚 Краткий геологический словарь для школьников
Под ред. Г. И. Немкова — М.: Недра, 1989.
                """
                # ИСПРАВЛЕНО: используем reply_markup с JSON
                await bot.send_message(
                    chat_id=chat_id,
                    text=response,
                    reply_markup=json.dumps(get_main_keyboard())
                )

            elif result['suggestions']:
                suggestions = "\n".join([f"• {term}" for term in result['suggestions']])
                response = f"""
🤔 Термин *"{text}"* не найден.

Возможно, вы имели в виду:
{suggestions}
                """
                # ИСПРАВЛЕНО: используем reply_markup с JSON
                await bot.send_message(
                    chat_id=chat_id,
                    text=response,
                    reply_markup=json.dumps(get_main_keyboard())
                )

            else:
                # ИСПРАВЛЕНО: используем reply_markup с JSON
                await bot.send_message(
                    chat_id=chat_id,
                    text=f"❌ Термин *{text}* не найден в словаре.",
                    reply_markup=json.dumps(get_main_keyboard())
                )
            clear_state(user_id)
            return

        # Если в режиме обратной связи
        if state == UserState.AWAITING_FEEDBACK:
            user_name = first_name
            feedback_id = add_feedback(user_id, user_name, text)

            # ИСПРАВЛЕНО: используем reply_markup с JSON
            await bot.send_message(
                chat_id=chat_id,
                text=f"✅ Спасибо! Сообщение #{feedback_id} отправлено разработчикам.",
                reply_markup=json.dumps(get_main_keyboard())
            )

            # Уведомление админу
            if ADMIN_ID != 0:
                admin_notification = f"""
📬 *Новое сообщение!*
👤 {user_name} (ID: {user_id})
💬 {text[:200]}
🔍 /view {feedback_id}
                """
                try:
                    await bot.send_message(chat_id=ADMIN_ID, text=admin_notification)
                except Exception as e:
                    logger.warning(f"Не удалось отправить уведомление админу: {e}")
            return

        # Если нет режима
        main_menu = create_main_menu()
        await bot.send_message(
            chat_id=chat_id,
            text="❓ Используйте кнопки меню для навигации:",
            attachments=[main_menu]
        )

    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


# ==================== ОБРАБОТЧИК НАЖАТИЙ НА КНОПКИ ====================

@dp.message_callback()
async def handle_callback(event):
    """Обработчик нажатий на inline-кнопки"""
    try:
        # Получаем данные из event
        callback = event.callback
        user_id = callback.user.user_id
        chat_id = event.chat.chat_id
        payload = callback.payload

        logger.info(f"🔘 Нажата кнопка: {payload} от {user_id}")

        # ===== КНОПКИ ПОЛЬЗОВАТЕЛЯ =====

        if payload == "user_search":
            set_state(user_id, UserState.AWAITING_TERM)
            exit_button = create_exit_button()
            await bot.send_message(
                chat_id=chat_id,
                text=SEARCH_MODE_TEXT,
                attachments=[exit_button]
            )

        elif payload == "user_feedback":
            set_state(user_id, UserState.AWAITING_FEEDBACK)
            exit_button = create_exit_button()
            await bot.send_message(
                chat_id=chat_id,
                text=FEEDBACK_MODE_TEXT,
                attachments=[exit_button]
            )

        elif payload == "user_info":
            await bot.send_message(
                chat_id=chat_id,
                text=SOURCE_INFO
            )

        elif payload == "user_help":
            main_menu = create_main_menu()
            await bot.send_message(
                chat_id=chat_id,
                text=HELP_TEXT,
                attachments=[main_menu]
            )

        # ===== КНОПКИ АДМИНА =====

        elif payload == "admin_stats":
            if user_id != ADMIN_ID:
                return

            users = get_all_users()
            stats = get_feedback_stats()
            response = f"""
📊 *Статистика бота*

👥 *Пользователи:* {len(users)}
📚 *Термины:* {len(dictionary.terms) if dictionary else 0}
📬 *Сообщения:* {stats['total']} всего, {stats['unread']} новых

👑 *Администратор:* {ADMIN_ID}
            """
            back_button = create_back_button()
            await bot.send_message(
                chat_id=chat_id,
                text=response,
                attachments=[back_button]
            )

        elif payload == "admin_dict_stats":
            if user_id != ADMIN_ID:
                return

            if dictionary:
                stats = dictionary.get_stats()
                response = f"""
📚 *Статистика словаря*

📊 Всего терминов: {stats['total']}
📝 С синонимами: {stats['with_synonym']}
📚 С происхождением: {stats['with_origin']}
🧪 С формулами: {stats['with_formula']}
🏷️ С классификацией: {stats['with_classification']}
                """
            else:
                response = "❌ Словарь не загружен"

            back_button = create_back_button()
            await bot.send_message(
                chat_id=chat_id,
                text=response,
                attachments=[back_button]
            )

        elif payload == "admin_feed":
            if user_id != ADMIN_ID:
                return

            feedback = load_feedback()
            if not feedback:
                await bot.send_message(chat_id=chat_id, text="📭 Нет сообщений.")
                return

            stats = get_feedback_stats()
            feedback.sort(key=lambda x: x['created_at'], reverse=True)
            recent = feedback[:5]

            response = "📬 *Последние сообщения:*\n\n"
            for msg in recent:
                status = "🆕" if not msg['is_read'] else "✅"
                response += f"{status} #{msg['id']} от {msg['user_name']}: "
                response += f"{msg['message'][:50]}...\n"
                response += f"📅 {msg['created_at']}\n\n"

            response += f"Всего: {len(feedback)}, непрочитано: {stats['unread']}\n"
            response += "Для просмотра: /view [id]"

            back_button = create_back_button()
            await bot.send_message(
                chat_id=chat_id,
                text=response,
                attachments=[back_button]
            )

        elif payload == "admin_broadcast":
            if user_id != ADMIN_ID:
                return

            admin_states[user_id] = "awaiting_broadcast"
            exit_button = create_exit_button()
            await bot.send_message(
                chat_id=chat_id,
                text=BROADCAST_MODE_TEXT,
                attachments=[exit_button]
            )

        elif payload == "admin_add_term":
            if user_id != ADMIN_ID:
                return

            admin_states[user_id] = "awaiting_term_add"
            exit_button = create_exit_button()
            await bot.send_message(
                chat_id=chat_id,
                text=ADD_TERM_TEXT,
                attachments=[exit_button]
            )

        elif payload == "admin_del_term":
            if user_id != ADMIN_ID:
                return

            admin_states[user_id] = "awaiting_term_del"
            exit_button = create_exit_button()
            await bot.send_message(
                chat_id=chat_id,
                text=DEL_TERM_TEXT,
                attachments=[exit_button]
            )

        elif payload == "admin_export":
            if user_id != ADMIN_ID:
                return

            users = get_all_users()
            feedback = load_feedback()

            users_file = f"users_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            feedback_file = f"feedback_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(users_file, 'w', encoding='utf-8') as f:
                json.dump(users, f, ensure_ascii=False, indent=2)

            with open(feedback_file, 'w', encoding='utf-8') as f:
                json.dump(feedback, f, ensure_ascii=False, indent=2)

            response = f"📁 *Экспорт данных*\n\n"
            response += f"👥 Пользователей: {len(users)}\n"
            response += f"💬 Сообщений: {len(feedback)}\n\n"
            response += f"Файлы созданы на сервере."

            back_button = create_back_button()
            await bot.send_message(
                chat_id=chat_id,
                text=response,
                attachments=[back_button]
            )

        elif payload == "admin_logs":
            if user_id != ADMIN_ID:
                return

            # Читаем последние 20 строк лога
            log_file = "bot.log"
            logs = "📋 *Последние логи*\n\n"
            try:
                if os.path.exists(log_file):
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()[-20:]
                        logs += "".join(lines[-20:])
                else:
                    logs += "Лог-файл не найден"
            except Exception as e:
                logs += f"Ошибка чтения логов: {e}"

            back_button = create_back_button()
            await bot.send_message(
                chat_id=chat_id,
                text=logs[:4000],
                attachments=[back_button]
            )

        elif payload == "admin_find_user":
            if user_id != ADMIN_ID:
                return

            admin_states[user_id] = "awaiting_find_user"
            exit_button = create_exit_button()
            await bot.send_message(
                chat_id=chat_id,
                text=FIND_USER_TEXT,
                attachments=[exit_button]
            )

        # ===== ОБЩИЕ КНОПКИ =====

        elif payload == "admin_back":
            if user_id != ADMIN_ID:
                return

            admin_states.pop(user_id, None)
            admin_menu = create_admin_menu()
            await bot.send_message(
                chat_id=chat_id,
                text=ADMIN_WELCOME,
                attachments=[admin_menu]
            )

        elif payload == "exit_mode":
            clear_state(user_id)
            admin_states.pop(user_id, None)
            main_menu = create_main_menu()
            await bot.send_message(
                chat_id=chat_id,
                text=EXIT_SEARCH_TEXT,
                attachments=[main_menu]
            )

        # ИСПРАВЛЕНО: правильный способ отправки callback
        try:
            # В вашей версии MAX API нужно отправить пустой текст
            await bot.send_callback(
                callback_id=callback.callback_id,
                text=" "  # Пробел, чтобы не было ошибки
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить callback: {e}")

    except Exception as e:
        logger.error(f"❌ Ошибка обработки callback: {e}")
        import traceback
        traceback.print_exc()


# ==================== ЗАПУСК ====================

async def main():
    logger.info("=" * 60)
    logger.info("🚀 ГЕОЛОГИЧЕСКИЙ БОТ (НОВАЯ ВЕРСИЯ СЛОВАРЯ)")
    logger.info("=" * 60)
    logger.info(f"📚 Терминов: {len(dictionary.terms) if dictionary else 0}")
    if dictionary:
        stats = dictionary.get_stats()
        logger.info(f"📊 С синонимами: {stats['with_synonym']}")
        logger.info(f"📚 С происхождением: {stats['with_origin']}")
        logger.info(f"🧪 С формулами: {stats['with_formula']}")
    logger.info(f"👑 ADMIN_ID: {ADMIN_ID}")
    logger.info("=" * 60)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())