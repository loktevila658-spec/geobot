"""
Скрипт для проверки структуры Excel-файла
"""

import pandas as pd
import os


def check_excel(file_path='dictionary.xlsx'):
    print(f"🔍 Проверка файла: {file_path}")
    print("=" * 50)

    # Проверяем существование
    if not os.path.exists(file_path):
        print(f"❌ Файл {file_path} не найден!")
        return

    print(f"✅ Файл найден, размер: {os.path.getsize(file_path)} байт")

    # Пробуем прочитать разными способами
    try:
        # Способ 1: без заголовков
        df1 = pd.read_excel(file_path, header=None)
        print(f"\n📊 Способ 1 (header=None):")
        print(f"   Форма: {df1.shape[0]} строк x {df1.shape[1]} колонок")
        print(f"   Первые 3 строки:")
        print(df1.head(3).to_string())
    except Exception as e:
        print(f"❌ Ошибка способа 1: {e}")

    try:
        # Способ 2: с заголовками
        df2 = pd.read_excel(file_path)
        print(f"\n📊 Способ 2 (с заголовками):")
        print(f"   Форма: {df2.shape[0]} строк x {df2.shape[1]} колонок")
        print(f"   Колонки: {list(df2.columns)}")
        print(f"   Первые 3 строки:")
        print(df2.head(3).to_string())
    except Exception as e:
        print(f"❌ Ошибка способа 2: {e}")

    try:
        # Способ 3: указываем engine
        df3 = pd.read_excel(file_path, header=None, engine='openpyxl')
        print(f"\n📊 Способ 3 (openpyxl):")
        print(f"   Форма: {df3.shape[0]} строк x {df3.shape[1]} колонок")
    except Exception as e:
        print(f"❌ Ошибка способа 3: {e}")


if __name__ == '__main__':
    check_excel()