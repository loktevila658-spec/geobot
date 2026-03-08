"""
Модуль для работы с геологическим словарем
"""

import pandas as pd
import Levenshtein
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class GeologicalDictionary:
    """Класс для работы с геологическим словарем"""

    def __init__(self, excel_file: str):
        self.excel_file = excel_file
        self.terms = {}  # {lowercase_term: {'term': оригинал, 'definition': определение}}
        self.all_terms = []  # список всех терминов в оригинале
        self.load_dictionary()

    def load_dictionary(self):
        """Загрузка словаря из Excel"""
        try:
            df = pd.read_excel(self.excel_file, header=None, names=['term', 'definition'])
            df = df.dropna(subset=['term', 'definition'])

            for _, row in df.iterrows():
                term = str(row['term']).strip()
                definition = str(row['definition']).strip()
                self.terms[term.lower()] = {
                    'term': term,
                    'definition': definition
                }
                self.all_terms.append(term)

            logger.info(f"✅ Загружено {len(self.terms)} терминов из {self.excel_file}")

        except FileNotFoundError:
            logger.error(f"❌ Файл {self.excel_file} не найден!")
            self.terms = {}
            self.all_terms = []
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
        - Если найден точно → возвращает определение
        - Если есть похожие → возвращает список
        - Если ничего нет → возвращает пустой результат
        """
        result = {
            'found': False,
            'term': None,
            'definition': None,
            'suggestions': []
        }

        if not query:
            return result

        # Прямой поиск
        term_data = self.find_term(query)
        if term_data:
            result['found'] = True
            result['term'] = term_data['term']
            result['definition'] = term_data['definition']
            return result

        # Поиск похожих
        suggestions = self.find_similar(query, threshold, max_suggestions)
        if suggestions:
            result['suggestions'] = suggestions

        return result