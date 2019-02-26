import requests
import json
from telegram.ext import CommandHandler
from telegram.ext import MessageHandler
from telegram.ext import Filters
from telegram.ext import Updater

# This Telegram bot uses the Totle API to check prices of various ERC-20 tokens across multiple exchanges
# and returns the current bid and ask price for each exchange that lists the token.


# Totle API endpoints for exchange and price data
tokenListAPI = 'https://services.totlesystem.com/tokens'
tokenPriceAPI = 'https://services.totlesystem.com/tokens/prices'
tokenExchangesAPI = 'https://services.totlesystem.com/exchanges'


# Telegram bot
botToken = "646659009:AAFX2K6WKOs9_EED-ru2k1RlkrdKwwqCxKM"


# Handle Totle API requests
def get_totle_api_data(requested_api_call):
    try:
        request = requests.get(requested_api_call)
        return request
    except requests.exceptions.Timeout:
        print("I'm sorry, my connection to Totle timed out. Please try again.")
    except requests.exceptions.TooManyRedirects:
        print("I'm sorry, I couldn't find the API requested. Please contact Totle support.")
    except requests.exceptions.RequestException as e:
        print("I'm sorry, there was an unexpected error when I tried to process your request. Please try again.")
        print(e)


# Retrieve a list of exchanges from Totle Exchange API endpoint
def get_exchanges():
    response_exchange_names = get_totle_api_data(tokenExchangesAPI)
    content_exchanges = response_exchange_names.content.decode("utf8")
    exchange_list_data = json.loads(content_exchanges)
    return exchange_list_data['exchanges']


# Retrieve price data for a specific token from Totle Price API endpoint
def get_token_price(contract, update):
    response_token_prices = get_totle_api_data(tokenPriceAPI)
    content_price = response_token_prices.content.decode("utf8")
    token_price_data = json.loads(content_price)
    output = "Results from Totle's Price Data\n\n"

    for tokenContract in token_price_data['response']:

        if tokenContract == contract:
            exchange_names = get_exchanges()
            token_exchange_prices = token_price_data['response'][tokenContract]

            # Set up variables for arbitrage check
            highest_bid = -99999999.000
            lowest_ask = 99999999.000
            hb_exchange = "None"
            la_exchange = "None"

            for k, v in token_exchange_prices.items():
                for exchange in exchange_names:
                    exchange_key = exchange['id']
                    if int(exchange_key) == int(k):
                        output += "Bid: {}, Ask: {}, Exchange: {}\n".format(v['bid'], v['ask'], exchange['name'])
                        if float(v['bid']) > float(highest_bid):
                            highest_bid = float(v['bid'])
                            hb_exchange = exchange['name']
                        if float(v['ask']) < float(lowest_ask):
                            lowest_ask = float(v['ask'])
                            la_exchange = exchange['name']
            update.message.reply_text(output)

            # Report results of the arbitrage opportunity check
            output = "Results of Arbitrage Testing\n\n"
            if highest_bid > 0:
                gap = highest_bid - lowest_ask
                gap_percent = gap / lowest_ask
                output += "Lowest Ask: {} [{}] \nHighest Bid: {} [{}]\n".format(lowest_ask, la_exchange, highest_bid, hb_exchange)
                output += "Bid minus Ask: {0:.8f} \nGap %: {0:.8f}%\n".format(gap, gap_percent)

                if gap > 0:
                    output += "Good news, there might be some arbitrage potential!\n"
                    output += "Purchase at: {} for {}\n".format(la_exchange, lowest_ask)
                    output += "Sell at: {} for {}\n".format(hb_exchange, highest_bid)
                    update.message.reply_text(output)
                else:
                    output += "Sorry, I didn't find any arbitrage potential at these prices.\n"
                    update.message.reply_text(output)
            else:
                output = "Sorry, I couldn't find any data to check for arbitrage potential."
                update.message.reply_text(output)

            return
    output += "I'm sorry, I couldn't find any exchange data for that token."
    update.message.reply_text(output)


# Retrieve list of tokens from Totle Token List API endpoint
def retrieve_token_list(symbol, update):

    response_token_list = get_totle_api_data(tokenListAPI)
    content_token_list = response_token_list.content.decode("utf8")
    token_list_data = json.loads(content_token_list)

    token_found = 0
    for token in token_list_data['tokens']:
        tName = token['name']
        tSymbol = token['symbol']
        tContract = token['address']
        if tSymbol == symbol.upper():
            token_found = 1
            update.message.reply_text("Yay! Totle has data on {} [{}]. I'll check our exchange data.".format(tName, tSymbol))
            get_token_price(tContract, update)

    if token_found == 0:
        update.message.reply_text("I'm sorry, Totle doesn't have any data on {}".format(symbol.upper()))
        update.message.reply_text("You can try searching for another token with /check TokenSymbol")


