class ValidationError(ValueError):
    """Raised when persistent tracker data violates the repository contract."""


MODALITIES = {"writing", "speaking"}
TASK_TYPES = {
    "writing": {"email", "academic_discussion"},
    "speaking": {"listen_and_repeat", "take_an_interview"},
}
RECORD_TYPES = {"formal_original", "revision", "targeted_drill", "discussion_only"}
LEVELS = {"must_fix", "should_fix", "polish"}
SEVERITIES = {"minor", "clarity_reducing", "meaning_changing"}
STATUSES = {"new", "recurring", "persistent", "improving", "controlled", "relapsed"}
