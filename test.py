from datetime import datetime, timedelta
import re
from DatabaseManager import DatabaseManager
from JiraManager import JiraManager

# jira = JiraManager()

# msk_timedate = datetime.now() - timedelta(hours=4)
# upper_datetime = msk_timedate.strftime("%Y-%m-%d %H:%M")
# lower_datetime = (msk_timedate - timedelta(minutes=45)).strftime("%Y-%m-%d %H:%M")

# #jira.jiraInner.transition_issue('PRVWB-7091', transition='771')

# # Обновление UAT-задач (в разработке)

# # к внешнему фильтру только поиск в промежутке updated
# jira.current_outer_issues = 'assignee in (BTretail, DKX6LQ7, DKX62IC) AND type = Bug AND DemandID ~ PRJ-2527 AND' \
#                             ' status != Closed' \
#                             ' AND updated < "' + upper_datetime + '" AND updated > "' + lower_datetime + '"'

# jira.update_issues_from_outer_to_inner()

#db = DatabaseManager()

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

    print(current_filters)

message = '/filter_create inner UATs "assignee in (BTretail, DKX6LQ7, DKX62IC) AND type = Bug AND DemandID ~ PRJ-2527 AND status != Closed"'

splitted_message = message.split(' ')
if len(splitted_message) > 3:
    command = splitted_message[0]
    owner_name = splitted_message[1]
    filter_name = splitted_message[2]

    print(command)
    print(owner_name)
    print(filter_name)

    matched_filter = re.search(r'"(.*)"', message)
    if matched_filter:
        matched_value = matched_filter.group(0)
        matched_value_length = len(matched_value)
        filter_value = matched_value[1 : matched_value_length - 1]

        print(filter_value)