# Ключевые кадры видео в виджете `/konspekt` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить в ветку виджета `/konspekt` опциональное извлечение ключевых кадров видео (слайды, промпты, инфографика) с распознаванием текста и встраиванием в HTML-виджет.

**Architecture:** Opt-in ветка виджета. Питон достаёт видео (yt-dlp/локал) и режет кандидатов (scene-detection + transcript-cues) → contact-sheet. Vision-движок (Codex 5.5 при доступности, иначе актуальный Sonnet) в два прохода отбирает и распознаёт кадры, отдавая строгий JSON. Claude вписывает кадры в производную копию мастер-MD; текст переиспользует блок промпта/спецблок, иллюстрация — новый элемент-картинка `![](path)`, который генератор встраивает как base64-`<figure>`. Перед фичей — миграция имён скилла на префиксы `MASTER_`/`REVIEW_`/`WIDGET_`.

**Tech Stack:** Python 3.12, ffmpeg 8.1, yt-dlp, Pillow (PIL 12.2), pytest, Node (`node --check` для валидации JS виджета), `codex exec` (gpt-5.5) для vision.

## Global Constraints

- Скилл — под junction `~/.claude/skills/konspekt` → этот репозиторий; правки делать здесь.
- Windows / PowerShell основной, Bash доступен. Запуск питона скилла: `PYTHONUTF8=1 python ...`.
- Имена файлов — новый словарь префиксов: `SRC_` (источник, не трогать), `MASTER_` (мастер), `REVIEW_` (обзор), `WIDGET_` (виджет), `SEC_` (обслуга, не трогать). Курсы остаются на `OUT_*_мастер.md` — автопоиск серии ищет **оба** паттерна.
- Vision-модели через алиас (`sonnet`), а не пин версии. Codex-модель — из его `config.toml` (`gpt-5.5`), не хардкодить.
- Виджет — самодостаточный один HTML; инвариант сборки `✅ JS syntax OK` (через `node --check`) сохраняется.
- Никаких `var()` в inline-стилях виджета — только хардкод hex (существующее правило `layer2_widget.md`).
- TDD: сначала падающий тест, потом минимальная реализация. Частые локальные коммиты. **Push и PR не делать — пользователь сам.**
- Тесты скилла: `.claude/skills/konspekt/tests/`, запуск `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`.

---

## Файловая структура

**Фаза 0 (миграция имён) — правит существующее:**
- `md_parser.py` — логика имени выхода (`_parse_meta`).
- `SKILL.md`, `preview.md`, `layer2_widget.md`, `profile_lecture.md`, `layer3_recon.md`, `recon_patch_template.py` — текстовые упоминания имён и автопоиска.
- `tests/test_widget_generator.py` — тест на новую логику имени.

**Фаза 1 (встраивание картинок) — правит существующее:**
- `md_parser.py` — парс элемента `![alt](path)` в `### Текст`; проброс базового каталога.
- `widget_generator.py` — хелпер base64-встраивания + CSS для `figure`.
- `tests/test_widget_generator.py` — тесты парса и встраивания.

**Фаза 2–3 (извлечение кадров + оркестрация) — новое:**
- `frames_extract.py` — добыча видео, scene-detection, transcript-cues, дедуп, contact-sheet, извлечение shortlist, маппинг таймкодов, availability-гейт Codex, вызов vision.
- `cookies_spec.py` — общий модуль спецификации cookies (вынесен из `youtube_to_srt.py`).
- `frames_schema.json` — output-schema для vision-JSON.
- `tests/test_frames_extract.py` — тесты чистых функций (cues, маппинг, дедуп, availability).

**Фаза 4 (документация ветки) — правит существующее:**
- `layer2_widget.md` — opt-in ветка кадров.
- `SKILL.md` — триггер «виджет с кадрами».
- `.gitignore` — `frames_work/`.

---

# ФАЗА 0 — Миграция имён на префиксы

> Полный контекст, якоря grep и «не трогать» — в `docs/task-prefixes-by-type.md`. Здесь — исполняемые шаги. Решения приняты, не пересматривать. Префикс обзора — `REVIEW_` (не `PREVIEW_`).

### Task 0.0: Гейт чистоты дерева

**Files:** —

- [ ] **Step 1: Проверить незакоммиченные правки**

Run: `git status --short`
Ожидание: в `SKILL.md`, `preview.md`, `widget_generator.py` есть `M` из прошлых сессий.

- [ ] **Step 2: Разобрать чужие правки перед стартом**

Если правки **не связаны** с этой работой — СТОП, спросить пользователя (закоммитить отдельно / stash / разобрать). Не править поверх чужих несохранённых изменений. Продолжать Фазу 0 только после чистого дерева (кроме файлов этого плана).

### Task 0.1: Логика имени выхода `MASTER_ → WIDGET_`

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py:167-169` (в `_parse_meta`)
- Test: `.claude/skills/konspekt/tests/test_widget_generator.py`

**Interfaces:**
- Produces: `parse_master_md(path)['meta']['out']` — имя выходного HTML. Для входа с префиксом `MASTER_` → `WIDGET_<остаток>.html`.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_widget_generator.py — добавить
import md_parser

# ВНИМАНИЕ: _parse_segment (md_parser.py:319) требует РЕАЛЬНЫЙ формат:
# заголовок `## Сегмент N | HH:MM:SS-HH:MM:SS | Тема`, строки `**Тип:**`
# и `**Ключевая мысль:**`, порядок `### Карта` ПЕРЕД `### Текст`.
# Этот хелпер даёт валидную минимальную фикстуру — переиспользуется тестами ниже.
_SEG = (
    "## Сегмент 1 | 00:00:00-00:01:00 | Заголовок\n\n"
    "**Тип:** идея\n**Ключевая мысль:** мысль\n\n"
    "### Карта\n\n- **Термин:** пояснение\n\n"
    "### Текст\n\n{body}\n"
)
def _master(body="Проза."):
    return "# Название\n\n---\n\n" + _SEG.format(body=body)

def test_out_name_master_prefix(tmp_path):
    p = tmp_path / "MASTER_Урок 2.md"
    p.write_text(_master(), encoding="utf-8")
    assert md_parser.parse_master_md(str(p))['meta']['out'] == "WIDGET_Урок 2.html"

