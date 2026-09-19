import os
import json
import re
from datetime import datetime
from aiogram import types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.types.web_app_info import WebAppInfo
from config import dp, sheet, ADMIN_ID, pending_events
from ai_service import get_prompt, generate_with_retry


async def set_bot_commands(bot):
    commands = [
        BotCommand(command="add", description="➕ Открыть Mini App (панель)"),
        BotCommand(command="list", description="📋 Показать будущие мероприятия"),
        BotCommand(command="help", description="📖 Справка по командам и использованию")
    ]
    await bot.set_my_commands(commands)


@dp.message(F.from_user.id == ADMIN_ID, F.text == "/help")
async def help_command(message: types.Message):
    help_text = (
        "📖 **Справка по управлению ботом:**\n\n"
        "1️⃣ **Добавление мероприятия:**\n"
        "• Отправьте команду `/add`, чтобы открыть Mini App через удобную inline-кнопку.\n"
        "• Или отправьте текст анонса в чат — ИИ распознает его автоматически.\n\n"
        "2️⃣ **Просмотр мероприятий:**\n"
        "• `/list` или `/events` — показать будущие активные мероприятия.\n"
        "• `/list ДД.ММ.ГГГГ` — показать события на конкретный день.\n\n"
        "3️⃣ **Деактивация:**\n"
        "• `/delete [ID]` — переведет статус мероприятия в `inactive`."
    )
    await message.answer(help_text, parse_mode="Markdown")


@dp.message(F.from_user.id == ADMIN_ID, F.text.regexp(r"^/(list|events)(?:\s+(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))?)?$"))
async def list_events_command(message: types.Message):
    try:
        args = message.text.split()
        target_date_filter = args[1] if len(args) > 1 else None

        if target_date_filter and len(target_date_filter.split(".")[2]) == 2:
            day, month, year = target_date_filter.split(".")
            target_date_filter = f"{day}.{month}.20{year}"

        records = sheet.get_all_records()
        if not records:
            await message.answer("📭 В таблице пока нет мероприятий.")
            return

        now = datetime.now()
        current_date = now.date()

        text = "📋 **Список актуальных мероприятий:**\n\n"
        if target_date_filter:
            text = f"📋 **Мероприятия на дату {target_date_filter}:**\n\n"

        count = 0
        
        for idx, row in enumerate(records, start=2):
            status = str(row.get("status", "active")).lower()
            if status == "inactive":
                continue
                
            event_date_str = str(row.get("start_date", "")).strip()
            
            if not target_date_filter:
                try:
                    event_date = datetime.strptime(event_date_str, "%d.%m.%Y").date()
                    if event_date < current_date:
                        continue 
                except ValueError:
                    pass 
            else:
                if event_date_str != target_date_filter:
                    continue

            event_id = row.get("id", idx - 1)
            title = row.get("title", "Без названия")
            organizer_id = row.get("organizer_id", "-")
            
            text += f"🆔 **ID: {event_id}** | 📅 {event_date_str}\n📌 **{title}** (Орг. ID: {organizer_id})\n➖➖➖➖➖➖➖➖➖➖\n"
            count += 1
            
            if len(text) > 3500:
                await message.answer(text, parse_mode="Markdown")
                text = ""

        if count == 0:
            if target_date_filter:
                await message.answer(f"📭 На дату {target_date_filter} активных мероприятий не найдено.")
            else:
                await message.answer("📭 В базе нет будущих активных мероприятий (все уже прошли).")
        else:
            text += f"\n💡 Чтобы удалить/деактивировать мероприятие, отправьте:\n`/delete [ID]`"
            await message.answer(text, parse_mode="Markdown")

    except Exception as err:
        await message.answer(f"❌ Ошибка при чтении таблицы: {err}")


