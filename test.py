from datetime import datetime, timedelta
import requests
from database_manager import database_manager
from jira_manager import jira_manager

jira = jira_manager()

issue = jira.jira_inner.issue('PRVWB-7091')

if hasattr(issue.fields, 'attachment'):
    attachments = issue.fields.attachment
    for attach in attachments:
        image = attach.get()
        name = attach.filename