import sqlite3
import telebot
from init_sql import create_tables
from views import *
from markups import *
from callbacks import register_callbacks
from dotenv import load_dotenv
import os, re, time, requests, sys
from datetime import datetime
import threading


# Инициализация базы данных
conn = sqlite3.connect('chat_users.db', check_same_thread=False)
create_tables(conn)

# Инициализация бота
load_dotenv()

bot_token = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(bot_token)






@bot.message_handler(content_types=["new_chat_members"])
def handle_new_chat_member(message):
    """Обрабатывает событие добавления бота в новый чат."""
    for new_member in message.new_chat_members:
        if new_member.id == bot.get_me().id:  # Проверяем, что это бот
            add_chat(message)  # Добавляем чат в базу данных
            user_who_added_bot = message.from_user  # Пользователь, добавивший бота

            # Проверяем права бота
            bot_member = bot.get_chat_member(message.chat.id, bot.get_me().id)
            if bot_member.status != "administrator":
                try:
                    bot.reply_to(
                        message,
                        "Привет! Чтобы я мог корректно работать в этом чате, пожалуйста, дайте мне права администратора. 🙏",
                    )
                except telebot.apihelper.ApiTelegramException as e:
                    print(f"Ошибка отправки сообщения в чат {message.chat.id}: {e}")

            # Если бот уже администратор, продолжаем
            reply, group_name = add_user(
                user_who_added_bot.id,
                message.chat.id,
                user_who_added_bot.username,
                True,  # Указываем, что это администратор
            )

            try:
                bot.reply_to(
                    message,
                    reply + f" Спасибо за добавление меня в беседу, {user_who_added_bot.username}!",
                )
            except telebot.apihelper.ApiTelegramException as e:
                print(f"Ошибка отправки сообщения в чат {message.chat.id}: {e}")
            break


@bot.message_handler(commands=["getinfo"])
def handle_get_info(message):
    """Выводит информацию о чате и топике."""
    thread_id = message.message_thread_id if message.message_thread_id else None
    reply = f"CHAT:\n{message.chat}\nTHREAD:{message.message_thread_id}\n"
    reply2 = f"{message.chat}"

    if thread_id:
        bot.send_message(
            message.chat.id,
            reply,
            message_thread_id=thread_id,
        )
    else:
        bot.send_message(message.chat.id, reply2)


@bot.message_handler(commands=["myid"])
def handle_my_id(message):
    """Выводит ID пользователя."""
    thread_id = message.message_thread_id if message.message_thread_id else None
    reply = f"Твой ID, работяга ({message.from_user.username}): {message.from_user.id}"

    if thread_id:
        bot.send_message(
            message.chat.id,
            reply,
            message_thread_id=thread_id,
        )
    else:
        bot.send_message(message.chat.id, reply)


@bot.message_handler(commands=["initqueue"])
def handle_init_queue(message):
    """Инициализирует очередь."""
    thread_id = message.message_thread_id if message.message_thread_id else None
    response = init_queue(message, thread_id)

    if thread_id:
        bot.send_message(
            message.chat.id,
            response,
            message_thread_id=thread_id,
        )
    else:
        bot.send_message(message.chat.id, response)


@bot.message_handler(commands=["killqueue"])
def handle_kill_queue(message):
    """Удаляет очередь и всех пользователей из нее."""
    thread_id = message.message_thread_id if message.message_thread_id else None
    response = kill_queue(message, thread_id)

    if thread_id:
        bot.send_message(
            message.chat.id,
            response,
            message_thread_id=thread_id,
        )
    else:
        bot.send_message(message.chat.id, response)


@bot.message_handler(commands=["registerme"])
def register(message):
    """Регистрация пользователя."""
    thread_id = message.message_thread_id if message.message_thread_id else None
    user = message.from_user
    reply, group_name = add_user(
        user.id,
        message.chat.id,
        user.username,
        False,
    )
    if thread_id:
        bot.send_message(
            message.chat.id,
            reply,
            message_thread_id=thread_id,
        )
    else:
        bot.send_message(message.chat.id, reply)


