# Промпт для новой сессии: Codex-ревизия ветки «кадры видео в виджете»

> Скопируй всё, что ниже разделителя, в новую сессию Claude Code, запущенную в
> папке `d:\Users\Вова\Desktop\Work\VibeCoding\konspekt-project`.

---

Проведи ревизию реализованной фичи «ключевые кадры видео в виджете `/konspekt`»
через **Codex** (`codex exec` напрямую из Bash — субагент codex-rescue не умеет
опрашивать фоновую задачу; см. договорённости проекта).

## Контекст
- Репозиторий: `d:\Users\Вова\Desktop\Work\VibeCoding\konspekt-project` (это инструмент — исходник скилла `/konspekt`).
- Ветка: **`feat/konspekt-widget-frames`**. Сначала убедись, что checked out именно она (`git branch --show-current`) и HEAD = `5bb361e`. Если нет — переключись (`git switch feat/konspekt-widget-frames`).
- Фича уже реализована и прошла внутреннее whole-branch ревью на Opus (3 Important-правки закрыты в `5bb361e`). Цель этой сессии — **независимый второй взгляд Codex** перед живым прогоном и слиянием.
- Спека: `docs/superpowers/specs/2026-07-02-konspekt-widget-frames-design.md`
- План (с Global Constraints): `docs/superpowers/plans/2026-07-02-konspekt-widget-frames.md`
- Ход реализации/ревью: `.superpowers/sdd/progress.md`

## Что ревизировать
Диапазон коммитов фичи: **`1c0d652..5bb361e`** (16 коммитов; всё до `1c0d652` — это отдельная не-относящаяся работа и планы, НЕ ревизировать).

Ключевые файлы:
- `.claude/skills/konspekt/md_parser.py` — `_render_image` (base64-`<figure>`, экранирование alt, локальный импорт PIL), ветка `![](path)` в `_parse_text`, имя выхода `MASTER_→WIDGET_` в `_parse_meta`.
- `.claude/skills/konspekt/frames_extract.py` — `cue_timecodes`, `parse_showinfo_pts`, `dedup_by_gap`, обёртки `download_video`/`scene_timecodes`/`extract_frame`, `contact_sheet` (PIL), `build_candidates`, `codex_available`, CLI `main()`.
- `.claude/skills/konspekt/cookies_spec.py` — вынесенная спецификация cookies.
- `.claude/skills/konspekt/widget_generator.py` — CSS `figure.frame`.
- `.claude/skills/konspekt/frames_schema.json` — output-schema для vision.
- `.claude/skills/konspekt/layer2_widget.md` — документация opt-in ветки.

## Как запустить Codex
1. Сгенерируй диф в файл, например:
   `git diff 1c0d652 5bb361e > "$TMP/frames-feature.diff"` (или используй `.superpowers/sdd/review-1c0d652..bbac89c.diff`, но он до правок `5bb361e` — лучше пересобрать).
2. Запусти `codex exec` (модель — из его `config.toml`, не пинить) с ревью-промптом, передав диф и/или пути ключевых файлов. Промпт первым, вариативные флаги последними. Пример каркаса:
   ```bash
   codex exec --skip-git-repo-check \
     "Ты — строгий ревьюер. Проверь диф фичи (файл frames-feature.diff) на: (1) корректность логики (_render_image экранирование/ресайз/mime, парс ![](path) и взаимодействие со стоп-условием абзаца, build_candidates нумерация cand_id, dedup_by_gap прореживание по cap, cue_timecodes/parse_showinfo_pts, поведение-сохранение при выносе cookies_spec); (2) обёртки ffmpeg/yt-dlp (returncode-гарды, -ss перед -i, мягкая деградация при плохом таймкоде); (3) инвариант имён MASTER_→WIDGET_ и снятие суффикса _с_кадрами; (4) НЕТ хардкода версий моделей нигде (только алиасы/доступность) — это жёсткое правило; (5) виджет самодостаточный (base64 inline), node --check проходит; (6) тест-гигиена (реальное поведение, ничего не бьёт в сеть/ffmpeg/codex). Верни находки уровнями Critical/Important/Minor с file:line."
   ```
   При необходимости добавь `-i`/пути к файлам по механике codex.
3. Собери находки Codex, отсортируй по severity.

## Что сделать с находками
- Покажи мне сводку (Critical/Important/Minor) с file:line.
- **Правки не применяй без моей команды.** Для Critical/Important предложи минимальные хирургические фиксы; после моего «да» — правь по TDD (падающий тест → фикс → `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q` зелёные), коммить **по одной теме, без Claude-атрибуции**. Push/PR не делай.
- Договорённость по языку — русский. При развилках — уточняй.

## Критерий готовности
Сводка находок Codex у меня на руках; договорились, что чинить (если есть Critical/Important), и это применено с зелёными тестами — либо подтверждено, что блокеров нет.