def test_out_name_frames_copy_suffix(tmp_path):
    # Производная копия ветки кадров -> имя виджета БЕЗ суффикса _с_кадрами (инвариант спеки).
    p = tmp_path / "MASTER_Урок 2_с_кадрами.md"
    p.write_text(_master(), encoding="utf-8")
    assert md_parser.parse_master_md(str(p))['meta']['out'] == "WIDGET_Урок 2.html"

def test_out_name_legacy_suffix(tmp_path):
    # Легаси-курсы (OUT_*_мастер.md): сохраняем прежнее поведение — снимаем _мастер.
    p = tmp_path / "OUT_Урок 2_мастер.md"
    p.write_text(_master(), encoding="utf-8")
    assert md_parser.parse_master_md(str(p))['meta']['out'] == "Виджет — OUT_Урок 2.html"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py::test_out_name_master_prefix" -v`
Ожидание: FAIL (`out` == `Виджет — MASTER_Урок 2.html`).

- [ ] **Step 3: Заменить логику имени**

`md_parser.py`, заменить строки 167–169:

```python
    stem = Path(path).stem
    if stem.startswith('MASTER_'):
        core = stem[len('MASTER_'):]
        # Производная копия ветки кадров MASTER_X_с_кадрами.md -> WIDGET_X.html
        # (инвариант спеки: виджет без суффикса _с_кадрами).
        core = re.sub(r'_с_кадрами$', '', core)
        out = f"WIDGET_{core}.html"
    else:
        # Легаси-вход (курсы на OUT_*_мастер.md): сохраняем прежнее поведение.
        out_stem = re.sub(r'_мастер$', '', stem)
        out = f"Виджет — {out_stem}.html"
```

- [ ] **Step 4: Запустить оба теста — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py" -k out_name -v`
Ожидание: 3 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/md_parser.py .claude/skills/konspekt/tests/test_widget_generator.py
git commit -m "feat(konspekt): имя выхода MASTER_ -> WIDGET_ (миграция префиксов)"
```

### Task 0.2: Текстовые упоминания имён (генерация выхода)

**Files:**
- Modify: `.claude/skills/konspekt/SKILL.md` — `OUT_[название]_мастер.md`, `_чN_мастер.md`, отчёт «Мастер-MD готов» → `MASTER_[название].md`
- Modify: `.claude/skills/konspekt/preview.md` — `OUT_<Канал>_<название>_обзор.md`, `OUT_<название>_обзор.md`, отчёт «Обзор готов» → `REVIEW_<Канал>_<название>.md`
- Modify: `.claude/skills/konspekt/layer2_widget.md` — вход `…_мастер.md` → `MASTER_[Название].md`; выход `Виджет — [Название].html`/`.json` → `WIDGET_[Название].html`/`.json`
- Modify: `.claude/skills/konspekt/validate_widget.py:27` — regex hook-валидатора матчит только `Виджет.*\.html$`; расширить на `WIDGET_*.html`

- [ ] **Step 1: Найти якоря**

Run: `rg -n "OUT_|_мастер|_обзор|Виджет —" .claude/skills/konspekt/SKILL.md .claude/skills/konspekt/preview.md .claude/skills/konspekt/layer2_widget.md`

- [ ] **Step 2: Заменить продуктовые имена по таблице выше**

Править вручную по каждому попаданию. Тело имени (`[Название]`, `<Канал>`) не менять — только префикс/суффикс. `SRC_` не трогать.

- [ ] **Step 3: Обновить regex hook-валидатора**

В `validate_widget.py` строка 27 — заменить:

```python
    if not re.match(r'Виджет.*\.html$', filename):
```
на:
```python
    if not re.match(r'(Виджет.*|WIDGET_.*)\.html$', filename):
```

(Старый паттерн `Виджет` оставляем для легаси-виджетов курсов.)

- [ ] **Step 4: Проверить, что старых продуктовых имён не осталось**

Run: `rg -n "_мастер\.md|_обзор\.md|Виджет —|OUT_.*_мастер" .claude/skills/konspekt/SKILL.md .claude/skills/konspekt/preview.md .claude/skills/konspekt/layer2_widget.md`
Ожидание: пусто (кроме мест про автопоиск курсов — их правит Task 0.3).

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/SKILL.md .claude/skills/konspekt/preview.md .claude/skills/konspekt/layer2_widget.md .claude/skills/konspekt/validate_widget.py
git commit -m "docs(konspekt): генерация имён на префиксы MASTER_/REVIEW_/WIDGET_ + hook-валидатор"
```

### Task 0.3: Автопоиск серии — двойной поиск

**Files:**
- Modify: `.claude/skills/konspekt/SKILL.md` — ШАГ 0 серийный контекст, «Если есть `*_мастер.md` прошлых частей»
- Modify: `.claude/skills/konspekt/profile_lecture.md` — `*_мастер.md` серии
- Modify: `.claude/skills/konspekt/layer3_recon.md` — «Прочитать `_мастер.md` лекции»
- Modify: `.claude/skills/konspekt/recon_patch_template.py` — комментарий-пример `OUT_Виджет — …html`

- [ ] **Step 1: SKILL.md — двойной паттерн поиска мастеров серии**

Найти в ШАГ 0 текст про поиск `*_мастер.md`. Переписать: искать мастера серии по **`MASTER_*.md` И `OUT_*_мастер.md`** (новые продукты и легаси-курсы).

- [ ] **Step 2: Синхронизировать `profile_lecture.md` и `layer3_recon.md`**

Упомянуть оба паттерна в тех же формулировках.

- [ ] **Step 3: Обновить пример в `recon_patch_template.py`**

Комментарий-пример имени → `WIDGET_….html`.

- [ ] **Step 4: Полный grep продуктовых старых имён по скиллу**

Run: `rg -n "_мастер\.md|_обзор\.md|Виджет —" .claude/skills/konspekt/ -g '*.md' -g '*.py' -g '!tests/**' -g '!**/_archive*/**'`
Ожидание: остаются только упоминания легаси-паттерна `OUT_*_мастер.md` в контексте двойного поиска. `SRC_` на месте.