@dp.message(F.from_user.id == ADMIN_ID, F.text.startswith("/delete"))
async def delete_event_by_id(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Укажите ID мероприятия числом.\nПример: `/delete 3`", parse_mode="Markdown")
        return

    target_id = int(parts[1])

    try:
        records = sheet.get_all_records()
        row_to_update = None
        
        for idx, row in enumerate(records, start=2):
            if int(row.get("id", 0)) == target_id:
                row_to_update = idx
                break

        if not row_to_update:
            await message.answer(f"❌ Мероприятие с ID **{target_id}** не найдено в таблице.", parse_mode="Markdown")
            return

        sheet.update_cell(row_to_update, 2, "inactive")
        await message.answer(f"✅ Мероприятие с ID **{target_id}** успешно помечено как неактивное (`inactive`).", parse_mode="Markdown")

    except Exception as err:
        await message.answer(f"❌ Ошибка при удалении: {err}")


@dp.message(F.from_user.id == ADMIN_ID, F.text == "/add")
async def add_via_webapp(message: types.Message):
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if not render_url:
        await message.answer("⚠️ Ошибка: бот не может найти свой веб-адрес на Render.")
        return

    # Используем Inline-кнопку для открытия Mini App под сообщением
    web_app = WebAppInfo(url=f"{render_url}/form")
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть Mini App", web_app=web_app)]
        ]
    )
    await message.answer("Нажмите на кнопку ниже, чтобы открыть панель управления в Mini App:", reply_markup=keyboard)


@dp.message(F.from_user.id == ADMIN_ID, F.web_app_data)
async def web_app_data_handler(message: types.Message):
    data_str = message.web_app_data.data
    try:
        data = json.loads(data_str)
        user_id = message.from_user.id
        
        pending_events[user_id] = {"data": data, "waiting_for_edit": False}
        
        end_time_str = f" до {data.get('end_time')}" if data.get('end_time') else ""
        preview_text = (
            f"📌 **Данные из Mini App получены:**\n\n"
            f"**Название:** {data.get('title')}\n"
            f"**Дата и время:** {data.get('start_date')} в {data.get('start_time')}{end_time_str}\n"
            f"**Место:** {data.get('location_name')}\n"
            f"**Цена:** {data.get('price_min')} € - {data.get('price_max')} €\n"
            f"**Категория (ID):** {data.get('category_id')}\n"
            f"**Описание:** {data.get('description')}"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить в таблицу", callback_data="save_event")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
        ])
        
        await message.answer(preview_text, parse_mode="Markdown", reply_markup=keyboard)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка обработки данных формы: {e}")


