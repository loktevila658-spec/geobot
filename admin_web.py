"""
Веб-интерфейс для просмотра обратной связи
<<<<<<< HEAD
Версия для Bothost
=======
Версия для Render
>>>>>>> c24deee95cdd772c61d654963569e3fc5f857762
"""

from flask import Flask, jsonify, render_template_string, request
import json
import os
from datetime import datetime

app = Flask(__name__)
<<<<<<< HEAD
FEEDBACK_FILE = os.environ.get('FEEDBACK_FILE', 'feedback.json')

# Здесь вставьте HTML_TEMPLATE из предыдущих версий
# (он очень длинный, я не буду его копировать, но вы можете взять из предыдущего сообщения)

@app.route('/health')
def health():
    """Health check"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

=======
FEEDBACK_FILE = "feedback.json"

# HTML шаблон с красивым интерфейсом
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Геологический бот - Обратная связь</title>
    <meta charset="utf-8">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f0f2f5;
            padding: 20px;
        }
        .header {
            background: linear-gradient(135deg, #1e3c72, #2a5298);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .header h1 { font-size: 2em; margin-bottom: 10px; }
        .stats {
            display: flex;
            gap: 20px;
            margin-top: 15px;
            flex-wrap: wrap;
        }
        .stat-box {
            background: rgba(255,255,255,0.15);
            padding: 15px 25px;
            border-radius: 10px;
            backdrop-filter: blur(5px);
            min-width: 150px;
        }
        .stat-box .number { font-size: 1.8em; font-weight: bold; }
        .stat-box .label { opacity: 0.9; font-size: 0.9em; }
        .filters {
            margin: 20px 0;
            display: flex;
            gap: 10px;
        }
        .filter-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            background: white;
            color: #333;
            font-weight: 500;
            transition: all 0.2s;
        }
        .filter-btn.active {
            background: #2a5298;
            color: white;
        }
        .messages {
            display: grid;
            gap: 20px;
        }
        .message {
            background: white;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            transition: transform 0.2s;
            border-left: 5px solid;
        }
        .message:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.1);
        }
        .message.unread { border-left-color: #dc3545; }
        .message.read { border-left-color: #28a745; }
        .message-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #e9ecef;
        }
        .message-id {
            font-weight: bold;
            color: #2a5298;
            font-size: 1.1em;
        }
        .message-user {
            display: flex;
            gap: 20px;
            margin-bottom: 10px;
            color: #666;
        }
        .message-text {
            font-size: 1.1em;
            line-height: 1.5;
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            white-space: pre-wrap;
        }
        .message-reply {
            margin-top: 15px;
            padding: 15px;
            background: #e3f2fd;
            border-radius: 8px;
            border-left: 4px solid #2196f3;
        }
        .message-reply .label {
            color: #1976d2;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .actions {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
            transition: opacity 0.2s;
            text-decoration: none;
            display: inline-block;
        }
        .btn-mark {
            background: #28a745;
            color: white;
        }
        .btn-reply {
            background: #2a5298;
            color: white;
        }
        .btn-delete {
            background: #dc3545;
            color: white;
        }
        .reply-form {
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            display: none;
        }
        .reply-form textarea {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin-bottom: 10px;
            font-family: inherit;
            resize: vertical;
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: #666;
        }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #2a5298;
            color: white;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            cursor: pointer;
            box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            transition: transform 0.2s;
            border: none;
        }
        .refresh-btn:hover {
            transform: scale(1.1);
        }
        .empty-state {
            text-align: center;
            padding: 50px;
            background: white;
            border-radius: 12px;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📬 Геологический бот - Обратная связь</h1>
        <div class="stats" id="stats">
            <div class="stat-box">Загрузка...</div>
        </div>
    </div>

    <div class="filters">
        <button class="filter-btn active" onclick="filterMessages('all')">Все</button>
        <button class="filter-btn" onclick="filterMessages('unread')">Непрочитанные</button>
        <button class="filter-btn" onclick="filterMessages('read')">Прочитанные</button>
    </div>

    <div class="messages" id="messages"></div>

    <button class="refresh-btn" onclick="location.reload()">↻</button>

    <div class="footer">
        Сервер: Render.com | Страница обновляется вручную кнопкой ↻
    </div>

    <script>
        let allMessages = [];
        let currentFilter = 'all';

        async function loadData() {
            try {
                const response = await fetch('/api/feedback');
                allMessages = await response.json();

                // Статистика
                const total = allMessages.length;
                const unread = allMessages.filter(m => !m.is_read).length;

                document.getElementById('stats').innerHTML = `
                    <div class="stat-box">
                        <div class="number">${total}</div>
                        <div class="label">Всего сообщений</div>
                    </div>
                    <div class="stat-box">
                        <div class="number">${unread}</div>
                        <div class="label">Непрочитано</div>
                    </div>
                    <div class="stat-box">
                        <div class="number">${total - unread}</div>
                        <div class="label">Прочитано</div>
                    </div>
                `;

                filterMessages(currentFilter);

            } catch (e) {
                console.error('Ошибка загрузки:', e);
            }
        }

        function filterMessages(filter) {
            currentFilter = filter;

            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.target.classList.add('active');

            let filteredMessages = allMessages;
            if (filter === 'unread') {
                filteredMessages = allMessages.filter(m => !m.is_read);
            } else if (filter === 'read') {
                filteredMessages = allMessages.filter(m => m.is_read);
            }

            displayMessages(filteredMessages);
        }

        function displayMessages(messages) {
            const container = document.getElementById('messages');

            if (messages.length === 0) {
                container.innerHTML = '<div class="empty-state">📭 Нет сообщений</div>';
                return;
            }

            let html = '';
            messages.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));

            messages.forEach(msg => {
                const statusClass = msg.is_read ? 'read' : 'unread';

                html += `
                    <div class="message ${statusClass}" id="msg-${msg.id}">
                        <div class="message-header">
                            <span class="message-id">📝 #${msg.id}</span>
                            <span>${msg.created_at}</span>
                        </div>
                        <div class="message-user">
                            <span>👤 <b>${msg.user_name || 'Аноним'}</b> (ID: ${msg.user_id})</span>
                        </div>
                        <div class="message-text">
                            ${escapeHtml(msg.message)}
                        </div>
                `;

                if (msg.reply) {
                    html += `
                        <div class="message-reply">
                            <div class="label">✉️ Ваш ответ:</div>
                            ${escapeHtml(msg.reply)}
                            <div style="color: #666; font-size: 0.9em; margin-top: 5px;">${msg.replied_at || ''}</div>
                        </div>
                    `;
                }

                html += `
                        <div class="actions">
                            <button class="btn btn-mark" onclick="markAsRead(${msg.id})">✅ Отметить</button>
                            <button class="btn btn-reply" onclick="showReplyForm(${msg.id})">✉️ Ответить</button>
                            <button class="btn btn-delete" onclick="deleteMessage(${msg.id})">🗑️ Удалить</button>
                        </div>

                        <div class="reply-form" id="reply-form-${msg.id}">
                            <textarea id="reply-text-${msg.id}" rows="3" placeholder="Введите ваш ответ..."></textarea>
                            <div>
                                <button class="btn btn-reply" onclick="sendReply(${msg.id})">Отправить ответ</button>
                                <button class="btn" style="background: #6c757d;" onclick="hideReplyForm(${msg.id})">Отмена</button>
                            </div>
                        </div>
                    </div>
                `;
            });

            container.innerHTML = html;
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        async function markAsRead(id) {
            await fetch(`/mark/${id}`, {method: 'POST'});
            loadData();
        }

        async function deleteMessage(id) {
            if (confirm('Удалить сообщение?')) {
                await fetch(`/delete/${id}`, {method: 'POST'});
                loadData();
            }
        }

        function showReplyForm(id) {
            document.getElementById(`reply-form-${id}`).style.display = 'block';
        }

        function hideReplyForm(id) {
            document.getElementById(`reply-form-${id}`).style.display = 'none';
        }

        async function sendReply(id) {
            const text = document.getElementById(`reply-text-${id}`).value;
            if (!text) return;

            await fetch(`/reply/${id}`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({reply: text})
            });

            hideReplyForm(id);
            loadData();
        }

        // Добавляем health check для Render
        async function healthCheck() {
            await fetch('/health');
        }

        // Загружаем данные при открытии страницы
        loadData();

        // Периодически проверяем здоровье (для Render)
        setInterval(healthCheck, 300000); // каждые 5 минут
    </script>
</body>
</html>
"""


