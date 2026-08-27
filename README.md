# Badanie Wydajności Lokalnej Modeli Językowych

Projekt realizowany w ramach praktyk, którego celem jest zbadanie wydajności sprzętu oraz zachowania modeli językowych uruchamianych lokalnie za pomocą środowiska Ollama. Eksperyment skupia się wyłącznie na parametrach technicznych oraz szybkości przetwarzania bez analizy jakości merytorycznej generowanego tekstu.

## Cel i Zakres Badań

Głównym zadaniem jest analiza następujących zagadnień:
- Wpływ stopnia kwantyzacji na tempo generowania tekstu oraz zużycie pamięci dla tego samego modelu.
- Zachowanie systemu w momencie zapełnienia pamięci karty graficznej i konieczności przeniesienia części wag do pamięci operacyjnej komputera.
- Porównanie zapotrzebowania na zasoby między klasycznymi modelami gęstymi a architekturami wykorzystującymi mieszaninę ekspertów.

### Zestaw pytań testowych
W badaniu wykorzystano przygotowany zestaw trzydziestu pytań o zróżnicowanej długości wejścia. Pytania podzielono równomiernie na trzy grupy: krótkie, średnie oraz długie. Obejmują one zagadnienia z zakresu nauk ścisłych, programowania i wiedzy ogólnej.

## Badane Modele

Dobór modeli tworzy układ testowy o rosnącym zapotrzebowaniu na pamięć, dopasowany do dostępnych zasobów sprzętowych serwera 32 GB VRAM oraz 128 GB pamięci RAM:

| Model | Rozmiar | Rola w eksperymencie |
|---|---:|---|
| `qwen3.5:9b-q4_K_M` | 6,6 GB | Mały model bazowy mieszczący się całkowicie w pamięci karty graficznej |
| `qwen3.5:27b-q4_K_M` | 17 GB | Większy model po kompresji czterobitowej mieszczący się w pamięci karty graficznej |
| `qwen3.5:27b-q8_0` | 30 GB | Model po kompresji ośmiobitowej bliski granicy pamięci |
| `qwen3.5:27b-bf16` | 56 GB | Model w pełnej precyzji wymuszający przeniesienie części wag do pamięci RAM |
| `laguna-xs-2.1:q4_K_M` | 20 GB | Model z mieszaniną ekspertów mieszczący się w pamięci |
| `laguna-xs-2.1:q8_0` | 36 GB | Model z mieszaniną ekspertów przekraczający pojemność pamięci |

## Rejestrowane Parametry

W trakcie każdego przebiegu rejestrowane są:
- Szybkość generowania tekstu oraz tempo wstępnego przetwarzania zapytania wyrażone w liczbie tokenów na sekundę.
- Czas pierwszego załadowania modelu z dysku do pamięci.
- Podział alokacji wag modelu między pamięć karty graficznej a pamięć operacyjną komputera.
- Obciążenie procesora graficznego, wykorzystanie pamięci wideo temperatura układu oraz pobór energii elektrycznej.
- Bieżące zużycie pamięci operacyjnej przez procesy wykonawcze.
- Informacje o konfiguracji sprzętowej, wersji oprogramowania oraz ewentualnych błędach braku pamięci.

## Zapis Wyników

Wszystkie pomiary są automatycznie archiwizowane:
- Szczegółowe wyniki każdego pojedynczego zapytania testowego.
- Zestawienia ze średnimi i medianami dla poszczególnych modeli oraz długości pytań.
- Metryki czasu ładowania oraz stopnia podziału pamięci dla poszczególnych modeli.
- Raport ze stanem środowiska i konfiguracją.

