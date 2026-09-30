import telebot
from telebot import types
import time
import json

from selenium import webdriver
from selenium_stealth import stealth
from bs4 import BeautifulSoup

from curl_cffi import requests

def init_webdriver():
    driver = webdriver.Chrome()
    stealth(driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris Xe Graphics",
            fix_hairline=True)
    driver.maximize_window()
    return driver

def scrolldown(driver, deep):
    for _ in range(deep):
        driver.execute_script('window.scrollBy(0, 500)')
        #задержка для ослабления нагрузки
        time.sleep(0.1)

def get_product_info(product_url):
    session = requests.Session()

    raw_data = session.get("https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=" + product_url)
    json_data = json.loads(raw_data.content.decode())

    full_name = json_data["seo"]["title"]

    if json_data["layout"][0]["component"] == "userAdultModal":
        product_id = str(full_name.split()[-1])[1:-1]
        return (product_id, full_name, "Товар для лиц старше 18 лет", None, None)
    else:
        price = json.loads(json_data["seo"]["script"][0]["innerHTML"])["offers"]["price"] + " " +\
                json.loads(json_data["seo"]["script"][0]["innerHTML"])["offers"]["priceCurrency"]
        product_id = json.loads(json_data["seo"]["script"][0]["innerHTML"])["sku"]

        return (product_id, price)

def get_searchpage_cards(driver, url, all_cards):
    driver.get(url)
    scrolldown(driver, 100)
    search_page_html = BeautifulSoup(driver.page_source, "html.parser")

    content = search_page_html.find("div", {"id": "layoutPage"})
    content = content.find("div")

    content_with_cards = content.find("div", {"class": "widget-search-result-container"})
    content_with_cards = content_with_cards.find("div").findChildren(recursive=False)

    cards_in_page = list()
    for card in content_with_cards:
        card_url = card.find("a", href=True)["href"]
        card_name = card.find("span", {"class": "tsBody500Medium"}).contents[0]

        product_url = "https://ozon.ru" + card_url

        product_id, price = get_product_info(card_url)
        card_info = {product_id: {"short_name": card_name,
                                  "url": product_url,
                                  "price": price,
                                  "product_id": product_id
                                  }
                     }
        cards_in_page.append(card_info)
        
    return cards_in_page

# -- coding: cp1251 --
bot = telebot.TeleBot("XXX")

command_list = """
Команды, доступные для вас:
/help - Помощь и список команд
/checkprod - После ввода этой команды вы получите список продуктов для сравнения.
/savedprod - Сохранённые вами продукты для их быстрого сравнения.
"""

products_db = {
    "Молоко": ["Parmalat"],
    "Чай и кофе": [""],
    "колбаса": [""],
    "чипсы": [""],
    "Фрукты и ягоды": [""],
    "Овощи": [""]
}

user_states = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Добро пожаловать! Введите /help для получения списка команд.")

@bot.message_handler(commands=['help'])
def send_help(message):
    bot.send_message(message.chat.id, command_list, parse_mode='Markdown')

@bot.message_handler(commands=['checkprod'])
def check_prod(message):
    markup = types.InlineKeyboardMarkup()
    categories = [types.InlineKeyboardButton(text=cat, callback_data=cat) for cat in products_db.keys()]
    markup.add(*categories)
    
    bot.send_message(message.chat.id, "Выберите категорию продуктов:", reply_markup=markup)

@bot.message_handler(commands=['savedprod'])
def saved_prod(message):
    bot.send_message(message.chat.id, "Здесь будут ваши сохранённые продукты.")

@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.data in products_db.keys():
        bot.send_message(call.message.chat.id, "Подождите, собираем информацию...")
        search_list = [call.data]  # Сохраняем категорию
        cards_in_page = parse_products(search_list)  # Вызываем функцию парсинга
        bot.send_message(call.message.chat.id, "Парсинг завершен! Введите название продукта, который хотите найти:")
        
        user_states[call.message.chat.id] = cards_in_page  # Сохраняем результаты для пользователя
        bot.register_next_step_handler(call.message, process_search)

def parse_products(search_list):
    url_ozon = "https://www.ozon.ru"
    driver = init_webdriver()
    all_cards = []
    
    for search_tag in search_list:
        url_search = f"https://www.ozon.ru/search/?text={search_tag}&from_global=true"
        try:
            search_cards = get_searchpage_cards(driver, url_search, [])
            for card in search_cards:
                all_cards.append(card)
        except Exception as e:
            print(f"Ошибка при парсинге: {e}")

    return all_cards

def process_search(message):
    user_id = message.chat.id
    cards_in_page = user_states.get(user_id, [])

    if not cards_in_page:
        bot.send_message(user_id, "К сожалению, продукты не найдены.")
        return

    bot.send_message(user_id, "Выберите продукт из следующих (введите название):")
    
    # Находим 3 самых дешевых товара
    cheap_products = sorted(cards_in_page, key=lambda x: x[1]['price'])[:3]
    
    response = ""
    for product in cheap_products:
        response += f"{product[0]} - {product[1]['short_name']}: {product[1]['price']} Р\n"
    
    if response:
        bot.send_message(user_id, response)
    else:
        bot.send_message(user_id, "Нет доступных продуктов.")

bot.polling(none_stop=True)









'''
    content_with_next = [div for div in content.find_all("a", href=True) if "Дальше" in str(div)]
    if not content_with_next:
        return cards_in_page
    else:
        next_page_url = "https://www.ozon.ru" + content_with_next[0]["href"]
        all_cards.extend(get_searchpage_cards(driver, next_page_url, cards_in_page))
        return all_cards
'''
