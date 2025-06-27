from django.db import models
from django.db.models import Max

class AutoIncrementingPositiveIntegerField(models.PositiveIntegerField):
    """
    A PositiveIntegerField that auto-increments its value for each new object,
    scoped to a ForeignKey (e.g., chapter_number per book).
    Usage: set 'scope_field' to the name of the ForeignKey field to scope the increment.
    """
    def __init__(self, *args, scope_field=None, **kwargs):
        self.scope_field = scope_field
        # Allow null values initially so auto-increment can work
        kwargs['null'] = True
        kwargs['blank'] = True
        super().__init__(*args, **kwargs)

    def pre_save(self, model_instance, add):
        value = getattr(model_instance, self.attname)
        if add and (value is None or value == 0):
            # Scope by the given field (e.g., 'book')
            if self.scope_field:
                scope_value = getattr(model_instance, self.scope_field)
                qs = model_instance.__class__.objects.filter(**{self.scope_field: scope_value})
                max_val = qs.aggregate(max_val=Max(self.attname))["max_val"]
                value = (max_val or 0) + 1
            else:
                # No scope, just global increment
                max_val = model_instance.__class__.objects.aggregate(max_val=Max(self.attname))["max_val"]
                value = (max_val or 0) + 1
            setattr(model_instance, self.attname, value)
        return value 