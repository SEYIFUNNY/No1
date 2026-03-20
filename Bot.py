import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
import requests
import time
import threading
import re
import os
import json
import pyotp
import sqlite3
from datetime import datetime
from collections import deque, Counter
from flask import Flask

# ================= কনফিগারেশন =================
BOT_TOKEN = "8619583201:AAHg0WXP7TLHUclu2dqfqnzPnb1bgMXf1rU"
ADMIN_ID = 6358549806
GROUP_ID = -1002939166490 

STEX_EMAIL = "akinlabipraisegideon@gmail.com"
STEX_PASSWORD = "seyi4947"
STEX_LOGIN_URL = "https://v1mknetwork.com/login.php"

# ================= গ্লোবাল ভেরিয়েবল =================
bot = telebot.TeleBot(BOT_TOKEN)
AUTH_TOKEN = ""
posted_console_ids = deque(maxlen=1000)
# recent_fb_logs এখন (timestamp, country_code, range_val) স্টোর করবে 
recent_fb_logs = deque() 
last_hot_broadcast = {} # ব্রডকাস্ট স্প্যাম কমানোর জন্য
active_otp_checks = {} 
db_lock = threading.Lock()

app = Flask(__name__)
@app.route('/')
def home(): return "Bot is running perfectly on Render!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# ================= ডিকশনারি (Country Data) =================
COUNTRY_CODES = {
    "1": "US", "7": "RU", "20": "EG", "27": "ZA", "30": "GR", "31": "NL", "32": "BE", "33": "FR", "34": "ES", "36": "HU", 
    "39": "IT", "40": "RO", "41": "CH", "43": "AT", "44": "GB", "45": "DK", "46": "SE", "47": "NO", "48": "PL", "49": "DE", 
    "51": "PE", "52": "MX", "53": "CU", "54": "AR", "55": "BR", "56": "CL", "57": "CO", "58": "VE", "60": "MY", "61": "AU", 
    "62": "ID", "63": "PH", "64": "NZ", "65": "SG", "66": "TH", "82": "KR", "84": "VN", "86": "CN", "90": "TR", "91": "IN", 
    "92": "PK", "93": "AF", "94": "LK", "95": "MM", "98": "IR", "211": "SS", "212": "MA", "213": "DZ", "216": "TN", "218": "LY", 
    "220": "GM", "221": "SN", "222": "MR", "223": "ML", "224": "GN", "225": "CI", "226": "BF", "227": "NE", "228": "TG", "229": "BJ", 
    "230": "MU", "231": "LR", "232": "SL", "233": "GH", "234": "NG", "235": "TD", "236": "CF", "237": "CM", "238": "CV", "239": "ST", 
    "240": "GQ", "241": "GA", "242": "CG", "243": "CD", "244": "AO", "245": "GW", "246": "IO", "249": "SD", "250": "RW", "251": "ET", 
    "252": "SO", "253": "DJ", "254": "KE", "255": "TZ", "256": "UG", "257": "BI", "258": "MZ", "260": "ZM", "261": "MG", "262": "RE", 
    "263": "ZW", "264": "NA", "265": "MW", "266": "LS", "267": "BW", "268": "SZ", "269": "KM", "290": "SH", "291": "ER", "297": "AW", 
    "298": "FO", "299": "GL", "350": "GI", "351": "PT", "352": "LU", "353": "IE", "354": "IS", "355": "AL", "356": "MT", "357": "CY", 
    "358": "FI", "359": "BG", "370": "LT", "371": "LV", "372": "EE", "373": "MD", "374": "AM", "375": "BY", "376": "AD", "377": "MC", 
    "378": "SM", "380": "UA", "381": "RS", "382": "ME", "385": "HR", "386": "SI", "387": "BA", "389": "MK", "420": "CZ", "421": "SK", 
    "423": "LI", "500": "FK", "501": "BZ", "502": "GT", "503": "SV", "504": "HN", "505": "NI", "506": "CR", "507": "PA", "508": "PM", 
    "509": "HT", "590": "GP", "591": "BO", "592": "GY", "593": "EC", "594": "GF", "595": "PY", "596": "MQ", "597": "SR", "598": "UY", 
    "599": "CW", "670": "TL", "672": "NF", "673": "BN", "674": "NR", "675": "PG", "676": "TO", "677": "SB", "678": "VU", "679": "FJ", 
    "680": "PW", "681": "WF", "682": "CK", "683": "NU", "685": "WS", "686": "KI", "687": "NC", "688": "TV", "689": "PF", "690": "TK", 
    "691": "FM", "692": "MH", "850": "KP", "852": "HK", "853": "MO", "855": "KH", "856": "LA", "880": "BD", "886": "TW", "960": "MV", 
    "961": "LB", "962": "JO", "963": "SY", "964": "IQ", "965": "KW", "966": "SA", "967": "YE", "968": "OM", "970": "PS", "971": "AE", 
    "972": "IL", "973": "BH", "974": "QA", "975": "BT", "976": "MN", "977": "NP", "992": "TJ", "993": "TM", "994": "AZ", "995": "GE", 
    "996": "KG", "998": "UZ"
}