@app.route('/health')
def health():
    """Health check для Render"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200


>>>>>>> c24deee95cdd772c61d654963569e3fc5f857762
@app.route('/')
def index():
    """Главная страница"""
    return render_template_string(HTML_TEMPLATE)

<<<<<<< HEAD
=======

>>>>>>> c24deee95cdd772c61d654963569e3fc5f857762
@app.route('/api/feedback')
def api_feedback():
    """API для получения сообщений"""
    if not os.path.exists(FEEDBACK_FILE):
        return jsonify([])
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    except Exception as e:
        print(f"Ошибка чтения feedback.json: {e}")
        return jsonify([])

<<<<<<< HEAD
=======

>>>>>>> c24deee95cdd772c61d654963569e3fc5f857762
@app.route('/mark/<int:msg_id>', methods=['POST'])
def mark_read(msg_id):
    """Отметить как прочитанное"""
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for msg in data:
            if msg['id'] == msg_id:
                msg['is_read'] = True
                break
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка отметки прочитанным: {e}")
    return '', 200

<<<<<<< HEAD
# Добавьте остальные маршруты (reply, delete) аналогично

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("="*60)
    print("🌐 ВЕБ-ИНТЕРФЕЙС ЗАПУЩЕН")
    print("="*60)
    print(f"📁 Файл: {FEEDBACK_FILE}")
    print(f"🚀 Порт: {port}")
    print("="*60)
=======

@app.route('/reply/<int:msg_id>', methods=['POST'])
def reply(msg_id):
    """Ответить на сообщение"""
    reply_text = request.json.get('reply', '')
    if not reply_text:
        return '', 400
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for msg in data:
            if msg['id'] == msg_id:
                msg['reply'] = reply_text
                msg['replied_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                msg['is_read'] = True
                break
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка ответа: {e}")
    return '', 200


@app.route('/delete/<int:msg_id>', methods=['POST'])
def delete(msg_id):
    """Удалить сообщение"""
    try:
        with open(FEEDBACK_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        data = [msg for msg in data if msg['id'] != msg_id]
        with open(FEEDBACK_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка удаления: {e}")
    return '', 200


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("🌐 ВЕБ-ИНТЕРФЕЙС ДЛЯ ПРОСМОТРА ОБРАТНОЙ СВЯЗИ")
    print("=" * 60)
    print(f"📁 Файл: {FEEDBACK_FILE}")
    print(f"🚀 Запуск сервера на порту {port}...")
    print("📱 Health check: /health")
    print("=" * 60)

>>>>>>> c24deee95cdd772c61d654963569e3fc5f857762
    app.run(host='0.0.0.0', port=port)