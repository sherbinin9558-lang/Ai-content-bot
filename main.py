"""Надёжная точка входа для Amvera.

Amvera для Python-команд запускает `python3 <command>`, поэтому здесь
используется обычный файл верхнего уровня, а не `python -m ...`.
"""

from bot.main import main


if __name__ == "__main__":
    main()