SHORT_NAMES = {
    "AF": {"name": "Afghanistan", "flag": "🇦🇫"}, "AL": {"name": "Albania", "flag": "🇦🇱"}, "DZ": {"name": "Algeria", "flag": "🇩🇿"},
    "AD": {"name": "Andorra", "flag": "🇦🇩"}, "AO": {"name": "Angola", "flag": "🇦🇴"}, "AR": {"name": "Argentina", "flag": "🇦🇷"},
    "AM": {"name": "Armenia", "flag": "🇦🇲"}, "AU": {"name": "Australia", "flag": "🇦🇺"}, "AT": {"name": "Austria", "flag": "🇦🇹"},
    "AZ": {"name": "Azerbaijan", "flag": "🇦🇿"}, "BS": {"name": "Bahamas", "flag": "🇧🇸"}, "BH": {"name": "Bahrain", "flag": "🇧🇭"},
    "BD": {"name": "Bangladesh", "flag": "🇧🇩"}, "BB": {"name": "Barbados", "flag": "🇧🇧"}, "BY": {"name": "Belarus", "flag": "🇧🇾"},
    "BE": {"name": "Belgium", "flag": "🇧🇪"}, "BZ": {"name": "Belize", "flag": "🇧🇿"}, "BJ": {"name": "Benin", "flag": "🇧🇯"},
    "BT": {"name": "Bhutan", "flag": "🇧🇹"}, "BO": {"name": "Bolivia", "flag": "🇧🇴"}, "BA": {"name": "Bosnia", "flag": "🇧🇦"},
    "BW": {"name": "Botswana", "flag": "🇧🇼"}, "BR": {"name": "Brazil", "flag": "🇧🇷"}, "BN": {"name": "Brunei", "flag": "🇧🇳"},
    "BG": {"name": "Bulgaria", "flag": "🇧🇬"}, "BF": {"name": "Burkina Faso", "flag": "🇧🇫"}, "BI": {"name": "Burundi", "flag": "🇧🇮"},
    "KH": {"name": "Cambodia", "flag": "🇰🇭"}, "CM": {"name": "Cameroon", "flag": "🇨🇲"}, "CA": {"name": "Canada", "flag": "🇨🇦"},
    "CV": {"name": "Cape Verde", "flag": "🇨🇻"}, "CF": {"name": "Central African Rep", "flag": "🇨🇫"}, "TD": {"name": "Chad", "flag": "🇹🇩"},
    "CL": {"name": "Chile", "flag": "🇨🇱"}, "CN": {"name": "China", "flag": "🇨🇳"}, "CO": {"name": "Colombia", "flag": "🇨🇴"},
    "KM": {"name": "Comoros", "flag": "🇰🇲"}, "CG": {"name": "Congo", "flag": "🇨🇬"}, "CD": {"name": "Congo DRC", "flag": "🇨🇩"},
    "CI": {"name": "Ivory Coast", "flag": "🇨🇮"},
    "CR": {"name": "Costa Rica", "flag": "🇨🇷"}, "HR": {"name": "Croatia", "flag": "🇭🇷"}, "CU": {"name": "Cuba", "flag": "🇨🇺"},
    "CY": {"name": "Cyprus", "flag": "🇨🇾"}, "CZ": {"name": "Czech Republic", "flag": "🇨🇿"}, "DK": {"name": "Denmark", "flag": "🇩🇰"},
    "DJ": {"name": "Djibouti", "flag": "🇩🇯"}, "DM": {"name": "Dominica", "flag": "🇩🇲"}, "DO": {"name": "Dominican Rep", "flag": "🇩🇴"},
    "EC": {"name": "Ecuador", "flag": "🇪🇨"}, "EG": {"name": "Egypt", "flag": "🇪🇬"}, "SV": {"name": "El Salvador", "flag": "🇸🇻"},
    "GQ": {"name": "Equatorial Guinea", "flag": "🇬🇶"}, "ER": {"name": "Eritrea", "flag": "🇪🇷"}, "EE": {"name": "Estonia", "flag": "🇪🇪"},
    "ET": {"name": "Ethiopia", "flag": "🇪🇹"}, "FJ": {"name": "Fiji", "flag": "🇫🇯"}, "FI": {"name": "Finland", "flag": "🇫🇮"},
    "FR": {"name": "France", "flag": "🇫🇷"}, "GA": {"name": "Gabon", "flag": "🇬🇦"}, "GM": {"name": "Gambia", "flag": "🇬🇲"},
    "GE": {"name": "Georgia", "flag": "🇬🇪"}, "DE": {"name": "Germany", "flag": "🇩🇪"}, "GH": {"name": "Ghana", "flag": "🇬🇭"},
    "GR": {"name": "Greece", "flag": "🇬🇷"}, "GD": {"name": "Grenada", "flag": "🇬🇩"}, "GT": {"name": "Guatemala", "flag": "🇬🇹"},
    "GN": {"name": "Guinea", "flag": "🇬🇳"}, "GW": {"name": "Guinea-Bissau", "flag": "🇬🇼"}, "GY": {"name": "Guyana", "flag": "🇬🇾"},
    "HT": {"name": "Haiti", "flag": "🇭🇹"}, "HN": {"name": "Honduras", "flag": "🇭🇳"}, "HU": {"name": "Hungary", "flag": "🇭🇺"},
    "IS": {"name": "Iceland", "flag": "🇮🇸"}, "IN": {"name": "India", "flag": "🇮🇳"}, "ID": {"name": "Indonesia", "flag": "🇮🇩"},
    "IR": {"name": "Iran", "flag": "🇮🇷"}, "IQ": {"name": "Iraq", "flag": "🇮🇶"}, "IE": {"name": "Ireland", "flag": "🇮🇪"},
    "IL": {"name": "Israel", "flag": "🇮🇱"}, "IT": {"name": "Italy", "flag": "🇮🇹"}, "JM": {"name": "Jamaica", "flag": "🇯🇲"},
    "JP": {"name": "Japan", "flag": "🇯🇵"}, "JO": {"name": "Jordan", "flag": "🇯🇴"}, "KZ": {"name": "Kazakhstan", "flag": "🇰🇿"},
    "KE": {"name": "Kenya", "flag": "🇰🇪"}, "KI": {"name": "Kiribati", "flag": "🇰🇮"}, "KW": {"name": "Kuwait", "flag": "🇰🇼"},
    "KG": {"name": "Kyrgyzstan", "flag": "🇰🇬"}, "LA": {"name": "Laos", "flag": "🇱🇦"}, "LB": {"name": "Lebanon", "flag": "🇱🇧"},
    "LS": {"name": "Lesotho", "flag": "🇱🇸"}, "LR": {"name": "Liberia", "flag": "🇱🇷"}, "LY": {"name": "Libya", "flag": "🇱🇾"},
    "LI": {"name": "Liechtenstein", "flag": "🇱🇮"}, "LT": {"name": "Lithuania", "flag": "🇱🇹"}, "LU": {"name": "Luxembourg", "flag": "🇱🇺"},
    "MG": {"name": "Madagascar", "flag": "🇲🇬"}, "MW": {"name": "Malawi", "flag": "🇲🇼"}, "MY": {"name": "Malaysia", "flag": "🇲🇾"},
    "MV": {"name": "Maldives", "flag": "🇲🇻"}, "ML": {"name": "Mali", "flag": "🇲🇱"}, "MT": {"name": "Malta", "flag": "🇲🇹"},
    "MH": {"name": "Marshall Islands", "flag": "🇲🇭"}, "MR": {"name": "Mauritania", "flag": "🇲🇷"}, "MU": {"name": "Mauritius", "flag": "🇲🇺"},
    "MX": {"name": "Mexico", "flag": "🇲🇽"}, "FM": {"name": "Micronesia", "flag": "🇫🇲"}, "MD": {"name": "Moldova", "flag": "🇲🇩"},
    "MC": {"name": "Monaco", "flag": "🇲🇨"}, "MN": {"name": "Mongolia", "flag": "🇲🇳"}, "ME": {"name": "Montenegro", "flag": "🇲🇪"},
    "MA": {"name": "Morocco", "flag": "🇲🇦"}, "MZ": {"name": "Mozambique", "flag": "🇲🇿"}, "MM": {"name": "Myanmar", "flag": "🇲🇲"},
    "NA": {"name": "Namibia", "flag": "🇳🇦"}, "NR": {"name": "Nauru", "flag": "🇳🇷"}, "NP": {"name": "Nepal", "flag": "🇳🇵"},
    "NL": {"name": "Netherlands", "flag": "🇳🇱"}, "NZ": {"name": "New Zealand", "flag": "🇳🇿"}, "NI": {"name": "Nicaragua", "flag": "🇳🇮"},
    "NE": {"name": "Niger", "flag": "🇳🇪"}, "NG": {"name": "Nigeria", "flag": "🇳🇬"}, "KP": {"name": "North Korea", "flag": "🇰🇵"},
    "MK": {"name": "North Macedonia", "flag": "🇲🇰"}, "NO": {"name": "Norway", "flag": "🇳🇴"}, "OM": {"name": "Oman", "flag": "🇴🇲"},
    "PK": {"name": "Pakistan", "flag": "🇵🇰"}, "PW": {"name": "Palau", "flag": "🇵🇼"}, "PA": {"name": "Panama", "flag": "🇵🇦"},
    "PG": {"name": "Papua New Guinea", "flag": "🇵🇬"}, "PY": {"name": "Paraguay", "flag": "🇵🇾"}, "PE": {"name": "Peru", "flag": "🇵🇪"},
    "PH": {"name": "Philippines", "flag": "🇵🇭"}, "PL": {"name": "Poland", "flag": "🇵🇱"}, "PT": {"name": "Portugal", "flag": "🇵🇹"},
    "QA": {"name": "Qatar", "flag": "🇶🇦"}, "RO": {"name": "Romania", "flag": "🇷🇴"}, "RU": {"name": "Russia", "flag": "🇷🇺"},
    "RW": {"name": "Rwanda", "flag": "🇷🇼"}, "KN": {"name": "Saint Kitts", "flag": "🇰🇳"}, "LC": {"name": "Saint Lucia", "flag": "🇱🇨"},
    "VC": {"name": "Saint Vincent", "flag": "🇻🇨"}, "WS": {"name": "Samoa", "flag": "🇼🇸"}, "SM": {"name": "San Marino", "flag": "🇸🇲"},
    "SA": {"name": "Saudi Arabia", "flag": "🇸🇦"}, "SN": {"name": "Senegal", "flag": "🇸🇳"}, "RS": {"name": "Serbia", "flag": "🇷🇸"},
    "SC": {"name": "Seychelles", "flag": "🇸🇨"}, "SL": {"name": "Sierra Leone", "flag": "🇸🇱"}, "SG": {"name": "Singapore", "flag": "🇸🇬"},
    "SK": {"name": "Slovakia", "flag": "🇸🇰"}, "SI": {"name": "Slovenia", "flag": "🇸🇮"}, "SB": {"name": "Solomon Islands", "flag": "🇸🇧"},
    "SO": {"name": "Somalia", "flag": "🇸🇴"}, "ZA": {"name": "South Africa", "flag": "🇿🇦"}, "KR": {"name": "South Korea", "flag": "🇰🇷"},
    "SS": {"name": "South Sudan", "flag": "🇸🇸"}, "ES": {"name": "Spain", "flag": "🇪🇸"}, "LK": {"name": "Sri Lanka", "flag": "🇱🇰"},
    "SD": {"name": "Sudan", "flag": "🇸🇩"}, "SR": {"name": "Suriname", "flag": "🇸🇷"}, "SE": {"name": "Sweden", "flag": "🇸🇪"},
    "CH": {"name": "Switzerland", "flag": "🇨🇭"}, "SY": {"name": "Syria", "flag": "🇸🇾"}, "TW": {"name": "Taiwan", "flag": "🇹🇼"},
    "TJ": {"name": "Tajikistan", "flag": "🇹🇯"}, "TZ": {"name": "Tanzania", "flag": "🇹🇿"}, "TH": {"name": "Thailand", "flag": "🇹🇭"},
    "TG": {"name": "Togo", "flag": "🇹🇬"}, "TO": {"name": "Tonga", "flag": "🇹🇴"}, "TT": {"name": "Trinidad", "flag": "🇹🇹"},
    "TN": {"name": "Tunisia", "flag": "🇹🇳"}, "TR": {"name": "Turkey", "flag": "🇹🇷"}, "TM": {"name": "Turkmenistan", "flag": "🇹🇲"},
    "TV": {"name": "Tuvalu", "flag": "🇹🇻"}, "UG": {"name": "Uganda", "flag": "🇺🇬"}, "UA": {"name": "Ukraine", "flag": "🇺🇦"},
    "AE": {"name": "United Arab Emirates", "flag": "🇦🇪"}, "GB": {"name": "United Kingdom", "flag": "🇬🇧"}, "US": {"name": "United States", "flag": "🇺🇸"},
    "UY": {"name": "Uruguay", "flag": "🇺🇾"}, "UZ": {"name": "Uzbekistan", "flag": "🇺🇿"}, "VU": {"name": "Vanuatu", "flag": "🇻🇺"},
    "VA": {"name": "Vatican City", "flag": "🇻🇦"}, "VE": {"name": "Venezuela", "flag": "🇻🇪"}, "VN": {"name": "Vietnam", "flag": "🇻🇳"},
    "YE": {"name": "Yemen", "flag": "🇾🇪"}, "ZM": {"name": "Zambia", "flag": "🇿🇲"}
}

