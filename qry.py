#!/usr/bin/env python3
"""
ULTRA-SZYBKI PROCESOR PRZESZUKIWANIA I PRZETWARZANIA PLIKÓW
===========================================================

Najszybsze rozwiązania dla:
- Przeszukiwania JSON/CSV w HTML/MHTML
- Ekstraktowania metadanych (EML, PDF, obrazy, media)
- Konwersji między formatami
- Generowania HTML GUI z wynikami

Optymalizowane dla maksymalnej wydajności!

Wymagane zależności:
    pip install -r requirements.txt
"""

import json
import sys
import re
import hashlib
import time
import os
import importlib.util
import multiprocessing
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor

# ===============================================
# DEPENDENCY MANAGEMENT
# ===============================================

def check_dependencies() -> bool:
    """Sprawdza dostępność wymaganych zależności."""
    required = {
        'lxml': 'lxml',
        'PIL': 'Pillow',  # PIL is the package name to import, Pillow is the PyPI name
        'magic': 'python-magic',
        'dateutil': 'python-dateutil',
        'requests': 'requests',
        'ujson': 'ujson',
        'tqdm': 'tqdm',
        'pytz': 'pytz',
        'pandas': 'pandas',
        'numpy': 'numpy'
    }
    
    missing = []
    for pkg_name, pkg_install in required.items():
        try:
            if importlib.util.find_spec(pkg_name) is None:
                raise ImportError(f"{pkg_name} not found")
        except Exception as e:
            print(f"⚠️  Błąd podczas sprawdzania {pkg_name}: {e}")
            missing.append(pkg_install)
    
    if missing:
        print("\n❌ Brakujące zależności:")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\nZainstaluj je używając:")
        print("   pip install -r requirements.txt")
        print("lub pojedynczo:")
        print(f"   pip install {' '.join(missing)}")
        print("\nUpewnij się, że środowisko wirtualne jest aktywowane!")
        print("   source venv/bin/activate  # Linux/Mac")
        print("   .\\venv\\Scripts\\activate  # Windows")
        return False
    
    print("✓ Wszystkie wymagane zależności są zainstalowane")
    return True

# ===============================================
# FAST LIBRARIES WITH GRACEFUL FALLBACKS
# ===============================================

try:
    import ujson as json_lib  # 2-3x faster than json
except ImportError:
    import json as json_lib
    print("⚠️  ujson nie jest zainstalowany. Użycie wbudowanego modułu json (wolniejsze).")
    print("   Zainstaluj: pip install ujson")

try:
    import lxml.html as html_parser
    HTML_PARSER = 'lxml'
except ImportError:
    try:
        from bs4 import BeautifulSoup as html_parser
        HTML_PARSER = 'bs4'
        print("⚠️  lxml nie jest zainstalowany. Użycie BeautifulSoup (wolniejsze).")
        print("   Zainstaluj: pip install lxml")
    except ImportError:
        print("❌ Brak parsera HTML. Zainstaluj lxml lub beautifulsoup4")
        print("   pip install lxml  # zalecane")
        print("   lub")
        print("   pip install beautifulsoup4")
        html_parser = None
        HTML_PARSER = None

# Check for required dependencies before proceeding
if not check_dependencies():
    sys.exit(1)

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    Image = None

try:
    import eyed3  # MP3 metadane - najszybszy
except ImportError:
    eyed3 = None

try:
    import cv2  # OpenCV - najszybsze przetwarzanie video
except ImportError:
    cv2 = None

try:
    import fitz  # PyMuPDF - najszybszy dla PDF
except ImportError:
    fitz = None

try:
    import email
    import email.policy
    from email.mime.text import MIMEText
except ImportError:
    email = None

# ===============================================
# STRUKTURY DANYCH
# ===============================================

@dataclass
class SearchResult:
    file_path: str
    file_type: str
    content_type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime
    size: int
    hash: str = None

@dataclass
class SearchQuery:
    query_text: str
    file_types: List[str]
    date_range: Tuple[datetime, datetime] = None
    content_types: List[str] = None  # json, csv, metadata, exif
    output_format: str = "html"  # html, json, csv
    include_previews: bool = True
    max_results: int = 1000

# ===============================================
# ULTRA-SZYBKIE PARSERY SPECJALIZOWANE
# ===============================================

