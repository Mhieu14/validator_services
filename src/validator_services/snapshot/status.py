import enum

class SnapshotStatus(enum.Enum):
    CREATE_PENDING = 1
    CREATE_FAIL = 2
    CREATED = 3
    DELETE_PENDING = 4
    DELETE_FAIL = 5
    DELETED = 6
    # UPDATE_PENDING = 6
    # UPDATE_FAIL = 7

class SnapshotUpdateStatus(enum.Enum):
    UPDATE_PENDING = 1
    UPDATE_FAIL = 2
    UPDATED = 3