# ================= ডাটাবেস (SQLite3) =================
def init_db():
    with db_lock:
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, first_name TEXT, username TEXT, joined TEXT, balance REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
        conn.commit()
        conn.close()

def get_setting(key, default):
    with db_lock:
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = c.fetchone()
        conn.close()
        return json.loads(row[0]) if row else default

def set_setting(key, value):
    with db_lock:
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("REPLACE INTO settings (key, value) VALUES (?, ?)", (key, json.dumps(value, ensure_ascii=False)))
        conn.commit()
        conn.close()

def get_user(user_id):
    with db_lock:
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id=?", (str(user_id),))
        row = c.fetchone()
        conn.close()
        if row: return {"user_id": row[0], "first_name": row[1], "username": row[2], "joined": row[3], "balance": row[4]}
        return None

def update_balance(user_id, amount):
    with db_lock:
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, str(user_id)))
        conn.commit()
        conn.close()

def set_user_balance(user_id, new_balance):
    with db_lock:
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("UPDATE users SET balance = ? WHERE user_id=?", (new_balance, str(user_id)))
        conn.commit()
        conn.close()

def get_all_users():
    with db_lock:
        conn = sqlite3.connect("bot_database.db")
        c = conn.cursor()
        c.execute("SELECT user_id, first_name, balance FROM users ORDER BY balance DESC")
        rows = c.fetchall()
        conn.close()
        return rows

init_db()

# Default Settings Load
default_config = {
    "reward_per_otp": 0.25,
    "withdraw_status": True,
    "withdraw_notice": "উইথড্র সাময়িকভাবে বন্ধ আছে।",
    "min_withdraw": {"Bkash": 50, "Nagad": 50, "Rocket": 50},
    "sub_admins":[],
    "force_channel_id": "@Seyitechfreeno",
    "force_channel_url": "https://t.me/Seyitechfreeno",
    "force_group_id": "", 
    "force_group_url": "https://t.me/OtphomeGroup",
    "support_url": "https://t.me/Crypt4947",
    "services": {"Facebook🔥": {}}
}

current_settings = get_setting("config", default_config)
if "support_url" not in current_settings: current_settings["support_url"] = "https://t.me/MEeASDF"
if "Facebook🔥" not in current_settings["services"]: current_settings["services"]["Facebook🔥"] = {}
set_setting("config", current_settings)

def is_admin(user_id):
    cfg = get_setting("config", default_config)
    return user_id == ADMIN_ID or user_id in cfg.get("sub_admins",[])

# ================= Force Join & Registration =================
def check_registered(message):
    if not get_user(message.chat.id):
        bot.send_message(message.chat.id, "⚠️ 𝐒𝐞𝐚𝐬𝐬𝐨𝐧 𝐄𝐱𝐩𝐚𝐢𝐫𝐞𝐝 /start কমান্ড দিয়ে 𝐁𝐨𝐭 𝐑𝐮𝐧 করুন।")
        return False
    return True

def check_joined(user_id):
    if is_admin(user_id): return True
    cfg = get_setting("config", default_config)
    ch_id = cfg.get("force_channel_id", "").strip()
    gr_id = cfg.get("force_group_id", "").strip()
    
    joined_ch, joined_gr = True, True
    try:
        if ch_id: joined_ch = bot.get_chat_member(ch_id, user_id).status not in ['left', 'kicked']
    except: pass 
    try:
        if gr_id: joined_gr = bot.get_chat_member(gr_id, user_id).status not in['left', 'kicked']
    except: pass
    return joined_ch and joined_gr

def force_join_msg(chat_id):
    cfg = get_setting("config", default_config)
    markup = InlineKeyboardMarkup(row_width=1)
    if cfg.get("force_channel_url"): markup.add(InlineKeyboardButton("📢 Join Channel", url=cfg["force_channel_url"]))
    if cfg.get("force_group_url"): markup.add(InlineKeyboardButton("💬 Join Group", url=cfg["force_group_url"]))
    markup.add(InlineKeyboardButton("✅ Verify", callback_data="verify_join"))
    bot.send_message(chat_id, "⚠️ **বটটি ব্যবহার করতে অবশ্যই আমাদের চ্যানেল ও গ্রুপে যুক্ত হোন!**\nযুক্ত হওয়ার পর 'Verify' বাটনে ক্লিক করুন।", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "verify_join")
def verify_join_callback(call):
    if check_joined(call.message.chat.id):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "✅ 𝑽𝒆𝒓𝒊𝒇𝒊𝒄𝒂𝒕𝒊𝒐𝒏 𝑪𝒐𝒎𝒑𝒍𝒆𝒕𝒆!", reply_markup=main_menu(call.message.chat.id))
    else:
        bot.answer_callback_query(call.id, "❌ আপনি এখনো যুক্ত হননি!", show_alert=True)

# ================= API Auth =================
def refresh_jwt_token():
    global AUTH_TOKEN
    try:
        response = requests.post(STEX_LOGIN_URL, json={"email": STEX_EMAIL, "password": STEX_PASSWORD})
        if response.status_code == 200:
            AUTH_TOKEN = response.json().get("token") or response.json().get("data", {}).get("token")
            return True
    except: pass
    return False

