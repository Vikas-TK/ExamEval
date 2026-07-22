from app.academic_master_service import (
    list_records as list_academic_records,
    get_record as get_academic_record,
    create_record as create_academic_record,
    update_record as update_academic_record,
    delete_record as delete_academic_record,
)
from app.blueprint_service import (
    create_blueprint,
    get_blueprint,
    list_blueprints,
    attach_faculty_answer_key,
)

__all__ = [
    "list_academic_records",
    "get_academic_record",
    "create_academic_record",
    "update_academic_record",
    "delete_academic_record",
    "create_blueprint",
    "get_blueprint",
    "list_blueprints",
    "attach_faculty_answer_key",
]