# Check the data for arbitrage opportunities and report any if they exist
def check_for_arbitrage(bot, token_list, token_prices, exchange_list, update):

    output = ""
    exchange_names = exchange_list['exchanges']

    for token in token_list['tokens']:
        tName = token['name']
        tSymbol = token['symbol']
        tContract = token['address']

        try:
            token_exchange_prices = token_prices['response'][tContract]

            # Set up variables for arbitrage check
            highest_bid = -99999999.000
            lowest_ask = 99999999.000
            hb_exchange = "None"
            la_exchange = "None"

            # Compare different exchange prices to get highest bid and lowest ask available
            for k, v in token_exchange_prices.items():
                for exchange in exchange_names:
                    exchange_key = exchange['id']
                    if int(exchange_key) == int(k):
                        if float(v['bid']) > float(highest_bid):
                            highest_bid = float(v['bid'])
                            hb_exchange = exchange['name']
                        if float(v['ask']) < float(lowest_ask):
                            lowest_ask = float(v['ask'])
                            la_exchange = exchange['name']

            outputLength = len(output) + len(tName) + len(tSymbol) + len(token_exchange_prices)

            gap = highest_bid - lowest_ask
            arbitrage_percent = gap / lowest_ask * 100
            if gap > 0:
                if la_exchange == hb_exchange:
                    print("Possible price error for {} [{}] (arbitrage on same exchange unlikely.)".format(tName, tSymbol))
                else:
                    if outputLength < 2048:

                        # Compile and send the arbitrage data to Telegram
                        output = "{} [{}]\n\n".format(tName, tSymbol)
                        output += "{} Lowest Ask [{}]\n".format('{:.8f}'.format(lowest_ask), la_exchange)
                        output += "{} Highest Bid [{}]\n\n".format('{:.8f}'.format(highest_bid), hb_exchange)
                        output += "Arbitrage Potential = {:.1f}%\n".format(arbitrage_percent)
                        output += "Buy at {}, sell at {}\n".format(la_exchange, hb_exchange)
                        update.message.reply_text(output)
                    else:
                        output = "{} [{}] {:.1f}%\n".format(tName, tSymbol, arbitrage_percent)
                        output += " {} Bid".format('{:.8f}'.format(highest_bid))
                        output += " [{}]\n".format(hb_exchange)
                        output += " {} Ask".format('{:.8f}'.format(lowest_ask))
                        output += " [{}]\n\n".format(la_exchange)
                        update.message.reply_text(output)
        except Exception as e:
            if str(e).strip("'") == tContract:
                print("Couldn't find price data for {} [{}] [{}]".format(tName, tSymbol, e))
            else:
                print(e)


# Retrieve Totle token API data
def retrieve_totle_data(bot, update):

    # Retrieve token list
    update.message.reply_text("Retrieving token list\n")
    response_token_list = get_totle_api_data(tokenListAPI)
    content_token_list = response_token_list.content.decode("utf8")
    token_list_data = json.loads(content_token_list)

    # Retrieve token price data
    update.message.reply_text("Retrieving token price data\n")
    response_token_prices = get_totle_api_data(tokenPriceAPI)
    content_price = response_token_prices.content.decode("utf8")
    token_price_data = json.loads(content_price)

    # Retrieve exchange price data
    update.message.reply_text("Retrieving exchange data\n")
    response_exchange_names = get_totle_api_data(tokenExchangesAPI)
    content_exchanges = response_exchange_names.content.decode("utf8")
    exchange_list_data = json.loads(content_exchanges)

    # Send data to check for arbitrage
    check_for_arbitrage(bot, token_list_data, token_price_data, exchange_list_data, update)
    update.message.reply_text("Arbitrage check completed.")


# Commence the arbitrage check
def arbitrage(bot, update):
    try:
        update.message.reply_text("Thanks, I'll check for data now...")
        retrieve_totle_data(bot, update)
    except Exception as e:
        print(e)


# Telegram command handlers
def start(bot, update):
    output = "Hi! To display the price of a token using Totle, use: /check TokenSymbol (ex: /check BAT)"
    update.message.reply_text(output)


def check_price(bot, update, args):

    try:
        symbol = args[0].upper()
        update.message.reply_text("Thanks, checking now for token symbol: {}".format(symbol))
        retrieve_token_list(symbol, update)
    except:
        output = "Sorry, I couldn't understand your request. Please try: /check TokenSymbol"
        update.message.reply_text(output)


# Telegram bot operations
def main():
    # Set the updater
    botUpdater = Updater(botToken)

    # Set the dispatcher to register the command handlers for Telegram
    botDispatch = botUpdater.dispatcher

    # Register the Telegram command handlers
    botDispatch.add_handler(CommandHandler("start", start))
    botDispatch.add_handler(CommandHandler("help", start))
    botDispatch.add_handler(CommandHandler("check", check_price, pass_args=True))
    botDispatch.add_handler(CommandHandler("arbitrage", arbitrage))

    # Start checking updates
    botDispatch.add_handler(MessageHandler(Filters.text, check_price))
    botDispatch.add_handler(MessageHandler(Filters.text, arbitrage))

    # Start the bot
    botUpdater.start_polling(poll_interval=0.0, timeout=10, clean=True)
    botUpdater.idle()


if __name__ == '__main__':
    main()

