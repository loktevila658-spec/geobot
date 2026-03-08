import maxapi
from maxapi import Dispatcher

print("="*60)
print("🔍 ИССЛЕДОВАНИЕ БИБЛИОТЕКИ MAXAPI")
print("="*60)

# Что есть в maxapi
print("\n📦 maxapi:")
for attr in dir(maxapi):
    if not attr.startswith('_'):
        print(f"  • {attr}")

# Что есть в Dispatcher
print("\n📦 Dispatcher:")
for attr in dir(Dispatcher):
    if not attr.startswith('_'):
        print(f"  • {attr}")

# Попробуем создать бота и посмотреть его методы
try:
    from maxapi import Bot
    bot = Bot(token="test")
    print("\n🤖 Bot методы:")
    for attr in dir(bot):
        if not attr.startswith('_') and callable(getattr(bot, attr)):
            print(f"  • {attr}")
except Exception as e:
    print(f"Ошибка: {e}")