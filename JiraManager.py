from DatabaseManager import DatabaseManager
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


class JiraManager:

    def __init__(self):
        cur_date = datetime.now().strftime("%Y-%m-%d")

        self.log_filename = os.path.dirname(os.path.abspath(__file__)) + '/../logs/' + 'jira_' + cur_date + '.log'

        logging.basicConfig(filename=self.log_filename, level=logging.INFO)

        logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start init JiraManager")

        with open(os.path.dirname(os.path.abspath(__file__)) + '/../conf/app_settings.json', encoding='utf-8') as settings_file:
            self.settings = json.load(settings_file)

        self.db = DatabaseManager()

        self.jiraOuter = JIRA(
            self.settings['JIRA settings']['Domain VW Bank JIRA'],
            basic_auth=(
                self.settings['Credentials VW Bank JIRA']['Login'],
                self.settings['Credentials VW Bank JIRA']['Password']
            )
        )
        self.jiraInner = JIRA(
            self.settings['JIRA settings']['Domain FIS JIRA'],
            basic_auth=(
                self.settings['Credentials FIS JIRA']['Login'],
                self.settings['Credentials FIS JIRA']['Password']
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
        self.__current_inner_issues = self.jiraInner.search_issues(filter_inner, maxResults=1000)

    @property
    def current_outer_issues(self):
        return self.__current_outer_issues

    @current_outer_issues.setter
    def current_outer_issues(self, filter_outer):
        self.__current_outer_issues = self.jiraOuter.search_issues(filter_outer, maxResults=1000)

    def get_inner_issue_by_filter(self, filter_inner):
        return self.jiraInner.search_issues(filter_inner, maxResults=1000)

    def get_outer_issue_by_filter(self, filter_outer):
        return self.jiraOuter.search_issues(filter_outer, maxResults=1000)

    def get_bank_issues(self, filter_name, owner_name, condition):
        messages = []

        issues = []
        host = ''
        if owner_name == 'outer':
            issues = self.jiraOuter.search_issues(condition)
            host = self.settings['JIRA settings']['Domain VW Bank JIRA']

        elif owner_name == 'inner':
            issues = self.jiraInner.search_issues(condition)
            host = self.settings['JIRA settings']['Domain FIS JIRA']

        for issue in issues:
            if not self.db.contain_issue_by_key(filter_name, owner_name, issue.key):
                self.db.add_issue(filter_name, owner_name, issue)

                comment = ''

                comments = []
                if owner_name == 'inner':
                    comments = self.jiraInner.comments(issue)
                elif owner_name == 'outer':
                    comments = self.jiraOuter.comments(issue)

                if comments:
                    i = len(comments) - 1
                    comment += "\n\nПоследний комментарий:\n" + comments[i].author.displayName + ''\
                    ' ' + comments[i].created + '\n' + comments[i].body


                messages.append(issue.key + " " + issue.fields.priority.name.split(" - ")[1] + " '"
                + issue.fields.summary + "'" + comment + "\n" + host + "/browse/" + issue.key)

        return {
            'Messages': messages,
            'Issues': issues
        }

    def send_comment_to_inner_issue(self, key, message):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start send_comment_to_inner_issue " + key)

        issue = self.jiraInner.issue(key)

        if not issue:
            logging.info(
                datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Задача не найдена в системе")

            return 'Error'
        else:
            self.jiraInner.add_comment(issue, message)

            return 'Success'

    def create_issue(self, key, jira_outer_session):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start create_issue " + key)

        issue = self.jiraOuter.issue(key)

        issue_summary = issue.key + ' ' + issue.fields.summary
        issue_description = issue.fields.description

        # Создать задачу
        new_issue = self.jiraInner.create_issue(project='PRVWB', summary=issue_summary,
                                                description=issue_description,
                                                issuetype={'name': 'Bug'})
        # Переназначить задачу
        self.jiraInner.assign_issue(new_issue, None)

        if 'PMA' not in key:
            # Добавить лидов в вотчеры
            self.jiraInner.add_watcher(new_issue, 'erchimeng')
            self.jiraInner.add_watcher(new_issue, 'dzhana2')

        # Проставить приоритет
        new_issue.update(priority={"id": issue.fields.priority.id})

        custom_labels = ['VWBR_внешний']

        # Проставить ЭНВ если есть лейбл
        for label in issue.fields.labels:
            if label == '-C':
                new_issue.update(environment='C')
            if label == '-V':
                new_issue.update(environment='V')
            if label == '-T':
                new_issue.update(environment='T')
            if label == '-P':
                new_issue.update(environment='P')

            if 'Sprint' in label:
                custom_labels.append('VWBR_' + label)

        if hasattr(issue.fields, 'customfield_13425'):
            category = issue.fields.customfield_13425.value

            if 'CR' in category:
                custom_labels.append('VWBR_CR')
            elif 'Дефект' in category:
                custom_labels.append('VWBR_bug')

        if custom_labels:
            new_issue.update(fields={"labels": custom_labels})

        # Залить комменты
        vw_comments = self.jiraOuter.comments(issue)
        for vw_comment in vw_comments:
            self.jiraInner.add_comment(new_issue,
                                        vw_comment.author.displayName + ' ' + vw_comment.created +
                                        '\r\n' + vw_comment.body)

        if hasattr(issue.fields, 'attachment'):
            attachments = issue.fields.attachment
            for attach in attachments:
                url = attach.content

                r = jira_outer_session.get(url)
                name = attach.filename
                self.jiraInner.add_attachment(issue=new_issue, attachment=r.content, filename=name)

        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End create_issue")

        return "Success"

    # Обновление задач
    def update_issues_from_outer_to_inner(self):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start update_issues_from_outer_to_inner")

        jira_outer_session = self.check_jira_outer_session()

        for outer_issue in self.current_outer_issues:

            finded_inner_issue = self.get_inner_issue_by_filter('summary ~ ' + outer_issue.key)

            if not finded_inner_issue:
                self.create_issue(outer_issue.key, jira_outer_session)
                return "Success"
            else:

                logging.info(
                    datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start update issue with key " + outer_issue.key)

                outer_issue = self.jiraOuter.issue(outer_issue.key)

                inner_issue = self.jiraInner.issue(finded_inner_issue[0].key)

                #logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Создаем " + issue.key)
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
                vw_comments = self.jiraOuter.comments(outer_issue)
                inner_comments = self.jiraInner.comments(inner_issue)
                inner_comments_by_bot = [
                                            comment
                                            for comment in inner_comments
                                            if re.search(self.settings['Credentials FIS JIRA']['Login'], comment.author.displayName)
                                        ]
                inner_comments_max_index = len(inner_comments_by_bot) - 1
                for i in range(len(vw_comments)):

                    inner_form_comment = vw_comments[i].author.displayName + ' ' + vw_comments[i].created + '\r\n' + vw_comments[i].body

                    if i > inner_comments_max_index:
                        self.jiraInner.add_comment(inner_issue, inner_form_comment)
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
                            url = outer_attach.content
                            r = jira_outer_session.get(url)
                            name = outer_attach.filename
                            self.jiraInner.add_attachment(issue=inner_issue, attachment=r.content, filename=name)

                logging.info(
                    datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End update issue")


        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End update_issues_from_outer_to_inner")

        return "Success"

    def create_issues_from_outer_to_inner(self):
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
                issue_single_jql = 'project = PRVWB AND text ~ "' + key + '"'
                issues_list_single_inner = self.jiraInner.search_issues(issue_single_jql)
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
                    find_issue = self.jiraOuter.issue(key)
                    is_inner_issue_find = True
                except Exception:
                    is_inner_issue_find = False
                if is_inner_issue_find:
                    if find_issue.fields.status.id == '6':
                        try:
                            logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Closing issue " +
                                         issue_inner.key
                                         )
                            self.jiraInner.transition_issue(issue_inner, '131')
                        except Exception:
                            pass
                            logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                         'Failure closing issue ' + issue_inner.key
                                         )

        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "End create_issues_from_outer_to_inner")

    def check_jira_outer_session(self):
        host = self.settings['JIRA settings']['Domain VW Bank JIRA']

        test_management_href = host + self.settings['JIRA settings']['VW Bank JIRA paths']['Test Management']

        with open(os.path.dirname(os.path.abspath(__file__)) + '/../storage/outer_jira_session.pkl', 'rb') as f:
            jira_outer_session = pickle.load(f)

        check_session = jira_outer_session.get(test_management_href)

        if check_session.status_code != 200 or self.settings['JIRA settings']['Keywords for VW JIRA']["Test Management"] not in get_title(check_session.text):
            self.twofactor_authorize_in_outer_jira()

            with open(os.path.dirname(os.path.abspath(__file__)) + '/../storage/outer_jira_session.pkl', 'rb') as f:
                jira_outer_session = pickle.load(f)

            check_session = jira_outer_session.get(test_management_href)

            if check_session.status_code != 200 or self.settings['JIRA settings']['Keywords for VW JIRA']["Test Management"] not in get_title(check_session.text):
                raise Exception(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                "Response is not required. Status code: " + str(check_session.status_code) +
                                ", title:" + get_title(check_session.text)
                                )
            else:
                return jira_outer_session
        else:
            return jira_outer_session

    def twofactor_authorize_in_outer_jira(self):
        logging.basicConfig(filename=self.log_filename, level=logging.INFO)
        logging.info(
            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Start twofactor_authorize_in_outer_jira")

        login = self.settings['Credentials VW Bank JIRA']['Login']
        password = self.settings['Credentials VW Bank JIRA']['Password']
        secure_base_64_code = self.settings['Credentials VW Bank JIRA']['Secure Base64 code']

        host = self.settings['JIRA settings']['Domain VW Bank JIRA']
        login_href = host + self.settings['JIRA settings']['VW Bank JIRA paths']['Login']

        session = requests.Session()

        resp = session.get(login_href)

        if resp.status_code == 200 and self.settings['JIRA settings']['Keywords for VW JIRA']['Login'] in get_title(resp.text):
            logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + get_title(resp.text))

            form_data_login = {
                'os_username': login,
                'os_password': password,
                'os_destination': '',
                'user_role': '',
                'atl_token': '',
                'login': 'Log In'
            }

            resp = session.post(login_href, data=form_data_login)

            if resp.status_code == 200 and self.settings['JIRA settings']['Keywords for VW JIRA']['PIN validation'] in get_title(resp.text):
                logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + get_title(resp.text))

                pin_validation_href = host + self.settings['JIRA settings']['VW Bank JIRA paths']['PIN validation']

                totp = pyotp.TOTP(secure_base_64_code)
                logging.info(
                    datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + "Current pin is" + totp.now())

                form_data_pin = {
                    '2fpin': totp.now(),
                    'atl_token': '$atl_token'
                }

                resp = session.post(pin_validation_href, data=form_data_pin)

                if resp.status_code == 200 and self.settings['JIRA settings']['Keywords for VW JIRA']['Dashboard'] in get_title(resp.text):
                    logging.info(
                        datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + get_title(resp.text))

                    test_management_href = host + self.settings['JIRA settings']['VW Bank JIRA paths']['Test Management']

                    check_session = session.get(test_management_href)

                    if check_session.status_code == 200 and self.settings['JIRA settings']['Keywords for VW JIRA']["Test Management"] in get_title(check_session.text):
                        logging.info(
                            datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " + get_title(resp.text))

                        pickle.dump(session, open(os.path.dirname(os.path.abspath(__file__)) + '/../storage/outer_jira_session.pkl', 'wb'), protocol=pickle.HIGHEST_PROTOCOL)
                    else:
                        logging.warning(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                        "Response is not required. Status code: " + str(resp.status_code) +
                                        ", title:" + get_title(resp.text)
                                        )
                        logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                        "Execute reauthorize."
                                        )
                        self.twofactor_authorize_in_outer_jira()

                    logging.info(
                        datetime.now().strftime(
                            "%d.%m.%Y, %H.%M:%S") + "   :   " + "End twofactor_authorize_in_outer_jira")
                else:
                    logging.warning(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                    "Response is not required. Status code: " + str(resp.status_code) +
                                    ", title:" + get_title(resp.text)
                                    )
                    logging.info(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                    "Execute reauthorize."
                                    )
                    self.twofactor_authorize_in_outer_jira()
            else:
                get_title(resp.text)
                logging.warning(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                                "Response is not required. Status code: " + str(resp.status_code) +
                                ", title:" + get_title(resp.text)
                                )
        else:
            get_title(resp.text)
            logging.warning(datetime.now().strftime("%d.%m.%Y, %H.%M:%S") + "   :   " +
                            "Response is not required. Status code: " + str(resp.status_code) +
                            ", title:" + get_title(resp.text)
                            )
