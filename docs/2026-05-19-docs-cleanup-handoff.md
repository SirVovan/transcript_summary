# Промпт для сессии уборки docs/

**Создан:** 2026-05-19
**Назначение:** наведение порядка в `docs/` после сессии рефакторинга парсера мастер-MD.

---

В `docs/` накопилось 9 untracked-файлов с прошлых сессий. Нужна короткая сессия наведения порядка: по каждому файлу решить — закоммитить, добавить в `.gitignore` или удалить. Спрашивай меня по неясным.

Список файлов:

- `docs/cleanup-plan-2026-05-13.md`
- `docs/konspekt-optimization-handoff.md`
- `docs/superpowers/plans/2026-05-05-konspekt-architecture-redesign.md`
- `docs/superpowers/plans/2026-05-14-konspekt-backlog-formatting-timeline.md`
- `docs/superpowers/specs/2026-05-05-konspekt-architecture-redesign.md`
- `docs/token-audit-2026-05-13.md`
- `docs/token-audit-2026-05-17.md`
- `docs/Приемер сегментации.md`
- `extract_segments.py` (в корне)

Контекст: последняя сессия 2026-05-19 — рефакторинг парсера мастер-MD (`docs/history.md` строки 596+). Working tree сейчас чист по модифицированным файлам, только эти 9 untracked. Закоммиченные плановые/handoff-документы 2026-05-19 (`docs/2026-05-19-konspekt-md-parser-handoff.md`, `docs/superpowers/plans/2026-05-19-konspekt-md-parser.md`) трогать не нужно — они в git.

Не перечитывай весь `docs/history.md` целиком. Если нужен контекст по конкретному файлу — открой именно его и читай первые ~50 строк, дальше спрашивай меня.

В конце сессии — `git status` должен показать чистое working tree (или только осознанно оставленные позиции).
