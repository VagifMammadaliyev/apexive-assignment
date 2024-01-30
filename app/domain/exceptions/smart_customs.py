class SmartCustomsError(Exception):
    pass


class InvalidApiResponseError(SmartCustomsError):
    pass


class NoAirwayBillError(SmartCustomsError):
    pass


class NoRegNumberError(SmartCustomsError):
    pass
