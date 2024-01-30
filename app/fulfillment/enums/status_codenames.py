class SCN:
    """SCN.
    Status codenames
    """

    class ORDER:
        CREATED = "created"
        PAID = "paid"
        UNPAID = "unpaid"
        PROCESSING = "processing"
        ORDERED = "ordered"
        DELETED = "deleted"

    class PACKAGE:
        AWAITING = "awaiting"
        PROBLEMATIC = "problematic"
        FOREIGN = "foreign"
        DELETED = "deleted"

    class SHIPMENT:
        PROCESSING = "processing"
        TOBESHIPPED = "tobeshipped"
        ONTHEWAY = "ontheway"
        CUSTOMS = "customs"
        RECEIVED = "received"
        DONE = "done"
        DELETED = "deleted"

    class COURIER:
        CREATED = "created"
        ONTHEWAY = "ontheway"
        FAILED = "failed"
        SUCCEED = "succeed"

    class TICKET:
        ACCEPTED = "accepted"
        INVESTIGATING = "investigating"
        CLOSED = "closed"
        DELETED = "deleted"
