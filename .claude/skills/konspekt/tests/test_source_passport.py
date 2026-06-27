import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import source_passport


def test_passport_from_clipping_youtube(tmp_path):
    clip = tmp_path / "clip.md"
    clip.write_text(
        '---\ntitle: "T"\nsource: "https://www.youtube.com/watch?v=SR6TTf4q1uw"\n---\nтело\n',
        encoding="utf-8",
    )
    p = source_passport.passport_from_clipping(clip)
    assert p["source_id"] == "SR6TTf4q1uw"
    assert p["source_url"] == "https://www.youtube.com/watch?v=SR6TTf4q1uw"


def test_passport_watch_url_with_extra_params(tmp_path):
    # тот же баг-кейс, что ловился в source_id: v= не первый параметр
    clip = tmp_path / "clip.md"
    clip.write_text(
        '---\nsource: "https://www.youtube.com/watch?list=PL1&v=SR6TTf4q1uw"\n---\n',
        encoding="utf-8",
    )
    p = source_passport.passport_from_clipping(clip)
    assert p["source_id"] == "SR6TTf4q1uw"


def test_passport_lines_format():
    line = source_passport.passport_lines("SR6TTf4q1uw", "https://youtu.be/SR6TTf4q1uw")
    assert "source_id: SR6TTf4q1uw" in line
    assert "source_url: https://youtu.be/SR6TTf4q1uw" in line
