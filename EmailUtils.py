import smtplib
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os.path


def send_email(subject, message):
    with open(os.path.dirname(os.path.abspath(__file__)) + '/../conf/app_settings.json', encoding='utf-8') as settings_file:
        settings = json.load(settings_file)

    msg = MIMEMultipart()
    msg['Subject'] = subject
    body = MIMEText(message)
    msg.attach(body)

    s = smtplib.SMTP_SSL(settings["Mail settings"]["SMTP-server"], settings["Mail settings"]["SMTP-port"])

    s.login(settings["Mail settings"]["Login"], settings["Mail settings"]["Password"])

    s.sendmail(settings["Mail settings"]["Login"], settings["Mail settings"]["Login"], msg.as_string().encode('utf-8'))

    s.quit()