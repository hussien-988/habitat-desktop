# -*- coding: utf-8 -*-
"""
Step validation service for Office Survey Wizard.

Validates context data for each step without UI coupling.
"""

from typing import Tuple, List


class StepValidator:
    """Validates wizard step data based on context."""

    # Step constants
    STEP_BUILDING = 0
    STEP_UNIT = 1
    STEP_HOUSEHOLD = 2
    STEP_PERSONS = 3
    STEP_RELATIONS = 4
    STEP_CLAIM = 5
    STEP_REVIEW = 6

    @staticmethod
    def validate_step(step_index: int, context) -> Tuple[bool, str]:
        """
        Validate step data from context.

        Args:
            step_index: Current step index
            context: SurveyContext object

        Returns:
            Tuple of (is_valid, error_message)
        """
        if step_index == StepValidator.STEP_BUILDING:
            if not context.building:
                return False, "يجب اختيار مبنى للمتابعة"
            return True, ""

        elif step_index == StepValidator.STEP_UNIT:
            if not context.unit and not context.is_new_unit:
                return False, "يجب اختيار أو إنشاء وحدة عقارية"
            return True, ""

        elif step_index == StepValidator.STEP_HOUSEHOLD:
            # Household step is optional, always valid
            return True, ""

        elif step_index == StepValidator.STEP_PERSONS:
            if len(context.persons) == 0:
                return False, "يجب تسجيل شخص واحد على الأقل"
            return True, ""

        elif step_index == StepValidator.STEP_RELATIONS:
            if len(context.relations) == 0:
                return False, "يجب إضافة علاقة واحدة على الأقل للمتابعة"
            return True, ""

        elif step_index == StepValidator.STEP_CLAIM:
            # Claim step auto-saves, always valid
            return True, ""

        elif step_index == StepValidator.STEP_REVIEW:
            # Final validation
            errors = []
            if not context.building:
                errors.append("لا يوجد مبنى مختار")
            if not context.unit:
                errors.append("لا يوجد وحدة مختارة")
            if len(context.persons) == 0:
                errors.append("لا يوجد أشخاص مسجلين")

            if errors:
                return False, " | ".join(errors)
            return True, ""

        # Unknown step
        return True, ""

    @staticmethod
    def get_step_name(step_index: int) -> str:
        """Get Arabic name for step."""
        names = [
            "اختيار المبنى",
            "الوحدة العقارية",
            "الأسرة والإشغال",
            "تسجيل الأشخاص",
            "العلاقات والأدلة",
            "إنشاء المطالبة",
            "المراجعة النهائية"
        ]
        if 0 <= step_index < len(names):
            return names[step_index]
        return ""
