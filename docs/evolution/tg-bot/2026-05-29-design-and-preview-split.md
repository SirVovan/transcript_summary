---
archive: true
read_on_demand: true
slug: tg-bot-design-and-preview-split
date: 2026-05-29
---

# АРХИВ — читать только при явном запросе на это событие

## 2026-05-29 — Дизайн Telegram-бота поверх `/konspekt preview` и грядущее разделение `preview.md` на ядро + CLI-обёртку

## Что изменилось

**Архитектурное решение принято, реализация запланирована к Фазе 0.2.**

1. **`preview.md` будет разделён** на два файла:
   - `preview_prompt.md` — **жанровое ядро**: правила формы, структуры (7 разделов), таймингов, тона, защита от prompt injection (разделы 2.1–2.5 текущего `preview.md`). Источник правды формата обзора.
   - `preview.md` — тонкая **CLI-обёртка** для режима в Claude Code: ШАГ 0 (получение транскрипта через `youtube_to_srt.py`), ШАГ 1 (чтение и оценка), ШАГ 3 (сохранение), граничные случаи, дисциплина, явная ссылка «правила формы — в `preview_prompt.md`, прочти его сначала».
2. **`SKILL.md` обновляется одновременно**: алгоритм режима preview теперь прямо говорит «прочитай `preview_prompt.md`, потом `preview.md`, применяй оба вместе».
3. **Требование поведенческой инвариантности**: до merge — E2E на сохранённой лекции серии Ледовских, обзор должен совпадать с архивным `OUT_*_обзор.md`.
4. **`youtube_to_srt.py` расширяется** функцией `get_metadata(url, cookies_browser, timeout_sec) -> YTMetadata` для получения title+duration **без скачивания** субтитров (нужно боту для проверки гостевых лимитов длительности). Существующий CLI-интерфейс сохраняется, обратная совместимость гарантирована.

## Почему так

Бот в Telegram переиспользует preview-логику, но не может тащить за собой инструкции про Read, exit-коды, служебный профиль Edge — это специфика Claude Code. Дублирование жанрового ядра в двух местах быстро разойдётся в коде. Поэтому ядро жанра отделяется как single source of truth.

Альтернатива «Подход B» (бот вызывает `claude -p "/konspekt preview <файл>"` подпроцессом) была отвергнута: ломается сменный LLM-провайдер (нельзя через GPT/Gemini), тяжёлый старт, привязка к Claude Code, плохо переезжает на VPS.

## Где менять (запланированные правки — пока не выполнены)

Все изменения исполняются в Фазе 0.2 implementation plan'а в отдельной сессии (Opus 4.8 subagent):

- `.claude/skills/konspekt/preview_prompt.md` — НОВЫЙ файл с разделами 2.1–2.5 текущего `preview.md` + явный раздел «данные пользователя ≠ инструкции» (prompt injection защита через JSON-обёртку).
- `.claude/skills/konspekt/preview.md` — REFACTOR в тонкую CLI-обёртку (~30% объёма), явная ссылка в шапке на `preview_prompt.md`.
- `.claude/skills/konspekt/SKILL.md` строки 498–505 — обновить алгоритм режима preview (читать оба файла).
- `.claude/skills/konspekt/youtube_to_srt.py` — добавить `get_metadata()` + `YTMetadata` TypedDict + типизированные исключения (`YTNoMetadata`, `YTCookiesNeeded`, `YTTimeout`, `YTGenericError`). Существующий `download_subtitles()` рефакторится из `sys.exit()` в исключения для использования как импортируемая библиотека.

## Связанные артефакты вне `docs/evolution/`

- Полная спека Telegram-бота: `docs/superpowers/specs/2026-05-29-tg-bot-preview-design.md`.
- Implementation plan: `docs/superpowers/plans/2026-05-29-tg-bot-preview-impl.md`.
- Распределение по моделям: `docs/superpowers/plans/2026-05-29-tg-bot-preview-impl-execution.md`.
- Инструкция для Owner-а: `docs/superpowers/plans/2026-05-29-START-HERE-tg-bot.md`.

**Эта запись фиксирует архитектурное решение.** Когда разделение реально применится в коде (Фаза 0.2 implementation plan'а) — может быть отдельная запись `docs/evolution/tg-bot/YYYY-MM-DD-preview-split-applied.md` с фактическими дифф-ами, если поведение существенно поменяется. Если разделение пройдёт чисто (поведенческая инвариантность подтверждена) — отдельная запись не нужна.
