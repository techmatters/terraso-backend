import uuid
from collections import defaultdict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from rules.contrib.models import RulesModelBase, RulesModelMixin
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteModel


def validate_name(value):
    if value.lower() in settings.DISALLOWED_NAMES_LIST:
        raise ValidationError(
            _("%(value)s is not allowed as a name"), params={"value": value}, code="invalid"
        )


def _unique_constraint_from_field_name(fieldname):
    return models.UniqueConstraint(
        fields=(fieldname,),
        condition=models.Q(deleted_at__isnull=True),
        name=f"%(app_label)s_%(class)s_unique_active_{fieldname}",
        violation_error_message=fieldname,
    )


class ModelMetaMeta(type):
    """Metaclass for inner Meta class to support generating unique constraints that agree
    with django-safedelete"""

    def __new__(metacls, clsname, bases, attrs):
        all_constraints = list(attrs.get("constraints", ()))

        all_unique_fields = set(
            attrs.get("_unique_fields", [])
            + [field for base in bases for field in getattr(base, "_unique_fields", [])]
        )
        for unique_field in all_unique_fields:
            constraint = _unique_constraint_from_field_name(unique_field)
            all_constraints.append(constraint)
        attrs["constraints"] = tuple(all_constraints)
        return super().__new__(metacls, clsname, bases, attrs)


class BaseModel(RulesModelMixin, SafeDeleteModel, metaclass=RulesModelBase):
    _safedelete_policy = SOFT_DELETE_CASCADE

    fields_to_trim = []

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta(metaclass=ModelMetaMeta):
        abstract = True
        get_latest_by = "-created_at"
        ordering = ["created_at"]

    def save(self, *args, **kwargs):
        for field in self.fields_to_trim:
            setattr(self, field, getattr(self, field).strip())
        return super().save(*args, **kwargs)

    def validate_constraints(self, *args, **kwargs):
        try:
            super().validate_constraints(*args, **kwargs)
        except ValidationError as e:
            errors = self._associate_errors_to_constraints(e.message_dict)
            raise ValidationError(errors)

    @staticmethod
    def _is_unique_field_constraint(constraint):
        # our "unique fields" will only generate a unique constraint with a length of 1
        return isinstance(constraint, models.UniqueConstraint) and len(constraint.fields) == 1

    def _associate_errors_to_constraints(self, message_dict):
        unique_constraints_by_field = {
            constraint.fields[0]: constraint
            for constraint in getattr(self._meta, "constraints", [])
            if self._is_unique_field_constraint(constraint)
        }

        errors = defaultdict(list)

        for error_message in message_dict.get("__all__", []):
            constraint = unique_constraints_by_field.get(error_message, None)
            if not constraint:
                errors["__all__"].append(error_message)
                continue
            field_name = error_message
            errors[field_name].append(
                ValidationError(
                    message=f"Unique constraint for {field_name} is violated", code="unique"
                )
            )
        return dict(errors)


class SlugModel(BaseModel):
    slug = models.SlugField(max_length=250, blank=True, editable=False)

    def save(self, *args, **kwargs):
        value_to_slugify = getattr(self, self.field_to_slug)
        self.slug = slugify(value_to_slugify)
        return super().save(*args, **kwargs)

    class Meta(BaseModel.Meta):
        abstract = True
        _unique_fields = ["slug"]
