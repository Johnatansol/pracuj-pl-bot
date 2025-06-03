import os
import requests
from bs4 import BeautifulSoup
import asyncio
from datetime import datetime
from telegram import Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
import json
import re
import hashlib

load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_IDS = [int(id.strip()) for id in os.getenv("TELEGRAM_CHAT_IDS").split(",")]
PRACUJ_URL = "https://www.pracuj.pl/praca/zywiec;wp?rd=30&ws=0&popular=3"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept-Language": "pl-PL,pl;q=0.9"
}

bot = Bot(TOKEN)

async def test(update, context):
    await update.message.reply_text("✅ Bot działa! Rozpoczynam skanowanie...")
    await send_all_offers()

async def force(update, context):
    await update.message.reply_text("⚠️ Wymuszam wysłanie WSZYSTKICH ofert...")
    await send_all_offers(force_send=True)

def load_sent_offers():
    try:
        if os.path.exists("sent_offers.json"):
            with open("sent_offers.json", "r") as f:
                return json.load(f)
    except:
        return {}
    return {}

def save_offer(offer_id):
    sent_offers = load_sent_offers()
    sent_offers[offer_id] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open("sent_offers.json", "w") as f:
        json.dump(sent_offers, f)

def generate_offer_id(link, title):
    offer_id = re.search(r'(?:/oferta,|o=)(\d+)', link)
    if offer_id:
        return offer_id.group(1)
    unique_str = f"{link}_{title}"
    return hashlib.md5(unique_str.encode()).hexdigest()[:16]

async def send_all_offers(force_send=False):
    print("\n🔍 Rozpoczynam skanowanie ofert (force_send={})...".format(force_send))
    try:
        response = requests.get(PRACUJ_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        with open("last_page.html", "w", encoding="utf-8") as f:
            f.write(response.text)
        
        offers = []
        for elem in soup.find_all(['div', 'article']):
            try:
                title_elem = elem.find(['h2', 'h3'], class_=lambda x: x and 'title' in x.lower()) or \
                             elem.find(attrs={"data-test": "offer-title"}) or \
                             elem.find(class_=lambda x: x and 'offer' in x.lower())
                link_elem = elem.find('a', href=lambda x: x and '/praca/' in x) or \
                            elem.find(attrs={"data-test": "offer-link"})
                
                if title_elem and link_elem:
                    title = title_elem.get_text(strip=True)
                    link = link_elem['href']
                    if not link.startswith('http'):
                        link = f"https://www.pracuj.pl{link}"
                    offer_id = generate_offer_id(link, title)
                    offers.append((title, link, offer_id))
            except:
                continue
        
        print(f"Znaleziono {len(offers)} ofert")
        
        sent_offers = {} if force_send else load_sent_offers()
        new_offers = 0
        sent_ids = set()

        for title, link, offer_id in offers:
            try:
                if offer_id not in sent_offers and offer_id not in sent_ids:
                    message = f"🏭 Nowa oferta!\n\n{title}\n\n🔗 {link}"
                    print(f"📨 Wysyłam: {title[:50]}... (ID: {offer_id})")
                    for chat_id in CHAT_IDS:
                        await bot.send_message(
                            chat_id=chat_id,
                            text=message,
                            disable_web_page_preview=True
                        )
                        await asyncio.sleep(0.5)
                    if not force_send:
                        save_offer(offer_id)
                    sent_ids.add(offer_id)
                    new_offers += 1
                    await asyncio.sleep(1)

            except Exception as e:
                print(f"⚠️ Błąd przetwarzania oferty: {str(e)}")

        print(f"\n📊 Wysłano {new_offers} nowych ofert")
        
        # Zmiana: Brak powiadomień na Telegramie, gdy brak nowych ofert
        if new_offers == 0:
            print("ℹ️ Brak nowych ofert. Ostatnie sprawdzenie:", datetime.now().strftime('%H:%M:%S'))
            if len(offers) == 0:
                print("🔄 Nie znaleziono żadnych ofert na stronie.")

    except Exception as e:
        error_msg = f"❌ Błąd: {str(e)}"
        print(error_msg)
        for chat_id in CHAT_IDS:
            await bot.send_message(chat_id=chat_id, text=error_msg)

async def main():
    print(f"\n🤖 Bot wystartował dla chatów: {CHAT_IDS}")
    
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("test", test))
    application.add_handler(CommandHandler("force", force))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    
    print("\n🔍 Bot nasłuchuje komend /test i /force...")
    while True:
        await asyncio.sleep(180)
        await send_all_offers()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Zamykanie bota...")
    except Exception as e:
        print(f"💥 Niespodziewany błąd: {e}")