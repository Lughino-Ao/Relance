"""Envoi d'email minimaliste via SMTP (compatible Gmail avec mot de passe
d'application — gratuit, sans domaine à vérifier).

Si SMTP_USER / SMTP_PASSWORD ne sont pas définis dans l'environnement,
l'email n'est pas envoyé : le contenu est simplement écrit dans les logs.
Ça permet de tester le flux de confirmation avant d'avoir configuré un
vrai compte d'envoi, sans jamais faire planter l'application.
"""
import os
import smtplib
import logging
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_FROM = os.environ.get("SMTP_FROM", SMTP_USER)


def is_configured():
    return bool(SMTP_USER and SMTP_PASSWORD)


def send_email(to_address, subject, body_text):
    """Retourne True si l'email a été envoyé, False s'il a seulement été loggé."""
    if not is_configured():
        logger.warning(
            "SMTP non configuré — email NON envoyé, contenu affiché ci-dessous.\n"
            "--- À: %s | Sujet: %s ---\n%s\n--- fin du message ---",
            to_address, subject, body_text,
        )
        return False

    msg = MIMEText(body_text, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_address

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(SMTP_FROM, [to_address], msg.as_string())
    return True
