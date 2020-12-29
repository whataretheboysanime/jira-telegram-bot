from database_manager import database_manager
from jira import JIRA
import pyotp
import requests
import json
import re
import logging
from datetime import datetime
import traceback
import pickle
import os


# Help function
def get_title(html):
    return re.findall('<title>(.*?)</title>', html, flags=re.DOTALL)[0].strip()


class jira_manager:

    def __init__(self):
        cur_date = datetime.now().strftime("%Y-%m-%d")

        self.log_filename = os.path.dirname(os.path.abspath(__file__)) + '/../logs/' + 'jira_' + cur_date + '.log'

        logging.basicConfig(filename=self.log_filename, level=logging.INFO)

        logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start init JiraManager")

        with open(os.path.dirname(os.path.abspath(__file__)) + '/../conf/app_settings.json', encoding='utf-8') as settings_file:
            self.settings = json.load(settings_file)

        self.db = database_manager()

        self.jira_outer = JIRA(
            self.settings['JIRA settings']['Domain Outer JIRA'],
            basic_auth=(
                self.settings['Credentials Outer JIRA']['Login'],
                self.settings['Credentials Outer JIRA']['Password']
            )
        )
        self.jira_inner = JIRA(
            self.settings['JIRA settings']['Domain Inner JIRA'],
            basic_auth=(
                self.settings['Credentials Inner JIRA']['Login'],
                self.settings['Credentials Inner JIRA']['Password']
            )
        )

        self.__current_inner_issues = []
        self.__current_outer_issues = []

        logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End init JiraManager")

    @property
    def current_inner_issues(self):
        return self.__current_inner_issues

    @current_inner_issues.setter
    def current_inner_issues(self, filter_inner):
        self.__current_inner_issues = self.jira_inner.search_issues(filter_inner, maxResults=1000)

    @property
    def current_outer_issues(self):
        return self.__current_outer_issues

    @current_outer_issues.setter
    def current_outer_issues(self, filter_outer):
        self.__current_outer_issues = self.jira_outer.search_issues(filter_outer, maxResults=1000)

    def get_inner_issue_by_filter(self, filter_inner):
        return self.jira_inner.search_issues(filter_inner, maxResults=1000)

    def get_outer_issue_by_filter(self, filter_outer):
        return self.jira_outer.search_issues(filter_outer, maxResults=1000)

    def get_notification_issues(self, filter_name, owner_name, condition):
        messages = []

        issues = []
        host = ''
        if owner_name == 'outer':
            issues = self.jira_outer.search_issues(condition)
            host = self.settings['JIRA settings']['Domain Outer JIRA']

        elif owner_name == 'inner':
            issues = self.jira_inner.search_issues(condition)
            host = self.settings['JIRA settings']['Domain Inner JIRA']

        for issue in issues:
            if not self.db.contain_issue_by_key(filter_name, owner_name, issue.key):
                self.db.add_issue(filter_name, owner_name, issue)

                comment = ''

                comments = []
                if owner_name == 'inner':
                    comments = self.jira_inner.comments(issue)
                elif owner_name == 'outer':
                    comments = self.jira_outer.comments(issue)

                if comments:
                    i = len(comments) - 1
                    comment += "\n\nПоследний комментарий:\n" + comments[i].author.displayName + ''\
                    ' ' + comments[i].created + '\n' + comments[i].body


                messages.append(issue.key + " " + issue.fields.priority.name.split(" - ")[1] + " '"
                + issue.fields.summary + "'" + comment + "\n\n" + host + "/browse/" + issue.key)

        return {
            'Messages': messages,
            'Issues': issues
        }

    def send_comment_to_inner_issue(self, key, message):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start send_comment_to_inner_issue " + key)

        issue = self.jira_inner.issue(key)

        if not issue:
            logging.info(
                datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Задача не найдена в системе")

            return 'Error'
        else:
            self.jira_inner.add_comment(issue, message)

            return 'Success'

    def create_issue(self, project_name, key, jira_outer_session):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start create_issue " + key)

        issue = self.jira_outer.issue(key)

        issue_summary = issue.key + ' ' + issue.fields.summary
        issue_description = issue.fields.description

        # Если не передали наименование проекта, то скидываем в дефолтный
        if not project_name:
            project_name = self.settings["JIRA settings"]["Project name (default)"]

        # Создать задачу
        new_issue = self.jira_inner.create_issue(project=project_name, summary=issue_summary,
                                                description=issue_description,
                                                issuetype={'name': self.settings["JIRA settings"]["Issues type (default)"]})
        # Переназначить задачу
        self.jira_inner.assign_issue(new_issue, None)

        for user in self.settings["JIRA settings"]["Watchers"]:
            # Добавить вотчеров
            self.jira_inner.add_watcher(new_issue, user)

        # Проставить приоритет
        new_issue.update(priority={"id": issue.fields.priority.id})

        labels = [label for label in self.settings["JIRA settings"]["Labels"]]

        if labels:
            new_issue.update(fields={"labels": labels})

        # Залить комменты
        outer_comments = self.jira_outer.comments(issue)
        for outer_comment in outer_comments:
            self.jira_inner.add_comment(new_issue,
                                        outer_comment.author.displayName + ' ' + outer_comment.created +
                                        '\r\n' + outer_comment.body)

        if hasattr(issue.fields, 'attachment'):
            attachments = issue.fields.attachment
            for attach in attachments:
                self.jira_inner.add_attachment(issue=new_issue, attachment=attach.get(), filename=attach.filename)

        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End create_issue")

        return "Success"

    # Обновление задач
    def update_issues_from_outer_to_inner(self, project_name):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start update_issues_from_outer_to_inner")

        jira_outer_session = self.check_jira_outer_session()

        for outer_issue in self.current_outer_issues:

            finded_inner_issue = self.get_inner_issue_by_filter('summary ~ ' + outer_issue.key)

            if not finded_inner_issue:
                self.create_issue(project_name, outer_issue.key, jira_outer_session)
                return "Success"
            else:

                logging.info(
                    datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start update issue with key " + outer_issue.key)

                outer_issue = self.jira_outer.issue(outer_issue.key)

                inner_issue = self.jira_inner.issue(finded_inner_issue[0].key)

                # Блок переоткрытия задачи

                if 'Reopen' in outer_issue.fields.status.name and not 'Reopen' in inner_issue.fields.status.name:
                    transitions = self.jiraInner.transitions(inner_issue)
                    reopen_transition = [t['id'] for t in transitions if 'Reopen' in t['name']]

                    if reopen_transition:
                        self.jiraInner.transition_issue(inner_issue, reopen_transition[0])

                outer_issue_summary = outer_issue.key + ' ' + outer_issue.fields.summary
                if outer_issue_summary != inner_issue.fields.summary:
                    inner_issue.update(summary=outer_issue_summary)

                outer_issue_description = outer_issue.fields.description
                if outer_issue_description != inner_issue.fields.description:
                    inner_issue.update(description=outer_issue_description)

                outer_issue_priority_id = outer_issue.fields.priority.id
                if outer_issue_priority_id != inner_issue.fields.priority.id:
                    inner_issue.update(priority={"id": outer_issue_priority_id})

                # Залить комменты
                outer_comments = self.jira_outer.comments(outer_issue)
                inner_comments = self.jira_inner.comments(inner_issue)
                inner_comments_by_bot = [
                                            comment
                                            for comment in inner_comments
                                            if re.search(self.settings['Credentials Inner JIRA']['Login'], comment.author.displayName)
                                        ]
                inner_comments_max_index = len(inner_comments_by_bot) - 1
                for i in range(len(outer_comments)):

                    outer_comment = outer_comments[i]
                    inner_form_comment = outer_comment.author.displayName + ' ' + outer_comment.created + '\r\n' + outer_comment.body

                    if i > inner_comments_max_index:
                        self.jira_inner.add_comment(inner_issue, inner_form_comment)
                    else:
                        if inner_form_comment != inner_comments_by_bot[i].body:
                            inner_comments_by_bot[i].update(body = inner_form_comment)

                if hasattr(outer_issue.fields, 'attachment'):
                    outer_attachments = outer_issue.fields.attachment

                    inner_attachments = []
                    if hasattr(inner_issue.fields, 'attachment'):
                        inner_attachments = inner_issue.fields.attachment

                    for outer_attach in outer_attachments:

                        is_attach_find = False

                        for inner_attach in inner_attachments:
                            if outer_attach.filename == inner_attach.filename:
                                is_attach_find = True
                                break

                        if not is_attach_find:
                            self.jira_inner.add_attachment(issue=inner_issue, attachment=outer_attach.get(), filename=outer_attach.filename)

                logging.info(
                    datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End update issue")


        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End update_issues_from_outer_to_inner")

        return "Success"

    def create_issues_from_outer_to_inner(self, project_name):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start create_issues_from_outer_to_inner")

        jira_outer_session = self.check_jira_outer_session()

        for issue_outer in self.__current_outer_issues:
            logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Outer issue with key = " +
                        issue_outer.key
                        )
            key = issue_outer.key
            is_found_issue = False
            for issue_inner in self.__current_inner_issues:
                if issue_inner.fields.summary.find(key) > -1:
                    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Find inner issue with " +
                                "key = " + issue_inner.key
                                )
                    is_found_issue = True
            if not is_found_issue:

                if not project_name:
                    project_name = self.settings["JIRA settings"]["Project name"]

                issue_single_jql = 'project = ' + project_name + ' AND text ~ "' + key + '"'
                issues_list_single_inner = self.jira_inner.search_issues(issue_single_jql)
                if len(issues_list_single_inner) == 0:
                    self.create_issue(key, jira_outer_session)

        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End create_issues_from_outer_to_inner")

    def close_inner_issues_from_outer(self):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start close_inner_issues_from_outer")

        for issue_inner in self.__current_inner_issues:
            key = issue_inner.fields.summary.split(' ')[0]
            is_find = False
            for issue_outer in self.__current_outer_issues:
                if issue_outer.key == key:
                    is_find = True
            if not is_find:
                try:
                    find_issue = self.jira_outer.issue(key)
                    is_inner_issue_find = True
                except Exception:
                    is_inner_issue_find = False
                if is_inner_issue_find:
                    if find_issue.fields.status.id == '6':
                        try:
                            logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Closing issue " +
                                         issue_inner.key
                                         )

                            transitions = self.jira_inner.transitions(issue_inner)
                            close_transition = [t['id'] for t in transitions if 'Close' in t['name']]

                            if close_transition:
                                self.jira_inner.transition_issue(issue_inner, close_transition[0])
                        except Exception:
                            pass
                            logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                         'Failure closing issue ' + issue_inner.key
                                         )

        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End create_issues_from_outer_to_inner")
