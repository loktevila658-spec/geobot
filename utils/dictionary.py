"""
Модуль для работы с геологическим словарем
Новый формат: A(буква)/B(термин)/C(синоним)/D(происхождение)/E(формула)/F(описание)/G(классификация)
Все остальные функции бота остаются без изменений
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

            # Загружаем Excel с указанными колонками
            df = pd.read_excel(
                self.excel_file,
                header=None,
                names=['letter', 'term', 'synonym', 'origin', 'formula', 'description', 'classification']
            )

            # Удаляем строки без термина
            df = df.dropna(subset=['term'])

            # Заполняем пустые значения
            df = df.fillna('')

            # Преобразуем в строки
            for col in df.columns:
                df[col] = df[col].astype(str)

            # Заполняем словарь
            for _, row in df.iterrows():
                term = row['term'].strip()
                if not term:
                    continue

                term_lower = term.lower()

                # Сохраняем всю информацию о термине
                self.terms[term_lower] = {
                    'term': term,
                    'letter': row['letter'].strip(),
                    'synonym': row['synonym'].strip(),
                    'origin': row['origin'].strip(),
                    'formula': row['formula'].strip(),
                    'description': row['description'].strip(),
                    'classification': row['classification'].strip()
                }
                self.all_terms.append(term)

            logger.info(f"✅ Загружено {len(self.terms)} терминов из {self.excel_file}")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки словаря: {e}")
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
        if term_data['synonym'] and term_data['synonym'] != 'nan':
            lines.append(f"📝 *Синоним:* {term_data['synonym']}")

        # Происхождение (если есть)
        if term_data['origin'] and term_data['origin'] != 'nan':
            lines.append(f"📚 *Происхождение:* {term_data['origin']}")

        # Формула (если есть)
        if term_data['formula'] and term_data['formula'] != 'nan':
            lines.append(f"🧪 *Формула:* {term_data['formula']}")

        # Описание (всегда есть)
        if term_data['description'] and term_data['description'] != 'nan':
            lines.append(f"📖 *Описание:* {term_data['description']}")

        # Классификация (если есть)
        if term_data['classification'] and term_data['classification'] != 'nan':
            lines.append(f"🏷️ *Классификация:* {term_data['classification']}")

        return '\n'.join(lines)

    def get_stats(self) -> Dict:
        """Статистика словаря"""
        return {
            'total': len(self.terms),
            'with_synonym': len([t for t in self.terms.values() if t['synonym'] and t['synonym'] != 'nan']),
            'with_origin': len([t for t in self.terms.values() if t['origin'] and t['origin'] != 'nan']),
            'with_formula': len([t for t in self.terms.values() if t['formula'] and t['formula'] != 'nan']),
            'with_classification': len(
                [t for t in self.terms.values() if t['classification'] and t['classification'] != 'nan'])
        }