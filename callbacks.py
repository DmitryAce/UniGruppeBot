from views import *


def register_callbacks(bot, conn, handle_queue, add_user):
    """Регистрация всех callback-обработчиков."""
    
    @bot.callback_query_handler(func=lambda call: call.data == "join_queue")
    def handle_join_queue(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        thread_id = call.message.message_thread_id if call.message.message_thread_id else None

        cursor = conn.cursor()

        if thread_id:
            cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
        else:
            cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))
        
        queue_result = cursor.fetchone()

        if queue_result is None:
            bot.answer_callback_query(call.id, "Очередь не существует.")
            cursor.close()
            return

        queue_id = queue_result[0]

        cursor.execute("SELECT user_id FROM users WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
        user_exists = cursor.fetchone()

        if not user_exists:
            user = call.from_user
            add_user(user.id, chat_id, user.username, False)

        cursor.execute("SELECT user_id FROM enqueued WHERE user_id = ? AND queue_id = ?", (user_id, queue_id))
        in_queue = cursor.fetchone()

        if in_queue:
            bot.answer_callback_query(call.id, "Вы уже в очереди.")
            cursor.close()
            return
        else:
            # Получаем список всех занятых позиций в очереди
            cursor.execute('SELECT position FROM enqueued WHERE queue_id = ? ORDER BY position', (queue_id,))
            occupied_positions = [row[0] for row in cursor.fetchall()]  # Извлекаем список позиций

            # Определяем минимальную свободную позицию
            next_position = 1
            while next_position in occupied_positions:
                next_position += 1

            # Добавляем пользователя на найденную позицию
            cursor.execute('INSERT INTO enqueued (queue_id, user_id, position, priority) VALUES (?, ?, ?, 0)', 
                        (queue_id, user_id, next_position))
            conn.commit()
            bot.answer_callback_query(call.id, f"Вы записались в очередь на позицию {next_position}.")


        
        cursor.close()
        handle_queue(call.message, call.from_user.id)

    @bot.callback_query_handler(func=lambda call: call.data == "leave_queue")
    def handle_leave_queue(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        thread_id = call.message.message_thread_id if call.message.message_thread_id else None

        cursor = conn.cursor()

        if thread_id:
            cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
        else:
            cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))

        queue_result = cursor.fetchone()

        if queue_result is None:
            bot.answer_callback_query(call.id, "Очередь не существует.")
            cursor.close()
            return

        queue_id = queue_result[0]

        # Проверяем, есть ли текущий пользователь в очереди
        cursor.execute('SELECT position FROM enqueued WHERE queue_id = ? AND user_id = ? LIMIT 1', (queue_id, user_id))
        user_position = cursor.fetchone()

        if not user_position:
            conn.commit()
            cursor.close()
            bot.answer_callback_query(call.id, "Вас нет в очереди!")
            return

        current_position = user_position[0]  # Текущая позиция пользователя

        # Удаление пользователя из очереди
        cursor.execute('DELETE FROM enqueued WHERE queue_id = ? AND user_id = ?', (queue_id, user_id))

        # Сдвиг позиций всех пользователей ниже
        cursor.execute('''
            UPDATE enqueued
            SET position = position - 1
            WHERE queue_id = ? AND position > ?
        ''', (queue_id, current_position))

        conn.commit()
        bot.answer_callback_query(call.id, "Вы покинули очередь.")
        
        cursor.close()
        handle_queue(call.message, call.from_user.id)


    @bot.callback_query_handler(func=lambda call: call.data == "down_one")
    def handle_move_down(call):
        user_id = call.from_user.id
        chat_id = call.message.chat.id
        thread_id = call.message.message_thread_id if call.message.message_thread_id else None

        cursor = conn.cursor()

        # Получаем ID очереди
        if thread_id:
            cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
        else:
            cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))

        queue_result = cursor.fetchone()

        if queue_result is None:
            bot.answer_callback_query(call.id, "Очередь не существует.")
            cursor.close()
            return

        queue_id = queue_result[0]

        # Проверяем текущую позицию пользователя в очереди
        cursor.execute('''SELECT position FROM enqueued WHERE queue_id = ? AND user_id = ? LIMIT 1''', (queue_id, user_id))
        user_position = cursor.fetchone()

        if not user_position:
            conn.commit()
            cursor.close()
            bot.answer_callback_query(call.id, "Вас нет в очереди!")
            return

        current_position = user_position[0]  # Получаем значение позиции

        # Найти следующего пользователя ниже текущей позиции
        cursor.execute('''SELECT user_id, position FROM enqueued WHERE queue_id = ? AND position == ? ORDER BY position ASC LIMIT 1''', (queue_id, current_position+1))
        next_user = cursor.fetchone()

        if not next_user:
            new_position = current_position + 1  # Увеличиваем позицию на 1
            cursor.execute('''UPDATE enqueued SET position = ? WHERE queue_id = ? AND user_id = ?''', (new_position, queue_id, user_id))
            bot.answer_callback_query(call.id, f"Вы переместились на позицию {new_position}.")
            conn.commit()
            cursor.close()
            handle_queue(call.message, call.from_user.id)
            return

        next_user_id, next_user_position = next_user

        # Обмен позициями
        cursor.execute('''UPDATE enqueued SET position = ? WHERE queue_id = ? AND user_id = ?''', (next_user_position, queue_id, user_id))
        cursor.execute('''UPDATE enqueued SET position = ? WHERE queue_id = ? AND user_id = ?''', (current_position, queue_id, next_user_id))

        conn.commit()
        bot.answer_callback_query(call.id, f"Вы переместились на позицию {next_user_position}.")

        cursor.close()
        handle_queue(call.message, call.from_user.id)






