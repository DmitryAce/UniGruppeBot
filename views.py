import sqlite3
from views import *
from markups import *

conn = sqlite3.connect('chat_users.db', check_same_thread=False)


def get_admins_and_moderators(chat_id):
    """
    Возвращает списки администраторов и модераторов для заданного чата.
    """
    cursor = conn.cursor()

    # Получаем список администраторов
    cursor.execute('SELECT user_tag FROM users WHERE admin = 1 AND chat_id = ?', (chat_id,))
    q_admins = cursor.fetchall()
    admins = [f"@{admin_row[0]}" for admin_row in q_admins]

    # Получаем список модераторов
    cursor.execute('SELECT user_tag FROM users WHERE moderator = 1 AND chat_id = ?', (chat_id,))
    q_moderators = cursor.fetchall()
    moderators = [f"@{moderator_row[0]}" for moderator_row in q_moderators]

    cursor.close()

    # Формируем строки для вывода
    admin_list = "\n".join(admins) if admins else "Нет зарегистрированных администраторов."
    moderator_list = "\n".join(moderators) if moderators else "Нет зарегистрированных модераторов."

    return admin_list, moderator_list






def add_chat(message):
    """Добавляет чат в базу данных, если его нет."""
    chat_id = message.chat.id
    chat_title = message.chat.title
    cursor = conn.cursor()

    cursor.execute("SELECT chat_id FROM chats WHERE chat_id = ?", (chat_id,))
    chat_exists = cursor.fetchone()

    if not chat_exists:
        cursor.execute(
            "INSERT INTO chats (chat_id, chat_title) VALUES (?, ?)",
            (chat_id, chat_title),
        )
        conn.commit()
    
    cursor.close()


def add_user(user_id, chat_id, user_name, is_admin, user_tag):
    """Добавляет пользователя в базу данных с возможностью присвоения статуса администратора."""
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ? AND chat_id = ?",
        (user_id, chat_id),
    )
    user_exists = cursor.fetchone()
    
    cursor.execute(
        "SELECT chat_title FROM chats WHERE chat_id = ?",
        (chat_id,),
    )
    chat = cursor.fetchone()
    group_name = chat[0]
    
    if not user_exists:
        cursor.execute(
            "INSERT INTO users (user_id, chat_id, user_name, admin, status, user_tag) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, chat_id, user_name, is_admin, "active", user_tag),
        )
        conn.commit()
        
        if is_admin:   
            reply = f"Добро пожаловать в {group_name}, {user_name}, теперь ты администратор бота в этом чате."
        else:
            reply = f"Добро пожаловать в {group_name}, {user_name}"
    else:
        # Если пользователь уже существует, обновляем его user_tag
        cursor.execute(
            "UPDATE users SET user_tag = ? WHERE user_id = ? AND chat_id = ?",
            (user_name, user_id, chat_id)
        )
        conn.commit()
        reply = f"{user_name} уже зарегистрирован в этом чате."
        
    cursor.close()
    return reply, group_name


def init_queue(message, thread_id=None):
    """Инициализирует очередь для текущего чата или топика."""
    chat_id = message.chat.id
    thread_id = message.message_thread_id if message.message_thread_id else thread_id
    cursor = conn.cursor()
    
    if chat_id > 0:
        return f"И кто в очереди будет?"
    
    cursor.execute(
        'SELECT admin, moderator FROM users WHERE user_id = ? AND chat_id = ?', 
            (message.from_user.id, chat_id)
        )
    roles = cursor.fetchone()

    if roles is None or (roles[0] == 0 and roles[1] == 0):
        admin_list, moderator_list = get_admins_and_moderators(chat_id)

        cursor.close()
        conn.commit()
        return (
            "У тебя недостаточно прав на такие действия, попроси администратора или модератора.\n\n"
            f"Администратор:\n{admin_list}\n\n"
            f"Список модераторов:\n{moderator_list}"
        )
    if thread_id:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))

    existing_queue = cursor.fetchone()

    if existing_queue:
        cursor.close()
        return f"Очередь уже существует. ID очереди: {existing_queue[0]}"

    cursor.execute('INSERT INTO queues (chat_id, thread_id) VALUES (?, ?)', (chat_id, thread_id))
    conn.commit()
    queue_id = cursor.lastrowid
    cursor.close()

    return f"Очередь успешно создана. ID очереди: {queue_id}"