- [ ] **Step 5: Прогнать весь pytest**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное.

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/SKILL.md .claude/skills/konspekt/profile_lecture.md .claude/skills/konspekt/layer3_recon.md .claude/skills/konspekt/recon_patch_template.py
git commit -m "docs(konspekt): автопоиск серии — двойной поиск MASTER_ и OUT_*_мастер"
```

---

# ФАЗА 1 — Встраивание картинок в виджет

Ядро рендера: элемент `![alt](path)` в `### Текст` → base64-`<figure>`. Тестируется без видео.

### Task 1.1: Проброс базового каталога MD в парсер тела

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py` — `parse_master_md`, `_parse_segment`, `_parse_text`

**Interfaces:**
- Produces: `_parse_text(block, prompt_counter, base_dir)` — новый третий аргумент `base_dir: Path` (каталог мастер-MD, для чтения относительных путей картинок). `_parse_segment(block, idx, prompt_counter, base_dir)` — тоже плюс `base_dir`.

- [ ] **Step 1: Найти сигнатуру `_parse_segment` и его вызов `_parse_text`**

Run: `rg -n "_parse_segment|_parse_text\(" .claude/skills/konspekt/md_parser.py`

- [ ] **Step 2: Пробросить `base_dir` без изменения поведения**

В `parse_master_md` (после строки `text = Path(path).read_text(...)`):

```python
    base_dir = Path(path).parent
```

Изменить строку сборки сегментов на:

```python
    segments = [_parse_segment(b, i + 1, prompt_counter, base_dir) for i, b in enumerate(sections['segments'])]
```

Добавить `base_dir` в сигнатуру `_parse_segment(block, idx, prompt_counter, base_dir)` и прокинуть в вызов `_parse_text(text_block, prompt_counter, base_dir)`. В `_parse_text(block, prompt_counter, base_dir)` пока `base_dir` не используется.

- [ ] **Step 3: Прогнать существующие тесты парсера — без регрессий**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/test_route_block.py .claude/skills/konspekt/tests/test_widget_generator.py -q`
Ожидание: всё зелёное (поведение не менялось).

- [ ] **Step 4: Коммит**

```bash
git add .claude/skills/konspekt/md_parser.py
git commit -m "refactor(konspekt): проброс base_dir в парсер тела сегмента"
```

### Task 1.2: Хелпер base64-встраивания картинки

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py` — новая функция `_render_image`
- Test: `.claude/skills/konspekt/tests/test_widget_generator.py`

**Interfaces:**
- Produces: `_render_image(alt: str, src: str, base_dir: Path) -> str` — возвращает `<figure>...</figure>` с `data:`-URI. Ресайз до ширины ≤1280, RGB→JPEG(quality 82), RGBA→PNG. `alt`/подпись экранируются. Если файл не найден/битый — возвращает `''` и печатает предупреждение в stderr (мягкая деградация).

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_widget_generator.py — добавить
from pathlib import Path
from PIL import Image
import md_parser

def _make_png(path, size=(40, 20), color=(10, 20, 30)):
    Image.new("RGB", size, color).save(path)

def test_render_image_embeds_base64(tmp_path):
    _make_png(tmp_path / "f.png")
    # alt с кавычкой, <, & — идёт в атрибут alt="...", кавычки обязаны экранироваться
    out = md_parser._render_image('Слайд "12" <b>&', 'f.png', tmp_path)
    assert out.startswith('<figure')
    assert 'data:image/jpeg;base64,' in out
    assert '<figcaption>' in out
    assert '&lt;b&gt;' in out and '&amp;' in out and '&quot;' in out
    assert '<b>' not in out

def test_render_image_missing_file(tmp_path):
    out = md_parser._render_image('Нет файла', 'missing.png', tmp_path)
    assert out == ''
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py::test_render_image_embeds_base64" -v`
Ожидание: FAIL (`_render_image` не существует).

- [ ] **Step 3: Реализовать `_render_image`**

В `md_parser.py` (рядом с `_render_prompt`; вверху файла добавить `import base64`, `import io`, `import sys`, `import html`, `from PIL import Image` — проверить, что дублей нет):

```python
IMG_MAX_WIDTH = 1280

def _render_image(alt, src, base_dir):
    """`![alt](src)` -> <figure> c base64 data-URI. Мягкая деградация -> ''."""
    path = Path(base_dir) / src
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:
        print(f"[frames] пропуск картинки {src!r}: {e}", file=sys.stderr)
        return ''
    if img.width > IMG_MAX_WIDTH:
        h = round(img.height * IMG_MAX_WIDTH / img.width)
        img = img.resize((IMG_MAX_WIDTH, h))
    buf = io.BytesIO()
    if img.mode in ('RGBA', 'LA', 'P'):
        img.convert('RGBA').save(buf, format='PNG', optimize=True)
        mime = 'image/png'
    else:
        img.convert('RGB').save(buf, format='JPEG', quality=82, optimize=True)
        mime = 'image/jpeg'
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    cap = html.escape(alt, quote=True)   # экранирует и кавычки — alt идёт в атрибут
    return (f'<figure class="frame"><img alt="{cap}" '
            f'src="data:{mime};base64,{b64}"><figcaption>{cap}</figcaption></figure>')
```

> Владелец встраивания картинок — `md_parser.py` (не `widget_generator.py`): тело сегмента приходит в генератор уже готовым HTML (в `var BODY`), поэтому резолвить `![](path)` нужно на этапе парсинга. `widget_generator.py` отвечает только за CSS (Task 1.4). JSON-путь сборки виджета картинки в `### Текст` не поддерживает — это осознанное ограничение (ветка кадров всегда идёт через MD-копию).

- [ ] **Step 4: Запустить тесты — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py" -k render_image -v`
Ожидание: 2 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/md_parser.py .claude/skills/konspekt/tests/test_widget_generator.py
git commit -m "feat(konspekt): _render_image — base64-встраивание кадра в figure"
```

### Task 1.3: Распознавание `![alt](path)` в `_parse_text`

**Files:**
- Modify: `.claude/skills/konspekt/md_parser.py` — ветка в `_parse_text`
- Test: `.claude/skills/konspekt/tests/test_widget_generator.py`

**Interfaces:**
- Consumes: `_render_image(alt, src, base_dir)` из Task 1.2.
- Produces: строка-картинка на своей строке в `### Текст` → `<figure>` в HTML тела сегмента.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_widget_generator.py — добавить (использует _master и _make_png выше)
def test_parse_text_image_line(tmp_path):
    _make_png(tmp_path / "cand_01.png")
    md = tmp_path / "MASTER_X.md"
    md.write_text(_master("Абзац до.\n\n![Слайд 12](cand_01.png)\n\nАбзац после."), encoding="utf-8")
    data = md_parser.parse_master_md(str(md))
    body = data['segments'][0]['body']
    assert '<figure' in body and 'data:image/' in body
    assert body.index('<p>Абзац до.</p>') < body.index('<figure')
    assert body.index('<figure') < body.index('<p>Абзац после.</p>')
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py::test_parse_text_image_line" -v`
Ожидание: FAIL (картинка попала в `<p>` как текст).

