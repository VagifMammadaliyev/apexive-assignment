from django.contrib.admin.models import LogEntry, ADDITION, CHANGE, DELETION


class ActionLevel:

    DANGER = "danger"
    WARNING = "warning"
    INFO = "info"

    _flag_action_map = {DELETION: DANGER, ADDITION: INFO, CHANGE: INFO}

    def __getitem__(self, key):
        return self._flag_action_map[key]


ActionLevel = ActionLevel()
PERFORMING_METHOD_NAMES = ["perform_create", "perform_update", "perform_destroy"]
