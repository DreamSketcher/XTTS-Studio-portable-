# Базовый уровень безопасности зависимостей (Security Baseline)

**Дата фиксации:** 2026-07-16  
**Версия Python:** 3.11 / 3.13  
**Целевая платформа:** Windows 10/11 x64

## Зафиксированные версии ключевых библиотек

- `torch==2.2.2`
- `torchaudio==2.2.2`
- `torchvision==0.17.2`
- `transformers==4.38.2`
- `TTS==0.22.0`
- `nltk==3.9.4`
- `cryptography==49.0.0`

Библиотека `diskcache` удалена из прямых зависимостей, так как не используется приложением и не требует сохранения кэша через pickle.

## Команда аудита уязвимостей

```bash
python tools/pip_audit_gate.py \
  --requirements requirements.txt \
  --allowlist .security/pip-audit-allowlist.yml
```

Gate запускает `pip-audit`, определяет severity каждой уязвимости из OSV и применяет политику TASK-001: Critical/High валят сборку, если их нет в `.security/pip-audit-allowlist.yml`; Medium/Low — warning; просроченные allowlist-записи валят сборку. Этот шаг вшит в CI. Новые High/Critical CVE, отсутствующие в allowlist, валят сборку.

## Задокументированные исключения

Замороженный ML-стек (`torch==2.2.2`, `transformers==4.38.2`, а также `pillow`, `msgpack`, `nltk`) несёт известные advisory, которые нельзя убрать, не сломав связку XTTS v2 + RVC. Каждое — узкое, датированное, задокументированное исключение в `.security/pip-audit-allowlist.yml` с полями `reason`, `expires_at`, `issue_link` и пояснением в [SECURITY.md](./SECURITY.RU.md). Два representative-класса:

- **`torch` load/`weights_only` RCE (напр. CVE-2025-32434, CVE-2026-24747):** смягчены моделью доверия — грузятся только собственные/пиннутые XTTS-модели и RVC `.pth` под подтверждённым пользователем SHA-256-доверием; embedding cache через `weights_only=True`; attacker-чекпоинтов нет.
- **`torch` JIT/Inductor/distributed/quant/RNN-ops и неиспользуемые классы моделей `transformers`:** уязвимые code path не используются (только eager inference; грузится только XTTS v2, без `trust_remote_code` на remote-репозитории).

`expires_at` (квартал) — триггер переоценки, а не формальность: по истечении CI снова краснеет, пока каждую запись не продлят или не разберут. Список нельзя расширять на новые advisory без отдельного per-CVE анализа угроз и новой даты истечения.
