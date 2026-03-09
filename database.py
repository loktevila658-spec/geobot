import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path=''):
        self.db_path = db_path
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Только таблица для обратной связи
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    user_info TEXT,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_read INTEGER DEFAULT 0
                )
            ''')

            conn.commit()
            conn.close()
            logger.info("✅ База данных создана")

        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")

    def save_feedback(self, user_id, message, user_info=''):
        """Сохраняет сообщение обратной связи"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('''
                INSERT INTO feedback (user_id, user_info, message, created_at)
                VALUES (?, ?, ?, ?)
            ''', (user_id, user_info, message, now))

            feedback_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"✅ Feedback #{feedback_id} сохранен")
            return feedback_id

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}")
            return None

    def get_all_feedback(self):
        """Получает все сообщения"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM feedback ORDER BY created_at DESC')
            feedback = [dict(row) for row in cursor.fetchall()]
            conn.close()
            return feedback
        except Exception as e:
            logger.error(f"❌ Ошибка получения: {e}")
            return []

    def mark_feedback_read(self, feedback_id):
        """Отмечает сообщение как прочитанное"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE feedback SET is_read = 1 WHERE id = ?', (feedback_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return False

    def get_stats(self):
        """Статистика"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute('SELECT COUNT(*) as count FROM feedback')
            total = cursor.fetchone()['count']

            cursor.execute('SELECT COUNT(*) as count FROM feedback WHERE is_read = 0')
            unread = cursor.fetchone()['count']

            conn.close()

            return {
                'total': total,
                'unread': unread
            }
        except Exception as e:
            logger.error(f"❌ Ошибка: {e}")
            return {'total': 0, 'unread': 0}