def make_api_request(method, url, payload=None):
    headers = {"mauthtoken": AUTH_TOKEN, "Content-Type": "application/json"}
    for _ in range(2):
        try:
            res = requests.get(url, headers=headers) if method == "GET" else requests.post(url, json=payload, headers=headers)
            if res.status_code == 401: refresh_jwt_token(); continue
            return res
        except: return None
    return None

# ================= Console Monitor & Auto Facebook🔥 =================
def get_country_from_range(range_val):
    clean_r = str(range_val).replace("X", "").strip()
    for i in[4, 3, 2, 1]:
        if len(clean_r) >= i:
            prefix = clean_r[:i]
            if prefix in COUNTRY_CODES: return COUNTRY_CODES[prefix]
    return "Unknown"

def console_monitor_thread():
    global recent_fb_logs, last_hot_broadcast
    while True:
        try:
            res = make_api_request("GET", "https://stexsms.com/mapi/v1/mdashboard/console/info")
            if res and res.status_code == 200:
                logs = res.json().get("data", {}).get("logs",[])
                cfg = get_setting("config", default_config)
                now = time.time()
                
                for log in reversed(logs):
                    log_id = log.get("id")
                    if log_id in posted_console_ids: continue
                    posted_console_ids.append(log_id)
                    
                    app_name, country_str, range_val = log.get("app_name", "Unknown"), log.get("country", "Unknown"), str(log.get("range", ""))
                    sms, time_val = log.get("sms", ""), log.get("time", "")
                    
                    if "X" not in range_val: range_val += "XXX"
                    
 # Auto Update Facebook🔥 Service & Group Broadcast
                    if "facebook" in app_name.lower() or "fb" in app_name.lower():
                        c_code = get_country_from_range(range_val)
                        
                        # Country Flag ও Name অটোমেটিক ডিটেক্ট করা
                        c_flag = SHORT_NAMES.get(c_code, {}).get("flag", "🏳️") if c_code != "Unknown" else "🏳️"
                        c_name = SHORT_NAMES.get(c_code, {}).get("name", country_str) if c_code != "Unknown" else country_str
                        
                        if c_code != "Unknown":
                            # টাইমস্ট্যাম্প সহ রেঞ্জ সেভ করা
                            recent_fb_logs.append((now, c_code, range_val))

                        # Facebook Group Broadcast (প্রিমিয়াম ডিজাইন)
                        msg = (
                            f"┌── 📘 **{app_name.upper()}** ──┐\n"
                            f"🌍 **𝐂𝐨𝐮𝐧𝐭𝐫𝐲:** {c_flag} {c_name}\n"
                            f"📱 **𝐑𝐚𝐧𝐠𝐞:** `{range_val}`\n"
                            f"🔑 **𝐌𝐚𝐬𝐬𝐞𝐠𝐞:** `{sms}`\n"
                            f"⏱ **𝐓𝐢𝐦𝐞:** {time_val}\n"
                            f"└────────────────────┘"
                        )
                        try: 
                            bot.send_message(GROUP_ID, msg, parse_mode="Markdown")
                        except: 
                            pass
                
                # ৫ মিনিটের (300 সেকেন্ড) বেশি পুরোনো ট্রাফিক রিমুভ করা
                while recent_fb_logs and (now - recent_fb_logs[0][0]) > 300:
                    recent_fb_logs.popleft()
                
                # কনসোলের লাইভ ডেটা থেকে নতুন করে রেঞ্জ তৈরি করা
                freqs = Counter([r for _, _, r in recent_fb_logs])
                live_ranges_by_country = {}
                
                for _, c, r in recent_fb_logs:
                    if c not in live_ranges_by_country:
                        live_ranges_by_country[c] = set()
                    live_ranges_by_country[c].add(r)
                
                new_fb_service = {}
                
                for c_code, ranges in live_ranges_by_country.items():
                    # ফ্রিকুয়েন্সি অনুসারে সাজানো (সর্বোচ্চ ৭টি রেঞ্জ)
                    sorted_r = sorted(list(ranges), key=lambda x: freqs[x], reverse=True)[:7]
                    new_ranges = {}
                    
                    for r in sorted_r:
                        is_hot = freqs[r] >= 6  # যদি ৫ মিনিটে ৪ বারের বেশি ট্রাফিক থাকে
                        r_name = f"🔥 {r}" if is_hot else r
                        new_ranges[r_name] = {}
                        
                        # ব্রডকাস্ট যদি হট রেঞ্জ হয় (২ ঘণ্টায় একবার)
                        if is_hot and (now - last_hot_broadcast.get(r, 0) > 7200): 
                            last_hot_broadcast[r] = now
                            c_info_name = SHORT_NAMES.get(c_code, {}).get("name", c_code)
                            c_info_flag = SHORT_NAMES.get(c_code, {}).get("flag", "🏳")
                            msg = f"🌸 *MOST ACTIVE RANGE!*\n\n#{c_code} | {c_info_name.upper()} {c_info_flag} - `/get {r}`\n🛠 Facebook🔥\n LIVE • HIGH TRAFFIC • USE FAST"
                            for u in get_all_users():
                                try: bot.send_message(u[0], msg, parse_mode="Markdown")
                                except: pass
                                
                    new_fb_service[c_code] = {
                        "name": SHORT_NAMES.get(c_code, {}).get("name", c_code), 
                        "flag": SHORT_NAMES.get(c_code, {}).get("flag", "🏳"), 
                        "ranges": new_ranges
                    }
                
                # ডেটাবেজ তখনই আপডেট হবে যদি নতুন কনসোল ডেটায় কোনো পরিবর্তন থাকে
                if cfg.get("services", {}).get("Facebook🔥") != new_fb_service:
                    if "services" not in cfg:
                        cfg["services"] = {}
                    cfg["services"]["Facebook🔥"] = new_fb_service
                    set_setting("config", cfg)
                    
        except Exception as e: pass
        time.sleep(5)

# ================= Main Menus =================
def main_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("☎️ Get Number"), KeyboardButton("🔢 Get Range"))
    markup.add(KeyboardButton("💰 Balance"), KeyboardButton("👤 Profile"))
    markup.add(KeyboardButton("💬 Support"), KeyboardButton("🔐 2FA"))
    if is_admin(user_id): markup.add(KeyboardButton("⚙️ Admin Panel"), KeyboardButton("👥 Users"))
    return markup

def back_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(KeyboardButton("🔙 Back to Home"))
    return markup

@bot.message_handler(commands=['start'])
def start_cmd(message):
    uid = str(message.chat.id)
    if not get_user(uid):
        with db_lock:
            conn = sqlite3.connect("bot_database.db")
            c = conn.cursor()
            c.execute("INSERT INTO users (user_id, first_name, username, joined, balance) VALUES (?, ?, ?, ?, ?)", 
                      (uid, message.from_user.first_name, message.from_user.username or "N/A", datetime.now().strftime("%Y-%m-%d"), 0.0))
            conn.commit()
            conn.close()
            
    if not check_joined(message.chat.id): return force_join_msg(message.chat.id)
    bot.send_message(message.chat.id, f"🆆︎🅴︎🅻︎🅲︎🅾︎🅼︎🅴︎ {message.from_user.first_name}! 🤖", reply_markup=main_menu(message.chat.id))

@bot.message_handler(func=lambda m: m.text == "🔙 Back to Home")
def back_home(m): 
    if check_registered(m): bot.send_message(m.chat.id, "🏠 𝚁𝚎𝚝𝚞𝚛𝚗 𝚝𝚘 𝚑𝚘𝚖𝚎।", reply_markup=main_menu(m.chat.id))

@bot.message_handler(func=lambda m: m.text == "👤 Profile")
def profile_cmd(m):
    if not check_registered(m): return
    if not check_joined(m.chat.id): return force_join_msg(m.chat.id)
    user = get_user(m.chat.id)
    bot.send_message(m.chat.id, f"👤 **𝐏𝐫𝐨𝐟𝐢𝐥𝐞**\n\n🔹 **ℕ𝕒𝕞𝕖:** {user['first_name']}\n🔹 **𝕌𝕚𝕕:** `{user['user_id']}`\n💰 **𝔹𝕒𝕝𝕒𝕟𝕔𝕖:** ৳{user['balance']}", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "💬 Support")
