from datetime import datetime, timedelta
from JiraManager import JiraManager
from DatabaseManager import DatabaseManager
import EmailUtils
import logging
import traceback
import os

cur_date = datetime.now().strftime("%Y-%m-%d")

filename = 'jira_' + cur_date + '.log'

logging.basicConfig(filename=os.path.dirname(os.path.abspath(__file__)) + "/../logs/" + filename, level=logging.INFO)

try:

    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "  JiraBot  :   " + 'start')

    msk_timedate = datetime.now() - timedelta(hours=4)
    upper_datetime = msk_timedate.strftime("%Y-%m-%d %H:%M")

    # вынести в настройки время апдейта задач
    lower_datetime = (msk_timedate - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M")

    jira = JiraManager()

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

    # старый функционал

    # # Создание PMA-задач

    # jira.current_outer_issues = 'assignee in (FISonlineapp, DKX61HV, DKX68Y3, DKX6LQ7) AND project = PMA AND' \
    #                             ' resolution = Unresolved AND labels = P1149 AND text ~ "PLATF_POS"'
    # jira.current_inner_issues = 'project = PRVWB AND status in (Новый, "In Progress", Переоткрыт, Решено, Проверено,' \
    #                             ' "Ожидание ответа") AND text ~ "PMA*"'

    # jira.create_issues_from_outer_to_inner()

    # # Обновление PMA-задач (в разработке)

    # # к внешнему фильтру только поиск в промежутке updated
    # jira.current_outer_issues = 'assignee in (FISonlineapp, DKX61HV, DKX68Y3, DKX6LQ7) AND project = PMA AND' \
    #                             ' resolution = Unresolved AND labels = P1149 AND text ~ "PLATF_POS"' \
    #                             ' AND updated < "' + upper_datetime + '" AND updated > "' + lower_datetime + '" ' \
    #                             'ORDER BY priority DESC, updated DESC'

    # jira.update_issues_from_outer_to_inner()

    # # Создание UAT-задач

    # jira.current_outer_issues = 'assignee in (BTretail, DKX6LQ7) AND type = Bug AND DemandID ~ PRJ-2527 AND' \
    #                             ' status != Closed'
    # jira.current_inner_issues = 'project = PRVWB AND status in (Новый, "In Progress", Переоткрыт, Решено, Проверено,' \
    #                             ' "Ожидание ответа") AND text ~ "uat*"'

    # jira.create_issues_from_outer_to_inner()

    # # Обновление UAT-задач (в разработке)

    # # к внешнему фильтру только поиск в промежутке updated
    # jira.current_outer_issues = 'assignee in (BTretail, DKX6LQ7) AND type = Bug AND DemandID ~ PRJ-2527 AND' \
    #                             ' status != Closed' \
    #                             ' AND updated < "' + upper_datetime + '" AND updated > "' + lower_datetime + '"'

    # jira.update_issues_from_outer_to_inner()

    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "  JiraBot  :   " + 'finish')

except Exception as e:

    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                  'Отправка email (JiraBot - error):\n' +
                 str(e) + "\n\n" + traceback.format_exc()
                  )
    EmailUtils.send_email("TelegramBot - error", str(e) + "\n\n" + traceback.format_exc())