class UltraFastParsers:
    """Najszybsze parsery dla różnych formatów"""
    
    @staticmethod
    def extract_json_from_html(html_content: str) -> List[Dict]:
        """Ekstraktuje JSON z HTML - 10x szybciej niż BeautifulSoup"""
        results = []
        
        # Regex dla JSON w script tagach (najszybsze)
        json_patterns = [
            r'<script[^>]*>\s*({.*?})\s*</script>',
            r'<script[^>]*type=["\']application/json["\'][^>]*>\s*({.*?})\s*</script>',
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'var\s+\w+\s*=\s*({.*?});',
            r'const\s+\w+\s*=\s*({.*?});'
        ]
        
        for pattern in json_patterns:
            matches = re.finditer(pattern, html_content, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    json_str = match.group(1)
                    parsed = json_lib.loads(json_str)
                    results.append(parsed)
                except:
                    continue
        
        return results
    
    @staticmethod
    def extract_csv_from_html(html_content: str) -> List[List[str]]:
        """Ekstraktuje dane CSV z tabel HTML"""
        results = []
        
        # Regex dla tabel (szybsze niż lxml dla prostych przypadków)
        table_pattern = r'<table[^>]*>(.*?)</table>'
        row_pattern = r'<tr[^>]*>(.*?)</tr>'
        cell_pattern = r'<t[dh][^>]*>(.*?)</t[dh]>'
        
        tables = re.finditer(table_pattern, html_content, re.DOTALL | re.IGNORECASE)
        
        for table in tables:
            table_content = table.group(1)
            rows = re.finditer(row_pattern, table_content, re.DOTALL | re.IGNORECASE)
            
            csv_data = []
            for row in rows:
                row_content = row.group(1)
                cells = re.finditer(cell_pattern, row_content, re.DOTALL | re.IGNORECASE)
                row_data = [re.sub(r'<[^>]+>', '', cell.group(1)).strip() for cell in cells]
                if row_data:
                    csv_data.append(row_data)
            
            if csv_data:
                results.extend(csv_data)
        
        return results
    
    @staticmethod
    def extract_image_exif(file_path: str) -> Dict[str, Any]:
        """Najszybsza ekstraktacja EXIF z obrazów"""
        if not Image:
            return {}
        
        try:
            with Image.open(file_path) as img:
                exif_dict = {}
                exif = img._getexif()
                
                if exif is not None:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        exif_dict[tag] = str(value)
                
                # Dodaj podstawowe informacje
                exif_dict.update({
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': os.path.getsize(file_path)
                })
                
                return exif_dict
        except:
            return {}
    
    @staticmethod
    def extract_pdf_metadata(file_path: str) -> Dict[str, Any]:
        """Najszybsza ekstraktacja metadanych PDF"""
        if not fitz:
            return {}
        
        try:
            doc = fitz.open(file_path)
            metadata = doc.metadata
            
            result = {
                'title': metadata.get('title', ''),
                'author': metadata.get('author', ''),
                'subject': metadata.get('subject', ''),
                'creator': metadata.get('creator', ''),
                'producer': metadata.get('producer', ''),
                'creation_date': metadata.get('creationDate', ''),
                'modification_date': metadata.get('modDate', ''),
                'page_count': doc.page_count,
                'encrypted': doc.is_encrypted,
                'size_bytes': os.path.getsize(file_path)
            }
            
            doc.close()
            return result
        except:
            return {}
    
    @staticmethod
    def extract_email_metadata(file_path: str) -> Dict[str, Any]:
        """Najszybsza ekstraktacja metadanych EML"""
        if not email:
            return {}
        
        try:
            with open(file_path, 'rb') as f:
                msg = email.message_from_bytes(f.read())
            
            return {
                'subject': msg.get('Subject', ''),
                'from': msg.get('From', ''),
                'to': msg.get('To', ''),
                'date': msg.get('Date', ''),
                'message_id': msg.get('Message-ID', ''),
                'content_type': msg.get('Content-Type', ''),
                'attachments': len([part for part in msg.walk() if part.get_content_disposition() == 'attachment']),
                'size_bytes': os.path.getsize(file_path)
            }
        except:
            return {}
    
    @staticmethod
    def extract_mp3_metadata(file_path: str) -> Dict[str, Any]:
        """Najszybsza ekstraktacja metadanych MP3"""
        if not eyed3:
            return {}
        
        try:
            audiofile = eyed3.load(file_path)
            if audiofile.tag:
                return {
                    'title': audiofile.tag.title or '',
                    'artist': audiofile.tag.artist or '',
                    'album': audiofile.tag.album or '',
                    'album_artist': audiofile.tag.album_artist or '',
                    'release_date': str(audiofile.tag.release_date) if audiofile.tag.release_date else '',
                    'genre': audiofile.tag.genre.name if audiofile.tag.genre else '',
                    'duration': audiofile.info.time_secs if audiofile.info else 0,
                    'bitrate': audiofile.info.bit_rate[1] if audiofile.info else 0,
                    'size_bytes': os.path.getsize(file_path)
                }
        except:
            pass
        
        return {}
    
    @staticmethod
    def extract_video_metadata(file_path: str) -> Dict[str, Any]:
        """Najszybsza ekstraktacja metadanych video"""
        if not cv2:
            return {}
        
        try:
            cap = cv2.VideoCapture(file_path)
            
            metadata = {
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'duration': cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS),
                'size_bytes': os.path.getsize(file_path)
            }
            
            cap.release()
            return metadata
        except:
            return {}

# ===============================================
# ULTRA-SZYBKIE KONWERTERY
# ===============================================

class UltraFastConverters:
    """Najszybsze konwertery między formatami"""
    
    @staticmethod
    def html_to_text(html_content: str) -> str:
        """Najszybsza konwersja HTML -> text"""
        # Regex szybszy niż lxml dla prostego strippingu
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    @staticmethod
    def pdf_to_text(file_path: str) -> str:
        """Najszybsza konwersja PDF -> text"""
        if not fitz:
            return ""
        
        try:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except:
            return ""
    
    @staticmethod
    def image_to_base64(file_path: str, max_size: Tuple[int, int] = (300, 300)) -> str:
        """Najszybsza konwersja obrazu -> base64 thumbnail"""
        if not Image:
            return ""
        
        try:
            with Image.open(file_path) as img:
                # Stwórz miniaturkę
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Konwertuj do base64
                import io
                buffer = io.BytesIO()
                img_format = 'JPEG' if img.mode == 'RGB' else 'PNG'
                img.save(buffer, format=img_format, quality=85)
                
                encoded = base64.b64encode(buffer.getvalue()).decode()
                return f"data:image/{img_format.lower()};base64,{encoded}"
        except:
            return ""
    
    @staticmethod
    def eml_to_html(file_path: str) -> str:
        """Najszybsza konwersja EML -> HTML"""
        if not email:
            return ""
        
        try:
            with open(file_path, 'rb') as f:
                msg = email.message_from_bytes(f.read())
            
            html_parts = []
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    html_parts.append(part.get_payload(decode=True).decode('utf-8', errors='ignore'))
            
            return ''.join(html_parts)
        except:
            return ""

