import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import *
from aiogram.utils import executor
from fuzzywuzzy import fuzz, process
from bs4 import BeautifulSoup
from datetime import date, time, datetime, timedelta
import sqlite3

async def parse_website ():
    async def parse_webpage ():
        group_soup = BeautifulSoup (await response.text (), 'lxml')
        group_items = group_soup.find_all ('tr')
        
        for group_item in group_items:
            try: p_num = group_item.find ('td', class_='b1 ac vam').text
            except: pass
            
            timetable_cells = group_item.find_all ('td', class_='al b1 p2 vam al')
            empty_class_cell = group_item.find ('td', class_='b1 ac vac')
            replacement_type_cell = group_item.find ('td', class_='b1 p2 vam ac b cred')
            replacement_cells_a = group_item.find_all ('td', class_='b1 p2 vam ac')
            replacement_cells_b = group_item.find_all ('td', class_='b1 p2 vam al')
            aud_cell = group_item.find ('td', class_='al b1 p2 vam ac')
            
            if timetable_cells != []:
                current_row = [group.text, current_day, p_num]
                for current_cell in timetable_cells:
                    current_row.append (current_cell.get_text (' / '))
                current_row.append (aud_cell.get_text (' / '))
                db.execute ('insert into timetable values (?, ?, ?, ?, ?, ?, ?)', current_row)
            else:
                try: current_day = group_item.find ('td', 'b ac cell_medium b1 p2').text
                except: pass
            
            if empty_class_cell is not None:
                current_row = [group.text, current_day, p_num, '', empty_class_cell.text, '', '']
                db.execute ('insert into timetable values (?, ?, ?, ?, ?, ?, ?)', current_row)
            
            if replacement_cells_a != []:
                current_row = [group.text, replacement_date, replacement_type_cell.text, replacement_cells_a [0].text]
                if replacement_cells_b != []:
                    current_row.extend ([replacement_cells_b [0].get_text (' / '), replacement_cells_b [1].text, replacement_cells_a [1].text])
                else:
                    current_row.extend ([replacement_cells_a [1].text, '', ''])
                db.execute ('insert into replacements values (?, ?, ?, ?, ?, ?, ?)', current_row)
            else:
                try: replacement_date = group_item.find ('td', class_='b ac cell_medium b1 p2').text
                except: pass
    
    async with aiohttp.ClientSession() as session:
        db = sqlite3.connect (':memory:')
        db.execute ('create table timetable (grp, day, num, resc, disc, tcr, aud)')
        db.execute ('create table replacements (grp, date, type, num, disc, tcr, aud)')
        url = 'http://www.ks54.ru/расписание-онлайн/'
        async with session.get (url) as response:
            soup = BeautifulSoup (await response.text (), 'lxml')
            groups = soup.find_all ('a', class_='typesel mr10')
            group = soup.find ('a', class_='typesel mr10 typeselect')
            await parse_webpage ()
        
        for grp_num, group in enumerate (groups):
            async with session.get (f'{url}?group={group.text}') as response:
                print (f'Downloaded: {grp_num + 1}/{len (groups)} Now loading: {group.text}    ', end='\r')
                await parse_webpage ()
    return db

weekdays = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

async def update_db ():
    global db
    try: db = await parse_website ()
    except: await update_db ()

# Starting bot

bot = Bot (token='5476652158:AAFQ1nNItzFPTMAry2UPjUmSyTQ1jWUue8M')
storage = MemoryStorage ()
dp = Dispatcher (bot, storage=storage)

class Form (StatesGroup):
    start = State ()
    role = State () 
    days = State () 
    name = State () 

@dp.message_handler(state="*", commands="cancel")
async def cancel_handler(message: Message, state: FSMContext):
    await state.finish()
    await message.reply("Отменено.")

@dp.message_handler (commands=['start'])
async def cmd_start (message: Message):
    markup = InlineKeyboardMarkup ().add (InlineKeyboardButton ("Узнать расписание", callback_data='start'))
    await message.answer ("Бот узнающий расписание", reply_markup=markup)
    await Form.start.set ()

@dp.callback_query_handler (Text (equals=['start']), state=Form.start)
async def process_start (call: CallbackQuery):
    markup = InlineKeyboardMarkup ().add (InlineKeyboardButton ("Преподаватель", callback_data='prepod'), InlineKeyboardButton ("Студент", callback_data='student'))
    await call.message.edit_text ("Пользователь", reply_markup=markup)
    await Form.role.set ()

