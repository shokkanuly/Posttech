from enum import Enum


class UserRole(str, Enum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR_ADMIN = "hr_admin"


class RequestType(str, Enum):
    VACATION = "Vacation"
    ADVANCE_PAYMENT = "Advance payment"
    PROFILE_UPDATE = "Profile update"


class RequestStatus(str, Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class RequestEventType(str, Enum):
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMMENTED = "COMMENTED"


class EnrollmentStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class NotificationType(str, Enum):
    REQUEST = "REQUEST"
    ACADEMY = "ACADEMY"
    SYSTEM = "SYSTEM"
