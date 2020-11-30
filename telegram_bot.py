from datetime import datetime
from database_manager import database_manager
from jira_manager import jira_manager
import email_utils
import telebot
import json
import logging
import traceback
import os
import re

with open(os.path.dirname(os.path.abspath(__file__)) + '/../conf/app_settings.json', encoding='utf-8') as settings_file:
    settings = json.load(settings_file)

def bot_polling():

    try:
        db = database_manager()
        jira = jira_manager()

        bot = telebot.TeleBot(settings['Telebot token'])

        def contain_this_user_in_whitelist(authorize_data):
            for user in settings["Whitelist"]:
                if user['Username'] == authorize_data[1] and user['Password'] == authorize_data[2]:
                    return True
            return False


        def request_authorize(tg_id):
            bot.send_message(tg_id, settings['Command messages']['request authorize'])


        def authorize_this_user(chat, authorize_data):
            if contain_this_user_in_whitelist(authorize_data):
                db.create_new_user(chat)
                bot.send_message(chat.id, settings['Command messages']['start'])
            else:
                bot.send_message(chat.id, settings['Command messages']['error authorize'])

        def parse_add_filter_command(message, group_name, method):
            splitted_message = message.split(' ')
            if len(splitted_message) > 3:
                command = splitted_message[0]
                owner_name = splitted_message[1]
                filter_name = splitted_message[2]

                matched_filter = re.search(r'"(.*)"', message)
                if matched_filter:
                    matched_value = matched_filter.group(0)
                    matched_value_length = len(matched_value)
                    filter_value = matched_value[1 : matched_value_length - 1]

                    if method == 'add':
                        jira.db.add_filter(group_name, owner_name, filter_name, filter_value)
                    elif method == 'update':
                        jira.db.update_filter(group_name, owner_name, filter_name, filter_value)

        @bot.message_handler(commands=['start', 'help'])
        def start_message(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:
                bot.send_message(message.chat.id, settings['Command messages']['start'])


        # @bot.message_handler(commands=['current'])
        # def send_current_issues(message):
        #     if not db.contain_this_user_in_db(message.chat.id):
        #         request_authorize(message.chat.id)
        #     else:
        #         bot.send_message(message.chat.id, jira.get_bank_issues())


        @bot.message_handler(commands=['authorize'])
        def authorize(message):
            input = message.html_text.split(" ")
            if len(input) == 3 and "/authorize " in message.html_text:
                authorize_this_user(message.chat, input)
            else:
                bot.send_message(message.from_user.id, settings['Command messages']['default'])


        @bot.message_handler(commands=['create'])
        def create_task(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:

                input = message.html_text.split(" ")

                if len(input) == 1 and "/create" in message.html_text and hasattr(message, "reply_to_message"):

                    jira_outer_session = jira.check_jira_outer_session()
                    issue_key = message.reply_to_message.html_text.split(" ")[0]

                    result = jira.create_issue(issue_key, jira_outer_session)
                    if result == "Success":
                        bot.send_message(message.chat.id, settings['Command messages']['create issue success'])
                    else:
                        raise Exception(result)

                elif len(input) == 2 and "/create" in message.html_text:

                    jira_outer_session = jira.check_jira_outer_session()
                    issue_key = message.html_text.split(" ")[1]

                    result = jira.create_issue(issue_key, jira_outer_session)
                    if result == "Success":
                        bot.send_message(message.chat.id, settings['Command messages']['create issue success'])
                    else:
                        raise Exception(result)

        @bot.message_handler(commands=['comment'])
        def create_comment(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:

                input = message.html_text.split(" ")

                if len(input) == 2 and hasattr(message, "reply_to_message"):
                    issue_key = input[1]

                    result = jira.send_comment_to_inner_issue(issue_key, message.reply_to_message.html_text)

                    if result == 'Success':
                        bot.send_message(message.chat.id, 'Комментарий был успешно добавлен в задачу ' + issue_key)
                    else:
                        message = 'Задача ' + issue_key + ' не была найдена в системе.'
                        bot.send_message(message.chat.id, message)
                        raise Exception(message)

        @bot.message_handler(commands=['add_filter_notification'])
        def add_filter_notification(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:
                parse_add_filter_command(message.html_text, 'notification', 'add')
                bot.send_message(message.chat.id, settings['Command messages']['create filter success'])

        @bot.message_handler(commands=['add_filter_creation'])
        def add_filter_creation(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:
                parse_add_filter_command(message.html_text, 'creation', 'add')
                bot.send_message(message.chat.id, settings['Command messages']['create filter success'])

        @bot.message_handler(commands=['delete_filter'])
        def delete_filter(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:
                splitted_message = message.html_text.split(' ')
                if len(splitted_message) == 2:
                    jira.db.delete_filter(splitted_message[1])
                    bot.send_message(message.chat.id, settings['Command messages']['delete filter success'])

        @bot.message_handler(commands=['update_filter_notification'])
        def update_filter_notification(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:
                parse_add_filter_command(message.html_text, 'notification', 'update')
                bot.send_message(message.chat.id, settings['Command messages']['update filter success'])

        @bot.message_handler(commands=['update_filter_creation'])
        def update_filter_creation(message):
            if not db.contain_this_user_in_db(message.chat.id):
                request_authorize(message.chat.id)
            else:
                parse_add_filter_command(message.html_text, 'creation', 'update')
                bot.send_message(message.chat.id, settings['Command messages']['update filter success'])


        # @bot.message_handler(content_types=['text'])
        # def get_text_messages(message):
        #    input = message.html_text.split(" ")
        #    if len(input) == 3 and "/authorize " in message.html_text:
        #        authorize_this_user(message.chat, input)
        #     else:
        #         bot.send_message(message.from_user.id, settings['Command messages']['default'])

        bot.polling()

    except Exception as e:

        traceback_str = traceback.format_exc()

        if "Read timed out." in traceback_str or "Connection aborted." in traceback_str:
            bot_polling()
        else:
            cur_date = datetime.now().strftime("%Y-%m-%d")

            filename = 'tg_' + cur_date + '.log'

            logging.basicConfig(filename=os.path.dirname(os.path.abspath(__file__)) + "/../../logs/" + filename, level=logging.INFO)
            logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                        'Отправка email (TelegramBot - error):\n' +
                        str(e) + "\n\n" + traceback_str
                        )
            email_utils.send_email("TelegramBot - error", str(e) + "\n\n" + traceback_str)

bot_polling()