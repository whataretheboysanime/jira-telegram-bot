from datetime import datetime, timedelta
from jira_manager import jira_manager
from database_manager import database_manager
import email_utils
import logging
import traceback
import os

cur_date = datetime.now().strftime("%Y-%m-%d")

filename = 'jira_' + cur_date + '.log'

logging.basicConfig(filename=os.path.dirname(os.path.abspath(__file__)) + "/../logs/" + filename, level=logging.INFO)

try:

    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "  JiraBot  :   " + 'start')

    with open(os.path.dirname(os.path.abspath(__file__)) + '/../conf/app_settings.json', encoding='utf-8') as settings_file:
        settings = json.load(settings_file)

    timezone_differ = settings["JIRA settings"]["Time zone difference"]
    update_delta = settings["JIRA settings"]["Delta for update issue"]

    msk_timedate = datetime.now() + timedelta(hours=timezone_differ)
    upper_datetime = msk_timedate.strftime("%Y-%m-%d %H:%M")

    # вынести в настройки время апдейта задач
    lower_datetime = (msk_timedate - timedelta(minutes=update_delta)).strftime("%Y-%m-%d %H:%M")

    jira = jira_manager()

    filters = jira.db.get_filters_by_group('creation')

    #уникальные наименования фильтров
    unique_name = list(set([filter['name'] for filter in filters]))

    for filter_name in unique_name:
        #список объектов, полученных при фильтрации по наименованию
        current_filters = [
            filter
            for filter in filters
            if filter['name'] == filter_name
        ]

        if len(current_filters) == 2:

            inner_filter = [
                                filter['condition']
                                for filter in current_filters
                                if filter['owner_name'] == 'inner'
                            ][0]

            outer_filter = [
                                filter['condition']
                                for filter in current_filters
                                if filter['owner_name'] == 'outer'
                            ][0]

            # Создание задач

            jira.current_outer_issues = outer_filter
            jira.current_inner_issues = inner_filter

            jira.create_issues_from_outer_to_inner()

            # Закроем задачи которые уже закрыты
            jira.close_inner_issues_from_outer()

            # Обновление задач

            jira.current_outer_issues = outer_filter + ''\
                                    ' AND updated < "' + upper_datetime + '" AND updated > "' + lower_datetime + '"'

            jira.update_issues_from_outer_to_inner()

    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "  JiraBot  :   " + 'finish')

except Exception as e:

    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                  'Отправка email (JiraBot - error):\n' +
                 str(e) + "\n\n" + traceback.format_exc()
                  )
    email_utils.send_email("TelegramBot - error", str(e) + "\n\n" + traceback.format_exc())