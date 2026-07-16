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

V Mergadu nastavte pravidlo **Import datového souboru (CSV / XML)** a párování `g:id` proti vstupnímu `g:id` v režimu přesné shody. CSV používá přímo názvy elementů projektu (`g:title`, `description`, `g:product_type`, `g:google_product_category`, `g:brand` a `g:custom_label_0` až `g:custom_label_4`).

## Ruční test

```bash
python generate_feed.py
```

Výstup `docs/status.json` obsahuje čas běhu, počet vstupních a výstupních položek, vynechané služby a SHA-256 vstupního XML.

## Důležité

- Repo musí být veřejné, aby URL mohl Mergado načíst bez přihlášení.
- GitHub Actions musí mít povolené zapisování do repozitáře (`Workflow permissions: Read and write`).
- Pokud zdrojový feed klesne pod 50 položek nebo obsahuje duplicitní/chybějící ID, běh skončí chybou a poslední funkční CSV se nepřepíše.
