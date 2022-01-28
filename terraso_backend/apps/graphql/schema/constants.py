from enum import Enum


class MutationTypes(Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

    def __str__(self):
        return self.value
