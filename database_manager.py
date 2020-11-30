import json
import sqlite3
from datetime import datetime
import os


class database_manager:

    def __init__(self):
        with open(os.path.dirname(os.path.abspath(__file__)) + '/../conf/app_settings.json', encoding='utf-8') as settings_file:
            self.settings = json.load(settings_file)

        self.database_name = os.path.dirname(__file__) + self.settings['DB name']
        self.table_name_users = self.settings['Table name for users']
        self.table_name_issues = self.settings['Table name for notication-issues']
        self.table_name_filters = self.settings['Table name for filters storage']

        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()

            # Создание таблицы, если нет
            sql_check_db = """CREATE TABLE IF NOT EXISTS %s
                            (ID INTEGER PRIMARY KEY AUTOINCREMENT, creation_date text, telegram_ID INTEGER,
                            username text, firstname text, lastname text)
                        """ % self.table_name_users
            cursor.execute(sql_check_db)

            # Создание таблицы, если нет
            sql_check_db = """CREATE TABLE IF NOT EXISTS %s
                            (ID INTEGER PRIMARY KEY AUTOINCREMENT, creation_date text,
                            group_name text, owner_name text, name text, condition text)
                        """ % self.table_name_filters
            cursor.execute(sql_check_db)

            # Создание таблицы, если нет
            sql_check_db = """CREATE TABLE IF NOT EXISTS %s
                            (ID INTEGER PRIMARY KEY AUTOINCREMENT, creation_date text, issue_key TEXT,
                            filter_ID INTEGER, CONSTRAINT fk_filters FOREIGN KEY (filter_ID) REFERENCES filters(ID)
                            ON DELETE CASCADE)
                        """ % self.table_name_issues
            cursor.execute(sql_check_db)

    def contain_this_user_in_db(self, id):
        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM %s WHERE telegram_ID = %d" % (self.table_name_users, id)
            cursor.execute(query)

            rows = cursor.fetchall()

            return len(rows) > 0

    def create_new_user(self, chat):
        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            cur_datetime = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            # Вставляем данные в таблицу
            query = """INSERT INTO %s (creation_date, telegram_ID, username, firstname, lastname)
                            VALUES('%s', %d, '%s', '%s', '%s')
                        """ % (
                self.table_name_users, cur_datetime, chat.id, chat.username, chat.first_name, chat.last_name)
            cursor.execute(query)
            # Сохраняем изменения
            conn.commit()

    def contain_issue_by_key(self, filter_name, owner_name, key):
        rows = []

        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            query = """
                        SELECT %s.* FROM %s
                        JOIN (SELECT * FROM %s
                        WHERE name = '%s' and owner_name = '%s') finded_%s
                        ON %s.filter_ID = finded_%s.ID
                        WHERE issue_key = '%s'
                    """ % (self.table_name_issues, self.table_name_issues,
                            self.table_name_filters, filter_name, owner_name, self.table_name_filters,
                            self.table_name_issues, self.table_name_filters, key)
            cursor.execute(query)

            rows = cursor.fetchall()

        return len(rows) > 0

    def add_issue(self, filter_name, owner_name, issue):
        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            cur_datetime = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            # Вставляем данные в таблицу
            query = """
                    INSERT INTO %s (creation_date, issue_key, filter_ID)
                    SELECT '%s', '%s', ID FROM %s WHERE name = '%s' and owner_name = '%s'
                    """ % (self.table_name_issues, cur_datetime, issue.key,
                            self.table_name_filters, filter_name, owner_name)
            cursor.execute(query)
            # Сохраняем изменения
            conn.commit()

    def check_non_actual_issues(self, filter_name, owner_name, issues):
        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            query_str = """SELECT * FROM %s WHERE
                            filter_ID IN (SELECT ID FROM %s WHERE name = '%s' and owner_name = '%s')
                        """ % (self.table_name_issues, self.table_name_filters, filter_name,
                        owner_name)

            query = cursor.execute(query_str)

            for issue_db in query:

                is_actual = False
                for issue_jira in issues:
                    if issue_db[2] == issue_jira.key:
                        is_actual = True

                if not is_actual:
                    self.delete_issue(filter_name, owner_name, issue_db[2], conn)

    def delete_issue(self, filter_name, owner_name, key, conn):
        cursor = conn.cursor()
        query = """DELETE FROM %s WHERE issue_key = '%s'
                    AND filter_ID IN (SELECT ID FROM %s WHERE name = '%s' and owner_name = '%s')
                    """ % (self.table_name_issues, key, self.table_name_filters,
                     filter_name, owner_name)
        cursor.execute(query)
        # Сохраняем изменения
        conn.commit()

    def add_filter(self, group_name, owner_name, filter_name, condition):
        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            cur_datetime = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
            # Вставляем данные в таблицу
            query = """
                    INSERT INTO %s (creation_date, group_name, owner_name, name, condition)
                    VALUES('%s', '%s', '%s', '%s', '%s')
                    """ % (self.table_name_filters, cur_datetime, group_name,
                            owner_name, filter_name, condition.replace("'", '"'))
            cursor.execute(query)
            # Сохраняем изменения
            conn.commit()

    def update_filter(self, group_name, owner_name, filter_name, condition):
        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            # Обновляем данные в таблице
            query = """
                    UPDATE %s SET condition = '%s'
                    WHERE group_name = '%s' AND owner_name = '%s' AND name = '%s'
                    """ % (self.table_name_filters, condition.replace("'", '"'), group_name,
                            owner_name, filter_name)
            cursor.execute(query)
            # Сохраняем изменения
            conn.commit()

    def delete_filter(self, filter_name):
        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            query = """DELETE FROM %s WHERE name = '%s'
                        """ % (self.table_name_filters, filter_name)
            cursor.execute(query)
            # Сохраняем изменения
            conn.commit()

    def get_users(self):
        users = []

        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM %s" % self.table_name_users
            for user in cursor.execute(query):
                users.append(user[2])

        return users

    def get_filters_by_group(self, group_name):
        filters = []

        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            query = "SELECT name, owner_name, condition FROM %s WHERE group_name = '%s'" % (self.table_name_filters, group_name)
            for filter in cursor.execute(query):
                filters.append({'name': filter[0], 'owner_name': filter[1], 'condition': filter[2]})

        return filters

    def contain_filter_by_name(self, filter_name):
        rows = []

        with sqlite3.connect(self.database_name) as conn:
            cursor = conn.cursor()
            query = "SELECT name, owner_name, condition FROM %s WHERE name = '%s'" % (self.table_name_filters, filter_name)
            cursor.execute(query)

            rows = cursor.fetchall()

        return len(rows) > 0