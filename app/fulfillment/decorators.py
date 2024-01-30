from modeltranslation.utils import fallbacks


def no_lang_fallback(func):
    def wrapper(*args, **kwargs):
        with fallbacks(False):
            return func(*args, **kwargs)

    return wrapper