- [ ] **Step 3: Добавить ветку в `_parse_text`**

В `_parse_text`, после блока «Заголовок `#### Шаг N`» (перед маркированным списком), добавить:

```python
        # Картинка-кадр: ![alt](src) на своей строке
        m_img = re.match(r'^!\[(.*?)\]\((.+?)\)$', stripped)
        if m_img:
            html = _render_image(m_img.group(1), m_img.group(2), base_dir)
            if html:
                parts.append(html)
            i += 1
            continue
```

Также добавить `'!['`-строку в условие остановки абзаца (строки 619–624), чтобы картинка не приклеивалась к абзацу:

```python
        while (
            i < len(lines)
            and lines[i].strip() != ''
            and not lines[i].strip().startswith(('>', '#### ', '```', '- ', '!['))
            and not re.match(r'\d+\.\s+', lines[i].strip())
        ):
```

- [ ] **Step 4: Запустить тест + весь набор — зелёные**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/md_parser.py .claude/skills/konspekt/tests/test_widget_generator.py
git commit -m "feat(konspekt): парс элемента-картинки ![](path) в теле сегмента"
```

### Task 1.4: CSS для `figure.frame` + сквозная проверка сборки

**Files:**
- Modify: `.claude/skills/konspekt/widget_generator.py` — константа `CSS`
- Test: `.claude/skills/konspekt/tests/test_widget_generator.py`

**Interfaces:**
- Consumes: тело сегмента с `<figure class="frame">` из Task 1.3.

- [ ] **Step 1: Написать тест сборки HTML с картинкой**

```python
# tests/test_widget_generator.py — добавить
import widget_generator

def test_build_html_with_frame(tmp_path):
    _make_png(tmp_path / "c.png")
    md = tmp_path / "MASTER_X.md"
    md.write_text(_master("![Слайд](c.png)"), encoding="utf-8")
    data = md_parser.parse_master_md(str(md))
    out_html = widget_generator.build_html(data)
    assert 'figure.frame' in out_html          # CSS присутствует
    assert 'data:image/jpeg;base64,' in out_html
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_widget_generator.py::test_build_html_with_frame" -v`
Ожидание: FAIL (`figure.frame` нет в CSS).

- [ ] **Step 3: Добавить CSS**

В `widget_generator.py`, в конец строковой константы `CSS` (перед закрывающими медиа-запросами или в основной блок) добавить:

```css
figure.frame { margin:10px 0; }
figure.frame img { display:block; width:100%; max-width:100%; height:auto; border-radius:10px; box-shadow:0 1px 4px rgba(0,0,0,.12); }
figure.frame figcaption { margin-top:4px; font-size:11.5px; color:#6b7280; }
```

(Добавлять как строку внутри существующего литерала `CSS` — согласовать с его формой: если это тройная кавычка, вставить строки; если конкатенация — добавить фрагмент.)

- [ ] **Step 4: Запустить тест + весь набор**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное.

- [ ] **Step 5: Сквозная проверка — реальная сборка + `node --check`**

Собрать виджет из фикстуры вручную и проверить JS:

```bash
PYTHONUTF8=1 python .claude/skills/konspekt/widget_generator.py "<путь к тестовому MASTER_X.md с картинкой>"
```
Ожидание: `✅ JS syntax OK` и создан `WIDGET_X.html`; открыть в браузере — картинка видна, подпись под ней.

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/widget_generator.py .claude/skills/konspekt/tests/test_widget_generator.py
git commit -m "feat(konspekt): CSS figure.frame для встроенных кадров"
```

---

# ФАЗА 2 — Извлечение кадров (`frames_extract.py`)

Питон-конвейер добычи и подготовки кандидатов. Чистые функции — под TDD; ffmpeg/yt-dlp — тонкие обёртки, проверяются smoke-прогоном.

### Task 2.1: Общий модуль cookies

**Files:**
- Create: `.claude/skills/konspekt/cookies_spec.py`
- Modify: `.claude/skills/konspekt/youtube_to_srt.py` — импорт из нового модуля
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `cookies_from_browser_args(browser: str) -> list[str]` — список аргументов yt-dlp (`['--cookies-from-browser', <spec>]`) либо `[]`. Плюс константа `DEFAULT_BROWSER` (текущий дефолт `youtube_to_srt.py` — `edge`). Вынесено из существующей логики `youtube_to_srt.py` без изменения поведения; диагностика cookie-lock/cookie-error остаётся в `youtube_to_srt.py`.

- [ ] **Step 1: Найти текущую cookies-логику**

Run: `rg -n "cookies-from-browser|cookies_browser|def .*cookie" .claude/skills/konspekt/youtube_to_srt.py`

- [ ] **Step 2: Написать тест на вынесенную функцию**

```python
# tests/test_frames_extract.py — создать файл
import cookies_spec

def test_cookies_args_empty_when_no_browser():
    assert cookies_spec.cookies_from_browser_args('') == []

def test_cookies_args_has_flag():
    args = cookies_spec.cookies_from_browser_args('firefox')
    assert args[0] == '--cookies-from-browser'
    assert 'firefox' in args[1]
```

- [ ] **Step 3: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -v`
Ожидание: FAIL (модуля нет).

- [ ] **Step 4: Создать `cookies_spec.py`**

Перенести в него построение спецификации cookies из `youtube_to_srt.py` (ветку выбора браузера/пути; логику из района `def _cookies*`/`--cookies-from-browser`). Реализовать `cookies_from_browser_args(browser)` возвращающей список аргументов. В `youtube_to_srt.py` — заменить локальную сборку на `from cookies_spec import cookies_from_browser_args` и использовать её (не менять поведение субтитровой ветки).