@dp.message(F.from_user.id == ADMIN_ID)
async def handle_announcement(message: types.Message):
    user_id = message.from_user.id

    if user_id in pending_events and pending_events[user_id].get("waiting_for_edit"):
        status_msg = await message.answer("🔄 Применяю исправления через Gemini...")
        try:
            now = datetime.now()
            current_date_str = now.strftime("%d.%m.%Y")
            
            correction_prompt = (
                f"Текущая дата: {current_date_str}.\n"
                f"У нас есть уже распарсенные данные мероприятия:\n{json.dumps(pending_events[user_id]['data'], ensure_ascii=False)}\n\n"
                f"Пользователь прислал исправления или дополнения: '{message.text}'. "
                f"Обнови JSON-объект с учетом этих правок и верни ТОЛЬКО валидный JSON в прежнем формате."
            )
            
            response = await generate_with_retry(correction_prompt)
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                new_data = json.loads(json_match.group(0))
                pending_events[user_id]["data"] = new_data
                pending_events[user_id]["waiting_for_edit"] = False

                end_time_str = f" до {new_data.get('end_time')}" if new_data.get('end_time') else ""
                preview_text = (
                    f"📌 **Обновленные данные:**\n\n"
                    f"**Название:** {new_data.get('title')}\n"
                    f"**Дата и время:** {new_data.get('start_date')} в {new_data.get('start_time')}{end_time_str}\n"
                    f"**Место:** {new_data.get('location_name')} ({new_data.get('location_address')})\n"
                    f"**Цена:** {new_data.get('price_min') or 0} € - {new_data.get('price_max') or 0} €\n"
                    f"**ID Категории:** {new_data.get('category_id')}\n"
                    f"**ID Организатора:** {new_data.get('organizer_id')}\n"
                    f"**Описание:** {new_data.get('description')}\n"
                    f"**Доп. инфо:** {new_data.get('additional_info')}"
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="✅ Сохранить в таблицу", callback_data="save_event")],
                    [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_event")],
                    [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
                ])
                await status_msg.edit_text(preview_text, parse_mode="Markdown", reply_markup=keyboard)
                return
        except Exception as e:
            await status_msg.edit_text(f"❌ Ошибка при внесении правок: {e}")
            return

    if not message.text:
        await message.answer("Пожалуйста, отправьте текстовый анонс мероприятия.")
        return

    status_msg = await message.answer("🧠 Извлекаю данные через Gemini AI...")

    try:
        now = datetime.now()
        current_date_str = now.strftime("%d.%m.%Y")
        
        prompt = get_prompt(current_date_str) + message.text
        response = await generate_with_retry(prompt)
        json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
        
        if not json_match:
            raise ValueError("Не удалось получить структурированный JSON от модели.")
            
        data = json.loads(json_match.group(0))
        pending_events[user_id] = {"data": data, "waiting_for_edit": False}

        end_time_str = f" до {data.get('end_time')}" if data.get('end_time') else ""
        preview_text = (
            f"📌 **Проверьте распарсенные данные:**\n\n"
            f"**Название:** {data.get('title')}\n"
            f"**Дата и время:** {data.get('start_date')} в {data.get('start_time')}{end_time_str}\n"
            f"**Место:** {data.get('location_name')} ({data.get('location_address')})\n"
            f"**Цена:** {data.get('price_min') or 0} € - {data.get('price_max') or 0} €\n"
            f"**ID Категории:** {data.get('category_id')}\n"
            f"**ID Организатора:** {data.get('organizer_id')}\n"
            f"**Описание:** {data.get('description')}\n"
            f"**Доп. инфо:** {data.get('additional_info')}"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Сохранить в таблицу", callback_data="save_event")],
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data="edit_event")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_event")]
        ])

        await status_msg.edit_text(preview_text, parse_mode="Markdown", reply_markup=keyboard)

    except Exception as err:
        await status_msg.edit_text(f"❌ Ошибка при обработке: {err}")


@dp.callback_query(F.data == "edit_event")
async def edit_event_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_events:
        pending_events[user_id]["waiting_for_edit"] = True
        await callback.message.answer("✍️ Напишите текстом, что именно нужно исправить или изменить:")
    await callback.answer()


@dp.callback_query(F.data == "save_event")
async def save_to_sheets(callback: CallbackQuery):
    user_id = callback.from_user.id
    user_session = pending_events.get(user_id)

    if not user_session or not user_session.get("data"):
        await callback.message.edit_text("❌ Данные не найдены или сессия истекла.")
        return

    data = user_session["data"]

    try:
        records = sheet.get_all_records()
        next_id = len(records) + 1

        row = [
            next_id,
            "active",
            "FALSE",
            data.get("title", "") or "",
            data.get("description", "") or "",
            "",
            data.get("start_date", "") or "",
            data.get("start_time", "") or "",
            data.get("end_time", "") or "",
            data.get("location_name", "") or "",
            data.get("location_address", "") or "",
            data.get("price_min") if data.get("price_min") is not None else 0,
            data.get("price_max") if data.get("price_max") is not None else 0,
            "",
            data.get("additional_info", "") or "",
            data.get("category_id", "") or "",
            data.get("organizer_id", "") or ""
        ]

        sheet.append_row(row)
        del pending_events[user_id]
        await callback.message.edit_text("🎉 **Событие успешно добавлено в Google Таблицу!**")

    except Exception as err:
        await callback.message.edit_text(f"❌ Ошибка записи в таблицу: {err}")


@dp.callback_query(F.data == "cancel_event")
async def cancel_save(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_events:
        del pending_events[user_id]
    await callback.message.edit_text("Действие отменено.")