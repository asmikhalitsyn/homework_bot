class APIResponseStatusCodeError(Exception):
    pass


class MissingRequiredTokenError(Exception):
    pass


class ServerResponseError(Exception):
    pass


class TelegramError(Exception):
    pass