def support_cmd(m):
    if not check_registered(m): return
    cfg = get_setting("config", default_config)
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("💬 Support Chat", url=cfg.get("support_url", "https://t.me/MEeASDF")))
    bot.send_message(m.chat.id, "যেকোনো প্রয়োজনে আমাদের সাপোর্ট টিমের সাথে যোগাযোগ করুন:\n\n👨‍💻 **Bot Developer シ︎**MD SADIK", reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔐 2FA")
def ask_2fa(m):
    if not check_registered(m): return
    msg = bot.send_message(m.chat.id, "🔐 আপনার 2FA Secret Key পাঠান:", reply_markup=back_menu())
    bot.register_next_step_handler(msg, process_2fa)

def process_2fa(m):
    if m.text == "🔙 Back to Home": return back_home(m)
    secret = m.text.replace(" ", "").upper()
    try:
        code = pyotp.TOTP(secret).now()
        bot.send_message(m.chat.id, f"✅ **𝐘𝐨𝐮𝐫 𝐎𝐓𝐏 𝐆𝐞𝐧𝐞𝐫𝐚𝐭𝐞 𝐒𝐮𝐜𝐜𝐞𝐬𝐬...!\n 𝐓𝐨𝐩 𝐅𝐨𝐫 𝐂𝐨𝐩𝐲**\n\n🔑 𝐂𝐨𝐝𝐞: `{code}`", parse_mode='Markdown', reply_markup=main_menu(m.chat.id))
    except:
        bot.send_message(m.chat.id, "❌ Error: Secret Key টি সঠিক নয়।", reply_markup=main_menu(m.chat.id))

# ================= Earn & Withdraw =================
@bot.message_handler(func=lambda m: m.text == "💰 Balance")
def balance_cmd(m):
    if not check_registered(m): return
    if not check_joined(m.chat.id): return force_join_msg(m.chat.id)
    user = get_user(m.chat.id)
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("💸 Withdraw", callback_data="req_withdraw"))
    bot.send_message(m.chat.id, f"💰 **বর্তমান ব্যালেন্স:** ৳{user['balance']}", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "req_withdraw")
def withdraw_req(call):
    cfg = get_setting("config", default_config)
    if not cfg.get("withdraw_status", True):
        return bot.answer_callback_query(call.id, cfg.get('withdraw_notice', 'Withdraw closed.'), show_alert=True)
        
    text = "🏦 **Withdraw Methods:**\n\n"
    for method, minim in cfg["min_withdraw"].items(): text += f"🔹 {method}: Min ৳{minim}\n"
    markup = InlineKeyboardMarkup(row_width=3).add(
        InlineKeyboardButton("Bkash", callback_data="wth_Bkash"),
        InlineKeyboardButton("Nagad", callback_data="wth_Nagad"),
        InlineKeyboardButton("Rocket", callback_data="wth_Rocket")
    )
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("wth_"))
def wth_amount(call):
    method = call.data.split("_")[1]
    user = get_user(call.message.chat.id)
    cfg = get_setting("config", default_config)
    min_w = cfg["min_withdraw"].get(method, 50)
    
    if user['balance'] < min_w: return bot.answer_callback_query(call.id, f"❌ আপনার ব্যালেন্স কম! মিনিমাম ৳{min_w} প্রয়োজন।", show_alert=True)
    msg = bot.send_message(call.message.chat.id, f"✅ Method: {method}\n💰 Available: ৳{user['balance']}\n\nকতো টাকা তুলতে চান?", reply_markup=back_menu())
    bot.register_next_step_handler(msg, lambda m: process_wth_amount(m, method, user['balance']))

def process_wth_amount(m, method, bal):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    try:
        amount = float(m.text)
        if amount < cfg["min_withdraw"].get(method, 50) or amount > bal:
            return bot.send_message(m.chat.id, "❌ এমাউন্ট সঠিক নয় বা ব্যালেন্স কম।", reply_markup=main_menu(m.chat.id))
        msg = bot.send_message(m.chat.id, f"✅ আপনার {method} নাম্বারটি লিখুন:")
        bot.register_next_step_handler(msg, lambda mx: process_wth_final(mx, method, amount))
    except: bot.send_message(m.chat.id, "❌ শুধুমাত্র সংখ্যা ব্যবহার করুন।", reply_markup=main_menu(m.chat.id))

def process_wth_final(m, method, amount):
    if m.text == "🔙 Back to Home": return back_home(m)
    update_balance(m.chat.id, -amount)
    bot.send_message(m.chat.id, f"✅ উইথড্র রিকোয়েস্ট সফল!\n💳 {method}: ৳{amount}\n📱 Number: {m.text}", reply_markup=main_menu(m.chat.id))
    bot.send_message(ADMIN_ID, f"🔔 **NEW WITHDRAW**\n👤 User:[{m.from_user.first_name}](tg://user?id={m.chat.id})\n💳 {method} ৳{amount}\n📱 Num: `{m.text}`", parse_mode="Markdown")