def kill_queue(message, thread_id=None):
    """Удаляет очередь и всех пользователей для текущего чата или топика."""
    chat_id = message.chat.id
    thread_id = message.message_thread_id if message.message_thread_id else thread_id
    cursor = conn.cursor()

    # Проверка на права администратора
    cursor.execute(
        'SELECT admin, moderator FROM users WHERE user_id = ? AND chat_id = ?', 
            (message.from_user.id, chat_id)
        )
    roles = cursor.fetchone()

    if roles is None or (roles[0] == 0 and roles[1] == 0):
        # Получаем список администраторов
        admin_list, moderator_list = get_admins_and_moderators(chat_id)

        cursor.close()
        conn.commit()
        return (
            "У тебя недостаточно прав на такие действия, попроси администратора или модератора.\n\n"
            f"Администратор:\n{admin_list}\n\n"
            f"Список модераторов:\n{moderator_list}"
        )


    # Получение ID очереди
    if thread_id:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))

    queue_result = cursor.fetchone()

    if not queue_result:
        cursor.close()
        return "Очередь не существует."

    queue_id = queue_result[0]

    # Удаление пользователей из очереди
    cursor.execute('DELETE FROM enqueued WHERE queue_id = ?', (queue_id,))
    # Удаление самой очереди
    cursor.execute('DELETE FROM queues WHERE queue_id = ?', (queue_id,))
    
    conn.commit()
    cursor.close()

    return "Очередь успешно удалена."


def get_queue(message, thread_id=None, user_id=None):
    """Получение текущей очереди"""
    chat_id = message.chat.id
    cursor = conn.cursor()

    if thread_id:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))

    existing_queue = cursor.fetchone()

    if not existing_queue:
        admin_list, moderator_list = get_admins_and_moderators(chat_id)
        cursor.close()
        conn.commit()
        # Формируем сообщение
        return (
            "Очереди еще нет, попросите администратора или модератора создать очередь.\n\n"
            f"Администратор:\n{admin_list}\n\n"
            f"Список модераторов:\n{moderator_list}"
        )

    queue_id = existing_queue[0]
        
    cursor.execute('''SELECT DISTINCT u.user_name, e.position, u.user_id, u.user_tag
                    FROM enqueued e 
                    JOIN users u ON e.user_id = u.user_id 
                    WHERE e.queue_id = ? 
                    ORDER BY e.position''', (queue_id,))

    enqueued_users = cursor.fetchall()

    if not enqueued_users:
        cursor.close()
        conn.commit()
        return "Очередь пуста."

    max_name_length = max(len(user_name) for user_name, _, _, _ in enqueued_users)
    name_column_width = max(max_name_length + 2, 20)

    # Формируем заголовок таблицы
    queue_output = "Очередь:\n"
    queue_output += f"{'№':<3} | {'Имя пользователя':<{name_column_width}}\n"
    queue_output += "-" * (3 + 3 + name_column_width) + "\n"

    if chat_id == -1001641522876:
        # логика для обработки вывода очереди нашей группы с emojis
        for i, (user_name, position, current_user_id, user_tag) in enumerate(enqueued_users, start=1):
            truncated_name = user_name[:15] + "..." if len(user_name) > 15 else user_name
            if position == 1:  # Если пользователь первый в очереди
                if current_user_id == 811311997:
                    queue_output += f"<b>{position:<3} | 👑@{user_tag:<{name_column_width}}</b>\n"
                else:
                    queue_output += f"<b>{position:<3} | @{user_tag:<{name_column_width}}</b>\n"
                continue
            if current_user_id == 811311997:
                queue_output += f"<b>{position:<3} | 👑{user_name:<{name_column_width}}</b>\n"
                continue
            elif current_user_id == 2035497506:
                queue_output += f"<b>{position:<3} | 🅰️🅱️🅾️🅱️🅰️</b>\n"
                continue
            if current_user_id == user_id:
                queue_output += f"<b>{position:<3} | {truncated_name:<{name_column_width}}</b>\n"
            else:
                queue_output += f"{position:<3} | {truncated_name:<{name_column_width}}\n"
    else:
        for i, (user_name, position, current_user_id, user_tag) in enumerate(enqueued_users, start=1):
            truncated_name = user_name[:15] + "..." if len(user_name) > 15 else user_name
            if position == 1:  # Если пользователь первый в очереди
                if current_user_id == 811311997:
                    queue_output += f"<b>{position:<3} | 👑@{user_tag:<{name_column_width}}</b>\n"
                else:
                    queue_output += f"<b>{position:<3} | @{user_tag:<{name_column_width}}</b>\n"
                continue
            if current_user_id == 811311997:
                queue_output += f"<b>{position:<3} | 👑{user_name:<{name_column_width}}</b>\n"
                continue
            if current_user_id == user_id:
                queue_output += f"<b>{position:<3} | {truncated_name:<{name_column_width}}</b>\n"
            else:
                queue_output += f"{position:<3} | {truncated_name:<{name_column_width}}\n"



    conn.commit()
    cursor.close()

    return queue_output


