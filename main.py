import sqlite3
import telebot
from init_sql import create_tables
from views import *
from markups import *
from callbacks import register_callbacks
from dotenv import load_dotenv
import os
import re

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

    # Получение очереди.
    thread_id = message.message_thread_id if message.message_thread_id else None
    reply = get_queue(message, thread_id, user_id)

    cursor = conn.cursor()
    chat_id = message.chat.id

    # Получаем queue_id для чата и потока
    if thread_id:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id = ?', (chat_id, thread_id))
    else:
        cursor.execute('SELECT queue_id FROM queues WHERE chat_id = ? AND thread_id IS NULL', (chat_id,))

    queue_id = cursor.fetchone()

    if queue_id:
        queue_id = queue_id[0]  # извлекаем значение из кортежа
        cursor.execute('SELECT user_id FROM enqueued WHERE user_id = ? AND queue_id = ?', (user_id, queue_id))
        user_in_queue = cursor.fetchone() is not None  # Проверяем, есть ли пользователь в очереди
    else:
        user_in_queue = False  # Если queue_id не найдено
        queue_id = False

    cursor.close()

    bot.send_message(
        message.chat.id,
        reply,
        parse_mode="html",
        message_thread_id=thread_id if thread_id else None,
        reply_markup=queue_buttons(user_in_queue, queue_id)
    )


@bot.message_handler(commands=['swap'])
def swap_command(message):
    """Обработчик команды swap"""
    user_id = message.from_user.id
    thread_id = message.message_thread_id if message.message_thread_id else None
    args = message.text.split()

    if len(args) != 3:
        bot.send_message(
            message.chat.id,
            "Для использования команды swap необходимо указать две позиции. Пример: /swap 4 3",
            parse_mode="html",
            message_thread_id=thread_id if thread_id else None,
        )
        return

    pos1, pos2 = args[1], args[2]
    response = swap_positions(message, thread_id, user_id, pos1, pos2)

    # Обновляем очередь
    reply = get_queue(message, thread_id, user_id)

    bot.send_message(
        message.chat.id,
        response + "\n\n" + reply,
        parse_mode="html",
        message_thread_id=thread_id if thread_id else None,
    )


@bot.message_handler(commands=['pop'])
def pop_command(message):
    """Обработчик команды pop"""
    user_id = message.from_user.id
    thread_id = message.message_thread_id if message.message_thread_id else None
    args = message.text.split()

    if len(args) != 2:
        bot.send_message(
            message.chat.id,
            "Для использования команды pop необходимо указать № в очереди. Пример: /pop 1",
            parse_mode="html",
            message_thread_id=thread_id if thread_id else None,
        )
        return

    pos = args[1]
    response = pop_position(message, thread_id, user_id, pos)

    # Обновляем очередь
    reply = get_queue(message, thread_id, user_id)
    
    bot.send_message(
        message.chat.id,
        response + "\n\n" + reply,
        parse_mode="html",
        message_thread_id=thread_id if thread_id else None,
    )


@bot.message_handler(commands=["feedback"])
def handle_feedback(message):
    user_id = message.from_user.id
    thread_id = message.message_thread_id if message.message_thread_id else None
    user_name = message.from_user.username
    chat_id = message.chat.id
    args = message.text

    # Используем регулярное выражение, чтобы извлечь отзыв
    match = re.match(r"^/feedback(@\w+)?\s+(.*)$", args)
    if not match:
        bot.reply_to(message, 
                     "Пожалуйста, напишите ваш отзыв после команды.",
                     message_thread_id=thread_id if thread_id else None,
                     )
        return

    message_text = match.group(2)
    target_user_id = 811311997  # ID пользователя, которому будет отправлен отзыв
    feedback_message = f"Отзыв от {user_name} ({user_id}) из чата {chat_id}: \n\n{message_text}"

    try:
        # Отправляем сообщение в личку указанному пользователю
        bot.send_message(target_user_id, feedback_message)
        bot.reply_to(message, 
                     "Спасибо за ваш отзыв! Сообщение отправлено.",
                     message_thread_id=thread_id if thread_id else None,
                     )
    except Exception as e:
        # Если возникла ошибка, сообщаем об этом пользователю
        bot.reply_to(message, 
                     f"Произошла ошибка при отправке сообщения: {str(e)}",
                     message_thread_id=thread_id if thread_id else None,
                     )




register_callbacks(bot, conn, handle_queue, add_user)

try:
    print("Bot is running...")
    bot.polling()
finally:
    shutdown()