# ================= GET NUMBER / RANGE =================
@bot.message_handler(func=lambda m: m.text == "☎️ Get Number")
def get_number_start(m):
    if not check_registered(m) or not check_joined(m.chat.id): return
    cfg = get_setting("config", default_config)
    if not cfg.get("services"): return bot.send_message(m.chat.id, "❌ 𝐍𝐨 𝐒𝐞𝐫𝐯𝐢𝐜𝐞 𝐀𝐯𝐚𝐢𝐚𝐛𝐥𝐞!।")
    markup = InlineKeyboardMarkup(row_width=2)
    for srv in cfg["services"].keys(): markup.add(InlineKeyboardButton(srv, callback_data=f"getSrv_{srv}"))
    bot.send_message(m.chat.id, "🔧 **𝐒𝐞𝐥𝐞𝐜𝐭 𝐘𝐨𝐮𝐫 𝐒𝐞𝐫𝐯𝐢𝐜𝐞?**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("getSrv_"))
def select_country(call):
    srv = call.data.split("_")[1]
    cfg = get_setting("config", default_config)
    countries = cfg.get("services", {}).get(srv, {})
    
    if not countries: 
        return bot.answer_callback_query(call.id, "❌ এই সার্ভিসে বর্তমানে কোনো দেশ অ্যাক্টিভ নেই!", show_alert=True)
        
    markup = InlineKeyboardMarkup(row_width=2)
    for code, details in countries.items(): 
        markup.add(InlineKeyboardButton(f"{details.get('flag','🏳')} #{code} | {details.get('name','Unknown')}", callback_data=f"getCnt_{srv}_{code}"))
    markup.add(InlineKeyboardButton("🔙 Back", callback_data="back_srv"))
    bot.edit_message_text("🌍 **𝐒𝐞𝐥𝐞𝐜𝐭 𝐂𝐨𝐮𝐧𝐭𝐫𝐲:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "back_srv")
def back_to_srv(call):
    m = call.message
    m.text = "☎️ Get Number"
    get_number_start(m)

@bot.callback_query_handler(func=lambda call: call.data.startswith("getCnt_"))
def select_range(call):
    _, srv, code = call.data.split("_")
    cfg = get_setting("config", default_config)
    
    country_data = cfg.get("services", {}).get(srv, {}).get(code)
    if not country_data:
        return bot.answer_callback_query(call.id, "❌ 𝐍𝐨 𝐦𝐨𝐫𝐞 𝐚𝐥𝐢𝐯𝐞 𝐭𝐡𝐢𝐬 𝐂𝐨𝐮𝐧𝐭𝐞𝐫𝐲!", show_alert=True)
        
    ranges = country_data.get("ranges", {})
    if not ranges:
        return bot.answer_callback_query(call.id, "❌ 𝐍𝐨 𝐦𝐨𝐫𝐞 𝐚𝐥𝐢𝐯𝐞 𝐭𝐡𝐢𝐬 𝐫𝐚𝐧𝐠𝐞!", show_alert=True)
        
    markup = InlineKeyboardMarkup(row_width=2)
    for r in ranges.keys(): markup.add(InlineKeyboardButton(f"{r}", callback_data=f"getRng_{srv}_{code}_{r}"))
    markup.add(InlineKeyboardButton("🔙 Back", callback_data=f"getSrv_{srv}"))
    bot.edit_message_text("🔢 **𝐒𝐞𝐥𝐞𝐜𝐭 𝐑𝐚𝐧𝐠𝐞:**", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🔢 Get Range")
def ask_get_range(m):
    if not check_registered(m): return
    bot.send_message(m.chat.id, "🔢 **রেঞ্জ টাইপ করুন:**\n\nউদাহরণ: `/get 237697` বা `/get 237697XXX`", parse_mode="Markdown")

@bot.message_handler(commands=['get'])
def cmd_get_range(m):
    if not check_registered(m) or not check_joined(m.chat.id): return
    try:
        range_val = m.text.split(" ")[1].strip()
        if "X" not in range_val.upper(): range_val += "XXX"
        range_val = range_val.upper()
        
        c_code = get_country_from_range(range_val)
        c_details = {"name": SHORT_NAMES.get(c_code, {}).get("name", c_code), "flag": SHORT_NAMES.get(c_code, {}).get("flag", "🏳")}
        
        fetch_number_logic(m.chat.id, None, "Custom Range", c_code, c_details, range_val, m)
    except:
        bot.send_message(m.chat.id, "❌ সঠিক ফরম্যাট ব্যবহার করুন। যেমন: `/get 237697`", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("getRng_") or call.data.startswith("reRng_"))
def fetch_number(call):
    # split-এর প্যারামিটার ফিক্স করে দেওয়া হয়েছে যাতে রেঞ্জের নামে "_" থাকলেও সমস্যা না হয়
    parts = call.data.split("_", 3)
    srv, code, range_val = parts[1], parts[2], parts[3].replace("🔥 ", "")
    cfg = get_setting("config", default_config)
    
    c_details = cfg.get("services", {}).get(srv, {}).get(code)
    if not c_details:
        return bot.answer_callback_query(call.id, "❌ 𝐒𝐨𝐦𝐞𝐭𝐡𝐢𝐠 𝐔𝐧𝐚𝐯𝐚𝐢𝐚𝐛𝐥𝐞..!", show_alert=True)
        
    fetch_number_logic(call.message.chat.id, call.message.message_id, srv, code, c_details, range_val)

def fetch_number_logic(chat_id, msg_id, srv, code, c_details, range_val, msg_obj=None):
    cfg = get_setting("config", default_config)
    reward = cfg.get("reward_per_otp", 0.25)
    
    loading_text = "⏳ *𝚂𝚎𝚊𝚛𝚌𝚑𝚒𝚗𝚐 𝙽𝚞𝚖𝚋𝚎𝚛 𝙿𝚕𝚎𝚊𝚜𝚎 𝚠𝚊𝚒𝚝...*"
    if msg_id: bot.edit_message_text(loading_text, chat_id, msg_id, parse_mode="Markdown")
    else: msg_id = bot.send_message(chat_id, loading_text, parse_mode="Markdown").message_id
    
    res = make_api_request("POST", "https://stexsms.com/mapi/v1/mdashboard/getnum/number", {"range": range_val})
    raw_number = None
    if res and res.status_code in[200, 201]:
        try: raw_number = res.json().get('number') or res.json().get('data', {}).get('number')
        except: pass
        if not raw_number:
            match = re.search(r'"number"\s*:\s*"?(\d+)"?', res.text)
            if match: raw_number = match.group(1)

    if raw_number:
        clean_num = str(raw_number).replace("+", "").strip()
        active_otp_checks[str(chat_id)] = clean_num 
        
        text = f"┌── 𝐍𝐔𝐌𝐁𝐄𝐑 𝐕𝐄𝐑𝐈𝐅𝐈𝐄𝐃 ──┐\n✨ যাচাই সম্পন্ন\n🌍 দেশ ও দাম: {c_details['flag']} {c_details['name']} (৳{reward})\n\n𖠌 ℕ𝕦𝕞𝕓𝕖𝕣 : ➪`{clean_num}`\n\n🔑 𝕆𝕥𝕡 : ⏳ 𝚆𝙰𝙸𝚃..\n└── 𝐍𝐔𝐌𝐁𝐄𝐑 𝐕𝐄𝐑𝐈𝐅𝐈𝐄𝐃 ──┘"
        markup = InlineKeyboardMarkup()
        markup.row(InlineKeyboardButton("🆕 Same Range", callback_data=f"reRng_{srv}_{code}_{range_val}"))
        if cfg.get("force_group_url"): markup.row(InlineKeyboardButton("💬 OTP Group", url=cfg["force_group_url"]))
            
        bot.edit_message_text(text, chat_id, msg_id, parse_mode="Markdown", reply_markup=markup)
        threading.Thread(target=auto_check_otp, args=(chat_id, msg_id, clean_num, srv, c_details, reward), daemon=True).start()
    else: 
        markup = InlineKeyboardMarkup()
        if srv != "Custom Range" and code != "Unknown": markup.add(InlineKeyboardButton("🔙 Back to Ranges", callback_data=f"getCnt_{srv}_{code}"))
        bot.edit_message_text("❌ ℕ𝕠 ℕ𝕦𝕞𝕓𝕖𝕣 𝕀𝕟 𝕋𝕙𝕚𝕤 ℝ𝕒𝕟𝕘𝕖।", chat_id, msg_id, reply_markup=markup)

def auto_check_otp(chat_id, msg_id, number, srv, c_details, reward):
    uid = str(chat_id)
    for _ in range(60):
        if active_otp_checks.get(uid) != number:
            try: bot.edit_message_text(f"⚠️ `{number}` এর OTP চেক বাতিল করা হয়েছে কারণ আপনি নতুন নাম্বার নিয়েছেন।", chat_id, msg_id, parse_mode="Markdown")
            except: pass
            return
            
        time.sleep(5)
        res = make_api_request("GET", f"https://stexsms.com/mapi/v1/mdashboard/getnum/info?date={datetime.now().strftime('%Y-%m-%d')}&page=1&search={number}&status=")
        if res and res.status_code == 200:
            items = res.json().get("data", {}).get("numbers",[])
            if items:
                status, full_msg = items[0].get("status", "pending"), items[0].get("message", "")
                if status == "success" and full_msg:
                    code_match = re.search(r'\b\d{4,8}\b', full_msg)
                    code = code_match.group(0) if code_match else "N/A"
                    
                    update_balance(uid, reward)
                    new_bal = get_user(uid)['balance']
                    
                    text = f"✅ **𝐎𝐓𝐏 𝐑𝐄𝐂𝐄𝐕𝐈𝐄𝐃 !**\n\n📱 **𝙽𝚄𝙼𝙱𝙴𝚁:** `{number}`\n ᴛᴀᴘ ᴛᴏ ᴄᴏᴘʏ \n🔑 **𝙲𝙾𝙳𝙴:**`{code}`︎\n\n💬 **𝚂𝙼𝚂:** _{full_msg}_\n\n💰 **𝚁𝙰𝚆𝙰𝚁𝙳:** ৳{reward} 𝚊𝚍𝚍𝚎𝚍!\n💳 **𝙱𝙰𝙻𝙰𝙽𝙲𝙴:** ৳{new_bal}"
                    
                    try:
                        bot.send_message(chat_id, text, parse_mode="Markdown")
                        bot.edit_message_text(f"✅ 𝐎𝐓𝐏 𝐑𝐞𝐜𝐞𝐢𝐯𝐞𝐝 𝐅𝐨𝐫  `{number}`.", chat_id, msg_id, parse_mode="Markdown")
                    except: pass
                    return
                elif status == "failed":
                    try: bot.edit_message_text(f"❌ 𝐍𝐮𝐦𝐛𝐞𝐫 𝐂𝐚𝐧𝐜𝐥𝐞..!\n📱 `{number}`", chat_id, msg_id)
                    except: pass
                    return

# ================= ADMIN PANEL =================
@bot.message_handler(func=lambda m: m.text == "⚙️ Admin Panel")
def admin_panel(m):
    if not is_admin(m.chat.id): return
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("💰 Earn Setup", callback_data="adm_earn"), InlineKeyboardButton("🔧 Services Setup", callback_data="adm_srv"))
    if m.chat.id == ADMIN_ID: markup.add(InlineKeyboardButton("👮 Admin & Links", callback_data="adm_sub"))
    bot.send_message(m.chat.id, "⚙️ **Admin Dashboard**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_") and is_admin(call.message.chat.id))
def admin_nav(call):
    act, cid, mid = call.data, call.message.chat.id, call.message.message_id
    cfg = get_setting("config", default_config)
    
    if act == "adm_earn":
        st = "✅ ON" if cfg["withdraw_status"] else "❌ OFF"
        text = f"💰 **Earn Settings**\nReward/OTP: ৳{cfg['reward_per_otp']}\nWithdraw: {st}\nMin WTH: Bkash:{cfg['min_withdraw']['Bkash']} | Nagad:{cfg['min_withdraw']['Nagad']}"
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Edit Reward", callback_data="set_reward"), InlineKeyboardButton("Edit Min WTH", callback_data="set_minwth"),
            InlineKeyboardButton("Toggle Withdraw", callback_data="tog_withdraw"), InlineKeyboardButton("🔙 Back", callback_data="adm_home")
        )
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")
        
    elif act == "adm_srv":
        markup = InlineKeyboardMarkup(row_width=2)
        for srv in cfg.get("services", {}).keys(): markup.add(InlineKeyboardButton(srv, callback_data=f"eds_{srv}"))
        markup.add(InlineKeyboardButton("➕ Add Service", callback_data="add_srv"), InlineKeyboardButton("🔙 Back", callback_data="adm_home"))
        bot.edit_message_text("🔧 **Services Management**", cid, mid, reply_markup=markup, parse_mode="Markdown")
        
    elif act == "adm_sub" and cid == ADMIN_ID:
        text = f"👮 **Admins:** {len(cfg['sub_admins'])}\n📢 **Channel:** {cfg['force_channel_id']}\n💬 **Group:** {cfg['force_group_id']}\n🎧 **Support:** {cfg.get('support_url', 'N/A')}"
        markup = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("➕ Add Admin", callback_data="sub_add"), InlineKeyboardButton("➖ Rem Admin", callback_data="sub_rem"),
            InlineKeyboardButton("🔗 Set Channel", callback_data="set_chl"), InlineKeyboardButton("🔗 Set Group", callback_data="set_grl"),
            InlineKeyboardButton("🎧 Set Support", callback_data="set_sup"), InlineKeyboardButton("🔙 Back", callback_data="adm_home")
        )
        bot.edit_message_text(text, cid, mid, reply_markup=markup, parse_mode="Markdown")
        
    elif act == "adm_home":
        admin_panel(call.message); bot.delete_message(cid, mid)