def swap_positions(message, thread_id=None, user_id=None, pos1=None, pos2=None):
    """Команда для обмена позициями пользователей в очереди, доступная только администраторам"""
    chat_id = message.chat.id
    cursor = conn.cursor()

    # Проверка, является ли пользователь администратором
    cursor.execute(
        'SELECT admin, moderator FROM users WHERE user_id = ? AND chat_id = ?', 
            (message.from_user.id, chat_id)
        )
    roles = cursor.fetchone()

    if roles is None or (roles[0] == 0 and roles[1] == 0):
        conn.commit()
        cursor.close()
        return "У вас нет прав для выполнения этой команды. Только администраторы могут менять позиции."

    if not pos1 or not pos2:
        return "Необходимо указать две позиции для обмена."

    # Проверка, что позиции являются целыми числами
    try:
        pos1 = int(pos1)
        pos2 = int(pos2)
    except ValueError:
        return "Позиции должны быть целыми числами."

    if pos1 == pos2:
        return "Невозможно обменять одинаковые позиции."

    # Убедиться, что pos1 всегда меньше pos2
    if pos1 > pos2:
        pos1, pos2 = pos2, pos1

    # Получаем текущий queue_id
    if thread_id:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))
    
    existing_queue = cursor.fetchone()

    if not existing_queue:
        cursor.close()
        return "Очереди нет."

    queue_id = existing_queue[0]
    
    # Проверяем позиции для существующих пользователей
    cursor.execute('''SELECT u.user_name, e.position, e.user_id 
                      FROM enqueued e 
                      JOIN users u ON e.user_id = u.user_id 
                      WHERE e.queue_id = ? AND e.position IN (?, ?) 
                      ORDER BY e.position''', (queue_id, pos1, pos2))
    users_at_positions = cursor.fetchall()

    if len(users_at_positions) == 2:
        # Позиции заняты, меняем местами
        user1, position1, user1_id = users_at_positions[0]
        user2, position2, user2_id = users_at_positions[1]
        
        # Обновление позиций в базе данных
        cursor.execute('UPDATE enqueued SET position = ? WHERE queue_id = ? AND user_id = ?', (pos2, queue_id, user1_id))
        cursor.execute('UPDATE enqueued SET position = ? WHERE queue_id = ? AND user_id = ?', (pos1, queue_id, user2_id))
        conn.commit()

        response = f"Позиции пользователей {user1} и {user2} были обменены."
    elif len(users_at_positions) == 1:
        # Одна из позиций пуста, перемещаем пользователя на свободную позицию
        user, position, user_id = users_at_positions[0]
        target_position = pos1 if position != pos1 else pos2
        
        # Обновление позиции
        cursor.execute('UPDATE enqueued SET position = ? WHERE queue_id = ? AND user_id = ?', (target_position, queue_id, user_id))
        conn.commit()

        response = f"Пользователь {user} перемещён на позицию {target_position}."
    else:
        response = "На указанных позициях нет пользователей."

    cursor.close()
    return response


def pop_position(message, thread_id=None, user_id=None, pos=None):
    """Команда для удаления пользователя из очереди на указанной позиции, доступная только администраторам.
       Все пользователи ниже поднимаются на 1 позицию выше."""
    chat_id = message.chat.id
    cursor = conn.cursor()

    # Проверка, является ли пользователь администратором
    cursor.execute(
        'SELECT admin, moderator FROM users WHERE user_id = ? AND chat_id = ?', 
            (message.from_user.id, chat_id)
        )
    roles = cursor.fetchone()

    if roles is None or (roles[0] == 0 and roles[1] == 0):
        conn.commit()
        cursor.close()
        return "У вас нет прав для выполнения этой команды. Только администраторы могут удалять пользователей из очереди."

    if not pos:
        return "Необходимо указать позицию для удаления."

    # Проверка, что позиция является целым числом
    try:
        pos = int(pos)
    except ValueError:
        return "Позиция должна быть целым числом."

    # Получаем текущий queue_id
    if thread_id:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))
    
    existing_queue = cursor.fetchone()

    if not existing_queue:
        cursor.close()
        return "Очереди нет."

    queue_id = existing_queue[0]
    
    # Проверяем позицию для существующего пользователя
    cursor.execute('''SELECT u.user_name, e.position, e.user_id 
                      FROM enqueued e 
                      JOIN users u ON e.user_id = u.user_id 
                      WHERE e.queue_id = ? AND e.position = ?''', (queue_id, pos))
    user_at_position = cursor.fetchone()

    if user_at_position:
        user, position, user_id = user_at_position
        
        # Удаляем пользователя из очереди
        cursor.execute('DELETE FROM enqueued WHERE queue_id = ? AND user_id = ? AND position = ?', (queue_id, user_id, pos))
        conn.commit()

        # Поднимаем всех пользователей ниже на 1 позицию выше
        cursor.execute('''UPDATE enqueued 
                          SET position = position - 1 
                          WHERE queue_id = ? AND position > ?''', (queue_id, pos))
        conn.commit()

        response = f"Пользователь {user} был удалён с позиции {pos}. Все пользователи ниже подняты на 1 позицию."
    else:
        response = "На указанной позиции нет пользователя."

    cursor.close()
    return response


