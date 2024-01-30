from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.conf import settings

from ontime import messages as msg


class Queue(models.Model):
    TO_CASHIER = "cashier"
    TO_WAREHOUSEMAN = "whman"
    TO_CUSTOMER_SERVICE = "cservice"

    TYPES = (
        (TO_CASHIER, msg.TO_CASHIER),
        (TO_WAREHOUSEMAN, msg.TO_WAREHOUSEMAN),
        (TO_CUSTOMER_SERVICE, msg.TO_CUSTOMER_SERVICE),
    )

    monitor = models.ForeignKey(
        "fulfillment.Monitor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="queues",
        related_query_name="queue",
    )
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.CASCADE,
        related_name="queues",
        related_query_name="queue",
    )
    code = models.CharField(max_length=50)
    type = models.CharField(choices=TYPES, max_length=10)

    class Meta:
        db_table = "queue"
        unique_together = ["code", "warehouse"]

    def __str__(self):
        return "Queue %s [%s type=%s]" % (self.code, self.warehouse.codename, self.type)


class QueuedItem(models.Model):
    code = models.CharField(max_length=100, null=True, blank=True)
    queue = models.ForeignKey(
        "fulfillment.Queue",
        on_delete=models.SET_NULL,
        related_name="queued_items",
        related_query_name="queued_item",
        null=True,
        blank=True,
    )

    # Queue to which warehouseman must handover unpaid shipments
    dest_queue = models.ForeignKey(
        "fulfillment.Queue",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    # This is for easy unique together constraint
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse",
        on_delete=models.CASCADE,
        related_name="queued_items",
        related_query_name="queued_item",
        null=True,
        blank=True,
    )
    customer_service_ready = models.BooleanField(default=False)
    warehouseman_ready = models.BooleanField(default=False)
    cashier_ready = models.BooleanField(default=False)
    for_cashier = models.BooleanField(default=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="queued_items",
        related_query_name="queued_item",
    )
    recipient = models.ForeignKey(
        "customer.FrozenRecipient",
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "queued_item"
        unique_together = ["warehouse", "code"]

    def __str__(self):
        return "Queued item %s [queue=[%s] client=[%s] ready=%s]" % (
            self.code,
            self.queue,
            self.user_id and self.user.client_code or "???",
            self.ready,
        )

    @property
    def ready(self):
        if self.queue_id:
            if self.queue.type == Queue.TO_WAREHOUSEMAN:
                return self.warehouseman_ready
            elif self.queue.type == Queue.TO_CASHIER:
                return self.cashier_ready
            elif self.queue.type == Queue.TO_CUSTOMER_SERVICE:
                return self.customer_service_ready
        return False


class Monitor(models.Model):
    FOR_QUEUE = "for_queue"
    FOR_CUSTOMER = "for_customer"

    TYPES = ((FOR_QUEUE, msg.FOR_QUEUE), (FOR_CUSTOMER, msg.FOR_CUSTOMER))

    auth = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="as_monitor", on_delete=models.CASCADE
    )
    type = models.CharField(choices=TYPES, max_length=15)
    code = models.CharField(max_length=100)
    warehouse = models.ForeignKey(
        "fulfillment.Warehouse", on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        db_table = "monitor"
        unique_together = ["code", "warehouse"]

    def __str__(self):
        return "Monitor %s [warehouse=%s ]" % (
            self.code,
            self.warehouse and self.warehouse.codename,
        )


class CustomerServiceLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="customer_service_requests",
        related_query_name="customer_service_request",
        null=True,
        blank=True,
    )
    person_description = models.TextField(null=True, blank=True)
    problem_description = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customer_service_log"

    def __str__(self):
        return "%s [user=%s person=%s]" % (
            self.problem_description,
            self.user,
            self.person_description,
        )
