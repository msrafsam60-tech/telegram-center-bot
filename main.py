"""
Telegram Join Request Auto-DM Bot  (SK COMMUNITY)
Install:  pip install python-telegram-bot==21.6
Run:      python join_bot.py
"""
import asyncio
import copy
import csv
import io
import json
import logging
import os
import re
import time
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.error import RetryAfter
from telegram.ext import (
    Application, CallbackQueryHandler, ChatJoinRequestHandler, ChatMemberHandler,
    CommandHandler, ContextTypes, MessageHandler, filters,
)

# ╔══════════════════════════════════════════════╗
# ║            ⚙️  এখানে নিজের তথ্য বসাও            ║
# ╚══════════════════════════════════════════════╝
# ⚠️ BotFather থেকে /revoke করে নেওয়া নতুন টোকেন। Railway-তে Variables-এ BOT_TOKEN দিলে ভালো।
BOT_TOKEN = os.getenv("BOT_TOKEN", "9183980987:AAFXJhf0m9SYFSmmx4sCcIvRRP5LAALlLvg")

ADMIN_1_ID = 7122259829   # প্রথম অ্যাডমিনের Telegram user ID
ADMIN_2_ID = 6753121703            # দ্বিতীয় অ্যাডমিনের Telegram user ID (0 থাকলে বন্ধ)

BRAND = "SK COMMUNITY"

# Railway-তে Volume লাগালে Variables-এ DATA_DIR=/data দাও, তাহলে ডাটা মুছবে না
DATA_DIR = os.getenv("DATA_DIR", ".")
# ════════════════════════════════════════════════

os.makedirs(DATA_DIR, exist_ok=True)


def P(name):
    """ডাটা ফাইলের পাথ"""
    return os.path.join(DATA_DIR, name)


# দুইজনই মূল অ্যাডমিন (0 বা ফাঁকা আইডি বাদ যাবে)
ADMIN_IDS = [i for i in (ADMIN_1_ID, ADMIN_2_ID) if i]

CFG_FILE = P("config.json")
CHANNELS_FILE = P("channels.json")
LOG_FILE = P("sent_log.json")
USERS_FILE = P("users.json")
META_FILE = P("users_meta.json")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("joinbot")

DEFAULT = {
    # ---- ওয়েলকাম মেসেজ ----
    "text": f"স্বাগতম! <b>{BRAND}</b>-এ আপনার জয়েন রিকোয়েস্ট পেয়েছি।",
    "media_type": None,   # video / photo / animation
    "media_id": None,
    "buttons": [],        # ওয়েলকাম মেসেজের নিচের বাটন
    # ---- সেটিংস ----
    "auto_approve": False,
    "banned": [],         # ব্যান করা ইউজার আইডি
    "extra_admins": [],   # /addadmin দিয়ে যোগ হওয়া অ্যাডমিন
    "contact": "",        # কানেক্টেড অ্যাডমিনদের @username/লিংক (একাধিক হলে কমা/স্পেস দিয়ে)
    # ---- ইউজার মেনু ১: অ্যাকাউন্ট খোলার নিয়ম ----
    "rules": f"📖 <b>{BRAND} - অ্যাকাউন্ট খোলার নিয়ম</b>\n\n১️⃣ নিচের লিংকে ক্লিক করে রেজিস্ট্রেশন করুন\n২️⃣ আপনার তথ্য দিয়ে অ্যাকাউন্ট তৈরি করুন\n৩️⃣ অ্যাকাউন্ট ভেরিফাই করুন\n৪️⃣ এডমিনকে ইউজার আইডি পাঠান",
    "rules_buttons": [],
    # ---- ইউজার মেনু ২: কানেক্টেড এডমিন ----
    "profile": f"🧑‍💻 <b>{BRAND} - Developer Profile</b>\n\n🏷 Name ╌ আপনার নাম\n🎯 Dream ╌ আপনার লক্ষ্য\n💡 Work ╌ আপনার কাজ\n\nThanks for visiting {BRAND}! Hit the button ↓",
    "profile_buttons": [],
    # ---- ইউজার মেনু ৩: VIP FREE HACK ----
    "vip_locked": f"🔒 <b>এই অপশনটি এখন লক করা আছে।</b>\n\nআনলক করতে {BRAND} এডমিনের সাথে যোগাযোগ করুন।",
    "vip_buttons": [],
}

# ইউজার মেনুর তিনটা সেকশন: কোনটার টেক্সট ও বাটন config-এর কোন key-তে থাকে
SECTIONS = {
    "rules": {"label": "📖 অ্যাকাউন্ট খোলার নিয়ম", "text_key": "rules", "btn_key": "rules_buttons"},
    "admin": {"label": "👨‍💻 কানেক্টেড এডমিন", "text_key": "profile", "btn_key": "profile_buttons"},
    "vip": {"label": "💎 VIP FREE HACK", "text_key": "vip_locked", "btn_key": "vip_buttons"},
}


def load():
    if os.path.exists(CFG_FILE):
        with open(CFG_FILE, encoding="utf-8") as f:
            return {**copy.deepcopy(DEFAULT), **json.load(f)}
    return copy.deepcopy(DEFAULT)


