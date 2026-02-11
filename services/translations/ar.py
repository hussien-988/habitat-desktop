# -*- coding: utf-8 -*-
"""Arabic translations."""

AR_TRANSLATIONS = {
    # Dialogs
    "dialog.error": "خطأ",
    "dialog.warning": "تحذير",
    "dialog.success": "نجاح",
    "dialog.confirm": "تأكيد",
    "dialog.info": "معلومة",

    # Buttons
    "button.ok": "موافق",
    "button.cancel": "إلغاء",
    "button.save": "حفظ",
    "button.delete": "حذف",
    "button.confirm": "تأكيد",
    "button.yes": "نعم",
    "button.no": "لا",
    "button.close": "إغلاق",
    "button.retry": "إعادة المحاولة",

    # Error Messages - Building
    "error.building.create_failed": "فشل في إنشاء المبنى. يرجى التحقق من البيانات المدخلة.",
    "error.building.update_failed": "فشل في تحديث المبنى. يرجى المحاولة مرة أخرى.",
    "error.building.delete_failed": "فشل في حذف المبنى.",
    "error.building.not_found": "المبنى غير موجود.",
    "error.building.load_failed": "فشل في تحميل المباني.",

    # Error Messages - Unit
    "error.unit.create_failed": "فشل في إنشاء الوحدة. يرجى التحقق من البيانات.",
    "error.unit.update_failed": "فشل في تحديث الوحدة.",
    "error.unit.delete_failed": "فشل في حذف الوحدة.",
    "error.unit.not_found": "الوحدة غير موجودة.",
    "error.unit.duplicate": "يوجد وحدة بنفس الرقم والطابق.",

    # Error Messages - Person
    "error.person.create_failed": "فشل في إضافة الشخص.",
    "error.person.update_failed": "فشل في تحديث بيانات الشخص.",
    "error.person.delete_failed": "فشل في حذف الشخص.",
    "error.person.has_relations": "لا يمكن حذف الشخص لأنه مرتبط بعلاقات. يرجى حذف العلاقات أولاً.",

    # Error Messages - Survey
    "error.survey.create_failed": "فشل في إنشاء المسح.",
    "error.survey.finalize_failed": "فشل في إنهاء المسح.",
    "error.survey.not_found": "المسح غير موجود.",
    "error.survey.no_id": "لم يتم العثور على معرف المسح.\nيرجى التأكد من إنشاء المسح أولاً.",

    # Error Messages - Claim
    "error.claim.create_failed": "فشل في إنشاء المطالبة.",
    "error.claim.not_found": "المطالبة غير موجودة.",

    # Error Messages - Evidence
    "error.evidence.upload_failed": "فشل في رفع الوثيقة.",

    # Error Messages - API
    "error.api.connection": "خطأ في الاتصال بالخادم. يرجى التحقق من الاتصال بالإنترنت.",
    "error.api.timeout": "انتهت مهلة الاتصال بالخادم. يرجى المحاولة مرة أخرى.",
    "error.api.unauthorized": "غير مصرح. يرجى تسجيل الدخول مرة أخرى.",
    "error.api.forbidden": "ليس لديك صلاحية للوصول.",
    "error.api.not_found": "المورد غير موجود.",
    "error.api.validation": "خطأ في التحقق من البيانات:\n{details}",
    "error.api.server": "خطأ في الخادم. يرجى الاتصال بالدعم الفني.",
    "error.api.unknown": "حدث خطأ غير متوقع. يرجى المحاولة مرة أخرى.",

    # Error Messages - General
    "error.unexpected": "حدث خطأ غير متوقع.",
    "error.operation_failed": "فشلت العملية:\n{details}",

    # Validation Messages
    "validation.field_required": "الحقل '{field}' مطلوب",
    "validation.invalid_format": "صيغة الحقل '{field}' غير صحيحة",
    "validation.min_length": "الحقل '{field}' يجب أن يحتوي على {min} أحرف على الأقل",
    "validation.max_length": "الحقل '{field}' يجب ألا يتجاوز {max} حرفًا",
    "validation.numbers_only": "يجب إدخال أرقام فقط",
    "validation.check_data": "يرجى التحقق من البيانات المدخلة",
    "validation.select_required": "يرجى اختيار {field}",

    # Confirmation Messages
    "confirm.delete.title": "تأكيد الحذف",
    "confirm.delete.building": "هل أنت متأكد من حذف هذا المبنى؟",
    "confirm.delete.unit": "هل أنت متأكد من حذف هذه الوحدة؟",
    "confirm.delete.person": "هل أنت متأكد من حذف هذا الشخص؟",
    "confirm.delete.person_with_relations": "هذا الشخص مرتبط بعلاقات ({count} علاقة).\nسيتم حذف العلاقات أيضاً.\n\nهل تريد المتابعة؟",
    "confirm.cancel.title": "تأكيد الإلغاء",
    "confirm.cancel.wizard": "هل أنت متأكد من إلغاء المسح؟\nسيتم فقد جميع البيانات المدخلة.",
    "confirm.discard.changes": "لديك تغييرات غير محفوظة. هل تريد الاستمرار دون الحفظ؟",

    # Success Messages
    "success.building.created": "تم إنشاء المبنى بنجاح",
    "success.building.updated": "تم تحديث المبنى بنجاح",
    "success.building.deleted": "تم حذف المبنى بنجاح",
    "success.unit.created": "تم إنشاء الوحدة بنجاح",
    "success.unit.updated": "تم تحديث الوحدة بنجاح",
    "success.person.created": "تم إضافة الشخص بنجاح",
    "success.person.updated": "تم تحديث بيانات الشخص بنجاح",
    "success.survey.completed": "تم إنهاء المسح بنجاح",
    "success.survey.finalized": "تمت الإضافة بنجاح",
    "success.data_saved": "تم حفظ البيانات بنجاح",
    "success.draft_saved": "تم حفظ المسودة بنجاح",

    # Info Messages
    "info.no_results": "لا توجد نتائج",
    "info.loading": "جاري التحميل...",
    "info.draft_id": "معرف المسودة",
    "info.restart_required": "يجب إعادة تشغيل التطبيق لتطبيق التغييرات",

    # Warning Messages
    "warning.select_unit_type": "يرجى اختيار نوع الوحدة",
    "warning.enter_unit_number": "يرجى إدخال رقم الوحدة",
    "warning.area_numbers_only": "المساحة يجب أن تكون أرقام فقط",
    "warning.uniqueness_check_error": "خطأ في التحقق من التفرد",
    "warning.unit_number_taken": "يوجد وحدة بنفس الرقم والطابق",
    "warning.unit_number_available": "رقم الوحدة متاح",
}
