## Что делает этот PR

<!-- Краткое описание изменений и мотивация. Ссылки на issue, если есть. -->

## Тип изменений

- [ ] bugfix
- [ ] feature
- [ ] документация
- [ ] рефакторинг
- [ ] security (updater / env_core / CI / подпись / allowlist)
- [ ] AI-assisted (сгенерирован или существенно дополнен AI)

## Checklist

- [ ] `black --check .` зелёный
- [ ] `ruff check .` зелёный
- [ ] `pytest test/` проходит локально
- [ ] новые файлы проходят строгий набор `tools/ruff_new_files_gate.py --base origin/main`
- [ ] если PR меняет updater / env_core / security — соответствующие docs обновлены **в этом же** PR
- [ ] если меняется `requirements.txt` — SBOM и `THIRD_PARTY_NOTICES.md` перегенерированы
- [ ] security-находки не подавлены без per-CVE обоснования в `.security/pip-audit-allowlist.yml`
- [ ] новые файлы **не** добавлены в `[tool.ruff.lint.per-file-ignores]`

## Notes for reviewers

<!-- Что проверить особенно внимательно. Для security-PR — оценка поверхности атаки. -->