def save(cfg):
    with open(CFG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def all_admins():
    return set(ADMIN_IDS) | set(load().get("extra_admins", []))


def is_owner(update: Update):
    """দুইজন মূল অ্যাডমিন"""
    return bool(update.effective_user) and update.effective_user.id in ADMIN_IDS


def is_admin(update: Update):
    return bool(update.effective_user) and update.effective_user.id in all_admins()


# ╔══════════════════════════════════════════════╗
# ║      🎨 বাটন স্টাইল / প্রিমিয়াম ইমোজি          ║
# ╚══════════════════════════════════════════════╝
# স্টাইল: green(সবুজ) / red(লাল) / blue(নীল)
STYLE_MAP = {"green": "success", "red": "danger", "blue": "primary",
             "success": "success", "danger": "danger", "primary": "primary"}
# প্রিমিয়াম ইমোজি আইকন কাজ না করলে (বটের ওনারের Premium না থাকলে) এটা False করো
PREMIUM_ICONS = True


def _kw(style, emoji):
    kw = {}
    if style and style in STYLE_MAP:
        kw["style"] = STYLE_MAP[style]
    if emoji and PREMIUM_ICONS:
        kw["icon_custom_emoji_id"] = str(emoji)
    return kw or None


def mk_btn(text, url=None, cb=None, style=None, emoji=None):
    return InlineKeyboardButton(text, url=url, callback_data=cb, api_kwargs=_kw(style, emoji))


def parse_rows_msg(m):
    """
    অ্যাডমিনের পাঠানো মেসেজ থেকে বাটন বানায়।
    • প্রতি লাইন = একটা সারি, && দিয়ে পাশাপাশি বাটন
    • ফরম্যাট:  নাম | লিংক | [green/red/blue] | [emoji_id]
    • নামের ভেতরে প্রিমিয়াম ইমোজি থাকলে বট নিজেই সেটা বাটনের আইকন বানিয়ে নেয়
    """
    text = m.text or ""

    # টেলিগ্রামের offset UTF-16 হিসাবে আসে, তাই পাইথন ইনডেক্সে রূপান্তর করছি
    u16, pos = {}, 0
    for i, ch in enumerate(text):
        u16[pos] = i
        pos += 2 if ord(ch) > 0xFFFF else 1
    u16[pos] = len(text)

    emo = []  # (শুরু, শেষ, ইমোজি_আইডি)
    for e in (m.entities or []):
        if e.type == "custom_emoji":
            s, en = u16.get(e.offset), u16.get(e.offset + e.length)
            if s is not None and en is not None:
                emo.append((s, en, e.custom_emoji_id))

    rows = []
    line_start = 0
    for line in text.split("\n"):
        row = []
        part_start = line_start
        for part in line.split("&&"):
            part_end = part_start + len(part)
            bar = part.find("|")
            name_len = bar if bar >= 0 else len(part)
            name_end = part_start + name_len

            # নামের অংশে থাকা প্রিমিয়াম ইমোজি খুঁজে বের করো ও নাম থেকে সরাও
            eid, drop = None, set()
            for s, en, cid in emo:
                if part_start <= s and en <= name_end:
                    eid = eid or cid
                    drop.update(range(s - part_start, en - part_start))
            name = "".join(c for j, c in enumerate(part[:name_len]) if j not in drop)
            cleaned = name + part[name_len:]

            f = [x.strip() for x in cleaned.split("|")]
            if len(f) >= 2 and f[0] and f[1].startswith(("http://", "https://", "tg://")):
                style, emoji = None, eid
                for extra in f[2:]:
                    if extra.lower() in STYLE_MAP:
                        style = extra.lower()
                    elif extra.isdigit():
                        emoji = extra
                row.append([f[0], f[1], style, emoji])
            part_start = part_end + 2  # "&&" এর দৈর্ঘ্য
        if row:
            rows.append(row)
        line_start += len(line) + 1
    return rows


def norm_rows(rows):
    """পুরনো ফরম্যাট [নাম, লিংক] কে নতুন ফরম্যাটে আনে"""
    return [[r] if (r and isinstance(r[0], str)) else r for r in rows]


def rows_to_markup(rows):
    out = []
    for row in norm_rows(rows):
        out.append([mk_btn(b[0], url=b[1], style=b[2] if len(b) > 2 else None,
                           emoji=b[3] if len(b) > 3 else None) for b in row])
    return InlineKeyboardMarkup(out) if out else None


def parse_button_rows(m):
    return rows_to_markup(parse_rows_msg(m))


# বাটন যোগ করার নিয়ম (সব জায়গায় এই একই লেখা দেখাবে)
BTN_HELP = """🔘 বাটন যোগ করো (আগেরগুলো থাকবে)

✍️ ফরম্যাট (প্রতি লাইনে ১টা বাটন):
বাটনের নাম | https://লিংক

🎨 রঙ দিতে চাইলে শেষে লেখো green / red / blue:
বাটনের নাম | https://লিংক | green

💎 প্রিমিয়াম ইমোজি দিতে: বাটনের নামের শুরুতে প্রিমিয়াম ইমোজি বসিয়ে পাঠাও। আমি নিজেই বাটনের পাশে সেট করে নেব (Premium অ্যাকাউন্ট থেকে লিখতে হবে)।
উদাহরণ: (প্রিমিয়াম ইমোজি) VIP জয়েন | https://t.me/xyz | green

↔️ পাশাপাশি ২টা বাটন: && দিয়ে আলাদা করো
নাম১ | লিংক১ && নাম২ | লিংক২

🗑 সব মুছতে লেখো: clear
❌ বাতিল করতে: /cancel"""


# ╔══════════════════════════════════════════════╗
# ║          📱 ইউজার মেনু (নিচের কিবোর্ড)          ║
# ╚══════════════════════════════════════════════╝
# (key, ইমোজি, লেখা, রঙ)
MENU_ITEMS = [
    ("rules", "📖", "অ্যাকাউন্ট খোলার নিয়ম", "green"),
    ("admin", "👨‍💻", "কানেক্টেড এডমিন", "blue"),
    ("vip", "💎", "VIP FREE HACK", "red"),
]
# চাইলে মেনু বাটনে প্রিমিয়াম ইমোজি বসাও: "rules": "ইমোজি_আইডি" (খালি থাকলে সাধারণ ইমোজি)
MENU_ICON_IDS = {"rules": "", "admin": "", "vip": ""}


def build_menu_kb():
    from telegram import KeyboardButton
    btns = {}
    for key, emo, label, color in MENU_ITEMS:
        icon = MENU_ICON_IDS.get(key)
        text = label if (icon and PREMIUM_ICONS) else f"{emo} {label}"
        btns[key] = KeyboardButton(text, api_kwargs=_kw(color, icon))
    return ReplyKeyboardMarkup(
        [[btns["rules"]], [btns["admin"], btns["vip"]]],
        resize_keyboard=True, is_persistent=True)


MENU_REGEX = "(" + "|".join(re.escape(l) for _, _, l, _ in MENU_ITEMS) + ")$"


def contact_urls(cfg):
    """কন্টাক্টে এক বা একাধিক @username/লিংক থাকতে পারে (কমা বা স্পেস দিয়ে আলাদা)"""
    raw = (cfg.get("contact") or "").replace(",", " ").split()
    urls = []
    for c in raw:
        urls.append(c if c.startswith("http") else "https://t.me/" + c.lstrip("@"))
    return urls


def section_markup(sec, cfg):
    """একটা মেনুর মেসেজের নিচের সব বাটন (এডমিন ইনবক্স বাটন + অ্যাডমিনের যোগ করা বাটন)"""
    out = []
    if sec == "admin":
        urls = contact_urls(cfg)
        for i, u in enumerate(urls, 1):
            label = "💬 ইনবক্স করুন" if len(urls) == 1 else f"💬 এডমিন {i} কে ইনবক্স করুন"
            out.append([mk_btn(label, url=u, style="blue")])
    mk = rows_to_markup(cfg.get(SECTIONS[sec]["btn_key"], []))
    if mk:
        out.extend([list(r) for r in mk.inline_keyboard])
    return InlineKeyboardMarkup(out) if out else None


async def send_section(bot, chat_id, sec, cfg):
    await bot.send_message(
        chat_id, cfg[SECTIONS[sec]["text_key"]], parse_mode="HTML",
        reply_markup=section_markup(sec, cfg), disable_web_page_preview=True)


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cfg = load()
    t = update.message.text
    if is_banned(update.effective_user.id):
        return
    add_user(update.effective_user.id)
    remember(update.effective_user)
    key = next((k for k, _, l, _ in MENU_ITEMS if t.endswith(l)), None)
    if key in SECTIONS:
        await send_section(context.bot, update.effective_chat.id, key, cfg)


async def send_menu(bot, chat_id):
    await bot.send_message(chat_id, "👇 নিচের মেনু থেকে অপশন বেছে নিন", reply_markup=build_menu_kb())


# ╔══════════════════════════════════════════════╗
# ║            📢 চ্যানেল / ডাটা ফাইল              ║
# ╚══════════════════════════════════════════════╝
def load_channels():
    if os.path.exists(CHANNELS_FILE):
        with open(CHANNELS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_channels(ch):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(ch, f, ensure_ascii=False)


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def add_user(uid):
    users = load_users()
    if uid not in users:
        users.add(uid)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(users), f)


def remember(user):
    """ইউজারের নাম/ইউজারনেম সেভ রাখো (@username দিয়ে খোঁজার জন্য)"""
    meta = {}
    if os.path.exists(META_FILE):
        with open(META_FILE, encoding="utf-8") as f:
            meta = json.load(f)
    meta[str(user.id)] = {"name": user.full_name, "username": (user.username or "").lower()}
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def find_user(query):
    """@username বা ID থেকে user id বের করো"""
    q = query.strip().lstrip("@").lower()
    if q.isdigit():
        return int(q)
    if os.path.exists(META_FILE):
        with open(META_FILE, encoding="utf-8") as f:
            for uid, d in json.load(f).items():
                if d["username"] == q:
                    return int(uid)
    return None


def add_log(entry):
    data = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    entry["ts"] = time.time()
    data.append(entry)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data[-5000:], f, ensure_ascii=False)


