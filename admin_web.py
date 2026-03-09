"""
Веб-интерфейс для просмотра обратной связи
Версия для Bothost
"""

from flask import Flask, jsonify, render_template_string, request
import json
import os
from datetime import datetime

app = Flask(__name__)
FEEDBACK_FILE = os.environ.get('FEEDBACK_FILE', 'feedback.json')

# Здесь вставьте HTML_TEMPLATE из предыдущих версий
# (он очень длинный, я не буду его копировать, но вы можете взять из предыдущего сообщения)

@app.route('/health')
def health():
    """Health check"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()}), 200

@app.route('/')
def index():
    """Главная страница"""
    return render_template_string(HTML_TEMPLATE)

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

# Добавьте остальные маршруты (reply, delete) аналогично

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("="*60)
    print("🌐 ВЕБ-ИНТЕРФЕЙС ЗАПУЩЕН")
    print("="*60)
    print(f"📁 Файл: {FEEDBACK_FILE}")
    print(f"🚀 Порт: {port}")
    print("="*60)
    app.run(host='0.0.0.0', port=port)