# --- EARN ACTIONS ---
@bot.callback_query_handler(func=lambda call: call.data in["set_reward", "set_minwth", "tog_withdraw"] and is_admin(call.message.chat.id))
def earn_actions(call):
    cfg = get_setting("config", default_config)
    if call.data == "tog_withdraw":
        cfg["withdraw_status"] = not cfg["withdraw_status"]; set_setting("config", cfg)
        bot.answer_callback_query(call.id, "Withdraw Status Changed!", show_alert=True)
    elif call.data == "set_reward":
        msg = bot.send_message(call.message.chat.id, "নতুন Reward Amount লিখুন (যেমন: 0.50):", reply_markup=back_menu())
        bot.register_next_step_handler(msg, process_reward)
    elif call.data == "set_minwth":
        msg = bot.send_message(call.message.chat.id, "বিকাশ, নগদ, রকেট এর মিনিমাম কমা দিয়ে লিখুন\n(যেমন: 50, 50, 50):", reply_markup=back_menu())
        bot.register_next_step_handler(msg, process_minwth)

def process_reward(m):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    try:
        cfg["reward_per_otp"] = float(m.text)
        set_setting("config", cfg); bot.send_message(m.chat.id, "✅ Reward Update Success!", reply_markup=main_menu(m.chat.id))
    except: bot.send_message(m.chat.id, "❌ Error! শুধুমাত্র সংখ্যা দিন।", reply_markup=main_menu(m.chat.id))

def process_minwth(m):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    try:
        parts =[int(x.strip()) for x in m.text.split(",")]
        if len(parts) >= 3:
            cfg["min_withdraw"] = {"Bkash": parts[0], "Nagad": parts[1], "Rocket": parts[2]}
            set_setting("config", cfg); bot.send_message(m.chat.id, "✅ Saved!", reply_markup=main_menu(m.chat.id))
        else: bot.send_message(m.chat.id, "❌ Error! ৩টি সংখ্যা কমা দিয়ে লিখুন।", reply_markup=main_menu(m.chat.id))
    except: bot.send_message(m.chat.id, "❌ Error! সঠিক ফরম্যাটে দিন।", reply_markup=main_menu(m.chat.id))

# --- SERVICE MUTATIONS ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("del_srv", "del_cnt", "del_rng", "add_srv", "add_cnt", "add_rng")) and is_admin(call.message.chat.id))
def service_mutations(call):
    parts = call.data.split("_")
    act = parts[0] + "_" + parts[1]
    cfg = get_setting("config", default_config)
    
    if act == "del_srv":
        del cfg["services"][parts[2]]; set_setting("config", cfg)
        bot.answer_callback_query(call.id, "Service Deleted!"); bot.delete_message(call.message.chat.id, call.message.message_id)
    elif act == "del_cnt":
        del cfg["services"][parts[2]][parts[3]]; set_setting("config", cfg)
        bot.answer_callback_query(call.id, "Country Deleted!"); bot.delete_message(call.message.chat.id, call.message.message_id)
    elif act == "add_srv":
        msg = bot.send_message(call.message.chat.id, "Service এর নাম লিখুন:", reply_markup=back_menu())
        bot.register_next_step_handler(msg, process_add_srv)
    elif act == "add_cnt":
        msg = bot.send_message(call.message.chat.id, "Short Code দিন (যেমন: BD, IN, CM):\n(অটোমেটিক Flag ও Name যুক্ত হবে)", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: process_add_cnt(m, parts[2]))
    elif act == "add_rng":
        msg = bot.send_message(call.message.chat.id, "Range লিখুন (যেমন: 88017):", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: process_add_rng(m, parts[2], parts[3]))
    elif act == "del_rng":
        msg = bot.send_message(call.message.chat.id, "যে Range ডিলিট করবেন তা লিখুন:", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: process_del_rng(m, parts[2], parts[3]))

def process_add_srv(m):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    cfg["services"][m.text.strip()] = {}
    set_setting("config", cfg); bot.send_message(m.chat.id, "✅ Added!", reply_markup=main_menu(m.chat.id))

def process_add_cnt(m, srv):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    code = m.text.strip().upper()
    name = SHORT_NAMES.get(code, {}).get("name", code)
    flag = SHORT_NAMES.get(code, {}).get("flag", "🏳")
    cfg["services"][srv][code] = {"name": name, "flag": flag, "ranges": {}}
    set_setting("config", cfg); bot.send_message(m.chat.id, f"✅ Added: {flag} {name}", reply_markup=main_menu(m.chat.id))

def process_add_rng(m, srv, cnt):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    cfg["services"][srv][cnt]["ranges"][m.text.strip()] = {}
    set_setting("config", cfg); bot.send_message(m.chat.id, "✅ Added!", reply_markup=main_menu(m.chat.id))