def is_banned(uid):
    return uid in load().get("banned", [])


async def notify_admins(bot, text):
    """সব অ্যাডমিনকে (দুইজন মূল + এক্সট্রা) নোটিফিকেশন পাঠায়"""
    for aid in all_admins():
        try:
            await bot.send_message(aid, text, disable_web_page_preview=True)
        except Exception as e:
            log.warning("অ্যাডমিন %s কে নোটিফিকেশন যায়নি (বটে /start দিয়েছে কি?): %s", aid, e)


# ╔══════════════════════════════════════════════╗
# ║     🟢🔴 জয়েন / লিভ নোটিফিকেশন (পাবলিক+প্রাইভেট) ║
# ╚══════════════════════════════════════════════╝
async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বটকে কোনো চ্যানেল/গ্রুপে অ্যাডমিন করলে অটো লিস্টে যোগ হবে"""
    c = update.my_chat_member
    chat = c.chat
    if chat.type == "private":
        return
    st = c.new_chat_member.status
    chs = load_channels()
    if st == "administrator":
        chs[str(chat.id)] = chat.title
        save_channels(chs)
        warn = ""
        if chat.type == "channel" and not getattr(c.new_chat_member, "can_post_messages", True):
            warn = "\n⚠️ কিন্তু 'Post Messages' পারমিশন নেই, পোস্ট করতে হলে অন করো।"
        await notify_admins(context.bot, f"✅ বট অ্যাডমিন হয়েছে: {chat.title}{warn}")
    elif str(chat.id) in chs:
        chs.pop(str(chat.id))
        save_channels(chs)
        await notify_admins(context.bot, f"➖ বট সরে গেছে/সরানো হয়েছে: {chat.title}")


IN_STATUSES = ("member", "administrator", "creator")


def _is_in(member):
    """ইউজার এখন চ্যানেল/গ্রুপের ভেতরে আছে কি না"""
    if member.status in IN_STATUSES:
        return True
    if member.status == "restricted":
        return bool(getattr(member, "is_member", True))
    return False


async def on_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কেউ জয়েন করলে বা লিভ নিলে/রিমুভ হলে সব অ্যাডমিনকে জানাবে"""
    c = update.chat_member
    chat = c.chat
    if chat.type == "private":
        return
    user = c.new_chat_member.user
    if user.is_bot:
        return

    was_in = _is_in(c.old_chat_member)
    now_in = _is_in(c.new_chat_member)
    if was_in == now_in:
        return  # জয়েন/লিভ নয় (শুধু পারমিশন বা অ্যাডমিন স্ট্যাটাস বদল)

    name = user.full_name
    uname = f"@{user.username}" if user.username else "(username নেই)"
    kind = "📢 চ্যানেল" if chat.type == "channel" else "👥 গ্রুপ"
    vis = "🌐 পাবলিক" if getattr(chat, "username", None) else "🔒 প্রাইভেট"

    if now_in:
        link = ""
        if c.invite_link:
            link = f"\n🔗 লিংক: {c.invite_link.invite_link}"
        msg = (f"🟢 নতুন জয়েন — {BRAND}\n"
               f"👤 {name}\n🔗 {uname}\n🆔 {user.id}\n"
               f"{kind}: {chat.title} ({vis}){link}")
    else:
        if c.new_chat_member.status == "kicked":
            reason = "🚫 ব্যান/রিমুভ করা হয়েছে"
        elif c.from_user and c.from_user.id != user.id:
            reason = "➖ রিমুভ করা হয়েছে"
        else:
            reason = "🔴 নিজে লিভ নিয়েছে"
        msg = (f"{reason} — {BRAND}\n"
               f"👤 {name}\n🔗 {uname}\n🆔 {user.id}\n"
               f"{kind}: {chat.title} ({vis})")

    add_log({"ok": now_in, "event": "join" if now_in else "leave", "id": user.id,
             "name": name, "username": uname, "channel": chat.title, "err": ""})
    await notify_admins(context.bot, msg)


