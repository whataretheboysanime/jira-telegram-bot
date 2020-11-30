from datetime import datetime
from DatabaseManager import DatabaseManager
import EmailUtils
from JiraManager import JiraManager
import telebot
import json
import logging
import traceback
import os.path

with open(os.path.dirname(os.path.abspath(__file__)) + '/../conf/app_settings.json', encoding='utf-8') as settings_file:
    settings = json.load(settings_file)

try:

    jira = JiraManager()
    bot = telebot.TeleBot(settings['Telebot token'])

    filters = jira.db.get_filters_by_group('notification')

    def mailing(filter):
        issues_obj = jira.get_bank_issues(filter['name'], filter['owner_name'], filter['condition'])

        if issues_obj['Messages']:
            users = jira.db.get_users()
            for user in users:
                for message in issues_obj['Messages']:
                    bot.send_message(user, message)

        jira.db.check_non_actual_issues(filter['name'], filter['owner_name'], issues_obj['Issues'])

    for filter in filters:
        mailing(filter)

except Exception as e:

    cur_date = datetime.now().strftime("%Y-%m-%d")

    filename = 'mailing_' + cur_date + '.log'

    logging.basicConfig(filename=os.path.dirname(os.path.abspath(__file__)) + "/../logs/" + filename, level=logging.INFO)
    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                 'Отправка email (MailingTelegram - error):\n' +
                 str(e) + "\n\n" + traceback.format_exc()
                 )
    EmailUtils.send_email("MailingTelegram - error", str(e) + "\n\n" + traceback.format_exc())
