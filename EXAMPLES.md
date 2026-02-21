# qry — Przykłady użycia / Usage examples

> Wszystkie polecenia poniżej działają z aktualną wersją `qry`.
> Używaj `poetry run qry …` lub zainstaluj pakiet globalnie.

---

## 1. Wyszukiwanie po nazwie pliku

```bash
# Proste wyszukiwanie — domyślnie przeszukuje nazwy plików
qry "invoice"

# Ogranicz zakres i głębokość
qry "faktura" --scope /home/user/dokumenty --depth 2

# Znajdź pliki PDF
qry "" --type pdf --scope /data/docs

# Znajdź pliki README
qry "README" --path . --depth 1
```

## 2. Wyszukiwanie w treści plików

```bash
# Szukaj słowa w zawartości plików
qry "faktura" -c

# Szukaj w konkretnych typach plików
qry "keyword" -c --type py,txt --path ./src

# Wyszukiwanie OR — znajdź pliki zawierające jedno z kilku słów
qry "TODO OR FIXME" -c --type py --path ./src

# Podgląd — pokaż dopasowaną linię z kontekstem
qry "def search" -c -P --path ./qry --depth 3
```

## 3. Wyszukiwanie z wyrażeniami regularnymi (regex)

```bash
# Znajdź pliki .py po nazwie za pomocą regex
qry "\.py$" -r --sort name

# Znajdź definicje funkcji w Pythonie
qry "def \w+\(" -c -r --type py --path ./src

# Znajdź importy na początku linii
qry "^import " -c -r --type py

# Regex + podgląd kontekstu
qry "class \w+Engine" -c -r -P --type py --path ./qry
```

## 4. Filtrowanie po rozmiarze pliku

```bash
# Pliki większe niż 1 MB
qry "" --min-size 1MB --sort size

# Pliki od 10 KB do 500 KB
qry "" --min-size 10k --max-size 500k

# Duże pliki logów
qry "" --type log --min-size 10MB --path /var/log

# Małe pliki Python (< 1 KB)
qry "" --type py --max-size 1k --path ./qry
```

## 5. Filtrowanie po dacie

```bash
# Pliki zmienione w ostatnich 7 dniach
qry "" --last-days 7

# Raporty PDF z ostatniego miesiąca
qry "report" --type pdf --last-days 30 --path /data/docs
```

## 6. Sortowanie wyników

```bash
# Sortuj po nazwie (alfabetycznie)
qry "" --sort name --path ./qry

# Sortuj po rozmiarze (najmniejsze najpierw)
qry "" --sort size --path .

# Sortuj po dacie modyfikacji
qry "" --sort date --last-days 30

# Największe pliki Pythona
qry "" --type py --sort size --path ./qry
```

## 7. Wykluczanie katalogów

Domyślnie pomijane: `.git` `.venv` `__pycache__` `dist` `node_modules` `.tox` `.mypy_cache`

```bash
# Dodaj własne katalogi do wykluczenia
qry "config" -e build -e ".cache"

# Wiele katalogów — rozdzielone przecinkiem
qry "config" -e "build,.cache,.eggs"

# Wyłącz wszystkie domyślne wykluczenia (przeszukaj wszystko)
qry "config" --no-exclude
```

## 8. Formaty wyjścia

```bash
# YAML (domyślny)
qry "invoice"

# JSON — do przetwarzania przez jq
qry "invoice" -o json | jq '.results[]'

# Paths — jedna ścieżka na linię, do pipe'owania
qry "invoice" -o paths

# Zapisz wyniki JSON do pliku
qry "report" --type pdf -o json > results.json
```

## 9. Integracja z innymi narzędziami (piping)

```bash
# Znajdź pliki z TODO i sprawdź ile razy występuje FIXME
qry "TODO" -c -o paths | xargs grep -c "FIXME"

# Skopiuj pasujące pliki do katalogu backup
qry "invoice" -o paths | xargs -I{} cp {} /backup/

# Zlicz linie w znalezionych plikach Python
qry "" --type py -o paths | xargs wc -l

# Otwórz znalezione pliki w edytorze
qry "config" --type yaml -o paths | xargs code
```

## 10. Przetwarzanie wsadowe (batch)

```bash
# Plik z zapytaniami — jedno na linię
echo -e "invoice\nreport\nconfig" > queries.txt

# Przetwórz wsadowo
qry batch queries.txt --format json --output-file results.json

# Wielowątkowe przetwarzanie
qry batch queries.txt --workers 8 --format csv --output-file results.csv
```

## 11. Tryb interaktywny

```bash
# Uruchom tryb interaktywny
qry interactive
# lub skrót:
qry i
```

## 12. Python API

```python
import qry

# Proste wyszukiwanie po nazwie
files = qry.search("invoice", scope="/data/docs")

# Wyszukiwanie w treści plików
matches = qry.search("TODO", scope="./src", mode="content", depth=5)

# Regex + sortowanie
py_files = qry.search(r"test_.*\.py$", scope=".", regex=True, sort_by="name")

# Filtrowanie po rozmiarze — duże pliki
big = qry.search("", scope=".", min_size=1024*1024, sort_by="size")

# Streaming — pamięciowo efektywny, obsługuje Ctrl+C
for file_path in qry.search_iter("faktura", scope="/data", mode="content"):
    print(file_path)

# Własne wykluczenia
files = qry.search("config", exclude_dirs=[".git", "build", ".venv"])

# Filtr po typie pliku
docs = qry.search("", scope="/data", file_types=["pdf", "docx", "md"])
```

## 13. Łączenie flag — przykłady złożone

```bash
# Pliki Pythona > 5 KB, posortowane po rozmiarze, z podglądem treści
qry "class" -c -P --type py --min-size 5k --sort size --path ./qry

# Regex: znajdź pliki testowe, posortowane po nazwie
qry "test_.*\.py$" -r --sort name --path .

# JSON output: pliki zmienione w ostatnim tygodniu, bez .git i node_modules
qry "" --last-days 7 --sort date -o json

# Pipe-friendly: pliki > 100 KB zmienione ostatnio
qry "" --min-size 100k --last-days 3 -o paths | head -20
```

## 14. Informacje o wersji

```bash
# Wersja i dostępne silniki wyszukiwania
qry version
```

---

## Ściągawka flag

| Flaga | Krótka | Opis |
|-------|--------|------|
| `--content` | `-c` | Szukaj w treści plików |
| `--filename` | `-f` | Szukaj po nazwie (domyślne) |
| `--regex` | `-r` | Traktuj zapytanie jako regex |
| `--preview` | `-P` | Pokaż dopasowaną linię (z `-c`) |
| `--type EXT` | `-t` | Filtruj po rozszerzeniu |
| `--path PATH` / `--scope PATH` | `-p` / `-s` | Katalog do przeszukania |
| `--depth N` | `-d` | Maks. głębokość katalogów |
| `--limit N` | `-l` | Maks. liczba wyników (0 = bez limitu) |
| `--min-size SIZE` | | Min. rozmiar pliku (1k, 10MB, 1G) |
| `--max-size SIZE` | | Maks. rozmiar pliku |
| `--last-days N` | | Pliki zmienione w ostatnich N dniach |
| `--sort KEY` | | Sortuj: `name`, `size`, `date` |
| `--exclude DIR` | `-e` | Wyklucz katalog (powtarzalne) |
| `--no-exclude` | | Wyłącz domyślne wykluczenia |
| `--output FMT` | `-o` | Format: `yaml`, `json`, `paths` |
