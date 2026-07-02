"""Тесты для cookies_spec.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import cookies_spec


def test_cookies_args_empty_when_no_browser():
    assert cookies_spec.cookies_from_browser_args('') == []


def test_cookies_args_has_flag():
    args = cookies_spec.cookies_from_browser_args('firefox')
    assert args[0] == '--cookies-from-browser'
    assert 'firefox' in args[1]
