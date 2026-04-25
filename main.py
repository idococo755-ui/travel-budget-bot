import os, json, logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
TOKEN = os.environ.get("BOT_TOKEN")

COUNTRY_CURRENCY = {
    'הודו': 'INR', 'תאילנד': 'THB', 'יפן': 'JPY', 'ישראל': 'ILS',
    'אמריקה': 'USD', 'ארצות הברית': 'USD', 'אירופה': 'EUR',
    'וייטנאם': 'VND', 'קמבודיה': 'KHR', 'לאוס': 'LAK',
    'אינדונזיה': 'IDR', 'מלזיה': 'MYR', 'סינגפור': 'SGD',
    'סין': 'CNY', 'נפאל': 'NPR', 'מקסיקו': 'MXN', 'ברזיל': 'BRL',
    'אנגליה': 'GBP', 'בריטניה': 'GBP', 'ספרד': 'EUR', 'צרפת': 'EUR',
    'איטליה': 'EUR', 'גרמניה': 'EUR', 'פורטוגל': 'EUR', 'טייוואן': 'TWD',
}

CURRENCY_WORDS = {
    'דולר': 'USD', 'יורו': 'EUR', 'שקל': 'ILS', 'דונג': 'VND',
    'רופי': 'INR', 'בהט': 'THB', 'ין': 'JPY', 'פאונד': 'GBP',
    'ריאל': 'BRL', 'USD': 'USD', 'EUR': 'EUR', 'ILS': 'ILS',
    'VND': 'VND', 'INR': 'INR', 'THB': 'THB', 'JPY': 'JPY',
}

ILS_RATES = {
    'VND': 0.000145, 'USD': 3.65, 'EUR': 4.0, 'ILS': 1.0,
    'THB': 0.107, 'INR': 0.044, 'JPY': 0.024, 'GBP': 4.6,
    'IDR': 0.00023, 'MYR': 0.83, 'SGD': 2.7, 'KHR': 0.00089,
    'LAK': 0.000047, 'CNY': 0.5, 'NPR': 0.027, 'MXN': 0.18,
    'BRL': 0.65, 'TWD': 0.11,
}

CAT_KEYWORDS = {
    'לינה': ['מלון', 'hostel', 'hotel', 'airbnb', 'חדר', 'לינה', 'קמפינג'],
    'אוכל ושתייה': ['אוכל', 'מסעדה', 'קפה', 'שתייה', 'ארוחה', 'סושי', 'פיצה', 'בר', 'שוק', 'pho', 'bun', 'banh', 'coffee', 'food'],
    'תחבורה': ['מונית', 'taxi', 'אוטובוס', 'רכבת', 'טיסה', 'uber', 'grab', 'טוקטוק', 'קטנוע', 'אופניים', 'bus', 'train', 'ferry', 'scooter'],
    'אטרקציות': ['מוזיאון', 'פארק', 'טיול', 'סיור', 'tour', 'museum', 'temple', 'מקדש', 'כניסה', 'zoo', 'beach'],
    'קניות': ['קניות', 'חנות', 'בגד', 'נעל', 'מזכרת', 'shopping', 'market'],
}

user_data = {}

def get_user(uid):
    if uid not in user_data:
        user_data[uid] = {'country': 'וייטנאם', 'currency': 'VND', 'expenses': []}
    return user_data[uid]

def today_str():
    return datetime.now().strftime('%d/%m/%Y')

def offset_date(days):
    return (datetime.now() + timedelta(days=days)).strftime('%d/%m/%Y')

def guess_category(desc):
    d = desc.lower()
    for cat, kws in CAT_KEYWORDS.items():
        if any(k in d for k in kws):
            return cat
    return 'שונות'

def to_ils(amount, currency):
    return amount * ILS_RATES.get(currency, 1.0)

def fmt_ils(v):
    return f"₪{v:,.2f}"

def parse_date(text):
    lower = text.lower()
    if 'אתמול' in lower or 'yesterday' in lower:
        return offset_date(-1), 'אתמול'
    if 'שלשום' in lower or 'לפני יומיים' in lower:
        return offset_date(-2), 'שלשום'
    import re
    m = re.search(r'\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b', text)
    if m:
        day, mon = m.group(1).zfill(2), m.group(2).zfill(2)
        yr = m.group(3) if m.group(3) else str(datetime.now().year)
        if len(yr) == 2:
            yr = '20' + yr
        return f"{day}/{mon}/{yr}", m.group(0)
    return None, None

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "שלום! אני מנהל תקציב הטיול שלך 🧳\n\n"
        "שלח לי הוצאות כך:\n"
        "• `קפה 40000` — הוצאה להיום\n"
        "• `אתמול מונית 150000` — הוצאה לאתמול\n"
        "• `24/04 מלון 500000` — תאריך ספציפי\n"
        "• `הגענו להודו` — עדכון מדינה\n\n"
        "פקודות:\n"
        "/summary — סיכום הוצאות\n"
        "/today — הוצאות היום\n"
        "/list — כל ההוצאות\n"
        "/clear — מחיקת הכל",
        parse_mode='Markdown'
    )

