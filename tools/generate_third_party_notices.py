#!/usr/bin/env python3
"""
tools/generate_third_party_notices.py — TASK-010.

Генерирует THIRD_PARTY_NOTICES.md из SBOM (json/sbom.cdx.json): таблица зависимостей
проекта ( CycloneDX-компоненты name@version + purl) + уведомления о ключевых
лицензиях (XTTS v2 CPML, RVC, GGUF) и сопроводительном тексте про коммерческое
использование. SBOM здесь — источник списка зависимостей; лицензии per-пакета
не зашиты в SBOM, поэтому генератор выводит перечисление компонентов, а
лицензионные обязательства и ключевые модели описаны в заголовке отдельно.

Запуск:
    python tools/generate_third_party_notices.py \
        --sbom json/sbom.cdx.json --output THIRD_PARTY_NOTICES.md
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HEADER = """\
# THIRD-PARTY NOTICES

Сгенерировано из SBOM (`json/sbom.cdx.json`) `{date}`.

XTTS Studio AI включает сторонние библиотеки и модели. Каждая лицензируется
на условиях её правообладателя и **независимо** от лицензии самого проекта
(см. [LICENSE.md](./LICENSE.md)). Использование стороннего компонента не означает
разрешения на коммерческое использование сверх того, что допускает его лицензия.

## Ключевые компоненты и их лицензии

| Компонент | Лицензия | Коммерческое использование |
|-----------|----------|----------------------------|
| XTTS Studio (код проекта) | [LICENSE.md](./LICENSE.md) | разрешено при условиях лицензии |
| XTTS v2 (модель) | [Coqui Public Model License (CPML)](https://coqui.ai/cpml) | ограничено CPML |
| PyTorch | BSD-3-Clause | OK |
| RVC-модели (community) | зависит от автора модели | не подразумевается |
| GGUF-модели (catalog) | зависит от автора модели | не подразумевается |

CPML ограничивает коммерческое использование XTTS v2. RVC/GGUF-модели, доступные
через каталог, имеют собственные лицензии авторов; возможность скачать файл или
его наличие в каталоге **не является** разрешением на коммерческое использование.

## Зависимости рантайма (из SBOM)

Полный список зафиксированных рантайм-зависимостей (source: `requirements.txt`,
через SBOM). Подробные лицензии per-пакета — на страницах пакетов по ссылке.

"""


def _components_table(sbom: dict) -> str:
    components = sbom.get("components", []) if isinstance(sbom, dict) else []
    # только библиотечные компоненты (исключаем сам проект-корень, если помечен)
    rows = []
    for c in components:
        if not isinstance(c, dict):
            continue
        name = c.get("name", "?")
        version = c.get("version", "")
        purl = c.get("purl", "")
        link = purl or name
        rows.append(f"- **{name}** `{version}` — {link}")
    rows.sort()
    return "\n".join(rows) if rows else "_нет данных в SBOM_"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate THIRD_PARTY_NOTICES.md from SBOM.")
    parser.add_argument("--sbom", default="json/sbom.cdx.json")
    parser.add_argument("--output", default="THIRD_PARTY_NOTICES.md")
    args = parser.parse_args(argv)

    sbom_path = Path(args.sbom)
    if not sbom_path.exists():
        print(f"❌ SBOM не найден: {sbom_path}", file=sys.stderr)
        return 2
    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))

    body = HEADER.format(date=date.today().isoformat())
    body += _components_table(sbom)
    footer = (
        "\n\n---\n\n"
        "*Файл генерируется; не редактируйте вручную — "
        "перегенерируйте через `tools/generate_third_party_notices.py`.*\n"
    )
    body += footer

    Path(args.output).write_text(body, encoding="utf-8")
    print(f"✅ Written {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
