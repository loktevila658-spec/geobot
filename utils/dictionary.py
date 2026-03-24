"""
Модуль для работы с геологическим словарем
Новый формат: A(буква)/B(термин)/C(синоним)/D(происхождение)/E(формула)/F(описание)/G(классификация)
Добавлена поддержка исправления опечаток
"""

import pandas as pd
import Levenshtein
import logging
import os
from typing import Dict, List, Optional
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class GeologicalDictionary:
    """Класс для работы с геологическим словарем"""

    def __init__(self, excel_file: str):
        self.excel_file = excel_file
        self.terms = {}  # {lowercase_term: вся информация}
        self.all_terms = []  # список всех терминов
        self.term_index = {}  # индекс для быстрого поиска по первым буквам
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
                
                # Создаем индекс для первых 3 букв
                prefix = term_lower[:3]
                if prefix not in self.term_index:
                    self.term_index[prefix] = []
                self.term_index[prefix].append(term_lower)
                
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

    def suggest_with_fix(self, user_input: str, threshold: float = 0.7, max_suggestions: int = 5):
        """
        Улучшенный поиск с предложением исправления опечаток
        Возвращает: (найденный_термин, список_предложений, сообщение_об_исправлении)
        """
        if len(user_input) < 2:
            return None, [], f"❌ Слишком короткий запрос: '{user_input}'"
            
        # Нормализуем ввод
        user_input_lower = user_input.lower().strip()
        
        # Сначала точный поиск
        if user_input_lower in self.terms:
            return self.terms[user_input_lower], [], None
        
        # Поиск по синонимам
        for term, data in self.terms.items():
            synonym = data.get('synonym', '')
            if synonym and isinstance(synonym, str):
                synonym_lower = synonym.lower()
                if user_input_lower == synonym_lower:
                    return data, [], f"🔍 Возможно, вы искали: *{data['term']}* (синоним)"
        
        # Собираем все варианты для нечёткого поиска
        candidates = []
        
        # Ограничим поиск только терминами с похожим началом для производительности
        prefix = user_input_lower[:3]
        potential_terms = self.term_index.get(prefix, [])
        
        # Если нет по индексу, проверяем все
        if not potential_terms:
            potential_terms = list(self.terms.keys())
        else:
            # Добавляем ещё несколько случайных для безопасности
            import random
            if len(self.terms) > 100:
                potential_terms.extend(random.sample(list(self.terms.keys()), min(50, len(self.terms))))
        
        # Проверяем основные термины
        for term_lower in set(potential_terms):
            term_data = self.terms[term_lower]
            
            # Проверяем на похожесть
            ratio = SequenceMatcher(None, user_input_lower, term_lower).ratio()
            
            # Особые случаи: опечатки в 1 букву
            if len(user_input_lower) > 3 and len(term_lower) > 3:
                # Проверка на замену одной буквы
                if len(user_input_lower) == len(term_lower):
                    diff_count = sum(1 for a, b in zip(user_input_lower, term_lower) if a != b)
                    if diff_count == 1:
                        ratio = max(ratio, 0.9)  # Повышаем рейтинг для односимвольных ошибок
                
                # Проверка на пропущенную букву
                if len(user_input_lower) == len(term_lower) - 1:
                    # Вставка буквы
                    for i in range(len(term_lower)):
                        if term_lower[:i] + term_lower[i+1:] == user_input_lower:
                            ratio = max(ratio, 0.9)
                            break
                
                # Проверка на лишнюю букву
                if len(user_input_lower) == len(term_lower) + 1:
                    # Удаление буквы
                    for i in range(len(user_input_lower)):
                        if user_input_lower[:i] + user_input_lower[i+1:] == term_lower:
                            ratio = max(ratio, 0.9)
                            break
            
            if ratio >= threshold:
                candidates.append((term_lower, ratio, 'term'))
        
        # Проверяем синонимы (только для потенциальных терминов)
        for term_lower in set(potential_terms):
            term_data = self.terms[term_lower]
            synonym = term_data.get('synonym', '')
            if synonym and isinstance(synonym, str) and synonym.lower() != 'nan':
                synonym_lower = synonym.lower()
                ratio = SequenceMatcher(None, user_input_lower, synonym_lower).ratio()
                if ratio >= threshold:
                    candidates.append((term_lower, ratio, 'synonym'))
        
        # Сортируем по рейтингу
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Берём уникальные термины
        seen = set()
        unique_candidates = []
        for term_lower, ratio, match_type in candidates:
            if term_lower not in seen:
                seen.add(term_lower)
                unique_candidates.append((term_lower, ratio, match_type))
        
        if unique_candidates:
            best_term_lower, best_ratio, best_type = unique_candidates[0]
            best_term_data = self.terms[best_term_lower]
            
            # Если нашли очень похожий вариант (выше 0.85)
            if best_ratio > 0.85:
                if best_type == 'synonym':
                    return best_term_data, [], f"🔍 Возможно, вы искали: *{best_term_data['term']}*"
                else:
                    # Проверяем, является ли это исправлением опечатки
                    if best_term_lower != user_input_lower:
                        correction_msg = f"🤔 Возможно, вы имели в виду: *{best_term_data['term']}*?"
                        suggestions = [self.terms[t]['term'] for t, _, _ in unique_candidates[:max_suggestions]]
                        return best_term_data, suggestions, correction_msg
                    else:
                        return best_term_data, [], None
            
            # Если нашли похожие, но не очень
            suggestions = [self.terms[t]['term'] for t, _, _ in unique_candidates[:max_suggestions]]
            return None, suggestions, f"🤔 Термин *{user_input}* не найден. Возможно, вы имели в виду:"
        
        return None, [], f"❌ Термин *{user_input}* не найден в словаре."

    def search(self, query: str, threshold: float = 0.7, max_suggestions: int = 5) -> Dict:
        """
        Полноценный поиск с исправлением опечаток
        """
        result = {
            'found': False,
            'term': None,
            'definition': None,
            'synonym': None,
            'origin': None,
            'formula': None,
            'classification': None,
            'suggestions': [],
            'correction_message': None
        }

        if not query or len(query.strip()) == 0:
            result['correction_message'] = "❌ Пустой запрос"
            return result

        term_data, suggestions, message = self.suggest_with_fix(query, threshold, max_suggestions)

        if term_data:
            result['found'] = True
            result['term'] = term_data['term']
            result['definition'] = term_data['description']
            result['synonym'] = term_data['synonym']
            result['origin'] = term_data['origin']
            result['formula'] = term_data['formula']
            result['classification'] = term_data['classification']
            result['correction_message'] = message
        else:
            result['suggestions'] = suggestions
            result['correction_message'] = message

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
