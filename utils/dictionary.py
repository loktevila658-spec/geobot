"""
Модуль для работы с геологическим словарем
Новый формат: A(буква)/B(термин)/C(синоним)/D(происхождение)/E(формула)/F(описание)/G(классификация)
"""

import pandas as pd
import Levenshtein
import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GeologicalDictionary:
    """Класс для работы с геологическим словарем"""

    def __init__(self, excel_file: str):
        self.excel_file = excel_file
        self.terms = {}  # {lowercase_term: вся информация}
        self.all_terms = []  # список всех терминов
        self.load_dictionary()

    def load_dictionary(self):
        """Загрузка словаря из Excel с новой структурой"""
        try:
            if not os.path.exists(self.excel_file):
                logger.error(f"❌ Файл {self.excel_file} не найден!")
                return

            # Пробуем разные способы чтения Excel
            try:
                # Способ 1: с указанием header=None (нет заголовков)
                df = pd.read_excel(self.excel_file, header=None)
                logger.info(f"✅ Файл прочитан, колонок: {len(df.columns)}")

                # Проверяем количество колонок
                if len(df.columns) >= 7:
                    # Назначаем имена колонкам
                    df.columns = ['letter', 'term', 'synonym', 'origin', 'formula', 'description',
                                  'classification'] + list(df.columns[7:])
                else:
                    logger.error(f"❌ В файле только {len(df.columns)} колонок, нужно минимум 7")
                    # Создаем недостающие колонки
                    for i in range(len(df.columns), 7):
                        df[i] = ''
                    df.columns = ['letter', 'term', 'synonym', 'origin', 'formula', 'description', 'classification']

            except Exception as e:
                logger.error(f"❌ Ошибка чтения Excel: {e}")
                # Способ 2: пробуем с engine='openpyxl'
                try:
                    df = pd.read_excel(self.excel_file, header=None, engine='openpyxl')
                    if len(df.columns) >= 7:
                        df.columns = ['letter', 'term', 'synonym', 'origin', 'formula', 'description',
                                      'classification'] + list(df.columns[7:])
                    else:
                        for i in range(len(df.columns), 7):
                            df[i] = ''
                        df.columns = ['letter', 'term', 'synonym', 'origin', 'formula', 'description', 'classification']
                except Exception as e2:
                    logger.error(f"❌ Ошибка чтения Excel openpyxl: {e2}")
                    return

            # Удаляем полностью пустые строки
            df = df.dropna(how='all')

            # Удаляем строки без термина
            df = df.dropna(subset=['term'])

            # Заполняем пустые значения
            df = df.fillna('')

            # Преобразуем все в строки и очищаем
            for col in df.columns:
                df[col] = df[col].astype(str).str.strip()

            # Фильтруем строки, где термин не пустой и не равен 'nan'
            df = df[df['term'].apply(lambda x: x and x.lower() != 'nan' and len(x) > 0)]

            # Заполняем словарь
            term_count = 0
            for idx, row in df.iterrows():
                term = row['term']
                if not term or term == 'nan':
                    continue

                term_lower = term.lower()

                # Очищаем значения от 'nan'
                synonym = row['synonym'] if row['synonym'] != 'nan' else ''
                origin = row['origin'] if row['origin'] != 'nan' else ''
                formula = row['formula'] if row['formula'] != 'nan' else ''
                description = row['description'] if row['description'] != 'nan' else ''
                classification = row['classification'] if row['classification'] != 'nan' else ''
                letter = row['letter'] if row['letter'] != 'nan' else (term[0].upper() if term else '')

                self.terms[term_lower] = {
                    'term': term,
                    'letter': letter,
                    'synonym': synonym,
                    'origin': origin,
                    'formula': formula,
                    'description': description,
                    'classification': classification
                }
                self.all_terms.append(term)
                term_count += 1

            logger.info(f"✅ Загружено {term_count} терминов из {self.excel_file}")

            # Считаем статистику
            with_synonym = len([t for t in self.terms.values() if t['synonym'] and t['synonym'] != ''])
            with_origin = len([t for t in self.terms.values() if t['origin'] and t['origin'] != ''])
            with_formula = len([t for t in self.terms.values() if t['formula'] and t['formula'] != ''])
            with_classification = len(
                [t for t in self.terms.values() if t['classification'] and t['classification'] != ''])

            logger.info(f"📊 Статистика: всего {term_count}, с синонимами: {with_synonym}, "
                        f"с происхождением: {with_origin}, с формулами: {with_formula}, "
                        f"с классификацией: {with_classification}")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка загрузки словаря: {e}")
            import traceback
            traceback.print_exc()
            self.terms = {}
            self.all_terms = []

    def find_term(self, query: str) -> Optional[Dict]:
        """Прямой поиск термина"""
        if not query:
            return None
        return self.terms.get(query.lower().strip())

    def find_similar(self, query: str, threshold: float = 0.7, max_results: int = 5) -> List[str]:
        """Поиск похожих терминов (исправление опечаток)"""
        if len(query) < 3 or not self.all_terms:
            return []

        query_lower = query.lower().strip()
        suggestions = []

        for term in self.all_terms:
            term_lower = term.lower()
            try:
                ratio = Levenshtein.ratio(query_lower, term_lower)
                if ratio >= threshold:
                    suggestions.append((term, ratio))
            except:
                continue

        suggestions.sort(key=lambda x: x[1], reverse=True)
        return [term for term, _ in suggestions[:max_results]]

    def search(self, query: str, threshold: float = 0.7, max_suggestions: int = 5) -> Dict:
        """
        Полноценный поиск:
        - Если найден точно → возвращает всю информацию
        - Если есть похожие → возвращает список
        - Если ничего нет → возвращает пустой результат
        """
        result = {
            'found': False,
            'term': None,
            'definition': None,
            'synonym': None,
            'origin': None,
            'formula': None,
            'classification': None,
            'suggestions': []
        }

        if not query:
            return result

        # Прямой поиск
        term_data = self.find_term(query)
        if term_data:
            result['found'] = True
            result['term'] = term_data['term']
            result['definition'] = term_data['description']
            result['synonym'] = term_data['synonym']
            result['origin'] = term_data['origin']
            result['formula'] = term_data['formula']
            result['classification'] = term_data['classification']
            return result

        # Поиск похожих
        suggestions = self.find_similar(query, threshold, max_suggestions)
        if suggestions:
            result['suggestions'] = suggestions

        return result

    def get_formatted_info(self, query: str) -> str:
        """
        Возвращает отформатированную информацию о термине для вывода в чат
        """
        term_data = self.find_term(query)
        if not term_data:
            return None

        lines = []

        # Синоним (если есть)
        if term_data['synonym'] and term_data['synonym'] != '':
            lines.append(f"📝 *Синоним:* {term_data['synonym']}")

        # Происхождение (если есть)
        if term_data['origin'] and term_data['origin'] != '':
            lines.append(f"📚 *Происхождение:* {term_data['origin']}")

        # Формула (если есть)
        if term_data['formula'] and term_data['formula'] != '':
            lines.append(f"🧪 *Формула:* {term_data['formula']}")

        # Описание (всегда есть)
        if term_data['description'] and term_data['description'] != '':
            lines.append(f"📖 *Описание:* {term_data['description']}")

        # Классификация (если есть)
        if term_data['classification'] and term_data['classification'] != '':
            lines.append(f"🏷️ *Классификация:* {term_data['classification']}")

        return '\n'.join(lines) if lines else "Информация отсутствует"

    def get_stats(self) -> Dict:
        """Статистика словаря"""
        total = len(self.terms)
        with_synonym = len([t for t in self.terms.values() if t['synonym'] and t['synonym'] != ''])
        with_origin = len([t for t in self.terms.values() if t['origin'] and t['origin'] != ''])
        with_formula = len([t for t in self.terms.values() if t['formula'] and t['formula'] != ''])
        with_classification = len([t for t in self.terms.values() if t['classification'] and t['classification'] != ''])

        return {
            'total': total,
            'with_synonym': with_synonym,
            'with_origin': with_origin,
            'with_formula': with_formula,
            'with_classification': with_classification
        }