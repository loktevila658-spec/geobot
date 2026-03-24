"""
Модуль для работы с обратной связью (JSON-хранилище)
Версия для Bothost - без зависимости от config.py
"""

import json
import time
import os
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

FEEDBACK_FILE = os.environ.get('FEEDBACK_FILE', 'feedback.json')


def load_feedback() -> List[Dict]:
    """Загрузка сообщений обратной связи"""
    try:
        if os.path.exists(FEEDBACK_FILE):
            with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Ошибка загрузки feedback: {e}")
        return []


def save_feedback(feedback: List[Dict]):
    """Сохранение сообщений обратной связи"""
    try:
        os.makedirs(os.path.dirname(FEEDBACK_FILE) or '.', exist_ok=True)
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(feedback, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Ошибка сохранения feedback: {e}")


def add_feedback(user_id: int, user_name: str, message: str) -> int:
    """Добавление нового сообщения обратной связи"""
    feedback = load_feedback()
    new_id = len(feedback) + 1

    feedback.append({
        'id': new_id,
        'user_id': user_id,
        'user_name': user_name,
        'message': message,
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'is_read': False,
        'reply': None,
        'replied_at': None
    })

    save_feedback(feedback)
    logger.info(f"✅ Новое сообщение #{new_id} от пользователя {user_id}")
    return new_id


def get_unread_feedback() -> List[Dict]:
    """Получение непрочитанных сообщений"""
    feedback = load_feedback()
    return [f for f in feedback if not f['is_read']]


def mark_as_read(feedback_id: int) -> bool:
    """Отметить сообщение как прочитанное"""
    feedback = load_feedback()
    for item in feedback:
        if item['id'] == feedback_id:
            item['is_read'] = True
            save_feedback(feedback)
            return True
    return False


def get_feedback_stats() -> Dict:
    """Получение статистики по обратной связи"""
    feedback = load_feedback()
    return {
        'total': len(feedback),
        'unread': len([f for f in feedback if not f['is_read']]),
    }
