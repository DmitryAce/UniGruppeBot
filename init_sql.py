import sqlite3

def create_tables(conn):
    """Создает необходимые таблицы в базе данных."""
    cursor = conn.cursor()
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS chats (
                        chat_id INTEGER PRIMARY KEY,
                        chat_title TEXT
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        user_id INTEGER,
                        chat_id INTEGER,
                        user_name TEXT,
                        admin BOOLEAN,
                        status TEXT,
                        PRIMARY KEY (user_id, chat_id),
                        FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
                    )''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS queues (
                        queue_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id INTEGER,
                        thread_id INTEGER,
                        bot_message_id INTEGER, -- идентификатор сообщения бота
                        FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
                    )''')


    cursor.execute('''CREATE TABLE IF NOT EXISTS enqueued (
                        queue_id INTEGER,
                        user_id INTEGER,
                        position INTEGER,
                        priority INTEGER,
                        PRIMARY KEY (queue_id, user_id),
                        FOREIGN KEY (queue_id) REFERENCES queues(queue_id),
                        FOREIGN KEY (user_id) REFERENCES users(user_id)
                    )''')


    conn.commit()
    print("db created")
    return cursor
