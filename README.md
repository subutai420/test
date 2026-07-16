# Louie.pet → automatický import pro Mergado

Generátor jednou za hodinu:

1. stáhne aktuální Feedyio XML,
2. zkontroluje minimální počet položek, povinná ID a duplicity,
3. automaticky klasifikuje nové produkty,
4. vynechá neproduktové služby,
5. vytvoří `docs/mergado-import.csv`,
6. změnu publikuje do veřejného GitHub repozitáře.

## URL pro Mergado

Po nahrání do veřejného repozitáře použijte:

`https://raw.githubusercontent.com/subutai420/test/main/docs/mergado-import.csv`

V Mergadu nastavte pravidlo **Import datového souboru (CSV / XML)**, přesnou shodu `ID` na vstupní `g:id` a mapování ostatních sloupců na odpovídající elementy.

## Ruční test

```bash
python generate_feed.py
```

Výstup `docs/status.json` obsahuje čas běhu, počet vstupních a výstupních položek, vynechané služby a SHA-256 vstupního XML.

## Důležité

- Repo musí být veřejné, aby URL mohl Mergado načíst bez přihlášení.
- GitHub Actions musí mít povolené zapisování do repozitáře (`Workflow permissions: Read and write`).
- Pokud zdrojový feed klesne pod 50 položek nebo obsahuje duplicitní/chybějící ID, běh skončí chybou a poslední funkční CSV se nepřepíše.
