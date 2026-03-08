"""
Модуль для работы с пользователями (JSON-хранилище)
"""

import json
import time
import os
import logging
from typing import Dict, Optional

# Добавляем импорт config
import config

logger = logging.getLogger(__name__)

# Глобальное хранилище состояний
user_states = {}
user_data = {}

class UserState:
    """Возможные состояния пользователя"""
    AWAITING_TERM = "awaiting_term"
    AWAITING_FEEDBACK = "awaiting_feedback"
    AWAITING_BROADCAST = "awaiting_broadcast"

def load_users() -> Dict:
    """Загрузка данных пользователей из JSON"""
    try:
        if os.path.exists(config.USERS_FILE):
            with open(config.USERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Ошибка загрузки пользователей: {e}")
        return {}

def save_users(users: Dict):
    """Сохранение данных пользователей в JSON"""
    try:
        with open(config.USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения пользователей: {e}")

def add_user(user_id: int, chat_id: int,
             username: Optional[str] = None,
             name: Optional[str] = None) -> bool:
    """Добавление или обновление пользователя"""
    users = load_users()
    user_id_str = str(user_id)
    is_new = user_id_str not in users

    users[user_id_str] = {
        'chat_id': chat_id,
        'username': username,
        'name': name,
        'created_at': users.get(user_id_str, {}).get(
            'created_at',
            time.strftime('%Y-%m-%d %H:%M:%S')
        ),
        'last_activity': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    save_users(users)

    if is_new:
        logger.info(f"Новый пользователь: {name} (ID: {user_id})")

    return is_new

def get_user(user_id: int) -> Optional[Dict]:
    """Получение данных пользователя"""
    users = load_users()
    return users.get(str(user_id))

def get_all_users() -> Dict:
    """Получение всех пользователей"""
    return load_users()

# Функции для работы с состояниями
def set_state(user_id: int, state: str):
    user_states[user_id] = state

def get_state(user_id: int) -> Optional[str]:
    return user_states.get(user_id)

def clear_state(user_id: int):
    if user_id in user_states:
        del user_states[user_id]

def set_data(user_id: int, key: str, value):
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id][key] = value

def get_data(user_id: int, key: str, default=None):
    return user_data.get(user_id, {}).get(key, default)

def clear_data(user_id: int):
    if user_id in user_data:
        del user_data[user_id]