- [ ] **Step 5: Тесты нового модуля + весь набор**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное (в т.ч. `test_youtube_to_srt.py`).

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/cookies_spec.py .claude/skills/konspekt/youtube_to_srt.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "refactor(konspekt): вынести спецификацию cookies в cookies_spec"
```

### Task 2.2: Парсер transcript-cues

**Files:**
- Create: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `cue_timecodes(srt_text: str) -> list[float]` — секунды реплик, где спикер показывает материал. Маркеры (без регистра): «смотрите», «на слайде», «на экране», «скопируйте», «вот промпт», «вот код», «покажу», «видите». Возвращает отсортированный уникальный список секунд начала реплики.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
import frames_extract

SRT = """1
00:00:05,000 --> 00:00:08,000
Смотрите на слайде важный момент

2
00:00:10,000 --> 00:00:12,000
просто болтовня без маркеров

3
00:01:00,000 --> 00:01:03,000
Скопируйте этот промпт себе
"""

def test_cue_timecodes_finds_markers():
    tc = frames_extract.cue_timecodes(SRT)
    assert 5.0 in tc
    assert 60.0 in tc
    assert 10.0 not in tc
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py::test_cue_timecodes_finds_markers" -v`
Ожидание: FAIL (функции нет).

- [ ] **Step 3: Реализовать `cue_timecodes`**

В тест дописать импорт модуля (в шапку `tests/test_frames_extract.py`, рядом с `import cookies_spec`): `import frames_extract`.

В новом `frames_extract.py`:

```python
"""Извлечение кадров-кандидатов для opt-in ветки виджета /konspekt."""
import re
import subprocess
from pathlib import Path

CUE_MARKERS = [
    'смотрите', 'на слайде', 'на экране', 'скопируйте',
    'вот промпт', 'вот код', 'покажу', 'видите',
]

def _srt_time_to_sec(t):
    h, m, rest = t.split(':')
    s, ms = rest.split(',')
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

def cue_timecodes(srt_text):
    out = []
    blocks = re.split(r'\n\s*\n', srt_text.strip())
    for b in blocks:
        lines = b.splitlines()
        tc_line = next((l for l in lines if '-->' in l), None)
        if not tc_line:
            continue
        text = ' '.join(l for l in lines if '-->' not in l and not l.strip().isdigit()).lower()
        if any(mk in text for mk in CUE_MARKERS):
            start = tc_line.split('-->')[0].strip()
            out.append(_srt_time_to_sec(start))
    return sorted(set(out))
```

- [ ] **Step 4: Запустить — зелёный**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py::test_cue_timecodes_finds_markers" -v`
Ожидание: PASS.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): transcript-cues -> таймкоды кандидатов"
```

### Task 2.3: Парсер `showinfo` → таймкоды

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `parse_showinfo_pts(stderr: str) -> list[float]` — список `pts_time` из вывода `showinfo` в порядке появления. Используется в `scene_timecodes` (Task 2.5).

> Отдельного `zip_candidates(pts, files)` не делаем: файлов на этапе `scene_timecodes` не создаётся (прогон `-f null`), а кадры извлекаются позже отдельным проходом `extract_frame`. Нумерация кандидатов (`cand_id`) идёт от `enumerate(tcs, 1)` в `build_candidates` (Task 2.6) — сшивать pts с файлами не нужно.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
SHOWINFO = (
    "[Parsed_showinfo_1 @ 0x..] n:0 pts:123 pts_time:12.5 pos:...\n"
    "[Parsed_showinfo_1 @ 0x..] n:1 pts:456 pts_time:47.0 pos:...\n"
)

def test_parse_showinfo_pts():
    assert frames_extract.parse_showinfo_pts(SHOWINFO) == [12.5, 47.0]
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py::test_parse_showinfo_pts" -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def parse_showinfo_pts(stderr):
    return [float(m) for m in re.findall(r'pts_time:([0-9.]+)', stderr)]
```

- [ ] **Step 4: Запустить — зелёный**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py::test_parse_showinfo_pts" -v`
Ожидание: PASS.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): parse_showinfo_pts -> таймкоды из showinfo"
```

### Task 2.4: Дедуп кандидатов по интервалу

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces: `dedup_by_gap(timecodes: list[float], min_gap: float = 3.0, cap: int = 60) -> list[float]` — сортирует, выкидывает кадры ближе `min_gap` секунд к предыдущему оставленному; при превышении `cap` прореживает равномерно.

- [ ] **Step 1: Написать падающий тест**

```python
# tests/test_frames_extract.py — добавить
def test_dedup_by_gap_min_gap():
    assert frames_extract.dedup_by_gap([0.0, 1.0, 2.5, 5.0], min_gap=3.0) == [0.0, 5.0]

def test_dedup_by_gap_cap():
    res = frames_extract.dedup_by_gap([float(i) for i in range(0, 200, 1)], min_gap=0.0, cap=10)
    assert len(res) <= 10
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k dedup -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать**

```python
def dedup_by_gap(timecodes, min_gap=3.0, cap=60):
    kept = []
    for t in sorted(set(timecodes)):
        if not kept or t - kept[-1] >= min_gap:
            kept.append(t)
    if len(kept) > cap:
        step = len(kept) / cap
        kept = [kept[int(i * step)] for i in range(cap)]
    return kept
```

- [ ] **Step 4: Запустить — зелёные**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k dedup -v`
Ожидание: 2 passed.

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): дедуп кандидатов по min-gap + cap"
```

### Task 2.5: Обёртки ffmpeg/yt-dlp (видео, scene-detect, стабильный кадр, contact-sheet)

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`

**Interfaces:**
- Produces:
  - `download_video(url, out_dir, browser=None) -> Path` — yt-dlp `-f "bv[height<=720]/best[height<=720]"`, cookies из `cookies_spec` (по умолчанию `DEFAULT_BROWSER`). При ненулевом коде yt-dlp — `RuntimeError` (ветка ловит → виджет без кадров).
  - `scene_timecodes(video: Path, threshold=0.3) -> list[float]` — прогон `select='gt(scene,threshold)',showinfo`, `parse_showinfo_pts` из stderr. При ненулевом коде ffmpeg — `RuntimeError` (не молчаливый пустой список).
  - `extract_frame(video: Path, t: float, out: Path, shift=0.7)` — снять один кадр в `t+shift` (устоявшийся слайд). `-ss` перед `-i` = быстрый seek — осознанный компромисс: для слайдов достаточно, для резких демонстраций менее точен.
  - `_cand_num(path) -> int` — число из имени `cand_NNNN.png` (= `cand_id`).
  - `contact_sheet(frames: list[Path], out: Path, cols=5, thumb_w=320) -> Path` — пронумерованная простыня из **самого списка** `frames` (PIL), номер на каждом мини-кадре = `_cand_num`.

- [ ] **Step 1: Написать падающий тест простыни/нумерации**

```python
# tests/test_frames_extract.py — добавить
from pathlib import Path
from PIL import Image

