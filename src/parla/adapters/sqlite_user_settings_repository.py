"""SQLite adapter for user settings persistence (single-row table)."""

import sqlite3

from parla.domain.user_settings import UserSettings


class SQLiteUserSettingsRepository:
    """Stores user settings as a single row in SQLite."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def get(self) -> UserSettings:
        row = self._conn.execute("SELECT * FROM user_settings WHERE id = 1").fetchone()
        if row is None:
            settings = UserSettings()
            self.save(settings)
            return settings
        return UserSettings(
            cefr_level=row["cefr_level"],
            english_variant=row["english_variant"],
            phonetic_display=bool(row["phonetic_display"]),
        )

    def save(self, settings: UserSettings) -> None:
        self._conn.execute(
            """\
            INSERT INTO user_settings (id, cefr_level, english_variant, phonetic_display)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                cefr_level = excluded.cefr_level,
                english_variant = excluded.english_variant,
                phonetic_display = excluded.phonetic_display
            """,
            (settings.cefr_level, settings.english_variant, int(settings.phonetic_display)),
        )
        self._conn.commit()