# ╔══════════════════════════════════════════════╗
# ║              📥 জয়েন রিকোয়েস্ট                ║
# ╚══════════════════════════════════════════════╝
def markup_from(cfg):
    return rows_to_markup(cfg["buttons"]) if cfg["buttons"] else None


async def send_welcome(bot, chat_id, cfg):
    kb = markup_from(cfg)
    mt, mid, text = cfg["media_type"], cfg["media_id"], cfg["text"]
    kw = dict(chat_id=chat_id, reply_markup=kb)
    if mt == "video":
        await bot.send_video(video=mid, caption=text, parse_mode="HTML", **kw)
    elif mt == "photo":
        await bot.send_photo(photo=mid, caption=text, parse_mode="HTML", **kw)
    elif mt == "animation":
        await bot.send_animation(animation=mid, caption=text, parse_mode="HTML", **kw)
    else:
        await bot.send_message(text=text, parse_mode="HTML", **kw)


async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    req = update.chat_join_request
    cfg = load()
    u = req.from_user
    name = u.full_name
    uname = f"@{u.username}" if u.username else "(username নেই)"
    target = getattr(req, "user_chat_id", None) or u.id
    if is_banned(u.id):
        try:
            await req.decline()
        except Exception as e:
            log.warning("Decline failed: %s", e)
        return await notify_admins(context.bot, f"🚫 ব্যান করা ইউজারের রিকোয়েস্ট বাতিল\n👤 {name} {uname} ({u.id})")
    ok, err = True, ""
    try:
        await send_welcome(context.bot, target, cfg)
        try:
            await send_menu(context.bot, target)
        except Exception:
            pass
    except Exception as e:
        ok, err = False, str(e)
        log.warning("DM failed for %s: %s", u.id, e)
    if cfg["auto_approve"]:
        try:
            await req.approve()
        except Exception as e:
            log.warning("Approve failed: %s", e)

    if ok:
        add_user(u.id)
        remember(u)
    add_log({"ok": ok, "event": "request", "id": u.id, "name": name, "username": uname,
             "channel": req.chat.title, "err": err})
    if ok:
        msg = (f"✅ ইনবক্সে মেসেজ গেছে\n👤 {name}\n🔗 {uname}\n🆔 {u.id}\n📢 {req.chat.title}")
    else:
        msg = (f"❌ ইনবক্সে মেসেজ যায়নি\n👤 {name}\n🔗 {uname}\n🆔 {u.id}\n"
               f"📢 {req.chat.title}\n⚠️ কারণ: {err}")
    await notify_admins(context.bot, msg)