@bot.message_handler(commands=["queue"])
def handle_queue(message, user_id=None):
    if user_id is None:
        user_id = message.from_user.id

    thread_id = message.message_thread_id if message.message_thread_id else None

    cursor = conn.cursor()
    chat_id = message.chat.id

    # Получаем данные об очереди
    if thread_id:
        cursor.execute('SELECT queue_id, bot_message_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id, bot_message_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))

    queue_data = cursor.fetchone()

    # Если очередь не существует
    if not queue_data:
        try:
            bot.delete_message(chat_id, message.message_id)
        except Exception:
            pass  # Игнорируем ошибку удаления

        bot.send_message(
            chat_id=chat_id,
            text="Очередь не инициализирована. Используйте команду /initqueue для создания очереди.",
            parse_mode="html",
            message_thread_id=thread_id if thread_id else None
        )
        cursor.close()
        return

    # Извлекаем данные об очереди
    queue_id, bot_message_id = queue_data
    cursor.execute('SELECT user_id FROM enqueued WHERE user_id = ? AND queue_id = ?', (user_id, queue_id))
    user_in_queue = cursor.fetchone() is not None

    reply = get_queue(message, thread_id, user_id)

    # Удаление сообщения пользователя
    try:
        bot.delete_message(chat_id, message.message_id)
    except Exception:
        pass  # Игнорируем ошибку удаления

    # Если сообщение бота уже существует, обновляем его
    if bot_message_id:
        try:
            bot.edit_message_text(
                chat_id=chat_id,
                message_id=bot_message_id,
                text=reply,
                parse_mode="html",
                reply_markup=queue_buttons(queue_id)
            )
        except Exception as e:
            print(f"Ошибка при обновлении сообщения бота: {e}")
    else:
        # Отправка нового сообщения, если его не было
        sent_message = bot.send_message(
            chat_id=chat_id,
            text=reply,
            parse_mode="html",
            reply_markup=queue_buttons(queue_id),
            message_thread_id=thread_id if thread_id else None
        )
        new_bot_message_id = sent_message.message_id

        # Обновление bot_message_id в базе данных
        cursor.execute(
            'UPDATE queues SET bot_message_id = ? WHERE queue_id = ?',
            (new_bot_message_id, queue_id)
        )
        conn.commit()

    cursor.close()


@bot.message_handler(commands=['pop'])
def pop_command(message):
    """Обработчик команды pop"""
    user_id = message.from_user.id
    thread_id = message.message_thread_id if message.message_thread_id else None
    args = message.text.split()

    # Проверяем корректность команды
    if len(args) != 2:
        try:
            bot.delete_message(message.chat.id, message.message_id)  # Удаляем сообщение пользователя
        except Exception as e:
            print(f"Ошибка при удалении сообщения пользователя: {e}")

        bot.send_message(
            message.chat.id,
            "Для использования команды pop необходимо указать № в очереди. Пример: /pop 1",
            parse_mode="html",
            thread_id=thread_id if thread_id else None,
        )
        return

    pos = args[1]
    response = pop_position(message, thread_id, user_id, pos)

    # Получаем данные об очереди
    cursor = conn.cursor()
    cursor.execute(
        'SELECT queue_id, bot_message_id FROM queues WHERE chat_id = ? AND thread_id = ?',
        (message.chat.id, thread_id),
    )
    queue_data = cursor.fetchone()

    if queue_data:
        queue_id, bot_message_id = queue_data
        reply = get_queue(message, thread_id, user_id)

        if bot_message_id:
            try:
                # Пытаемся обновить текст сообщения очереди
                bot.edit_message_text(
                    response + "\n\n" + reply,
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    reply_markup=queue_buttons(queue_id),
                    parse_mode="html",
                )
            except Exception as e:
                print(f"Ошибка при обновлении сообщения очереди: {e}")

                # Если сообщение не найдено или ошибка, отправляем новое сообщение
                sent_message = bot.send_message(
                    message.chat.id,
                    response + "\n\n" + reply,
                    parse_mode="html",
                    reply_markup=queue_buttons(queue_id),
                    thread_id=thread_id if thread_id else None,
                )
                new_bot_message_id = sent_message.message_id

                # Обновляем bot_message_id в базе данных
                cursor.execute(
                    'UPDATE queues SET bot_message_id = ? WHERE queue_id = ?',
                    (new_bot_message_id, queue_id),
                )
                conn.commit()
        else:
            # Если bot_message_id отсутствует, отправляем новое сообщение
            sent_message = bot.send_message(
                message.chat.id,
                response + "\n\n" + reply,
                parse_mode="html",
                reply_markup=queue_buttons(queue_id),
                thread_id=thread_id if thread_id else None,
            )
            new_bot_message_id = sent_message.message_id

            # Обновляем bot_message_id в базе данных
            cursor.execute(
                'UPDATE queues SET bot_message_id = ? WHERE queue_id = ?',
                (new_bot_message_id, queue_id),
            )
            conn.commit()
    else:
        # Если данные об очереди не найдены
        bot.send_message(
            message.chat.id,
            "Ошибка: очередь не найдена.",
            parse_mode="html",
            thread_id=thread_id if thread_id else None,
        )

    # Удаляем сообщение пользователя
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        print(f"Ошибка при удалении сообщения пользователя: {e}")

    cursor.close()


@bot.message_handler(commands=['swap'])
def swap_command(message):
    """Обработчик команды swap"""
    user_id = message.from_user.id
    thread_id = message.message_thread_id if message.message_thread_id else None
    args = message.text.split()

    # Проверяем, что указаны две позиции
    if len(args) != 3:
        try:
            bot.delete_message(message.chat.id, message.message_id)  # Удаляем сообщение пользователя
        except Exception as e:
            print(f"Ошибка при удалении сообщения пользователя: {e}")

        bot.send_message(
            message.chat.id,
            "Для использования команды swap необходимо указать две позиции. Пример: /swap 4 3",
            parse_mode="html",
            message_thread_id=thread_id if thread_id else None,
        )
        return

    pos1, pos2 = args[1], args[2]
    response = swap_positions(message, thread_id, user_id, pos1, pos2)

    # Получаем данные об очереди
    cursor = conn.cursor()
    cursor.execute(
        'SELECT queue_id, bot_message_id FROM queues WHERE chat_id = ? AND thread_id = ?',
        (message.chat.id, thread_id),
    )
    queue_data = cursor.fetchone()

    if queue_data:
        queue_id, bot_message_id = queue_data
        # Обновляем текст очереди
        reply = get_queue(message, thread_id, user_id)

        if bot_message_id:
            try:
                # Пытаемся изменить старое сообщение
                bot.edit_message_text(
                    response + "\n\n" + reply,
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    reply_markup=queue_buttons(queue_id),
                    parse_mode="html",
                )
            except Exception as e:
                print(f"Ошибка при обновлении сообщения очереди: {e}")

                # Если сообщение не найдено или ошибка, отправляем новое
                sent_message = bot.send_message(
                    message.chat.id,
                    response + "\n\n" + reply,
                    parse_mode="html",
                    reply_markup=queue_buttons(queue_id),
                    thread_id=thread_id if thread_id else None,
                )
                new_bot_message_id = sent_message.message_id

                # Обновляем bot_message_id в базе данных
                cursor.execute(
                    'UPDATE queues SET bot_message_id = ? WHERE queue_id = ?',
                    (new_bot_message_id, queue_id),
                )
                conn.commit()
        else:
            # Если bot_message_id отсутствует, отправляем новое сообщение
            sent_message = bot.send_message(
                message.chat.id,
                response + "\n\n" + reply,
                parse_mode="html",
                reply_markup=queue_buttons(queue_id),
                thread_id=thread_id if thread_id else None,
            )
            new_bot_message_id = sent_message.message_id

            # Обновляем bot_message_id в базе данных
            cursor.execute(
                'UPDATE queues SET bot_message_id = ? WHERE queue_id = ?',
                (new_bot_message_id, queue_id),
            )
            conn.commit()
    else:
        # Если данные об очереди не найдены
        bot.send_message(
            message.chat.id,
            "Ошибка: очередь не найдена.",
            parse_mode="html",
            thread_id=thread_id if thread_id else None,
        )

    # Удаляем сообщение пользователя
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        print(f"Ошибка при удалении сообщения пользователя: {e}")

    cursor.close()



@bot.message_handler(commands=['insert'])
def insert_command(message):
    """Обработчик команды insert"""
    user_id = message.from_user.id
    thread_id = message.message_thread_id if message.message_thread_id else None
    args = message.text.split()

    # Проверяем корректность аргументов команды
    if len(args) != 3:
        try:
            bot.delete_message(message.chat.id, message.message_id)  # Удаляем сообщение пользователя
        except Exception as e:
            print(f"Ошибка при удалении сообщения пользователя: {e}")

        bot.send_message(
            message.chat.id,
            "Для использования команды insert необходимо указать текущую позицию человека и новую позицию. Пример: /insert 3 1",
            parse_mode="html",
            thread_id=thread_id if thread_id else None,
        )
        return

    current_pos, new_pos = args[1], args[2]
    response = insert_position(message, thread_id, user_id, current_pos, new_pos)

    # Получаем данные об очереди
    cursor = conn.cursor()
    cursor.execute(
        'SELECT queue_id, bot_message_id FROM queues WHERE chat_id = ? AND thread_id = ?',
        (message.chat.id, thread_id),
    )
    queue_data = cursor.fetchone()

    if queue_data:
        queue_id, bot_message_id = queue_data
        reply = get_queue(message, thread_id, user_id)

        if bot_message_id:
            try:
                # Пытаемся изменить текст сообщения очереди
                bot.edit_message_text(
                    response + "\n\n" + reply,
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    reply_markup=queue_buttons(queue_id),
                    parse_mode="html",
                )
            except Exception as e:
                print(f"Ошибка при обновлении сообщения очереди: {e}")

                # Если сообщение не найдено или ошибка, отправляем новое сообщение
                sent_message = bot.send_message(
                    message.chat.id,
                    response + "\n\n" + reply,
                    parse_mode="html",
                    reply_markup=queue_buttons(queue_id),
                    thread_id=thread_id if thread_id else None,
                )
                new_bot_message_id = sent_message.message_id

                # Обновляем bot_message_id в базе данных
                cursor.execute(
                    'UPDATE queues SET bot_message_id = ? WHERE queue_id = ?',
                    (new_bot_message_id, queue_id),
                )
                conn.commit()
        else:
            # Если bot_message_id отсутствует, отправляем новое сообщение
            sent_message = bot.send_message(
                message.chat.id,
                response + "\n\n" + reply,
                parse_mode="html",
                reply_markup=queue_buttons(queue_id),
                thread_id=thread_id if thread_id else None,
            )
            new_bot_message_id = sent_message.message_id

            # Обновляем bot_message_id в базе данных
            cursor.execute(
                'UPDATE queues SET bot_message_id = ? WHERE queue_id = ?',
                (new_bot_message_id, queue_id),
            )
            conn.commit()
    else:
        # Если данные об очереди не найдены
        bot.send_message(
            message.chat.id,
            "Ошибка: очередь не найдена.",
            parse_mode="html",
            thread_id=thread_id if thread_id else None,
        )

    # Удаляем сообщение пользователя
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        print(f"Ошибка при удалении сообщения пользователя: {e}")

    cursor.close()



@bot.message_handler(commands=["feedback"])
def handle_feedback(message):
    user_id = message.from_user.id
    thread_id = message.message_thread_id if message.message_thread_id else None
    user_name = message.from_user.username
    chat_id = message.chat.id
    args = message.text

    # Регулярное выражение для захвата текста после команды, включая многострочные сообщения
    match = re.match(r"^/feedback(@\w+)?\s+([\s\S]+)$", args, re.DOTALL)

    if not match:
        bot.reply_to(
            message,
            "Пожалуйста, напишите ваш отзыв после команды.\nПример: /feedback Текст текст текст",
            message_thread_id=thread_id if thread_id else None,
        )
        return

    message_text = match.group(2).strip()  # Убираем лишние пробелы или переносы строк
    target_user_id = 811311997  # ID пользователя, которому будет отправлен отзыв
    feedback_message = f"Отзыв от {user_name} ({user_id}) из чата {chat_id}:\n\n{message_text}"

    try:
        # Отправляем сообщение в личку указанному пользователю
        bot.send_message(target_user_id, feedback_message)
        bot.reply_to(
            message,
            "Спасибо за ваш отзыв! Сообщение отправлено.",
            message_thread_id=thread_id if thread_id else None,
        )
    except Exception as e:
        # Если возникла ошибка, сообщаем об этом пользователю
        bot.reply_to(
            message,
            f"Произошла ошибка при отправке сообщения: {str(e)}",
            message_thread_id=thread_id if thread_id else None,
        )





register_callbacks(bot, conn, handle_queue, add_user)


running = True

def polling_loop():
    """Запускает бот в режиме polling."""
    global running
    while running:
        try:
            bot.polling(none_stop=True, timeout=10)
        except requests.exceptions.ReadTimeout as e:
            print(f"[{datetime.now()}] ReadTimeout: {e}. Restarting bot...")
            time.sleep(5)
        except Exception as e:
            print(f"[{datetime.now()}] Unexpected error: {e}. Restarting bot...")
            time.sleep(5)

def shutdown():
    """Корректное завершение работы."""
    global running
    print("Shutting down bot...")
    running = False
    bot.stop_polling()  # Останавливает polling
    print("Bot stopped.")

# Основной блок программы
try:
    print("Starting the bot...")
    polling_thread = threading.Thread(target=polling_loop)
    polling_thread.start()  # Запуск polling в отдельном потоке

    while True:
        time.sleep(1)  # Основной поток ожидает

except KeyboardInterrupt:
    print("\nBot stopped by user.")
    shutdown()  # Завершение работы

finally:
    if polling_thread.is_alive():
        polling_thread.join()  # Дожидаемся завершения потока
    print("Exiting program...")
    sys.exit(0)  # Завершаем программу