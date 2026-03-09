from maxapi import Bot, Dispatcher
import asyncio

bot = Bot(token="test")
dp = Dispatcher(bot)

print("Методы Dispatcher:")
for method in dir(dp):
    if not method.startswith('_'):
        print(f"  - {method}")
