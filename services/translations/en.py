# -*- coding: utf-8 -*-
"""English translations."""

EN_TRANSLATIONS = {
    # Dialogs
    "dialog.error": "Error",
    "dialog.warning": "Warning",
    "dialog.success": "Success",
    "dialog.confirm": "Confirm",
    "dialog.info": "Information",

    # Buttons
    "button.ok": "OK",
    "button.cancel": "Cancel",
    "button.save": "Save",
    "button.delete": "Delete",
    "button.confirm": "Confirm",
    "button.yes": "Yes",
    "button.no": "No",
    "button.close": "Close",
    "button.retry": "Retry",

    # Error Messages - Building
    "error.building.create_failed": "Failed to create building. Please check the entered data.",
    "error.building.update_failed": "Failed to update building. Please try again.",
    "error.building.delete_failed": "Failed to delete building.",
    "error.building.not_found": "Building not found.",
    "error.building.load_failed": "Failed to load buildings.",

    # Error Messages - Unit
    "error.unit.create_failed": "Failed to create unit. Please check the data.",
    "error.unit.update_failed": "Failed to update unit.",
    "error.unit.delete_failed": "Failed to delete unit.",
    "error.unit.not_found": "Unit not found.",
    "error.unit.duplicate": "A unit with the same number and floor already exists.",

    # Error Messages - Person
    "error.person.create_failed": "Failed to add person.",
    "error.person.update_failed": "Failed to update person data.",
    "error.person.delete_failed": "Failed to delete person.",
    "error.person.has_relations": "Cannot delete person with existing relations. Please delete relations first.",

    # Error Messages - Survey
    "error.survey.create_failed": "Failed to create survey.",
    "error.survey.finalize_failed": "Failed to finalize survey.",
    "error.survey.not_found": "Survey not found.",
    "error.survey.no_id": "Survey ID not found.\nPlease make sure a survey was created first.",

    # Error Messages - Claim
    "error.claim.create_failed": "Failed to create claim.",
    "error.claim.not_found": "Claim not found.",

    # Error Messages - Evidence
    "error.evidence.upload_failed": "Failed to upload document.",

    # Error Messages - API
    "error.api.connection": "Connection error. Please check your internet connection.",
    "error.api.timeout": "Connection timeout. Please try again.",
    "error.api.unauthorized": "Unauthorized. Please login again.",
    "error.api.forbidden": "Access forbidden.",
    "error.api.not_found": "Resource not found.",
    "error.api.validation": "Validation error:\n{details}",
    "error.api.server": "Server error. Please contact support.",
    "error.api.unknown": "An unexpected error occurred. Please try again.",

    # Error Messages - General
    "error.unexpected": "An unexpected error occurred.",
    "error.operation_failed": "Operation failed:\n{details}",

    # Validation Messages
    "validation.field_required": "Field '{field}' is required",
    "validation.invalid_format": "Field '{field}' has invalid format",
    "validation.min_length": "Field '{field}' must be at least {min} characters",
    "validation.max_length": "Field '{field}' must not exceed {max} characters",
    "validation.numbers_only": "Numbers only",
    "validation.check_data": "Please check the entered data",
    "validation.select_required": "Please select {field}",

    # Confirmation Messages
    "confirm.delete.title": "Confirm Delete",
    "confirm.delete.building": "Are you sure you want to delete this building?",
    "confirm.delete.unit": "Are you sure you want to delete this unit?",
    "confirm.delete.person": "Are you sure you want to delete this person?",
    "confirm.delete.person_with_relations": "This person has {count} relation(s).\nRelations will also be deleted.\n\nDo you want to continue?",
    "confirm.cancel.title": "Confirm Cancel",
    "confirm.cancel.wizard": "Are you sure you want to cancel the survey?\nAll entered data will be lost.",
    "confirm.discard.changes": "You have unsaved changes. Continue without saving?",

    # Success Messages
    "success.building.created": "Building created successfully",
    "success.building.updated": "Building updated successfully",
    "success.building.deleted": "Building deleted successfully",
    "success.unit.created": "Unit created successfully",
    "success.unit.updated": "Unit updated successfully",
    "success.person.created": "Person added successfully",
    "success.person.updated": "Person data updated successfully",
    "success.survey.completed": "Survey completed successfully",
    "success.survey.finalized": "Added successfully",
    "success.data_saved": "Data saved successfully",
    "success.draft_saved": "Draft saved successfully",

    # Info Messages
    "info.no_results": "No results found",
    "info.loading": "Loading...",
    "info.draft_id": "Draft ID",
    "info.restart_required": "Application restart required to apply changes",

    # Warning Messages
    "warning.select_unit_type": "Please select a unit type",
    "warning.enter_unit_number": "Please enter a unit number",
    "warning.area_numbers_only": "Area must be numbers only",
    "warning.uniqueness_check_error": "Error checking uniqueness",
    "warning.unit_number_taken": "A unit with the same number and floor exists",
    "warning.unit_number_available": "Unit number is available",
}
