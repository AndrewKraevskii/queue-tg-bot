import asyncio
from typing import Dict
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton
import logging
import user_queue
import pickle

BOT_CREATOR = 751586125
with open("queues.txt", "rb") as f:
    queues = pickle.load(f)
queues: Dict[str, user_queue.Queue]
CAN_CREATE_QUEUES = [751586125, 731492287, 406495448]

file = open('token.txt', 'r')
API_TOKEN = file.read()
file.close()

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)


@dp.message_handler(commands=["createq", "createqueue", "startq", "startqueue"])
async def create_queue(message: types.Message):
    if message.from_user.id not in CAN_CREATE_QUEUES:
        await message.answer("Ты не можешь создать очередь")
        return
    try:
        size = int(message.text.split()[1])
        _, qname = message.text.split(maxsplit=2)[1:]
    except ValueError:
        qname = message.text.split(maxsplit=1)[1]
        size = 25

    if qname in queues.keys():
        await message.answer("Эта очередь уже существует")
        return
    if '/' in qname:
        await message.answer("Не добавляй / в название очереди")
        return

    buttons = [InlineKeyboardButton(str(num) + "🟢", callback_data=f"key/{num - 1}/{qname}") for num in range(1, size + 1)]
    reset_button = InlineKeyboardButton("RESET", callback_data=f"reset/{qname}")
    stop_button = InlineKeyboardButton("STOP", callback_data=f"stop/{qname}")
    queues[qname] = user_queue.Queue(message.from_user.id, [buttons, reset_button, stop_button], size=size)
    await message.answer(f"{qname}:\n{queues[qname].get_print()}", reply_markup=queues[qname].get_keyboard())


@dp.message_handler(commands=["delaystartq"])
async def delay_create_queue(message: types.Message):
    time = 10
    if message.text.split()[1].startswith('t='):
        time = int(message.text.split()[1][2:])
        if time % 10 != 0:
            time -= time % 10 - 10
        message.text = message.text.replace(message.text.split()[1] + " ", "")

    start_time = time

    callback_query = await message.answer(f"Очередь запустится через {time} сек")
    while time != 0:
        time -= 10
        await asyncio.sleep(10)
        await bot.edit_message_text(message_id=callback_query.message_id, chat_id=callback_query.chat.id, text=f"Очередь запустится через {time} (start={start_time}) сек")
    await create_queue(message)
    await bot.edit_message_text(message_id=callback_query.message_id, chat_id=callback_query.chat.id, text=f"Очередь запущена!")

@dp.message_handler(commands=["listq"])
async def queue_list(message: types.Message):
    if message.from_user.id != BOT_CREATOR:
        return

    await message.answer(text="Очереди:\n" + '\n'.join(queues.keys()))


@dp.message_handler(commands=["delete"])
async def delete_all(message: types.Message):
    if message.from_user.id != BOT_CREATOR:
        return

    for i in list(queues.keys()):
        del queues[i]
    await message.answer(text="Done")


@dp.message_handler(commands=["shutdown", "exit"])
async def shutdown(message: types.Message):
    if message.from_user.id != BOT_CREATOR:
        return

    dp.stop_polling()
    pickle.dump(queues, open("queues.txt", "wb"))
    exit()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('key'))
async def insert_in_queue(callback_query: types.CallbackQuery):
    _, code, qname = callback_query.data.split("/")
    code = int(code)
    name = f"{callback_query.from_user.full_name} (@{callback_query.from_user.username})"
    text, code = queues[qname].set(code, name)
    await bot.answer_callback_query(callback_query.id, text=text)
    if code:
        await bot.edit_message_text(message_id=callback_query.message.message_id, chat_id=callback_query.message.chat.id, text=f"{qname}:\n{queues[qname].get_print()}", reply_markup=queues[qname].get_keyboard())


@dp.callback_query_handler(lambda c: c.data and c.data.startswith("stop"))
async def delete_queue(callback_query: types.CallbackQuery):
    _, qname = callback_query.data.split("/")
    if qname not in queues.keys():
        await bot.edit_message_text(message_id=callback_query.message.message_id,
                                    chat_id=callback_query.message.chat.id,
                                    text=f"{qname} (stopped)")
        return

    if callback_query.from_user.id != queues[qname].creator and callback_query.from_user.id != BOT_CREATOR:
        await bot.answer_callback_query(callback_query.id, text="Это может сделать только создатель очереди")
        return

    await bot.edit_message_text(message_id=callback_query.message.message_id, chat_id=callback_query.message.chat.id, text=f"{qname} (stopped):\n{queues[qname].get_print()}")
    del queues[qname]


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('reset'))
async def insert_in_queue(callback_query: types.CallbackQuery):
    _, qname = callback_query.data.split("/")
    if callback_query.from_user.id != queues[qname].creator and callback_query.from_user.id != BOT_CREATOR:
        await bot.answer_callback_query(callback_query.id, text="Это может сделать только создатель очереди")
        return

    is_modified = queues[qname].reset()
    if is_modified:
        await bot.edit_message_text(message_id=callback_query.message.message_id, chat_id=callback_query.message.chat.id, text=f"{qname}:\n{queues[qname].get_print()}", reply_markup=queues[qname].get_keyboard())
    else:
        await bot.answer_callback_query(callback_query.id, text="Очередь и была пуста")


executor.start_polling(dp, skip_updates=True)