def _png(path, size=(160, 90), color=(20, 40, 60)):
    Image.new("RGB", size, color).save(path)

def test_cand_num_from_name():
    assert frames_extract._cand_num(Path("cand_0007.png")) == 7

def test_contact_sheet_builds(tmp_path):
    frames = []
    for i in (1, 2, 3):
        p = tmp_path / f"cand_{i:04d}.png"
        _png(p); frames.append(p)
    out = tmp_path / "contact_sheet.png"
    res = frames_extract.contact_sheet(frames, out, cols=2, thumb_w=100)
    assert res.exists()
    im = Image.open(res)
    assert im.width == 2 * 100          # cols * thumb_w
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k "cand_num or contact_sheet" -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать обёртки**

```python
def download_video(url, out_dir, browser=None):
    from cookies_spec import cookies_from_browser_args, DEFAULT_BROWSER
    if browser is None:
        browser = DEFAULT_BROWSER
    out = Path(out_dir) / 'video.%(ext)s'
    cmd = ['yt-dlp', '-f', 'bv[height<=720]/best[height<=720]',
           '-o', str(out), *cookies_from_browser_args(browser), url]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'yt-dlp упал: {r.stderr.strip()[:300]}')
    vids = sorted(Path(out_dir).glob('video.*'))
    if not vids:
        raise RuntimeError('yt-dlp: видео не скачано')
    return vids[0]

def scene_timecodes(video, threshold=0.3):
    cmd = ['ffmpeg', '-i', str(video), '-vf',
           f"select='gt(scene,{threshold})',showinfo", '-f', 'null', '-']
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'ffmpeg scene-detect упал: {r.stderr.strip()[:300]}')
    return parse_showinfo_pts(r.stderr)

def extract_frame(video, t, out, shift=0.7):
    # -ss ПЕРЕД -i = быстрый seek; shift выводит на устоявшийся кадр после перехода.
    cmd = ['ffmpeg', '-y', '-ss', str(max(0.0, t + shift)), '-i', str(video),
           '-frames:v', '1', '-q:v', '2', str(out)]
    subprocess.run(cmd, check=True, capture_output=True)

def _cand_num(path):
    m = re.search(r'(\d+)', Path(path).stem)
    return int(m.group(1)) if m else 0

def contact_sheet(frames, out, cols=5, thumb_w=320):
    """Пронумерованная простыня из списка кадров (PIL). Номер = _cand_num(файла)."""
    from PIL import Image, ImageDraw
    if not frames:
        raise RuntimeError('contact_sheet: нет кадров')
    thumbs = []
    for f in frames:
        im = Image.open(f).convert('RGB')
        h = round(im.height * thumb_w / im.width)
        im = im.resize((thumb_w, h))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 46, 22], fill=(0, 0, 0))
        d.text((5, 4), str(_cand_num(f)), fill=(255, 230, 0))
        thumbs.append(im)
    cell_h = max(t.height for t in thumbs)
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * thumb_w, rows * cell_h), (28, 28, 32))
    for i, t in enumerate(thumbs):
        r, c = divmod(i, cols)
        sheet.paste(t, (c * thumb_w, r * cell_h))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return Path(out)
```

> Номер на простыне = `_cand_num` из имени `cand_NNNN.png`, тот же `cand_id`, что уходит в vision-JSON (Task 2.6, схема). Так vision надёжно ссылается на кадр по видимому номеру.

- [ ] **Step 4: Запустить тест простыни — зелёный; smoke на коротком видео (ручная)**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k "cand_num or contact_sheet" -v`
Ожидание: 2 passed.
Затем взять короткий mp4, в python-REPL проверить `scene_timecodes`/`extract_frame` (создаются PNG).

- [ ] **Step 5: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): обёртки ffmpeg/yt-dlp + пронумерованная contact-sheet (PIL)"
```

### Task 2.6: Оркестратор извлечения + availability-гейт Codex

**Files:**
- Modify: `.claude/skills/konspekt/frames_extract.py`
- Create: `.claude/skills/konspekt/frames_schema.json`
- Test: `.claude/skills/konspekt/tests/test_frames_extract.py`

**Interfaces:**
- Produces:
  - `codex_available() -> bool` — `codex --version` вернул 0.
  - `build_candidates(video, srt_text, work_dir, threshold=0.3, min_gap=3.0, cap=60) -> list[tuple[Path,float]]` — объединяет scene + cues, дедупит, извлекает кадры `cand_%04d.png`, возвращает `(файл, таймкод)`.
  - CLI `main()` с флагами `--url|--video`, `--srt`, `--work-dir`, `--dry-run`.

- [ ] **Step 1: Тест availability-гейта (мокаем subprocess)**

```python
# tests/test_frames_extract.py — добавить
def test_codex_available_true(monkeypatch):
    class R: returncode = 0
    monkeypatch.setattr(frames_extract.subprocess, 'run', lambda *a, **k: R())
    assert frames_extract.codex_available() is True

def test_codex_available_false(monkeypatch):
    def boom(*a, **k): raise FileNotFoundError()
    monkeypatch.setattr(frames_extract.subprocess, 'run', boom)
    assert frames_extract.codex_available() is False
```

- [ ] **Step 2: Запустить — падает**

Run: `PYTHONUTF8=1 python -m pytest ".claude/skills/konspekt/tests/test_frames_extract.py" -k codex_available -v`
Ожидание: FAIL.

- [ ] **Step 3: Реализовать гейт, оркестратор, схему, CLI**

