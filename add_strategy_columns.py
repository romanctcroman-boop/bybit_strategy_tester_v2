"""Add market_type and direction columns to strategies table."""

import os

from sqlalchemy import create_engine, text


def migrate():
    # Use data.sqlite3 for strategies table (not app.sqlite3)
    db_path = os.path.join(os.path.dirname(__file__), "data.sqlite3")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE strategies ADD COLUMN market_type VARCHAR(10) DEFAULT 'linear'"))
            print("Added market_type column")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("market_type column already exists")
            else:
                print(f"Error adding market_type: {e}")

        try:
            conn.execute(text("ALTER TABLE strategies ADD COLUMN direction VARCHAR(10) DEFAULT 'both'"))
            print("Added direction column")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("direction column already exists")
            else:
                print(f"Error adding direction: {e}")

        conn.commit()
        print("Migration complete!")


if __name__ == "__main__":
    migrate()
