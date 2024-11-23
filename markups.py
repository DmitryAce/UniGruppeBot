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


def queue_buttons(queue=True):
    """Создает кнопки для управления очередью в зависимости от состояния пользователя."""
    markup = types.InlineKeyboardMarkup()
    if not queue:
        return None

    btn1 = types.InlineKeyboardButton("📝 Записаться", callback_data="join_queue")
    btn2 = types.InlineKeyboardButton("🚪 Покинуть очередь", callback_data="leave_queue")
    btn3 = types.InlineKeyboardButton("⬇️ Спуститься на 1 ниже", callback_data="down_one")
    btn4 = types.InlineKeyboardButton("✅ Прошел", callback_data="passed_queue")
    btn5 = types.InlineKeyboardButton("🐺 Заслать долю ⚜️", callback_data="send_donation")


    markup.row(btn1)
    markup.row(btn2, btn3)
    markup.row(btn4)
    markup.row(btn5)

    return markup