```python
def codex_available():
    try:
        return subprocess.run(['codex', '--version'],
                              capture_output=True).returncode == 0
    except Exception:
        return False

def build_candidates(video, srt_text, work_dir, threshold=0.3, min_gap=3.0, cap=60):
    work = Path(work_dir); work.mkdir(parents=True, exist_ok=True)
    tcs = dedup_by_gap(scene_timecodes(video, threshold) + cue_timecodes(srt_text),
                       min_gap=min_gap, cap=cap)
    out = []
    for idx, t in enumerate(tcs, 1):
        f = work / f'cand_{idx:04d}.png'
        extract_frame(video, t, f)
        if f.exists():
            out.append((f, t))
    return out
```

`frames_schema.json` (output-schema для vision):

```json
{
  "type": "object",
  "properties": {
    "frames": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "cand_id": {"type": "integer"},
          "timecode": {"type": "number"},
          "type": {"type": "string", "enum": ["prompt", "slide-text", "illustration", "drop"]},
          "text": {"type": "string"},
          "caption": {"type": "string"},
          "segment_hint": {"type": "string"},
          "confidence": {"type": "number"}
        },
        "required": ["cand_id", "type", "confidence"]
      }
    }
  },
  "required": ["frames"]
}
```

CLI `main()`: аргументы `--url`/`--video` (взаимоисключающие), `--srt`, `--work-dir`, `--threshold`, `--dry-run`. При `--url` → `download_video`; `cands = build_candidates(...)`; `contact_sheet([f for f, _ in cands], work_dir/'contact_sheet.png')`; напечатать путь простыни и число кандидатов. При `--dry-run` — остановиться после простыни (не звать vision). Печатать отчёт: найдено кандидатов / путь contact-sheet.

- [ ] **Step 4: Тесты гейта — зелёные; весь набор**

Run: `PYTHONUTF8=1 python -m pytest .claude/skills/konspekt/tests/ -q`
Ожидание: всё зелёное.

- [ ] **Step 5: Dry-run на реальном коротком видео (ручная)**

```bash
PYTHONUTF8=1 python .claude/skills/konspekt/frames_extract.py --video "<короткий.mp4>" --srt "<файл.srt>" --work-dir "<...>/frames_work" --dry-run
```
Ожидание: собрана простыня, напечатан отчёт с числом кандидатов.

- [ ] **Step 6: Коммит**

```bash
git add .claude/skills/konspekt/frames_extract.py .claude/skills/konspekt/frames_schema.json .claude/skills/konspekt/tests/test_frames_extract.py
git commit -m "feat(konspekt): оркестратор кандидатов + availability-гейт Codex + схема + CLI dry-run"
```

---

# ФАЗА 3 — Оркестрация vision (документная, исполняется Claude в рантайме)

Vision-шаги 3–4 выполняются не питоном, а Claude/Codex в момент сборки виджета «с кадрами». Их поведение фиксируется в `layer2_widget.md` (Фаза 4). Здесь — заготовки команд, которые туда войдут.

### Task 3.1: Заготовки vision-вызовов (Codex-путь и Sonnet-фолбэк)

**Files:** — (тексты, встраиваются в `layer2_widget.md` в Task 4.1)

- [ ] **Step 1: Зафиксировать Codex-команду триажа**

Простыня → shortlist. Команда (промпт первым, `-i` последним — вариативный флаг иначе съедает промпт):

```bash
codex exec --skip-git-repo-check --output-schema .claude/skills/konspekt/frames_schema.json \
  "Простыня пронумерованных кадров. Верни JSON: для КАЖДОГО кандидата поле type (prompt|slide-text|illustration|drop) и confidence. drop — говорящая голова/декор/дубль. Читать текст не нужно, только отбор." \
  -i "<work_dir>/contact_sheet.png"
```

- [ ] **Step 2: Зафиксировать Codex-команду full-res разбора**

Только shortlist в полном разрешении, вместе с транскриптом. Политика уверенности: при сомнении в дословности промпта → `type=illustration` + пометка. Команда:

```bash
codex exec --skip-git-repo-check --output-schema .claude/skills/konspekt/frames_schema.json \
  "Для каждого приложенного кадра верни JSON-объект: type, дословный text (для prompt/slide-text, сохраняя переносы), caption, segment_hint (по таймкоду и транскрипту), confidence. Если дословность промпта под сомнением — type=illustration, в caption пометь 'проверить'. Транскрипт: <вставить релевантные реплики с таймкодами>." \
  -i "<work_dir>/cand_0007.png" -i "<work_dir>/cand_0012.png"
```

- [ ] **Step 3: Зафиксировать Sonnet-фолбэк**

Если `codex_available()` == false ИЛИ Codex вернул низкую `confidence` на кадре — тот же контракт через субагент актуального Sonnet (модель-алиас `sonnet`, Read по PNG, вернуть тот же JSON). Картинки в главный поток не возвращать — только JSON.

Эти три заготовки — вход для Task 4.1 (не отдельный коммит; коммитятся вместе с `layer2_widget.md`).

---

# ФАЗА 4 — Документация ветки и триггер

### Task 4.1: Ветка кадров в `layer2_widget.md`

**Files:**
- Modify: `.claude/skills/konspekt/layer2_widget.md`

- [ ] **Step 1: Добавить раздел «Opt-in ветка: виджет с кадрами»**

Описать пошагово (взять из спеки `docs/superpowers/specs/2026-07-02-konspekt-widget-frames-design.md`, разделы «Пайплайн» и «Компоненты»):
0. вход видео: URL из шапки транскрипта (`source:`) или локальный mp4/webm;
1. `frames_extract.py` → кандидаты + contact-sheet (упомянуть флаги, `--dry-run`, лимиты из таблицы);
2. триаж (Codex-команда из Task 3.1, фолбэк Sonnet);
3. full-res разбор (команда + политика уверенности);
4. вписать кадры в **производную копию** `MASTER_[Название]_с_кадрами.md`: текст → блок промпта/спецблок, иллюстрация → `![подпись · таймкод](frames_work/cand_NN.png)`;
5. обычная сборка генератором из копии → `WIDGET_[Название].html`;
6. отчёт (найдено/shortlist/текстом/картинкой/отброшено) и мягкая деградация (нет видео/ffmpeg/cookies → обычный виджет без кадров).

- [ ] **Step 2: Добавить таблицу лимитов и раскладку моделей**

