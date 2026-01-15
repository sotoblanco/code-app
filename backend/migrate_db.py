import sqlite3
import os

def migrate():
    db_path = "/data/database.db"
    
    # Check if DB exists
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}. Nothing to migrate.")
        return

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if language column exists
        cursor.execute("PRAGMA table_info(exercise)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "language" not in columns:
            print("Adding 'language' column to 'exercise' table...")
            cursor.execute("ALTER TABLE exercise ADD COLUMN language VARCHAR DEFAULT 'python'")
            conn.commit()
            print("Migration successful: Added 'language' column.")
        else:
            print("'language' column already exists.")

        if "passing_rule" not in columns:
            print("Adding 'passing_rule' column to 'exercise' table...")
            cursor.execute("ALTER TABLE exercise ADD COLUMN passing_rule VARCHAR DEFAULT 'tests_pass'")
            conn.commit()
            print("Migration successful: Added 'passing_rule' column.")
        else:
            print("'passing_rule' column already exists.")
            
        print("Migration complete.")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