async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/report - শেষ ৩০টা রিকোয়েস্টের সারাংশ"""
    if not is_admin(update):
        return
    if not os.path.exists(LOG_FILE):
        return await update.message.reply_text("এখনও কোনো রিকোয়েস্ট আসেনি।")
    with open(LOG_FILE, encoding="utf-8") as f:
        data = [d for d in json.load(f) if d.get("event", "request") == "request"][-30:]
    if not data:
        return await update.message.reply_text("এখনও কোনো রিকোয়েস্ট আসেনি।")
    sent = [d for d in data if d["ok"]]
    failed = [d for d in data if not d["ok"]]
    lines = [f"📊 শেষ {len(data)}টা: ✅ {len(sent)} | ❌ {len(failed)}"]
    if failed:
        lines.append("\n❌ মেসেজ যায়নি:")
        lines += [f"• {d['name']} {d['username']} ({d['id']})" for d in failed]
    if sent:
        lines.append("\n✅ মেসেজ গেছে:")
        lines += [f"• {d['name']} {d['username']} ({d['id']})" for d in sent]
    await update.message.reply_text("\n".join(lines)[:4000])


# ╔══════════════════════════════════════════════╗
# ║               ⚙️ অ্যাডমিন প্যানেল              ║
# ╚══════════════════════════════════════════════╝
def panel_kb(cfg):
    ap = "✅ ON" if cfg["auto_approve"] else "❌ OFF"
    return InlineKeyboardMarkup([
        [mk_btn("📢 ALL USER BROADCAST", cb="broadcast", style="blue")],
        [mk_btn("✉️ নির্দিষ্ট ইউজারকে মেসেজ", cb="dm_user")],
        [mk_btn("📣 চ্যানেলে পোস্ট করো", cb="post", style="green")],
        [mk_btn("📊 স্ট্যাটস", cb="stats"), mk_btn("📤 ইউজার এক্সপোর্ট", cb="export")],
        [mk_btn("🚫 ব্যান/আনব্যান", cb="ban_help", style="red")],
        [mk_btn("📋 ইউজার মেনু সেটিংস (নিয়ম / এডমিন / VIP)", cb="menu_settings", style="green")],
        [mk_btn("📝 ওয়েলকাম টেক্সট", cb="set_text"), mk_btn("🔘 ওয়েলকাম বাটন", cb="set_buttons")],
        [mk_btn("🔗 এডমিন কন্টাক্ট লিংক", cb="set_contact"), mk_btn("🎬 ভিডিও/ছবি/GIF", cb="set_media")],
        [mk_btn("👮 অ্যাডমিন লিস্ট", cb="admins_list")],
        [mk_btn("💎 প্রিমিয়াম ইমোজি ID বের করো", cb="emojiid", style="blue")],
        [mk_btn(f"Auto Approve: {ap}", cb="toggle_ap",
                style="green" if cfg["auto_approve"] else "red")],
        [mk_btn("👁 প্রিভিউ", cb="preview"), mk_btn("🗑 মিডিয়া মুছো", cb="clear_media")],
    ])


def menu_settings_kb():
    rows = [[mk_btn(s["label"], cb=f"sec:{k}")] for k, s in SECTIONS.items()]
    rows.append([mk_btn("⬅️ প্যানেলে ফিরে যাও", cb="panel_home")])
    return InlineKeyboardMarkup(rows)


def section_kb(sec):
    return InlineKeyboardMarkup([
        [mk_btn("📝 টেক্সট বদলাও", cb=f"sec_text:{sec}", style="blue")],
        [mk_btn("🔘 বাটন যোগ করো", cb=f"sec_btn:{sec}", style="green")],
        [mk_btn("🗑 সব বাটন মুছো", cb=f"sec_clr:{sec}", style="red")],
        [mk_btn("👁 প্রিভিউ", cb=f"sec_prev:{sec}")],
        [mk_btn("⬅️ পেছনে", cb="menu_settings")],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        if is_banned(update.effective_user.id):
            return
        add_user(update.effective_user.id)
        remember(update.effective_user)
        await send_welcome(context.bot, update.effective_chat.id, load())
        await send_menu(context.bot, update.effective_chat.id)
        return
    context.user_data.pop("await", None)
    await update.message.reply_text(f"⚙️ {BRAND} অ্যাডমিন প্যানেল", reply_markup=panel_kb(load()))


def build_admins_text():
    cfg = load()
    lines = ["👮 <b>অ্যাডমিন লিস্ট</b>\n"]
    for i, aid in enumerate(ADMIN_IDS, 1):
        lines.append(f"👑 মূল অ্যাডমিন {i}: <code>{aid}</code>")
    for aid in cfg.get("extra_admins", []):
        lines.append(f"🔹 এক্সট্রা অ্যাডমিন: <code>{aid}</code>")
    if not ADMIN_2_ID:
        lines.append("\n⚠️ দ্বিতীয় অ্যাডমিন সেট করা নেই। কোডে ADMIN_2_ID বসাও।")
    lines.append(f"\n📊 মোট অ্যাডমিন: {len(all_admins())}")
    return "\n".join(lines)


async def admins_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admins - সব অ্যাডমিনের লিস্ট"""
    if not is_admin(update):
        return
    await update.message.reply_text(build_admins_text(), parse_mode="HTML")


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if not is_admin(update):
        return await q.answer("Not allowed", show_alert=True)
    await q.answer()
    cfg = load()
    d = q.data
    prompts = {
        "set_contact": ("contact", "🔗 কানেক্টেড এডমিনদের টেলিগ্রাম @username বা লিংক পাঠাও।\n\nদুইজনের হলে কমা বা স্পেস দিয়ে লেখো, যেমন:\n@admin1, @admin2\n\nইউজাররা 'কানেক্টেড এডমিন' মেনুতে প্রতিজনের জন্য আলাদা ইনবক্স বাটন দেখবে।"),
        "set_text": ("text", "📝 নতুন ওয়েলকাম মেসেজ টেক্সট পাঠাও (bold/italic ফরম্যাটিং সাপোর্টেড)।"),
        "set_media": ("media", "🎬 একটা ভিডিও / ছবি / GIF পাঠাও।"),
        "set_buttons": ("buttons", "🔘 ওয়েলকাম মেসেজের নিচের বাটন।\n\n" + BTN_HELP),
    }
    if d in prompts:
        context.user_data["await"] = prompts[d][0]
        await q.message.reply_text(prompts[d][1])

    # ---------- ইউজার মেনু সেটিংস ----------
    elif d == "menu_settings":
        context.user_data.pop("await", None)
        await q.edit_message_text(
            "📋 ইউজার মেনু সেটিংস\n\nকোন মেনুর টেক্সট/বাটন বদলাতে চাও?",
            reply_markup=menu_settings_kb())
    elif d == "panel_home":
        context.user_data.pop("await", None)
        await q.edit_message_text(f"⚙️ {BRAND} অ্যাডমিন প্যানেল", reply_markup=panel_kb(cfg))
    elif d.startswith("sec:"):
        sec = d[4:]
        if sec in SECTIONS:
            count = sum(len(r) for r in norm_rows(cfg.get(SECTIONS[sec]["btn_key"], [])))
            await q.edit_message_text(
                f"{SECTIONS[sec]['label']}\n\n"
                f"🔘 এখন বাটন আছে: {count}টা\n"
                f"ইউজার এই মেনুতে চাপলে টেক্সট ও তার নিচে বাটনগুলো দেখবে।",
                reply_markup=section_kb(sec))
    elif d.startswith("sec_text:"):
        sec = d.split(":", 1)[1]
        context.user_data["await"] = d
        await q.message.reply_text(
            f"📝 {SECTIONS[sec]['label']} এর নতুন টেক্সট পাঠাও (bold/italic ফরম্যাটিং সাপোর্টেড)।\n\nবাতিল: /cancel")
    elif d.startswith("sec_btn:"):
        sec = d.split(":", 1)[1]
        context.user_data["await"] = d
        await q.message.reply_text(f"{SECTIONS[sec]['label']}\n\n" + BTN_HELP)
    elif d.startswith("sec_clr:"):
        sec = d.split(":", 1)[1]
        if sec in SECTIONS:
            cfg[SECTIONS[sec]["btn_key"]] = []
            save(cfg)
            await q.message.reply_text(f"🗑 {SECTIONS[sec]['label']} এর সব বাটন মুছে ফেলা হয়েছে ✅")
    elif d.startswith("sec_prev:"):
        sec = d.split(":", 1)[1]
        if sec in SECTIONS:
            await send_section(context.bot, q.message.chat_id, sec, cfg)

    # ---------- বাকি অপশন ----------
    elif d == "admins_list":
        await q.message.reply_text(build_admins_text(), parse_mode="HTML")
    elif d == "broadcast":
        context.user_data["await"] = "broadcast"
        await q.message.reply_text(BROADCAST_INFO + f"\n👥 মোট ইউজার: {len(load_users())}\n\nবাতিল করতে /cancel")
    elif d == "dm_user":
        context.user_data["await"] = "dm_target"
        await q.message.reply_text("ইউজারের @username অথবা ID পাঠাও।\n(শুধু যাদের সাথে বটের আগে যোগাযোগ হয়েছে)\n\nবাতিল: /cancel")
    elif d == "post":
        chs = load_channels()
        if not chs:
            await q.message.reply_text("কোনো চ্যানেল নেই। বটকে চ্যানেলে অ্যাডমিন করো (Post Messages পারমিশন সহ), অটো যোগ হবে।\nঅথবা: /addchannel @channel_username")
        else:
            kb = [[InlineKeyboardButton(t or cid, callback_data=f"pch:{cid}")] for cid, t in chs.items()]
            await q.message.reply_text("📣 কোন চ্যানেলে পোস্ট করবে?", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("pch:"):
        cid = d[4:]
        context.user_data["post"] = {"chat": int(cid), "title": load_channels().get(cid, cid)}
        context.user_data["await"] = "post_content"
        await q.message.reply_text(
            f"✅ চ্যানেল: {context.user_data['post']['title']}\n\n📝 এখন পোস্টটা পাঠাও (টেক্সট / ছবি / ভিডিও / ফাইল / ভয়েস, ক্যাপশনসহ)।\nবাতিল: /cancel")
    elif d in ("post_go", "post_pin"):
        post = context.user_data.pop("post", None)
        if not post or "mid" not in post:
            return await q.message.reply_text("কিছু পোস্ট করার জন্য তৈরি নেই।")
        try:
            sent = await context.bot.copy_message(
                post["chat"], post["src"], post["mid"], reply_markup=post.get("kb"))
            note = f"✅ পোস্ট হয়েছে: {post['title']}"
            if d == "post_pin":
                try:
                    await context.bot.pin_chat_message(post["chat"], sent.message_id)
                    note += " 📌 (পিন করা)"
                except Exception as e:
                    note += f"\n⚠️ পিন হয়নি: {e}"
            await q.message.reply_text(note)
        except Exception as e:
            await q.message.reply_text(f"❌ পোস্ট হয়নি: {e}\n(বটের 'Post Messages' পারমিশন আছে কি দেখো)")
    elif d == "post_cancel":
        context.user_data.pop("post", None)
        await q.message.reply_text("❌ পোস্ট বাতিল।", reply_markup=panel_kb(load()))
    elif d == "emojiid":
        context.user_data["await"] = "emojiid"
        await q.message.reply_text("💎 যেকোনো মেসেজে প্রিমিয়াম ইমোজি দিয়ে পাঠাও (Premium অ্যাকাউন্ট থেকে), আমি তাদের ID বলে দেব।\n\nবাতিল: /cancel")
    elif d == "stats":
        await q.message.reply_text(build_stats())
    elif d == "export":
        await send_export(context.bot, q.message.chat_id)
    elif d == "ban_help":
        await q.message.reply_text("🚫 ব্যান: /ban @username অথবা /ban ID\n✅ আনব্যান: /unban @username অথবা /unban ID\n\nব্যান করা ইউজার বটের মেনু/ব্রডকাস্ট পাবে না, আর জয়েন রিকোয়েস্ট অটো বাতিল হবে।")
    elif d == "toggle_ap":
        cfg["auto_approve"] = not cfg["auto_approve"]
        save(cfg)
        await q.edit_message_reply_markup(panel_kb(cfg))
    elif d == "clear_media":
        cfg["media_type"] = cfg["media_id"] = None
        save(cfg)
        await q.message.reply_text("মিডিয়া মুছে ফেলা হয়েছে ✅")
    elif d == "preview":
        await send_welcome(context.bot, q.message.chat_id, cfg)


BROADCAST_INFO = f"""👑 ━━━━━━━━━━━━━━━━━━━━━━━━━ 👑
   📢 {BRAND} BROADCAST MODE 📢
👑 ━━━━━━━━━━━━━━━━━━━━━━━━━ 👑

📝 এখন যেকোনো মেসেজ পাঠান:
• যেকোনো টেক্সট / লিংক / ক্যাপশন
• যেকোনো ছবি (Photo)
• যেকোনো ভিডিও (Video)
• যেকোনো ফাইল / ডকুমেন্ট (Document)
• যেকোনো ভয়েস / অডিও বা স্টিকার

(আপনি যা পাঠাবেন তা হুবহু সকল ইউজারের কাছে কপি হয়ে চলে যাবে)"""


async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m = update.message
    banned = set(load().get("banned", []))
    users = [x for x in load_users() if x not in banned]
    status = await m.reply_text(f"⏳ পাঠানো শুরু... (মোট {len(users)} জন)")
    ok = fail = 0
    for uid in users:
        try:
            await context.bot.copy_message(uid, m.chat_id, m.message_id)
            ok += 1
        except RetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
            try:
                await context.bot.copy_message(uid, m.chat_id, m.message_id)
                ok += 1
            except Exception:
                fail += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    await status.edit_text(f"✅ ব্রডকাস্ট শেষ\n📨 সফল: {ok}\n❌ ব্যর্থ: {fail}")


def build_stats():
    users = load_users()
    cfg = load()
    data = []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as f:
            data = json.load(f)
    reqs = [d for d in data if d.get("event", "request") == "request"]
    joins = sum(1 for d in data if d.get("event") == "join")
    leaves = sum(1 for d in data if d.get("event") == "leave")
    today = date.today()
    t = [d for d in reqs if date.fromtimestamp(d.get("ts", 0)) == today]
    ok = sum(1 for d in reqs if d["ok"])
    rate = f"{ok * 100 // len(reqs)}%" if reqs else "—"
    return (
        f"📊 {BRAND} স্ট্যাটিস্টিক্স\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"👥 মোট ইউজার: {len(users)}\n"
        f"📥 মোট জয়েন রিকোয়েস্ট: {len(reqs)}\n"
        f"✅ মেসেজ গেছে: {ok} | ❌ যায়নি: {len(reqs) - ok}\n"
        f"📈 সফলতার হার: {rate}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🟢 মোট জয়েন: {joins} | 🔴 মোট লিভ: {leaves}\n"
        f"📅 আজকের রিকোয়েস্ট: {len(t)} (✅ {sum(1 for d in t if d['ok'])})\n"
        f"🚫 ব্যান করা: {len(cfg.get('banned', []))}\n"
        f"👮 অ্যাডমিন: {len(all_admins())}\n"
        f"🤖 অটো অ্যাপ্রুভ: {'ON' if cfg['auto_approve'] else 'OFF'}"
    )


async def send_export(bot, chat_id):
    meta = {}
    if os.path.exists(META_FILE):
        with open(META_FILE, encoding="utf-8") as f:
            meta = json.load(f)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "name", "username"])
    for uid in sorted(load_users()):
        d = meta.get(str(uid), {})
        w.writerow([uid, d.get("name", ""), d.get("username", "")])
    data = io.BytesIO(("\ufeff" + buf.getvalue()).encode("utf-8"))
    data.name = "users.csv"
    await bot.send_document(chat_id, data, caption=f"👥 মোট {len(load_users())} জন")