@dp.callback_query_handler (Text (equals=['prepod', 'student']), state=Form.role)
async def process_role (call: CallbackQuery, state: FSMContext):
    async with state.proxy () as data:
        data ['role'] = call.data
    
    markup = InlineKeyboardMarkup ().add (InlineKeyboardButton ("На сегодня", callback_data='today'), InlineKeyboardButton ("На завтра", callback_data='tomorrow'), InlineKeyboardButton ("На неделю", callback_data='week'))
    await call.message.edit_text ("Интервал", reply_markup=markup)
    await Form.days.set ()

@dp.callback_query_handler (Text (equals=['today', 'tomorrow', 'week']), state=Form.days)
async def process_days (call: CallbackQuery, state: FSMContext):
    async with state.proxy () as data:
        data ['days'] = call.data
        role = data ['role']
    
    if role == 'prepod':
        await call.message.edit_text ("Фамилия И.О.")
    elif role == 'student':
        await call.message.edit_text ("Группа")
    
    await Form.name.set ()

@dp.message_handler (state=Form.name)
async def process_name (message: Message, state: FSMContext):
    def print_if_available (str_, sym):
        if str_ != '':
            return sym + str_
        return ''
    
    async with state.proxy () as data:
        role = data ['role']
        days = data ['days']
    
    if role == 'prepod':
        db_query = 'tcr'
        x = 0
    elif role == 'student':
        x = 5
        db_query = 'grp'
    
    if days == 'today':
        query_weekdays = [weekdays [date.today().weekday()]]
        dates = [date.today ()]
    elif days == 'tomorrow':
        query_weekdays = [weekdays [date.today().weekday() + 1]]
        dates = [date.today () + timedelta(days=1)]
    elif days == 'week':
        theday = date.today ()
        weekday = theday.isoweekday ()
        start = theday - timedelta(days=weekday)
        dates = [start + timedelta(days=d+1) for d in range(7)]
        query_weekdays = weekdays
    
    try:
        query_dates = [d.strftime ('%d.%m.%Y') for d in dates]
        all_names = [num [0] for num in set (list (db.execute (f'select {db_query} from timetable')) + list (db.execute (f'select {db_query} from replacements')))]
        name = process.extractOne (message.text, all_names)[0]
        
        ans = f'<b>Расписание</b> для {name}\n'
        for current_weekday, current_date in zip (query_weekdays, query_dates):
            all_num = [num [0] for num in set (list (db.execute (f'select num from timetable where {db_query} = "{name}" and day = "{current_weekday}"')) + list (db.execute (f'select num from replacements where {db_query} = "{name}" and date = "{current_date}"')))]
            all_num.sort ()
            
            if all_num != []:
                ans += f"\n<i>{current_weekday}</i>:\n"
                for current_num in all_num:
                    ans_timetable_data = list (db.execute (f'select * from timetable where {db_query} = "{name}" and day = "{current_weekday}" and num = "{current_num}"'))
                    ans_replacements_data = list (db.execute (f'select * from replacements where {db_query} = "{name}" and date = "{current_date}" and num = "{current_num}"'))
                    if ans_replacements_data == []:
                        if len (ans_timetable_data) == 2:
                            ans_timetable_elem = ans_timetable_data [not (date.today ().isocalendar().week % 2)]
                        else:
                            ans_timetable_elem = ans_timetable_data [0]
                        ans += f"{ans_timetable_elem [2]}. {ans_timetable_elem [4]}{print_if_available (ans_timetable_elem [x], ' - ')}{print_if_available (ans_timetable_elem [6], ' / ')}\n"
                    else:
                        ans_replacement_data = ans_replacements_data [0]
                        ans += f"<b>{ans_replacement_data [3]}. {ans_replacement_data [4]}{print_if_available (ans_replacement_data [x], ' - ')}{print_if_available (ans_replacement_data [6], ' / ')}</b>\n"
    except:
        await message.answer ('Произошла внутренняя ошибка')
    else:
        await message.answer (ans, parse_mode="HTML")
    finally:
        await state.finish ()
        await cmd_start (message)

scheduler = AsyncIOScheduler (timezone='Europe/Moscow')
scheduler.add_job (update_db, 'cron', hour=3, minute=0, second=0)
scheduler.start ()

executor.start_polling (dp, on_startup=lambda x: update_db ())
