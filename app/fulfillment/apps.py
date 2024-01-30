from django.apps import AppConfig


class FulfillmentConfig(AppConfig):
    name = "fulfillment"

    def ready(self):
        import fulfillment.signals
