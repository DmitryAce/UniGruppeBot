import telebot
from telebot import types


def main_markup():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('Перейти на сайт')
    btn2 = types.KeyboardButton('Новость NASA')
    btn3 = types.KeyboardButton('Мой ID')
    markup.row(btn1)
    markup.row(btn2, btn3)

    return markup


def queue_buttons(user_in_queue, queue=True):
    """Создает кнопки для управления очередью в зависимости от состояния пользователя."""
    markup = types.InlineKeyboardMarkup()
    if not queue:
        return None
    if user_in_queue:
        btn_leave = types.InlineKeyboardButton("Покинуть очередь", callback_data="leave_queue")
        btn_down_one = types.InlineKeyboardButton("Спуститься на 1 ниже", callback_data="down_one")
        markup.add(btn_leave, btn_down_one)
    else:
        btn_join = types.InlineKeyboardButton("Записаться", callback_data="join_queue")
        markup.add(btn_join)

    return markup