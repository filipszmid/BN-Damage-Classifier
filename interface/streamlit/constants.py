B24_SCHEMA = {
    'Części zamienne w kontenerac': ['numer kontenera', 'nr karty', 'Komentarz', 'part no.', 'ilość', 'Data odrzucenia'],
    'Niezakończone części zamien': ['numer kontenera', 'nr karty', 'Komentarz', 'part no.', 'ilość', 'Data zakończenia (klient)', 'Data odrzucenia'],
    'Karty z czynnikiem chłodniczy': ['numer kontenera', 'nr karty', 'Komentarz', 'ilość', 'armator', '*data zakończenia serwisu RU*', 'naprawa', 'Pojemność agregatu']
}

SAP_SCHEMA = {
    "Required Columns": ['Uwagi', 'Indeks', 'Ilość', 'Opis towaru/usługi', 'Cena jednostkowa']
}

MAP_SCHEMA = {
    "Required Columns": ['Kodkatalogowy']
}