def insert_position(message, thread_id=None, user_id=None, current_pos=None, new_pos=None):
    """Команда для перемещения человека в очереди с изменением нумерации"""
    chat_id = message.chat.id
    cursor = conn.cursor()

    # Проверка, является ли пользователь администратором
    cursor.execute(
        'SELECT admin, moderator FROM users WHERE user_id = ? AND chat_id = ?', 
            (message.from_user.id, chat_id)
        )
    roles = cursor.fetchone()

    if roles is None or (roles[0] == 0 and roles[1] == 0):
        conn.commit()
        cursor.close()
        return "У вас нет прав для выполнения этой команды. Только администраторы могут перемещать позиции."

    if not current_pos or not new_pos:
        return "Необходимо указать текущую позицию и новую позицию для перемещения."

    # Проверка, что позиции являются целыми числами
    try:
        current_pos = int(current_pos)
        new_pos = int(new_pos)
    except ValueError:
        return "Позиции должны быть целыми числами."

    if current_pos == new_pos:
        return "Позиция перемещения совпадает с текущей позицией."

    # Получаем текущий queue_id
    if thread_id:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))
    
    existing_queue = cursor.fetchone()

    if not existing_queue:
        cursor.close()
        return "Очереди нет."

    queue_id = existing_queue[0]

    # Проверяем, существует ли человек на указанной позиции
    cursor.execute('''SELECT user_id, position FROM enqueued 
                      WHERE queue_id = ? AND position = ?''', (queue_id, current_pos))
    user_to_move = cursor.fetchone()

    if not user_to_move:
        cursor.close()
        return f"На позиции {current_pos} нет пользователя."

    user_id_to_move, position = user_to_move

    # Сдвигаем позиции в очереди
    if current_pos < new_pos:
        # Сдвигаем вверх
        cursor.execute('''UPDATE enqueued
                          SET position = position - 1
                          WHERE queue_id = ? AND position > ? AND position <= ?''',
                       (queue_id, current_pos, new_pos))
    else:
        # Сдвигаем вниз
        cursor.execute('''UPDATE enqueued
                          SET position = position + 1
                          WHERE queue_id = ? AND position >= ? AND position < ?''',
                       (queue_id, new_pos, current_pos))

    # Устанавливаем новую позицию для перемещаемого пользователя
    cursor.execute('UPDATE enqueued SET position = ? WHERE queue_id = ? AND user_id = ?',
                   (new_pos, queue_id, user_id_to_move))
    conn.commit()

    cursor.close()
    return f"Пользователь на позиции {current_pos} был перемещён на позицию {new_pos}."


def toggle_moderator_status(message, conn, chat_id, user_tag):
    cursor = conn.cursor()
    # Проверяем наличие пользователя в базе
    cursor.execute('SELECT admin FROM users WHERE user_id = ? AND chat_id = ?', (message.from_user.id, chat_id))
    admin_check = cursor.fetchone()
    
    if not admin_check or not admin_check[0]:
        cursor.close()
        return "У вас нет прав для выполнения этой команды. Только администратор может назначать модераторов."
    
    cursor.execute('''
        SELECT user_id, moderator FROM users
        WHERE chat_id = ? AND user_tag = ?
    ''', (chat_id, user_tag))
    user_data = cursor.fetchone()

    if not user_data:
        return f"Пользователь @{user_tag} не найден в этом чате. Возможно пользователь не учавствовал в очередях, пусть @{user_tag} пропишет /registerme"

    user_id, current_status = user_data
    new_status = not current_status  # Переключаем статус

    # Обновляем статус в базе данных
    cursor.execute('''
        UPDATE users SET moderator = ? WHERE user_id = ? AND chat_id = ?
    ''', (new_status, user_id, chat_id))
    conn.commit()

    status_message = "Теперь модератор!" if new_status else "Больше не модератор!"
    return f"Пользователь {user_tag}: {status_message}"


def shutdown():
    """Закрывает соединение с базой данных."""
    conn.close()
