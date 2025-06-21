# QRY - Przykłady użycia

## 1. Wyszukiwanie plików

### Znajdź wszystkie obrazy w bieżącym katalogu i podkatalogach
```bash
qry "type:image"
```

### Znajdź pliki PDF z ostatnich 7 dni
```bash
qry "type:pdf date:7d"
```

### Wyszukaj pliki większe niż 5MB
```bash
qry "size:>5M"
```

## 2. Przeszukiwanie treści

### Znajdź pliki zawierające słowo "faktura"
```bash
qry "faktura"
```

### Szukaj w konkretnych typach plików
```bash
qry "keyword type:pdf,docx"
```

## 3. Praca z metadanymi

### Wyświetl metadane pliku
```bash
qry --metadata sciezka/do/pliku.jpg
```

### Znajdź zdjęcia z określonymi parametrami EXIF
```bash
qry "exif.camera:Canon exif.focal_length:50mm"
```

## 4. Eksport wyników

### Zapisz wyniki do pliku JSON
```bash
qry "zapytanie" --output results.json
```

### Wygeneruj raport HTML
```bash
qry "zapytanie" --html report.html
```

## 5. Zaawansowane zapytania

### Znajdź duplikaty plików
```bash
qry "duplicates:true"
```

### Wyszukaj puste pliki
```bash
qry "size:0"
```

## 6. Integracja z innymi narzędziami

### Przekaż wyniki do innego programu
```bash
qry "*.log" | grep "error"
```

### Zlicz linie w znalezionych plikach
```bash
qry "*.py" --exec "wc -l"
```

## 7. Przykłady dla programistów

### Znajdź funkcje w plikach Pythona
```bash
qry "def function_name" --type py
```

### Znajdź importy w kodzie źródłowym
```bash
qry "^import " --type py
```

## 8. Automatyzacja

### Usuń puste katalogi
```bash
qry --empty-dirs | xargs rmdir
```

### Zmień uprawnienia plików
```bash
qry "*.sh" --exec "chmod +x"
```

## 9. Przykłady dla dokumentacji

### Znajdź pliki README
```bash
qry "README*"
```

### Wyszukaj w dokumentacji
```bash
qry "słowo_kluczowe" --path /ścieżka/do/dokumentacji
```

## 10. Monitorowanie systemu

### Znajdź duże pliki tymczasowe
```bash
qry "size:>100M /tmp/"
```

### Monitoruj zmiany w katalogu
```bash
while true; do qry --changed 5m /sciezka/do/monitorowania; sleep 300; done
```

## 11. Przetwarzanie dokumentów

### Konwertuj HTML do tekstu
```bash
qry "file.html" --to-txt
```

### Wyodrębnij tabele z plików PDF
```bash
qry "*.pdf" --extract-tables
```

## 12. Praca z archiwami

### Przeszukaj zawartość archiwów ZIP
```bash
qry "*.zip" --search-in-archive
```

### Wyodrębnij pliki z archiwów
```bash
qry "*.zip" --extract-to=/katalog/docelowy
```

## 13. Bezpieczeństwo

### Sprawdź uprawnienia plików
```bash
qry "permissions:777"
```

### Znajdź pliki wykonywalne
```bash
qry "executable:true"
```

## 14. Integracja z bazami danych

### Eksport wyników do SQLite
```bash
qry "zapytanie" --sqlite baza.db
```

### Wykonaj zapytanie SQL na wynikach
```bash
qry "*.csv" --sql "SELECT * FROM results WHERE size > 1000000"
```

## 15. Przetwarzanie równoległe

### Przetwarzaj pliki wielowątkowo
```bash
qry "*.jpg" --threads 8 --exec "mogrify -resize 50%"
```

## 16. Filtrowanie wyników

### Wyklucz określone katalogi
```bash
qry "szukany_tekst" --exclude-dir "node_modules,.git"
```

### Filtruj po dacie modyfikacji
```bash
qry "modified:>2023-01-01"
```

## 17. Integracja z chmurą

### Przesyłaj znalezione pliki na S3
```bash
qry "*.log" --s3-upload s3://moj-kosz/logs/
```

### Synchronizuj z Google Drive
```bash
qry "--sync-gdrive folder_id /lokalna/sciezka"
```

## 18. Monitorowanie zmian

### Śledź nowe pliki
```bash
qry "--watch /sciezka --exec 'echo Zmieniono: %f'"
```

## 19. Przetwarzanie multimediów

### Konwertuj obrazy
```bash
qry "*.jpg" --convert "png" --quality 80
```

### Wyodrębnij klatki z wideo
```bash
qry "*.mp4" --extract-frames --fps 1
```

## 20. Analiza danych

### Analizuj logi
```bash
qry "access.log" --analyze-logs
```

### Generuj statystyki
```bash
qry "*.csv" --stats
```
