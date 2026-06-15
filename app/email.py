"""Абстракция отправки email. Провайдер не выбран (ТЗ, открытый вопрос №4) —
подключается позже добавлением одной реализации EmailSender и фабрики get_sender.
"""


class EmailSender:
    """Интерфейс отправки. Реальный провайдер (Resend/Postmark/SMTP) — отдельный класс."""

    def send(self, to, subject, body):
        raise NotImplementedError


class ConsoleEmailSender(EmailSender):
    """Пишет письмо в лог — для разработки, пока провайдер не подключён."""

    def send(self, to, subject, body):
        print(f"[email] → {to} | {subject}\n{body}\n")


class NullEmailSender(EmailSender):
    """Ничего не отправляет (тихо проглатывает)."""

    def send(self, to, subject, body):
        pass


def get_sender(config):
    backend = (config.get("EMAIL_BACKEND") or "console").lower()
    if backend == "null":
        return NullEmailSender()
    return ConsoleEmailSender()