Скопировать таблицы «Лимиты по умолчанию» и «Оркестрация» из спеки.

- [ ] **Step 3: Коммит**

```bash
git add .claude/skills/konspekt/layer2_widget.md
git commit -m "docs(konspekt): ветка виджета с кадрами (пайплайн, vision, лимиты)"
```

### Task 4.2: Триггер в `SKILL.md` + `.gitignore`

**Files:**
- Modify: `.claude/skills/konspekt/SKILL.md`
- Modify: `.gitignore`

- [ ] **Step 1: Описать opt-in триггер**

В `SKILL.md`, в разделе режимов, добавить: `/konspekt — сделай виджет с кадрами из <файл>` → ветка кадров (ссылка на `layer2_widget.md`). Обычный «сделай виджет» — без кадров, как раньше.

- [ ] **Step 2: Игнор рабочей папки**

В `.gitignore` добавить строку:

```
frames_work/
```

- [ ] **Step 3: Коммит**

```bash
git add .claude/skills/konspekt/SKILL.md .gitignore
git commit -m "docs(konspekt): триггер 'виджет с кадрами' + игнор frames_work/"
```

---

# ФАЗА 5 — E2E (ручной прогон)

### Task 5.1: Прогон на реальном уроке со слайдами

**Files:** —

- [ ] **Step 1: Выбрать урок с транскриптом и слайдами/демонстрацией экрана**

Взять существующую серию из K_T_P с `MASTER_*.md` и известным YouTube-URL в шапке транскрипта.

- [ ] **Step 2: Dry-run**

Прогнать `frames_extract.py --url <...> --srt <...> --work-dir <...> --dry-run`. Проверить contact-sheet и число кандидатов (должно быть в разумных пределах, не сотни).

- [ ] **Step 3: Полный прогон ветки**

Триаж → разбор (Codex, при недоступности — Sonnet) → вписать кадры в `MASTER_[Название]_с_кадрами.md` → собрать `WIDGET_[Название].html`.

- [ ] **Step 4: Проверка глазами**

Открыть виджет: кадры на местах (в нужных сегментах), промпты распознаны дословно и копируются, иллюстрации видны, подписи есть, вес HTML ≤8 МБ, `✅ JS syntax OK` при сборке.

- [ ] **Step 5: Зафиксировать наблюдения**

Если что-то отобралось/распозналось плохо — записать в backlog или скорректировать пороги/лимиты. Артефакты прогона (видео, frames_work, копию MD, виджет) не коммитить — это продукты в K_T_P.

---

## Self-Review (заполнено при написании плана)

**Покрытие спеки:**
- Источник видео (URL/локал) → Task 2.5 `download_video` + CLI 2.6.
- Гибрид кандидатов (scene + cues) → 2.2, 2.5, 2.6 `build_candidates`.
- Два прохода (contact-sheet триаж → full-res) → 2.5 `contact_sheet`, 3.1 команды, 4.1 документация.
- Vision: Codex при доступности, иначе Sonnet; JSON по схеме → 2.6 гейт+схема, 3.1 команды.
- Стабильный кадр (+shift), надёжный маппинг, дедуп, cap → 2.5 `extract_frame`, 2.3, 2.4.
- Встраивание: производная MASTER_-копия, текст→промпт/спецблок, иллюстрация→figure base64 → Фаза 1 + 4.1.
- Рендер: parse image, base64, CSS, экранирование, вес → 1.2–1.4.
- Миграция имён MASTER_/REVIEW_/WIDGET_ + двойной автопоиск → Фаза 0.
- Мягкая деградация + отчёт + dry-run → 1.2 (битый PNG), 2.6 CLI, 4.1.
- cookies общий модуль → 2.1.
- Тесты (parser, frames_extract, имя) → распределены; E2E → Фаза 5.

**Плейсхолдеры:** код приведён для всех тестируемых задач. `contact_sheet` собирается на PIL из самого списка кадров, номер = `_cand_num` из имени файла — покрыто юнит-тестом.

**Согласованность типов:** `cue_timecodes`/`scene_timecodes` → `list[float]`; `dedup_by_gap(list[float])→list[float]`; `build_candidates→list[(Path,float)]`; `_render_image(alt,src,base_dir)→str`; `contact_sheet(list[Path],...)→Path`; `parse_master_md['meta']['out']` — имя `WIDGET_*.html`. Имена функций сквозные.

## Ревизия по ревью Codex (2026-07-02)

Учтены находки Codex (REQUEST_CHANGES) после первой версии плана:

- **[критично]** Тестовые фикстуры приведены к реальному формату `_parse_segment` (заголовок с таймингом `HH:MM:SS-HH:MM:SS`, `**Тип:**`, `**Ключевая мысль:**`, порядок `### Карта` → `### Текст`) — хелпер `_master()`/`_SEG` в тестах.
- **[критично]** Устранено самопротиворечие Task 0.1: легаси-тест ожидает `Виджет — OUT_Урок 2.html` (совпадает с кодом, снимающим `_мастер`).
- **[критично]** Инвариант спеки закрыт: `_parse_meta` снимает суффикс `_с_кадрами` → производная `MASTER_X_с_кадрами.md` собирается в `WIDGET_X.html` (тест `test_out_name_frames_copy_suffix`).
- **[критично]** `contact_sheet` переписан на PIL: строит пронумерованную простыню из **списка кадров** (убран дубль `cmd` и чтение `cand_%04d.png`), номера видимы для vision, покрыт тестом.
- **[критично]** Мёртвый `zip_candidates` удалён (Task 2.3): нумерация идёт от `enumerate` в `build_candidates`.
- **[поправлено]** `scene_timecodes`/`download_video` проверяют `returncode` (не молчаливый пустой список); `download_video` по умолчанию берёт `DEFAULT_BROWSER` (edge) из `cookies_spec`.
- **[поправлено]** `_render_image` использует `html.escape(alt, quote=True)` — кавычки в `alt`-атрибуте больше не ломают HTML.
- **[поправлено]** Явно зафиксирован владелец встраивания картинок — `md_parser.py`; JSON-путь сборки картинки не поддерживает (осознанно).
- **[поправлено]** Фаза 0 обновляет `validate_widget.py` (regex hook под `WIDGET_*.html`).
- **[мелочь]** Проверочные команды переведены с `grep` на `rg` (Windows/кириллица).
