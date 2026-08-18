from __future__ import annotations

import asyncio
from html import escape

import httpx
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from core.config import get_settings
from core.distribution import render_session_powershell_launcher

settings = get_settings()
router = Router()


def allowed(user_id: int | None) -> bool:
    return user_id is not None and user_id in settings.owner_telegram_ids


def headers() -> dict[str, str]:
    return {"X-Owner-Key": settings.owner_api_key}


async def api(method: str, path: str, **kwargs):
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.request(method, f"{settings.server_url.rstrip('/')}{path}", headers=headers(), **kwargs)
        response.raise_for_status()
        return response.json()


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🖥 أجهزتي", callback_data="devices"), InlineKeyboardButton(text="➕ جلسة جديدة", callback_data="new")],
            [InlineKeyboardButton(text="📡 الجلسات", callback_data="sessions")],
        ]
    )


def session_connection_keyboard(methods: dict | None, pairing_code: str) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if methods and methods.get("remote_https_ready"):
        windows = methods.get("windows") or {}
        exe = windows.get("exe") or {}
        portable = windows.get("portable") or {}
        if exe.get("available") and exe.get("url"):
            rows.append(
                [
                    InlineKeyboardButton(text="🪟 Windows EXE", url=str(exe["url"])),
                    InlineKeyboardButton(text="⚡ PowerShell", callback_data=f"ps:{pairing_code}"),
                ]
            )
        if portable.get("available") and portable.get("url"):
            rows.append([InlineKeyboardButton(text="📦 Portable", url=str(portable["url"]))])
    rows.append([InlineKeyboardButton(text="↩️ الرئيسية", callback_data="home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(CommandStart())
async def start(message: Message) -> None:
    if not allowed(message.from_user.id if message.from_user else None):
        return
    await message.answer("<b>RemoteSessionControl</b>\n\nتحكم مؤقت قائم على جلسات محددة المدة.", reply_markup=home_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "home")
async def home(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    await callback.message.edit_text("<b>RemoteSessionControl</b>\n\nاختر من القائمة:", reply_markup=home_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "new")
async def new_session(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="15 دقيقة", callback_data="duration:900"), InlineKeyboardButton(text="30 دقيقة", callback_data="duration:1800")],
            [InlineKeyboardButton(text="ساعة", callback_data="duration:3600"), InlineKeyboardButton(text="ساعتان", callback_data="duration:7200")],
            [InlineKeyboardButton(text="4 ساعات", callback_data="duration:14400")],
            [InlineKeyboardButton(text="↩️ الرئيسية", callback_data="home")],
        ]
    )
    await callback.message.edit_text("اختر مدة الجلسة.\n\n<b>مهم:</b> المدة تبدأ عند أول تفعيل ناجح على الجهاز، وليس عند إنشاء المفتاح.", reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("duration:"))
async def create_duration(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    duration = int(callback.data.split(":", 1)[1])
    try:
        data = await api("POST", "/api/v1/sessions", json={"duration_seconds": duration})
    except Exception as exc:
        await callback.answer(f"تعذر إنشاء الجلسة: {exc}", show_alert=True)
        return

    try:
        methods = await api("GET", "/api/v1/client-methods")
    except Exception:
        methods = None

    session = data["session"]
    pairing_code = str(data["pairing_code"])
    minutes = duration // 60
    text = (
        "✅ <b>تم إنشاء جلسة جديدة</b>\n\n"
        f"🔑 مفتاح الربط: <code>{escape(pairing_code)}</code>\n"
        f"صلاحية المفتاح: {data['pairing_ttl_seconds'] // 60} دقائق\n"
        f"مدة الجلسة: {minutes} دقيقة\n\n"
        "⏱ تبدأ مدة الجلسة عند أول تفعيل ناجح على الجهاز.\n"
    )

    if methods and methods.get("remote_https_ready"):
        windows = methods.get("windows") or {}
        available = []
        if (windows.get("exe") or {}).get("available"):
            available.append("EXE")
        if windows.get("powershell_ready"):
            available.append("PowerShell")
        if (windows.get("portable") or {}).get("available"):
            available.append("Portable")
        if available:
            text += "\n🛟 <b>طرق الاتصال المتاحة:</b> " + " / ".join(available) + "\n"
            text += "يمكن استخدام أي طريقة؛ كلها تربط نفس الجلسة ولا تغيّر مدة انتهائها.\n"
        else:
            text += "\n⚠️ ملفات عميل Windows لم تُنشر على السيرفر بعد.\n"
    else:
        text += "\n⚠️ الاتصال المباشر سيظهر بعد تفعيل HTTPS/WSS على السيرفر.\n"

    text += f"\nSession ID: <code>{escape(session['id'])}</code>"
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=session_connection_keyboard(methods, pairing_code),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ps:"))
async def powershell_launcher(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    pairing_code = callback.data.split(":", 1)[1].strip().upper()
    try:
        methods = await api("GET", "/api/v1/client-methods")
        if not methods.get("remote_https_ready"):
            raise RuntimeError("HTTPS/WSS is not ready")
        windows = methods.get("windows") or {}
        exe = windows.get("exe") or {}
        if not exe.get("available") or not exe.get("url") or not exe.get("sha256"):
            raise RuntimeError("Windows EXE is not published on the server")
        script = render_session_powershell_launcher(
            server_url=str(methods["public_base_url"]),
            pairing_code=pairing_code,
            client_url=str(exe["url"]),
            expected_sha256=str(exe["sha256"]),
        )
    except Exception as exc:
        await callback.answer(f"تعذر تجهيز PowerShell: {exc}", show_alert=True)
        return

    filename = f"Start-RemoteSession-{pairing_code}.ps1"
    await callback.message.answer_document(
        BufferedInputFile(script.encode("utf-8-sig"), filename=filename),
        caption=(
            "⚡ ملف تشغيل PowerShell لهذه الجلسة.\n"
            "شغّله على جهاز Windows؛ سيحمّل العميل عبر HTTPS ويتحقق من SHA-256 ثم يطلب موافقة محلية قبل التفعيل.\n"
            "لا يثبت Service أو Startup أو Scheduled Task."
        ),
    )
    await callback.answer("تم تجهيز ملف PowerShell")


@router.callback_query(F.data == "devices")
async def devices(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    try:
        rows = await api("GET", "/api/v1/devices")
    except Exception as exc:
        await callback.answer(f"فشل الاتصال بالسيرفر: {exc}", show_alert=True)
        return
    buttons = []
    for row in rows:
        state = "🟢" if row.get("session") and row["session"].get("status") == "ACTIVE" else "⚪"
        buttons.append([InlineKeyboardButton(text=f"{state} {row['name']}", callback_data=f"device:{row['id']}")])
    buttons.append([InlineKeyboardButton(text="↩️ الرئيسية", callback_data="home")])
    text = "<b>🖥 أجهزتي</b>\n\n" + ("اختر جهازًا:" if rows else "لا توجد أجهزة مرتبطة بعد.")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


@router.callback_query(F.data.startswith("device:"))
async def device_panel(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    device_id = callback.data.split(":", 1)[1]
    rows = await api("GET", "/api/v1/devices")
    row = next((item for item in rows if item["id"] == device_id), None)
    if row is None:
        await callback.answer("الجهاز غير موجود", show_alert=True)
        return
    session = row.get("session") or {}
    remaining = int(session.get("remaining_seconds") or 0)
    h, rem = divmod(remaining, 3600)
    m, s = divmod(rem, 60)
    text = (
        f"<b>💻 {escape(row['name'])}</b>\n\n"
        f"النظام: {escape(row['platform'])} {escape(row.get('platform_version') or '')}\n"
        f"الجلسة: {escape(session.get('status') or 'غير فعالة')}\n"
        f"المتبقي: {h:02d}:{m:02d}:{s:02d}"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 صورة", callback_data=f"cmd:{device_id}:SCREENSHOT"), InlineKeyboardButton(text="🎥 فيديو 30ث", callback_data=f"cmd:{device_id}:RECORD_SCREEN")],
            [InlineKeyboardButton(text="ℹ️ معلومات", callback_data=f"cmd:{device_id}:DEVICE_INFO"), InlineKeyboardButton(text="⏱ الجلسة", callback_data=f"cmd:{device_id}:SESSION_STATUS")],
            [InlineKeyboardButton(text="🔌 إنهاء الجلسة", callback_data=f"cmd:{device_id}:DISCONNECT")],
            [InlineKeyboardButton(text="↩️ الأجهزة", callback_data="devices"), InlineKeyboardButton(text="🏠 الرئيسية", callback_data="home")],
        ]
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()


async def wait_command(command_id: str, timeout: int = 130) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        row = await api("GET", f"/api/v1/commands/{command_id}")
        if row["status"] in {"completed", "failed"}:
            return row
        await asyncio.sleep(1)
    raise TimeoutError("command timed out")


@router.callback_query(F.data.startswith("cmd:"))
async def command(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    _, device_id, name = callback.data.split(":", 2)
    payload = {"duration": 30, "fps": 5} if name == "RECORD_SCREEN" else {}
    await callback.answer("تم إرسال الأمر")
    try:
        created = await api("POST", f"/api/v1/devices/{device_id}/commands", json={"command": name, "payload": payload})
        row = created if created["status"] in {"completed", "failed"} else await wait_command(created["id"])
    except Exception as exc:
        await callback.message.answer(f"❌ تعذر تنفيذ الأمر: {escape(str(exc))}", parse_mode="HTML")
        return

    if row["status"] == "failed":
        await callback.message.answer(f"❌ فشل الأمر: {escape(row.get('error') or 'unknown error')}", parse_mode="HTML")
        return

    if row.get("media_id"):
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(f"{settings.server_url.rstrip('/')}/api/v1/media/{row['media_id']}", headers=headers())
            response.raise_for_status()
            payload_bytes = response.content
            content_type = response.headers.get("content-type", "application/octet-stream")
        if content_type.startswith("image/"):
            await callback.message.answer_photo(BufferedInputFile(payload_bytes, filename="screenshot.png"))
        elif content_type.startswith("video/"):
            await callback.message.answer_video(BufferedInputFile(payload_bytes, filename="screen.mp4"), supports_streaming=True)
        else:
            await callback.message.answer_document(BufferedInputFile(payload_bytes, filename="result.bin"))
        return

    result = row.get("result") or {}
    if name == "SESSION_STATUS":
        session = result.get("session") or {}
        await callback.message.answer(f"⏱ حالة الجلسة: {escape(session.get('status') or 'unknown')}\nالمتبقي: {int(session.get('remaining_seconds') or 0)} ثانية", parse_mode="HTML")
    elif name == "DEVICE_INFO":
        lines = ["ℹ️ <b>معلومات الجهاز</b>"] + [f"{escape(str(k))}: <code>{escape(str(v))}</code>" for k, v in result.items()]
        await callback.message.answer("\n".join(lines), parse_mode="HTML")
    elif name == "DISCONNECT":
        await callback.message.answer("🔌 تم إنهاء الجلسة.")
    else:
        await callback.message.answer("✅ تم التنفيذ.")


@router.callback_query(F.data == "sessions")
async def sessions(callback: CallbackQuery) -> None:
    if not allowed(callback.from_user.id):
        return
    rows = await api("GET", "/api/v1/sessions")
    lines = ["<b>📡 آخر الجلسات</b>", ""]
    for row in rows[:10]:
        lines.append(f"• <code>{escape(row['id'][:8])}</code> — {escape(row['status'])} — {int(row.get('remaining_seconds') or 0)}ث")
    if not rows:
        lines.append("لا توجد جلسات.")
    await callback.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="↩️ الرئيسية", callback_data="home")]]))
    await callback.answer()


async def main() -> None:
    if not settings.telegram_token:
        raise RuntimeError("RSC_TELEGRAM_TOKEN is not configured")
    if not settings.owner_telegram_ids:
        raise RuntimeError("RSC_TELEGRAM_OWNER_IDS is not configured")
    bot = Bot(settings.telegram_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