# ╔══════════════════════════════════════════════╗
# ║                 🛠 কমান্ডসমূহ                  ║
# ╚══════════════════════════════════════════════╝
async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    unban = update.message.text.lower().startswith("/unban")
    if not context.args:
        return await update.message.reply_text("ব্যবহার: /ban @username বা /ban ID")
    uid = find_user(context.args[0])
    if not uid:
        return await update.message.reply_text("❌ ইউজার পাওয়া যায়নি (লিস্টে নেই)। ID দিয়ে চেষ্টা করো।")
    cfg = load()
    if unban and uid in cfg["banned"]:
        cfg["banned"].remove(uid)
    elif not unban and uid not in cfg["banned"] and uid not in all_admins():
        cfg["banned"].append(uid)
    save(cfg)
    await update.message.reply_text(("✅ আনব্যান: " if unban else "🚫 ব্যান: ") + str(uid))


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update):
        await update.message.reply_text(build_stats())


async def add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addchannel @username  অথবা  /addchannel -100123..."""
    if not is_admin(update):
        return
    if not context.args:
        return await update.message.reply_text("ব্যবহার: /addchannel @channel_username")
    try:
        chat = await context.bot.get_chat(context.args[0])
        chs = load_channels()
        chs[str(chat.id)] = chat.title
        save_channels(chs)
        await update.message.reply_text(f"✅ যোগ হয়েছে: {chat.title}")
    except Exception as e:
        await update.message.reply_text(f"❌ পাওয়া যায়নি: {e}\n(বট ওই চ্যানেলে অ্যাডমিন আছে কি দেখো)")


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/id - নিজের ইউজার আইডি দেখাবে"""
    await update.message.reply_text(f"🆔 আপনার ইউজার আইডি: {update.effective_user.id}")


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin - অ্যাডমিন প্যানেল"""
    if not is_admin(update):
        return
    context.user_data.pop("await", None)
    await update.message.reply_text(f"⚙️ {BRAND} অ্যাডমিন প্যানেল", reply_markup=panel_kb(load()))


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addadmin 123456789 (শুধু দুইজন মূল অ্যাডমিন)"""
    if not is_owner(update) or not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("ব্যবহার: /addadmin ইউজার_আইডি (শুধু মূল অ্যাডমিনরা পারবে)")
    cfg = load()
    uid = int(context.args[0])
    if uid in ADMIN_IDS:
        return await update.message.reply_text("এই আইডি আগে থেকেই মূল অ্যাডমিন।")
    if uid not in cfg["extra_admins"]:
        cfg["extra_admins"].append(uid)
        save(cfg)
    await update.message.reply_text(f"✅ {uid} এখন অ্যাডমিন।")