def process_del_rng(m, srv, cnt):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    try:
        del cfg["services"][srv][cnt]["ranges"][m.text.strip()]
        set_setting("config", cfg); bot.send_message(m.chat.id, "✅ Deleted!", reply_markup=main_menu(m.chat.id))
    except: bot.send_message(m.chat.id, "❌ Not Found", reply_markup=main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("eds_") and is_admin(call.message.chat.id))
def edit_srv(call):
    srv = call.data.split("_")[1]
    cfg = get_setting("config", default_config)
    if srv not in cfg["services"]: return bot.answer_callback_query(call.id, "Already deleted!")
    markup = InlineKeyboardMarkup(row_width=2)
    for cnt, data in cfg["services"][srv].items(): markup.add(InlineKeyboardButton(f"{data['flag']} {data['name']}", callback_data=f"edc_{srv}_{cnt}"))
    markup.add(InlineKeyboardButton("➕ Add Country", callback_data=f"add_cnt_{srv}"), InlineKeyboardButton("🗑 Delete Service", callback_data=f"del_srv_{srv}"), InlineKeyboardButton("🔙 Back", callback_data="adm_srv"))
    bot.edit_message_text(f"⚙️ **Service:** {srv}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data.startswith("edc_") and is_admin(call.message.chat.id))
def edit_cnt(call):
    _, srv, cnt = call.data.split("_")
    cfg = get_setting("config", default_config)
    data = cfg["services"].get(srv, {}).get(cnt, {})
    if not data: return bot.answer_callback_query(call.id, "Not found!")
    markup = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("➕ Add Range", callback_data=f"add_rng_{srv}_{cnt}"), InlineKeyboardButton("🗑 Remove Range", callback_data=f"del_rng_{srv}_{cnt}"),
        InlineKeyboardButton("🗑 Delete Country", callback_data=f"del_cnt_{srv}_{cnt}"), InlineKeyboardButton("🔙 Back", callback_data=f"eds_{srv}")
    )
    bot.edit_message_text(f"🌍 **Country:** {data['flag']} {data['name']}\nRanges: {', '.join(data['ranges'].keys())}", call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")

# --- ADMIN & LINKS ---
@bot.callback_query_handler(func=lambda call: call.data in["sub_add", "sub_rem", "set_chl", "set_grl", "set_sup"] and call.message.chat.id == ADMIN_ID)
def sub_admin_actions(call):
    act = call.data
    if act == "sub_add":
        msg = bot.send_message(call.message.chat.id, "নতুন সাব-এডমিনের Telegram ID দিন:", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: process_sub_admin(m, True))
    elif act == "sub_rem":
        msg = bot.send_message(call.message.chat.id, "রিমুভ করতে এডমিনের Telegram ID দিন:", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: process_sub_admin(m, False))
    elif act == "set_chl":
        msg = bot.send_message(call.message.chat.id, "Channel এর Chat ID দিন (যেমন: @channelname বা -100...):", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: process_link_id(m, "channel"))
    elif act == "set_grl":
        msg = bot.send_message(call.message.chat.id, "Group এর Chat ID দিন (যেমন: -100...):", reply_markup=back_menu())
        bot.register_next_step_handler(msg, lambda m: process_link_id(m, "group"))
    elif act == "set_sup":
        msg = bot.send_message(call.message.chat.id, "Support ID বা Link দিন (যেমন: https://t.me/MEeASDF):", reply_markup=back_menu())
        bot.register_next_step_handler(msg, process_sup)

def process_sub_admin(m, is_add):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    try:
        sub_id = int(m.text.strip())
        if is_add and sub_id not in cfg["sub_admins"]: cfg["sub_admins"].append(sub_id)
        elif not is_add and sub_id in cfg["sub_admins"]: cfg["sub_admins"].remove(sub_id)
        set_setting("config", cfg); bot.send_message(m.chat.id, "✅ Done!", reply_markup=main_menu(m.chat.id))
    except: bot.send_message(m.chat.id, "❌ Error! শুধুমাত্র সংখ্যা দিন।", reply_markup=main_menu(m.chat.id))

def process_link_id(m, chat_type):
    if m.text == "🔙 Back to Home": return back_home(m)
    chat_id = m.text.strip()
    msg = bot.send_message(m.chat.id, f"এবার {chat_type.title()} এর Invite Link টি দিন:", reply_markup=back_menu())
    bot.register_next_step_handler(msg, lambda mx: process_link_url(mx, chat_type, chat_id))

def process_link_url(m, chat_type, chat_id):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    url = m.text.strip()
    if chat_type == "channel":
        cfg["force_channel_id"] = chat_id
        cfg["force_channel_url"] = url
    else:
        cfg["force_group_id"] = chat_id
        cfg["force_group_url"] = url
    set_setting("config", cfg); bot.send_message(m.chat.id, "✅ Successfully Updated!", reply_markup=main_menu(m.chat.id))

def process_sup(m):
    if m.text == "🔙 Back to Home": return back_home(m)
    cfg = get_setting("config", default_config)
    cfg["support_url"] = m.text.strip()
    set_setting("config", cfg)
    bot.send_message(m.chat.id, "✅ Support Link Updated!", reply_markup=main_menu(m.chat.id))

# ================= USERS PANEL & EDIT BALANCE =================
@bot.message_handler(func=lambda m: m.text == "👥 Users" and is_admin(m.chat.id))
def users_panel(m):
    all_users = get_all_users()
    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("📢 Broadcast", callback_data="do_broadcast"),
        InlineKeyboardButton("👤 Top Users (Edit Balance)", callback_data="view_users")
    )
    bot.send_message(m.chat.id, f"👥 **Total Users:** {len(all_users)}", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "view_users" and is_admin(call.message.chat.id))
def view_users(call):
    top_users = get_all_users()[:15]
    markup = InlineKeyboardMarkup(row_width=2)
    for u in top_users:
        markup.add(InlineKeyboardButton(f"{u[1][:10]} | ৳{u[2]}", callback_data=f"edBal_{u[0]}"))
    bot.edit_message_text("👤 **Top Users**\nব্যালেন্স এডিট করতে বাটনে ক্লিক করুন:", call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("edBal_") and is_admin(call.message.chat.id))
def ask_new_balance(call):
    uid = call.data.split("_")[1]
    msg = bot.send_message(call.message.chat.id, f"User `{uid}` এর নতুন ব্যালেন্স লিখুন:", parse_mode="Markdown", reply_markup=back_menu())
    bot.register_next_step_handler(msg, lambda m: _save_balance(m, uid))

def _save_balance(m, uid):
    if m.text == "🔙 Back to Home": return back_home(m)
    try:
        set_user_balance(uid, float(m.text))
        bot.send_message(m.chat.id, "✅ ব্যালেন্স আপডেট হয়েছে!", reply_markup=main_menu(m.chat.id))
    except: bot.send_message(m.chat.id, "❌ Error", reply_markup=main_menu(m.chat.id))

@bot.callback_query_handler(func=lambda call: call.data == "do_broadcast" and is_admin(call.message.chat.id))
def ask_broadcast(call):
    msg = bot.send_message(call.message.chat.id, "📢 ব্রডকাস্ট মেসেজ পাঠান:", reply_markup=back_menu())
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(m):
    if m.text == "🔙 Back to Home": return back_home(m)
    bot.send_message(m.chat.id, "⏳ পাঠানো শুরু হয়েছে...")
    success = 0
    for u in get_all_users():
        try: bot.copy_message(chat_id=u[0], from_chat_id=m.chat.id, message_id=m.message_id); success += 1
        except: pass
    bot.send_message(m.chat.id, f"✅ সফলভাবে {success} জনকে পাঠানো হয়েছে!", reply_markup=main_menu(m.chat.id))

# ================= RUNNER =================
if __name__ == "__main__":
    refresh_jwt_token()
    threading.Thread(target=console_monitor_thread, daemon=True).start()
    threading.Thread(target=run_flask, daemon=True).start()
    print("✅ Advanced Bot is LIVE! Auto Range fully synced with console logs.")
    while True:
        try: bot.infinity_polling(timeout=20, long_polling_timeout=15)
        except Exception as e: time.sleep(5)