# ===============================================
# GŁÓWNY PROCESOR PRZESZUKIWANIA
# ===============================================

import multiprocessing

class UltraFastSearchProcessor:
    """Główny procesor - najszybsze przeszukiwanie i przetwarzanie"""
    
    def __init__(self, max_workers: Optional[int] = None, cache_size: int = 1000):
        try:
            self.max_workers = max_workers or multiprocessing.cpu_count()
            self.cache = {}
            self.cache_size = cache_size
            self.parsers = UltraFastParsers()
            print(f"✅ Inicjalizacja procesora z {self.max_workers} wątkami")
        except Exception as e:
            print(f"⚠️  Błąd podczas inicjalizacji procesora: {e}")
            print("Używam domyślnych ustawień...")
            self.max_workers = 4  # Domyślna wartość w przypadku błędu
            self.cache = {}
            self.cache_size = cache_size
            self.parsers = UltraFastParsers()
        self.converters = UltraFastConverters()
    
    def search_files(self, query: SearchQuery, search_paths: List[str], scope: int = 1, max_depth: int = 2) -> List[SearchResult]:
        """Główna metoda przeszukiwania
        
        Args:
            query: Obiekt zapytania
            search_paths: Lista ścieżek do przeszukania
            scope: Liczba poziomów w górę (0 = bieżący katalog, 1 = jeden poziom wyżej, itd.)
            max_depth: Maksymalna głębokość przeszukiwania (1 = tylko bieżący katalog, 2 = jeden poziom w dół, itd.)
        """
        print(f"🔍 Rozpoczynam przeszukiwanie w {len(search_paths)} ścieżkach...")
        start_time = time.time()
        
        # Znajdź pliki kandydatów
        candidate_files = self._find_candidate_files(search_paths, query, scope=scope, max_depth=max_depth)
        print(f"📁 Znaleziono {len(candidate_files)} kandydatów do przeszukania")
        
        # Przetwarzaj równolegle
        results = self._process_files_parallel(candidate_files, query)
        
        # Filtruj i sortuj wyniki
        filtered_results = self._filter_and_sort_results(results, query)
        
        end_time = time.time()
        print(f"⚡ Przeszukiwanie zakończone w {end_time - start_time:.2f} sekund")
        print(f"🎯 Znaleziono {len(filtered_results)} dopasowań")
        
        return filtered_results[:query.max_results]
    
    def _find_candidate_files(self, search_paths: List[str], query: SearchQuery, scope: int = 1, max_depth: int = 2) -> List[str]:
        """Szybkie znajdowanie plików kandydatów z ograniczonym zakresem i głębokością
        
        Args:
            search_paths: Lista ścieżek do przeszukania
            query: Obiekt zapytania
            scope: Liczba poziomów w górę (0 = bieżący katalog, 1 = jeden poziom wyżej, itd.)
            max_depth: Maksymalna głębokość przeszukiwania (1 = tylko bieżący katalog, 2 = jeden poziom w dół, itd.)
        """
        candidates = []
        
        # Mapowanie rozszerzeń na typy
        extensions_map = {
            'html': ['.html', '.htm', '.mhtml'],
            'email': ['.eml', '.msg'],
            'pdf': ['.pdf'],
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'],
            'audio': ['.mp3', '.wav', '.flac', '.m4a'],
            'video': ['.mp4', '.avi', '.mkv', '.mov', '.wmv'],
            'csv': ['.csv'],
            'json': ['.json']
        }
        
        # Zbierz wszystkie rozszerzenia do szukania
        target_extensions = set()
        for file_type in query.file_types:
            if file_type in extensions_map:
                target_extensions.update(extensions_map[file_type])
        
        # Przetwórz każdą ścieżkę wyszukiwania
        for search_path in search_paths:
            # Przejdź o określoną liczbę poziomów w górę
            if scope > 0:
                path_parts = os.path.normpath(search_path).split(os.sep)
                search_path = os.sep.join(path_parts[:-scope] if len(path_parts) > scope else path_parts[0])
            
            # Normalizuj ścieżkę i upewnij się, że istnieje
            search_path = os.path.abspath(search_path)
            if not os.path.exists(search_path):
                continue
                
            # Przeszukaj z ograniczoną głębokością
            for root, dirs, files in os.walk(search_path):
                # Oblicz głębokość względem katalogu wyszukiwania
                rel_path = os.path.relpath(root, search_path)
                current_depth = 0 if rel_path == '.' else len(rel_path.split(os.sep))
                
                # Ogranicz głębokość przeszukiwania
                if current_depth >= max_depth:
                    dirs[:] = []  # Nie schodź głębiej
                    continue
                    
                # Pomiń ukryte foldery i pliki
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                files = [f for f in files if not f.startswith('.')]
                
                for file in files:
                    file_path = os.path.join(root, file)
                    ext = os.path.splitext(file)[1].lower()
                    
                    if not target_extensions or ext in target_extensions:
                        # Sprawdź datę jeśli potrzebne
                        if query.date_range:
                            try:
                                mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                                if not (query.date_range[0] <= mtime <= query.date_range[1]):
                                    continue
                            except:
                                continue
                        
                        candidates.append(file_path)
        
        return candidates
    
    def _process_files_parallel(self, file_paths: List[str], query: SearchQuery) -> List[SearchResult]:
        """Równoległe przetwarzanie plików"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Podziel na chunki dla lepszej wydajności
            chunk_size = max(1, len(file_paths) // (self.max_workers * 4))
            
            futures = []
            for i in range(0, len(file_paths), chunk_size):
                chunk = file_paths[i:i + chunk_size]
                future = executor.submit(self._process_file_chunk, chunk, query)
                futures.append(future)
            
            # Zbierz wyniki
            for future in futures:
                try:
                    chunk_results = future.result()
                    results.extend(chunk_results)
                except Exception as e:
                    print(f"⚠️ Błąd przetwarzania chunka: {e}")
        
        return results
    
    def _process_file_chunk(self, file_paths: List[str], query: SearchQuery) -> List[SearchResult]:
        """Przetwarzanie chunka plików"""
        results = []
        
        for file_path in file_paths:
            try:
                result = self._process_single_file(file_path, query)
                if result:
                    results.append(result)
            except Exception as e:
                print(f"⚠️ Błąd przetwarzania {file_path}: {e}")
        
        return results
    
    def _process_single_file(self, file_path: str, query: SearchQuery) -> Optional[SearchResult]:
        """Przetwarza pojedynczy plik i zwraca obiekt SearchResult.
        
        Args:
            file_path: Ścieżka do pliku do przetworzenia
            query: Obiekt zapytania zawierający kryteria wyszukiwania
            
        Returns:
            SearchResult: Obiekt z wynikami wyszukiwania lub None w przypadku błędu
        """
        try:
            if not os.path.exists(file_path):
                print(f"⚠️  Plik nie istnieje: {file_path}")
                return None
                
            file_size = os.path.getsize(file_path)
            file_mtime = os.path.getmtime(file_path)
            file_hash = hashlib.md5(f"{file_path}{file_size}{file_mtime}".encode()).hexdigest()
            
            # Pobierz podstawowe informacje o pliku
            file_info = {
                'path': file_path,
                'size': file_size,
                'mtime': datetime.fromtimestamp(file_mtime).isoformat(),
                'hash': file_hash
            }
            
            # Sprawdź typ pliku i odpowiednio go przetwórz
            try:
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
                    return self._process_image_file(file_path, file_info, query)
                elif file_path.lower().endswith(('.html', '.htm')):
                    return self._process_html_file(file_path, file_info, query)
                elif file_path.lower().endswith(('.pdf', '.docx', '.xlsx')):
                    return self._process_document_file(file_path, file_info, query)
                else:
                    return self._process_generic_file(file_path, file_info, query)
            except Exception as process_err:
                print(f"⚠️  Błąd przetwarzania pliku {file_path} (typ pliku): {process_err}")
                return self._process_generic_file(file_path, file_info, query)
                
        except Exception as process_err:
            print(f"⚠️  Błąd przetwarzania pliku {file_path}: {process_err}")
            return None
        # Stwórz wynik
        result = SearchResult(
            file_path=file_path,
            file_type=file_ext,
            content_type=content_type,
            data=data,
            metadata=metadata,
            timestamp=datetime.fromtimestamp(file_stat.st_mtime),
            size=file_stat.st_size,
            hash=file_hash
        )
        
        # Zapisz w cache
        self.cache[file_hash] = result
        
        return result if self._matches_query(result, query) else None
    
    def _process_html_file(self, file_path: str, query: SearchQuery) -> Tuple[Dict, Dict]:
        """Specjalne przetwarzanie plików HTML"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()
        except:
            return {}, {}
        
        data = {}
        metadata = {
            'title': '',
            'charset': '',
            'language': '',
            'meta_description': '',
            'meta_keywords': ''
        }
        
        # Ekstraktuj metadane HTML
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.IGNORECASE | re.DOTALL)
        if title_match:
            metadata['title'] = title_match.group(1).strip()
        
        # Ekstraktuj JSON jeśli potrzebne
        if 'json' in query.content_types:
            json_data = self.parsers.extract_json_from_html(html_content)
            if json_data:
                data['json'] = json_data
        
        # Ekstraktuj CSV z tabel jeśli potrzebne
        if 'csv' in query.content_types:
            csv_data = self.parsers.extract_csv_from_html(html_content)
            if csv_data:
                data['csv'] = csv_data
        
        return data, metadata
    
    def _get_file_hash(self, file_path: str, mtime: float) -> str:
        """Generuje szybki hash dla cache"""
        return hashlib.md5(f"{file_path}:{mtime}".encode()).hexdigest()
    
    def _matches_query(self, result: SearchResult, query: SearchQuery) -> bool:
        """Sprawdza czy wynik pasuje do zapytania"""
        if not query.query_text:
            return True
        
        # Szukaj w różnych miejscach
        search_text = query.query_text.lower()
        
        # W nazwie pliku
        if search_text in os.path.basename(result.file_path).lower():
            return True
        
        # W metadanych
        metadata_str = json.dumps(result.metadata).lower()
        if search_text in metadata_str:
            return True
        
        # W danych
        data_str = json.dumps(result.data).lower()
        if search_text in data_str:
            return True
        
        return False
    
    def _filter_and_sort_results(self, results: List[SearchResult], query: SearchQuery) -> List[SearchResult]:
        """Filtruje i sortuje wyniki"""
        # Sortuj po relevancji (prostą heurystyką)
        def relevance_score(result):
            score = 0
            query_lower = query.query_text.lower() if query.query_text else ""
            
            # Punkty za dopasowanie w nazwie
            if query_lower in os.path.basename(result.file_path).lower():
                score += 100
            
            # Punkty za świeżość
            days_old = (datetime.now() - result.timestamp).days
            score += max(0, 30 - days_old)
            
            # Punkty za rozmiar danych
            if result.data:
                score += min(50, len(str(result.data)) // 100)
            
            return score
        
        return sorted(results, key=relevance_score, reverse=True)

# ===============================================
# GENERATOR HTML GUI
# ===============================================

class HTMLGenerator:
    """Generator szybkich, responsywnych HTML GUI"""
    
    @staticmethod
    def generate_search_results_html(results: List[SearchResult], query: SearchQuery) -> str:
        """Generuje HTML z wynikami wyszukiwania"""
        
        # Grupuj wyniki jeśli to rachunki/faktury
        if 'rachunek' in query.query_text.lower() or 'faktur' in query.query_text.lower():
            return HTMLGenerator._generate_invoices_html(results, query)
        
        # Jeśli to zdjęcia
        elif any(r.content_type == 'image' for r in results):
            return HTMLGenerator._generate_photos_html(results, query)
        
        # Standardowy widok
        else:
            return HTMLGenerator._generate_standard_html(results, query)
    
    @staticmethod
    def _generate_invoices_html(results: List[SearchResult], query: SearchQuery) -> str:
        """HTML dla rachunków/faktur z podziałem na miesiące"""
        
        # Grupuj po miesiącach
        monthly_groups = {}
        for result in results:
            month_key = result.timestamp.strftime('%Y-%m')
            if month_key not in monthly_groups:
                monthly_groups[month_key] = []
            monthly_groups[month_key].append(result)
        
        html = f"""
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Rachunki i Faktury - {len(results)} wyników</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: rgba(255,255,255,0.95); border-radius: 15px; padding: 30px; 
                   margin-bottom: 30px; backdrop-filter: blur(10px); }}
        .month-section {{ background: rgba(255,255,255,0.9); border-radius: 12px; margin-bottom: 25px; 
                         padding: 20px; backdrop-filter: blur(10px); }}
        .month-header {{ font-size: 1.4em; font-weight: 600; color: #2d3748; margin-bottom: 15px; 
                        border-bottom: 2px solid #4299e1; padding-bottom: 8px; }}
        .invoice-table {{ width: 100%; border-collapse: collapse; }}
        .invoice-table th {{ background: #4299e1; color: white; padding: 12px; text-align: left; }}
        .invoice-table td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; }}
        .invoice-table tr:hover {{ background: #f7fafc; }}
        .file-link {{ color: #3182ce; text-decoration: none; font-weight: 500; }}
        .file-link:hover {{ text-decoration: underline; }}
        .file-size {{ color: #718096; font-size: 0.9em; }}
        .total-summary {{ background: rgba(66, 153, 225, 0.1); padding: 15px; border-radius: 8px; 
                         margin-top: 20px; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📄 Rachunki i Faktury</h1>
            <p>Znaleziono <strong>{len(results)}</strong> dokumentów dla zapytania: <em>"{query.query_text}"</em></p>
            <p>Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
"""
        
        # Dodaj sekcje miesięczne
        for month in sorted(monthly_groups.keys(), reverse=True):
            month_results = monthly_groups[month]
            month_name = datetime.strptime(month, '%Y-%m').strftime('%B %Y')
            
            html += f"""
        <div class="month-section">
            <div class="month-header">📅 {month_name} ({len(month_results)} dokumentów)</div>
            <table class="invoice-table">
                <thead>
                    <tr>
                        <th>Nazwa pliku</th>
                        <th>Data</th>
                        <th>Rozmiar</th>
                        <th>Typ</th>
                        <th>Podgląd metadanych</th>
                    </tr>
                </thead>
                <tbody>"""
            
            for result in month_results:
                file_name = os.path.basename(result.file_path)
                file_size = HTMLGenerator._format_file_size(result.size)
                metadata_preview = HTMLGenerator._format_metadata_preview(result.metadata)
                
                html += f"""
                    <tr>
                        <td><a href="file://{result.file_path}" class="file-link">{file_name}</a></td>
                        <td>{result.timestamp.strftime('%Y-%m-%d')}</td>
                        <td class="file-size">{file_size}</td>
                        <td>{result.content_type.upper()}</td>
                        <td>{metadata_preview}</td>
                    </tr>"""
            
            html += """
                </tbody>
            </table>
        </div>"""
        
        html += f"""
        <div class="total-summary">
            📊 Podsumowanie: {len(results)} dokumentów w {len(monthly_groups)} miesiącach
        </div>
    </div>
</body>
</html>"""
        
        return html
    
    @staticmethod
    def _generate_photos_html(results: List[SearchResult], query: SearchQuery) -> str:
        """HTML dla zdjęć z miniaturkami base64 (PWA style)"""
        
        html = f"""
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Galeria Zdjęć - {len(results)} zdjęć</title>
    <meta name="theme-color" content="#667eea">
    <link rel="manifest" href="data:application/manifest+json,{{'name':'Photo Gallery','short_name':'Gallery','start_url':'.','display':'standalone','theme_color':'#667eea'}}">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: #000; color: #fff; overflow-x: hidden; }}
        .header {{ background: linear-gradient(135deg, #667eea, #764ba2); padding: 20px; 
                  text-align: center; position: sticky; top: 0; z-index: 100; }}
        .gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); 
                   gap: 15px; padding: 20px; max-width: 1400px; margin: 0 auto; }}
        .photo-card {{ background: #1a1a1a; border-radius: 12px; overflow: hidden; 
                      transition: transform 0.3s ease, box-shadow 0.3s ease; }}
        .photo-card:hover {{ transform: translateY(-5px); box-shadow: 0 20px 40px rgba(102, 126, 234, 0.3); }}
        .photo-img {{ width: 100%; height: 200px; object-fit: cover; cursor: pointer; }}
        .photo-info {{ padding: 15px; }}
        .photo-name {{ font-weight: 600; margin-bottom: 8px; color: #e2e8f0; }}
        .photo-meta {{ font-size: 0.85em; color: #a0aec0; line-height: 1.4; }}
        .modal {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; 
                 background: rgba(0,0,0,0.95); z-index: 1000; }}
        .modal-content {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); 
                         max-width: 90%; max-height: 90%; }}
        .modal-img {{ max-width: 100%; max-height: 100%; border-radius: 8px; }}
        .close {{ position: absolute; top: 20px; right: 30px; color: #fff; font-size: 40px; 
                 cursor: pointer; z-index: 1001; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                 gap: 15px; padding: 20px; max-width: 1400px; margin: 0 auto; }}
        .stat-card {{ background: rgba(255,255,255,0.1); padding: 20px; border-radius: 12px; 
                     text-align: center; backdrop-filter: blur(10px); }}
        .filters {{ padding: 20px; text-align: center; }}
        .filter-btn {{ background: #4299e1; color: white; border: none; padding: 8px 16px; 
                      margin: 5px; border-radius: 20px; cursor: pointer; }}
        .filter-btn.active {{ background: #2b6cb0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📸 Galeria Zdjęć</h1>
        <p>{len(results)} zdjęć • {query.query_text}</p>
        <p>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="stats">
        <div class="stat-card">
            <h3>📊 Wszystkich zdjęć</h3>
            <p style="font-size: 2em; font-weight: bold;">{len(results)}</p>
        </div>
        <div class="stat-card">
            <h3>📅 Ostatni miesiąc</h3>
            <p style="font-size: 2em; font-weight: bold;">{len([r for r in results if (datetime.now() - r.timestamp).days <= 30])}</p>
        </div>
        <div class="stat-card">
            <h3>💾 Łączny rozmiar</h3>
            <p style="font-size: 2em; font-weight: bold;">{HTMLGenerator._format_file_size(sum(r.size for r in results))}</p>
        </div>
    </div>
    
    <div class="filters">
        <button class="filter-btn active" onclick="filterPhotos('all')">Wszystkie</button>
        <button class="filter-btn" onclick="filterPhotos('jpg')">JPG</button>
        <button class="filter-btn" onclick="filterPhotos('png')">PNG</button>
        <button class="filter-btn" onclick="filterPhotos('recent')">Ostatnie 30 dni</button>
    </div>
    
    <div class="gallery" id="gallery">"""
        
        # Dodaj każde zdjęcie
        from concurrent.futures import ThreadPoolExecutor
        converter = UltraFastConverters()
        
        for i, result in enumerate(results):
            if result.content_type == 'image':
                # Generuj miniaturkę
                thumbnail = converter.image_to_base64(result.file_path)
                if not thumbnail:
                    thumbnail = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjIwMCIgZmlsbD0iIzMzMzMzMyIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTQiIGZpbGw9IiM5OTk5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGR5PSIuM2VtIj5CcsOha2QgemRqxJljaWE8L3RleHQ+PC9zdmc+"
                
                file_name = os.path.basename(result.file_path)
                dimensions = f"{result.metadata.get('width', '?')}×{result.metadata.get('height', '?')}"
                file_size = HTMLGenerator._format_file_size(result.size)
                date_taken = result.metadata.get('DateTime', result.timestamp.strftime('%Y-%m-%d'))
                
                html += f"""
        <div class="photo-card" data-type="{result.file_type[1:]}" data-date="{result.timestamp.timestamp()}">
            <img src="{thumbnail}" alt="{file_name}" class="photo-img" 
                 onclick="openModal('{thumbnail}', '{file_name}')" loading="lazy">
            <div class="photo-info">
                <div class="photo-name">{file_name}</div>
                <div class="photo-meta">
                    📐 {dimensions}<br>
                    💾 {file_size}<br>
                    📅 {date_taken}<br>
                    📁 <a href="file://{result.file_path}" style="color: #4299e1;">Otwórz plik</a>
                </div>
            </div>
        </div>"""
        
        html += """
    </div>
    
    <!-- Modal dla pełnego podglądu -->
    <div id="modal" class="modal" onclick="closeModal()">
        <span class="close" onclick="closeModal()">&times;</span>
        <div class="modal-content">
            <img id="modal-img" class="modal-img" src="" alt="">
        </div>
    </div>
    
    <script>
        function openModal(src, alt) {
            document.getElementById('modal').style.display = 'block';
            document.getElementById('modal-img').src = src;
            document.getElementById('modal-img').alt = alt;
        }
        
        function closeModal() {
            document.getElementById('modal').style.display = 'none';
        }
        
        function filterPhotos(filter) {
            const cards = document.querySelectorAll('.photo-card');
            const buttons = document.querySelectorAll('.filter-btn');
            
            // Update button states
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            // Filter cards
            cards.forEach(card => {
                let show = true;
                
                if (filter === 'jpg') {
                    show = card.dataset.type === 'jpg' || card.dataset.type === 'jpeg';
                } else if (filter === 'png') {
                    show = card.dataset.type === 'png';
                } else if (filter === 'recent') {
                    const cardDate = new Date(parseFloat(card.dataset.date) * 1000);
                    const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
                    show = cardDate > thirtyDaysAgo;
                }
                
                card.style.display = show ? 'block' : 'none';
            });
        }
        
        // Keyboard navigation
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') closeModal();
        });
        
        // PWA functionality
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('data:text/javascript,// Empty SW');
        }
    </script>
</body>
</html>"""
        
        return html
    
    @staticmethod
    def _generate_standard_html(results: List[SearchResult], query: SearchQuery) -> str:
        """Standardowy HTML dla wyników"""
        
        html = f"""
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wyniki wyszukiwania - {len(results)} plików</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 20px; }}
        .header {{ background: rgba(255,255,255,0.95); border-radius: 15px; padding: 30px; 
                   margin-bottom: 30px; backdrop-filter: blur(10px); }}
        .results {{ display: grid; gap: 20px; }}
        .result-card {{ background: rgba(255,255,255,0.9); border-radius: 12px; padding: 20px; 
                       backdrop-filter: blur(10px); transition: transform 0.2s ease; }}
        .result-card:hover {{ transform: translateY(-2px); }}
        .file-name {{ font-size: 1.2em; font-weight: 600; margin-bottom: 10px; }}
        .file-path {{ color: #666; font-size: 0.9em; margin-bottom: 15px; }}
        .file-details {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .detail-section {{ background: #f8f9fa; padding: 15px; border-radius: 8px; }}
        .detail-title {{ font-weight: 600; margin-bottom: 8px; color: #2d3748; }}
        .metadata {{ font-family: monospace; font-size: 0.85em; background: #e2e8f0; 
                    padding: 10px; border-radius: 4px; overflow-x: auto; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Wyniki wyszukiwania</h1>
            <p>Znaleziono <strong>{len(results)}</strong> plików dla: <em>"{query.query_text}"</em></p>
            <p>Wygenerowano: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
        
        <div class="results">"""
        
        for result in results:
            file_name = os.path.basename(result.file_path)
            file_size = HTMLGenerator._format_file_size(result.size)
            
            html += f"""
            <div class="result-card">
                <div class="file-name">📄 {file_name}</div>
                <div class="file-path">{result.file_path}</div>
                
                <div class="file-details">
                    <div class="detail-section">
                        <div class="detail-title">Podstawowe informacje</div>
                        <p><strong>Typ:</strong> {result.content_type.upper()}</p>
                        <p><strong>Rozmiar:</strong> {file_size}</p>
                        <p><strong>Modyfikacja:</strong> {result.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p><a href="file://{result.file_path}" style="color: #3182ce;">Otwórz plik</a></p>
                    </div>"""
            
            if result.metadata:
                html += f"""
                    <div class="detail-section">
                        <div class="detail-title">Metadane</div>
                        <div class="metadata">{HTMLGenerator._format_json_pretty(result.metadata)}</div>
                    </div>"""
            
            if result.data:
                html += f"""
                    <div class="detail-section">
                        <div class="detail-title">Dane</div>
                        <div class="metadata">{HTMLGenerator._format_json_pretty(result.data)}</div>
                    </div>"""
            
            html += """
                </div>
            </div>"""
        
        html += """
        </div>
    </div>
</body>
</html>"""
        
        return html
    
    @staticmethod
    def _format_file_size(size_bytes: int) -> str:
        """Formatuje rozmiar pliku"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
    
    @staticmethod
    def _format_metadata_preview(metadata: Dict) -> str:
        """Formatuje podgląd metadanych"""
        if not metadata:
            return "Brak metadanych"
        
        preview_items = []
        for key, value in list(metadata.items())[:3]:
            if value and str(value).strip():
                preview_items.append(f"{key}: {str(value)[:50]}")
        
        result = " | ".join(preview_items)
        return result[:100] + "..." if len(result) > 100 else result
    
    @staticmethod
    def _format_json_pretty(data: Any) -> str:
        """Formatuje JSON czytelnie"""
        try:
            return json_lib.dumps(data, indent=2, ensure_ascii=False)[:500] + ("..." if len(str(data)) > 500 else "")
        except:
            return str(data)[:500]

# ===============================================
# INTERFEJS BASH/CLI
# ===============================================

class CLIInterface:
    """Interfejs linii poleceń dla szybkiego użycia"""
    
    def __init__(self):
        self.processor = UltraFastSearchProcessor()
        self.html_gen = HTMLGenerator()
    
    def execute_command(self, command: str, scope: int = 1, max_depth: int = 2) -> str:
        """Wykonuje polecenie i zwraca ścieżkę do wygenerowanego HTML
        
        Args:
            command: Polecenie wyszukiwania
            scope: Liczba poziomów w górę (0 = bieżący katalog, 1 = jeden poziom wyżej, itd.)
            max_depth: Maksymalna głębokość przeszukiwania (1 = tylko bieżący katalog, 2 = jeden poziom w dół, itd.)
        """
        # Parsuj polecenie
        query = self._parse_command(command)
        
        # Domyślne ścieżki przeszukiwania
        default_paths = [
            os.path.expanduser("~"),  # Home directory
            "/tmp" if os.name != 'nt' else "C:\\temp",
            "." # Current directory
        ]
        
        # Wykonaj przeszukiwanie
        print(f"🚀 Wykonuję: {command}")
        print(f"   Scope: {scope}, Max depth: {max_depth}")
        results = self.processor.search_files(query, default_paths, scope=scope, max_depth=max_depth)
        
        # Generuj HTML
        html_content = self.html_gen.generate_search_results_html(results, query)
        
        # Zapisz do pliku
        output_file = f"search_results_{int(time.time())}.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ Wyniki zapisane do: {output_file}")
        print(f"🌐 Otwórz w przeglądarce: file://{os.path.abspath(output_file)}")
        
        return output_file
    
    def _parse_command(self, command: str) -> SearchQuery:
        """Parsuje polecenie bash do SearchQuery"""
        command_lower = command.lower()
        
        # Wykryj typ wyszukiwania
        if 'rachunek' in command_lower or 'faktur' in command_lower or 'invoice' in command_lower:
            return SearchQuery(
                query_text="rachunek faktura invoice",
                file_types=['pdf', 'email', 'html'],
                content_types=['metadata'],
                output_format='html',
                include_previews=True
            )
        
        elif 'zdjęci' in command_lower or 'foto' in command_lower or 'photo' in command_lower:
            date_range = None
            if 'ostatni miesiąc' in command_lower or 'last month' in command_lower:
                date_range = (datetime.now() - timedelta(days=30), datetime.now())
            
            return SearchQuery(
                query_text="",
                file_types=['image'],
                date_range=date_range,
                content_types=['exif', 'metadata'],
                output_format='html',
                include_previews=True
            )
        
        elif 'json' in command_lower:
            return SearchQuery(
                query_text=command,
                file_types=['html', 'json'],
                content_types=['json'],
                output_format='html'
            )
        
        elif 'csv' in command_lower:
            return SearchQuery(
                query_text=command,
                file_types=['html', 'csv'],
                content_types=['csv'],
                output_format='html'
            )
        
        elif 'meta' in command_lower or 'exif' in command_lower:
            return SearchQuery(
                query_text=command,
                file_types=['image', 'pdf', 'email', 'audio', 'video'],
                content_types=['metadata', 'exif'],
                output_format='html'
            )
        
        else:
            # Ogólne wyszukiwanie
            return SearchQuery(
                query_text=command,
                file_types=['html', 'pdf', 'email', 'image', 'audio', 'video'],
                content_types=['json', 'csv', 'metadata', 'exif'],
                output_format='html'
            )

# ===============================================
# PRZYKŁADY UŻYCIA I DEMO
# ===============================================

def demo_fast_search():
    """Demonstracja szybkiego wyszukiwania"""
    print("🚀 DEMO: Ultra-szybkie wyszukiwanie")
    
    processor = UltraFastSearchProcessor()
    
    # Test wyszukiwania zdjęć
    query = SearchQuery(
        query_text="",
        file_types=['image'],
        date_range=(datetime.now() - timedelta(days=30), datetime.now()),
        content_types=['exif'],
        include_previews=True
    )
    
    results = processor.search_files(query, ["."])
    print(f"Znaleziono {len(results)} zdjęć z ostatnich 30 dni")
    
    # Generuj HTML
    html_gen = HTMLGenerator()
    html = html_gen.generate_search_results_html(results, query)
    
    with open("demo_photos.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print("✅ Demo zapisane do demo_photos.html")

def demo_cli_interface():
    """Demonstracja interfejsu CLI"""
    print("🖥️ DEMO: Interfejs CLI")
    
    cli = CLIInterface()
    
    # Przykładowe polecenia
    commands = [
        "szukam rachunków z ostatniego miesiąca",
        "pokaż wszystkie zdjęcia z ostatniego miesiąca",
        "znajdź JSON w plikach HTML",
        "ekstraktuj metadane EXIF z obrazów"
    ]
    
    for command in commands:
        print(f"\n💻 Polecenie: {command}")
        output_file = cli.execute_command(command)
        print(f"📄 Wynik: {output_file}")

# GŁÓWNA FUNKCJA
if __name__ == "__main__":
    print("""
╔═════════════════════════════════════════════════════════════╗
║            ULTRA-SZYBKI PROCESOR PLIKÓW v1.0                ║
║                                                             ║
║  🚀 Najszybsze przeszukiwanie i przetwarzanie plików        ║
║  📊 JSON/CSV w HTML/MHTML                                   ║
║  🖼️ Metadane obrazów, PDF, email, audio, video              ║
║  ⚡ Równoległe przetwarzanie                                ║
║  🌐 Generowanie HTML GUI (PWA style)                        ║
║                                                             ║
║  Przykłady użycia:                                          ║
║  python search.py "rachunki email"                          ║
║  python search.py "zdjęcia ostatni tydzień"                 ║
║  python search.py "json w html"                             ║
║  python search.py "metadane EXIF"                           ║
╚═════════════════════════════════════════════════════════════╝
    """)
    
    import sys
    
    if len(sys.argv) > 1:
        # Parse command line arguments
        import argparse
        
        parser = argparse.ArgumentParser(description='Szybkie wyszukiwanie plików')
        parser.add_argument('query', nargs='*', help='Zapytanie wyszukiwania')
        parser.add_argument('--scope', type=int, default=1, 
                         help='Liczba poziomów w górę (0 = bieżący katalog, 1 = jeden poziom wyżej, itd.)')
        parser.add_argument('--max-depth', type=int, default=2,
                         help='Maksymalna głębokość przeszukiwania (1 = tylko bieżący katalog, 2 = jeden poziom w dół, itd.)')
        
        # Handle help before checking for empty query
        if '--help' in sys.argv or '-h' in sys.argv:
            parser.print_help()
            sys.exit(0)
            
        args = parser.parse_args()
        
        if not args.query:
            print("Brak zapytania. Użyj --help, aby zobaczyć dostępne opcje.")
            sys.exit(1)
            
        command = " ".join(args.query)
        cli = CLIInterface()
        cli.execute_command(command, scope=args.scope, max_depth=args.max_depth)
    else:
        # Uruchom demo
        demo_fast_search()
        demo_cli_interface()
        
    print("\n🎯 NAJSZYBSZE ROZWIĄZANIA:")
    print("- Język: Python + C extensions (ujson, lxml, cv2, fitz)")
    print("- Alternatywy: Rust (ripgrep), Go, C++ dla maksymalnej wydajności")
    print("- Konwersje: FFmpeg (media), ImageMagick (obrazy), Pandoc (dokumenty)")
    print("- HTML: Jinja2 templates lub f-strings dla prostych przypadków")
    print("- Równoległość: ThreadPoolExecutor dla I/O, ProcessPoolExecutor dla CPU")