async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/removeadmin 123456789 (শুধু দুইজন মূল অ্যাডমিন)"""
    if not is_owner(update) or not context.args or not context.args[0].isdigit():
        return await update.message.reply_text("ব্যবহার: /removeadmin ইউজার_আইডি (শুধু মূল অ্যাডমিনরা পারবে)")
    cfg = load()
    uid = int(context.args[0])
    if uid in ADMIN_IDS:
        return await update.message.reply_text("❌ মূল অ্যাডমিনকে সরানো যাবে না (কোডে ADMIN_1_ID / ADMIN_2_ID বদলাতে হবে)।")
    if uid in cfg["extra_admins"]:
        cfg["extra_admins"].remove(uid)
        save(cfg)
    await update.message.reply_text(f"🗑 {uid} কে অ্যাডমিন থেকে সরানো হয়েছে।")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update):
        context.user_data.pop("await", None)
        await update.message.reply_text("বাতিল করা হয়েছে।", reply_markup=panel_kb(load()))


# ╔══════════════════════════════════════════════╗
# ║      ✍️ অ্যাডমিনের পাঠানো মেসেজ হ্যান্ডলার      ║
# ╚══════════════════════════════════════════════╝
async def on_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    mode = context.user_data.get("await")
    if not mode:
        return

    # ---------- ইউজার মেনুর টেক্সট / বাটন ----------
    if mode.startswith(("sec_text:", "sec_btn:")):
        kind, sec = mode.split(":", 1)
        m = update.message
        if sec not in SECTIONS:
            context.user_data.pop("await", None)
            return
        cfg = load()
        sc = SECTIONS[sec]
        if kind == "sec_text":
            if not m.text:
                return await m.reply_text("শুধু টেক্সট পাঠাও।")
            cfg[sc["text_key"]] = m.text_html
        else:
            if not m.text:
                return await m.reply_text("বাটনের লেখা টেক্সট আকারে পাঠাও।")
            if m.text.strip().lower() == "clear":
                cfg[sc["btn_key"]] = []
            else:
                added = parse_rows_msg(m)
                if not added:
                    return await m.reply_text("❌ কোনো বাটন পাইনি। ফরম্যাট: বাটনের নাম | https://লিংক")
                cfg[sc["btn_key"]] = norm_rows(cfg.get(sc["btn_key"], [])) + added
        save(cfg)
        context.user_data.pop("await", None)
        await m.reply_text(f"সেভ হয়েছে ✅  ({sc['label']})\n\n👇 ইউজার এভাবে দেখবে:")
        await send_section(context.bot, m.chat_id, sec, cfg)
        return await m.reply_text("আরও বদলাতে চাইলে:", reply_markup=section_kb(sec))

    if mode == "emojiid":
        m = update.message
        ents = list(m.entities or []) + list(m.caption_entities or [])
        ids = [e.custom_emoji_id for e in ents if e.type == "custom_emoji"]
        context.user_data.pop("await", None)
        if not ids:
            return await m.reply_text("❌ কোনো প্রিমিয়াম ইমোজি পাইনি। প্রিমিয়াম ইমোজি দিয়ে আবার চেষ্টা করো।")
        return await m.reply_text("💎 ইমোজি ID:\n" + "\n".join(ids))
    if mode == "post_content":
        m = update.message
        context.user_data["post"].update({"src": m.chat_id, "mid": m.message_id})
        context.user_data["await"] = "post_buttons"
        return await m.reply_text(
            "🔘 পোস্টের নিচে বাটন চাইলে পাঠাও।\n\n" + BTN_HELP.replace("সব মুছতে লেখো: clear", "বাটন না চাইলে লেখো: skip"))
    if mode == "post_buttons":
        m = update.message
        txt = (m.text or "").strip()
        kb = None if txt.lower() == "skip" else parse_button_rows(m)
        if kb is None and txt.lower() != "skip":
            return await m.reply_text("❌ বাটন বুঝতে পারিনি। ফরম্যাট: নাম | https://link  (অথবা skip)")
        post = context.user_data["post"]
        post["kb"] = kb
        context.user_data.pop("await", None)
        await m.reply_text("👁 প্রিভিউ:")
        await context.bot.copy_message(m.chat_id, post["src"], post["mid"], reply_markup=kb)
        return await m.reply_text(
            f"📣 চ্যানেল: {post['title']}\nপোস্ট করবে?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ পোস্ট করো", callback_data="post_go")],
                [InlineKeyboardButton("📌 পোস্ট + পিন", callback_data="post_pin")],
                [InlineKeyboardButton("❌ বাতিল", callback_data="post_cancel")],
            ]))
    if mode == "dm_target":
        uid = find_user(update.message.text or "")
        if not uid:
            return await update.message.reply_text("❌ এই ইউজার বটের লিস্টে নেই। আবার চেষ্টা করো বা /cancel।")
        context.user_data["dm_uid"] = uid
        context.user_data["await"] = "dm_msg"
        return await update.message.reply_text("✅ পেয়েছি। এখন যেকোনো মেসেজ (টেক্সট/ছবি/ভিডিও/ফাইল) পাঠাও।")
    if mode == "dm_msg":
        context.user_data.pop("await", None)
        uid = context.user_data.pop("dm_uid")
        try:
            await context.bot.copy_message(uid, update.message.chat_id, update.message.message_id)
            return await update.message.reply_text("✅ মেসেজ পাঠানো হয়েছে।")
        except Exception as e:
            return await update.message.reply_text(f"❌ পাঠানো যায়নি: {e}")
    if mode == "broadcast":
        context.user_data.pop("await", None)
        return await do_broadcast(update, context)

    # ---------- ওয়েলকাম টেক্সট / বাটন / মিডিয়া / কন্টাক্ট ----------
    m = update.message
    cfg = load()
    if mode == "text" and m.text:
        cfg["text"] = m.text_html
    elif mode == "contact" and m.text:
        cfg["contact"] = m.text.strip()
    elif mode == "media":
        if m.video:
            cfg["media_type"], cfg["media_id"] = "video", m.video.file_id
        elif m.photo:
            cfg["media_type"], cfg["media_id"] = "photo", m.photo[-1].file_id
        elif m.animation:
            cfg["media_type"], cfg["media_id"] = "animation", m.animation.file_id
        else:
            return await m.reply_text("ভিডিও/ছবি/GIF পাঠাও।")
    elif mode == "buttons" and m.text:
        if m.text.strip().lower() == "clear":
            cfg["buttons"] = []
        else:
            added = parse_rows_msg(m)
            if not added:
                return await m.reply_text("❌ কোনো বাটন পাইনি। ফরম্যাট: নাম | https://link")
            cfg["buttons"] = norm_rows(cfg["buttons"]) + added
    else:
        return
    save(cfg)
    context.user_data.pop("await", None)
    await m.reply_text("সেভ হয়েছে ✅", reply_markup=panel_kb(cfg))


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Unhandled error", exc_info=context.error)


def main():
    import telegram
    log.info("python-telegram-bot version: %s", telegram.__version__)
    log.info("মূল অ্যাডমিন: %s | ডাটা ফোল্ডার: %s", ADMIN_IDS, DATA_DIR)
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(on_error)
    app.add_handler(ChatJoinRequestHandler(on_join_request))
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("panel", start))
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("admins", admins_cmd))
    app.add_handler(CommandHandler("id", my_id))
    app.add_handler(CommandHandler("addchannel", add_channel))
    # বট নিজে অ্যাডমিন হলো/সরলো
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    # অন্য কেউ জয়েন/লিভ করলে (পাবলিক + প্রাইভেট চ্যানেল/গ্রুপ)
    app.add_handler(ChatMemberHandler(on_chat_member, ChatMemberHandler.CHAT_MEMBER))
    app.add_handler(CommandHandler(["ban", "unban"], ban_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("addadmin", add_admin))
    app.add_handler(CommandHandler("removeadmin", remove_admin))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(
        filters.ChatType.PRIVATE & filters.Regex(MENU_REGEX), handle_menu))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, on_admin_message))
    # chat_member আপডেট পেতে ALL_TYPES দেওয়া জরুরি
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