async def summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    exps = u['expenses']
    if not exps:
        await update.message.reply_text("אין הוצאות עדיין.")
        return
    total_ils = sum(to_ils(e['amount'], e['currency']) for e in exps)
    td = today_str()
    today_ils = sum(to_ils(e['amount'], e['currency']) for e in exps if e['date'] == td)
    countries = len(set(e['country'] for e in exps))
    cat_totals = {}
    for e in exps:
        cat_totals[e['category']] = cat_totals.get(e['category'], 0) + to_ils(e['amount'], e['currency'])
    cats = '\n'.join(f"  {c}: {fmt_ils(v)}" for c, v in sorted(cat_totals.items(), key=lambda x: -x[1]))
    await update.message.reply_text(
        f"📊 *סיכום תקציב*\n\n"
        f"סה\"כ: *{fmt_ils(total_ils)}*\n"
        f"היום: *{fmt_ils(today_ils)}*\n"
        f"מדינות: {countries}\n"
        f"הוצאות: {len(exps)}\n\n"
        f"*לפי קטגוריה:*\n{cats}",
        parse_mode='Markdown'
    )

async def today_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    td = today_str()
    exps = [e for e in u['expenses'] if e['date'] == td]
    if not exps:
        await update.message.reply_text("אין הוצאות להיום.")
        return
    total = sum(to_ils(e['amount'], e['currency']) for e in exps)
    lines = '\n'.join(f"• {e['category']} | {e['desc']} | {e['amount']:,} {e['currency']} ({fmt_ils(to_ils(e['amount'], e['currency']))})" for e in exps)
    await update.message.reply_text(f"📅 *הוצאות היום ({td})*\n\n{lines}\n\n*סה\"כ: {fmt_ils(total)}*", parse_mode='Markdown')

async def list_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    u = get_user(update.effective_user.id)
    exps = u['expenses']
    if not exps:
        await update.message.reply_text("אין הוצאות עדיין.")
        return
    running = 0
    lines = []
    for e in reversed(exps):
        running += to_ils(e['amount'], e['currency'])
    running = 0
    for e in list(reversed(exps))[:20]:
        ils = to_ils(e['amount'], e['currency'])
        running += ils
        lines.append(f"{e['date']} | {e['category']} | {e['desc']} | {e['amount']:,} {e['currency']} | {fmt_ils(ils)}")
    total = sum(to_ils(e['amount'], e['currency']) for e in exps)
    text = '\n'.join(lines)
    if len(exps) > 20:
        text += f"\n\n_(מציג 20 אחרונות מתוך {len(exps)})_"
    await update.message.reply_text(f"📋 *כל ההוצאות:*\n\n`{text}`\n\n*סה\"כ: {fmt_ils(total)}*", parse_mode='Markdown')

async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    get_user(update.effective_user.id)['expenses'] = []
    await update.message.reply_text("✅ כל ההוצאות נמחקו.")

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    import re
    u = get_user(update.effective_user.id)
    raw = update.message.text.strip()
    lower = raw.lower()

    # country detection
    arrivals = ['הגענו ל', 'הגענו אל', 'עברנו ל', 'עברנו אל', 'אנחנו ב', 'הגעתי ל']
    country_detected = None
    for p in arrivals:
        if p in lower:
            rest = raw[lower.index(p) + len(p):].split()[0]
            country_detected = rest
            break
    if not country_detected:
        for c in COUNTRY_CURRENCY:
            if lower.strip('.') == c.lower():
                country_detected = c
                break

    explicit_cur = None
    for w, c in CURRENCY_WORDS.items():
        if w.lower() in lower:
            explicit_cur = c
            break

    if country_detected:
        ckey = next((k for k in COUNTRY_CURRENCY if k.lower() == country_detected.lower()), None)
        if ckey:
            u['country'] = ckey
            u['currency'] = explicit_cur or COUNTRY_CURRENCY[ckey]
        else:
            u['country'] = country_detected
            if explicit_cur:
                u['currency'] = explicit_cur
        await update.message.reply_text(f"✅ עודכן: {u['country']} | {u['currency']}")
        return

    exp_date, date_kw = parse_date(raw)
    if date_kw:
        raw = raw.replace(date_kw, '').strip()
    exp_date = exp_date or today_str()

    num_m = re.search(r'(\d[\d,\.]*)', raw)
    if not num_m:
        await update.message.reply_text("לא הצלחתי לזהות הוצאה. נסה: `קפה 40000` או `אתמול מונית 150000`", parse_mode='Markdown')
        return

    amount = float(num_m.group(1).replace(',', ''))
    desc = raw.replace(num_m.group(0), '').strip() or 'הוצאה'
    currency = explicit_cur or u['currency']
    cat = guess_category(desc)
    ils = to_ils(amount, currency)

    u['expenses'].insert(0, {
        'date': exp_date, 'country': u['country'], 'category': cat,
        'desc': desc, 'amount': amount, 'currency': currency
    })

    total_ils = sum(to_ils(e['amount'], e['currency']) for e in u['expenses'])
    td = today_str()
    today_ils = sum(to_ils(e['amount'], e['currency']) for e in u['expenses'] if e['date'] == td)
    date_label = 'היום' if exp_date == td else exp_date

    await update.message.reply_text(
        f"✅ *{cat}* נרשם [{date_label}]\n"
        f"{desc} | {amount:,.0f} {currency} | {fmt_ils(ils)}\n\n"
        f"היום: {fmt_ils(today_ils)} | סה\"כ: {fmt_ils(total_ils)}",
        parse_mode='Markdown'
    )

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("today", today_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("clear", clear_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
