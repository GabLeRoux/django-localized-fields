import json

from typing import Union

from django.conf import settings
from django.db.utils import IntegrityError

from psqlextra.fields import HStoreField

from ..forms import LocalizedFieldForm
from ..value import LocalizedValue
from ..descriptor import LocalizedValueDescriptor


class LocalizedField(HStoreField):
    """A field that has the same value in multiple languages.

    Internally this is stored as a :see:HStoreField where there
    is a key for every language."""

    Meta = None

    # The class to wrap instance attributes in. Accessing to field attribute in
    # model instance will always return an instance of attr_class.
    attr_class = LocalizedValue

    # The descriptor to use for accessing the attribute off of the class.
    descriptor_class = LocalizedValueDescriptor

    def __init__(self, *args, **kwargs):
        """Initializes a new instance of :see:LocalizedField."""

        super(LocalizedField, self).__init__(*args, **kwargs)

    def contribute_to_class(self, model, name, **kwargs):
        """Adds this field to the specifed model.

        Arguments:
            cls:
                The model to add the field to.

            name:
                The name of the field to add.
        """
        super(LocalizedField, self).contribute_to_class(model, name, **kwargs)
        setattr(model, self.name, self.descriptor_class(self))

    @classmethod
    def from_db_value(cls, value, *_):
        """Turns the specified database value into its Python
        equivalent.

        Arguments:
            value:
                The value that is stored in the database and
                needs to be converted to its Python equivalent.

        Returns:
            A :see:LocalizedValue instance containing the
            data extracted from the database.
        """

        if not value:
            if getattr(settings, 'LOCALIZED_FIELDS_EXPERIMENTAL', False):
                return None
            else:
                return cls.attr_class()

        # we can get a list if an aggregation expression was used..
        # if we the expression was flattened when only one key was selected
        # then we don't wrap each value in a localized value, otherwise we do
        if isinstance(value, list):
            result = []
            for inner_val in value:
                if isinstance(inner_val, dict):
                    if inner_val is None:
                        result.append(None)
                    else:
                        result.append(cls.attr_class(inner_val))
                else:
                    result.append(inner_val)

            return result

        # this is for when you select an individual key, it will be string,
        # not a dictionary, we'll give it to you as a flat value, not as a
        # localized value instance
        if not isinstance(value, dict):
            return value

        return cls.attr_class(value)

    def to_python(self, value: Union[dict, str, None]) -> LocalizedValue:
        """Turns the specified database value into its Python
        equivalent.

        Arguments:
            value:
                The value that is stored in the database and
                needs to be converted to its Python equivalent.

        Returns:
            A :see:LocalizedValue instance containing the
            data extracted from the database.
        """

        # first let the base class  handle the deserialization, this is in case we
        # get specified a json string representing a dict
        try:
            deserialized_value = super(LocalizedField, self).to_python(value)
        except json.JSONDecodeError:
            deserialized_value = value

        if not deserialized_value:
            return self.attr_class()

        return self.attr_class(deserialized_value)

    def get_prep_value(self, value: LocalizedValue) -> dict:
        """Turns the specified value into something the database
        can store.

        If an illegal value (non-LocalizedValue instance) is
        specified, we'll treat it as an empty :see:LocalizedValue
        instance, on which the validation will fail.

        Arguments:
            value:
                The :see:LocalizedValue instance to serialize
                into a data type that the database can understand.

        Returns:
            A dictionary containing a key for every language,
            extracted from the specified value.
        """

        # default to None if this is an unknown type
        if not isinstance(value, LocalizedValue) and value:
            value = None

        if value:
            cleaned_value = self.clean(value)
            self.validate(cleaned_value)
        else:
            cleaned_value = value

        return super(LocalizedField, self).get_prep_value(
            cleaned_value.__dict__ if cleaned_value else None
        )

    def clean(self, value, *_):
        """Cleans the specified value into something we
        can store in the database.

        For example, when all the language fields are
        left empty, and the field is allows to be null,
        we will store None instead of empty keys.

        Arguments:
            value:
                The value to clean.

        Returns:
            The cleaned value, ready for database storage.
        """

        if not value or not isinstance(value, LocalizedValue):
            return None

        # are any of the language fiels None/empty?
        is_all_null = True
        for lang_code, _ in settings.LANGUAGES:
            # NOTE(seroy): use check for None, instead of
            # `bool(value.get(lang_code))==True` condition, cause in this way
            # we can not save '' value
            if value.get(lang_code) is not None:
                is_all_null = False
                break

        # all fields have been left empty and we support
        # null values, let's return null to represent that
        if is_all_null and self.null:
            return None

        return value

    def validate(self, value: LocalizedValue, *_):
        """Validates that the value for the primary language
        has been filled in.

        Exceptions are raises in order to notify the user
        of invalid values.

        Arguments:
            value:
                The value to validate.
        """

        if self.null:
            return

        primary_lang_val = getattr(value, settings.LANGUAGE_CODE)

        # NOTE(seroy): use check for None, instead of `not primary_lang_val`
        # condition, cause in this way we can not save '' value
        if primary_lang_val is None:
            raise IntegrityError(
                'null value in column "%s.%s" violates not-null constraint' % (
                    self.name,
                    settings.LANGUAGE_CODE
                )
            )

    def formfield(self, **kwargs):
        """Gets the form field associated with this field."""

        defaults = {
            'form_class': LocalizedFieldForm
        }

        defaults.update(kwargs)
        return super().formfield(**defaults)

    def deconstruct(self):
        """Gets the values to pass to :see:__init__ when
        re-creating this object."""

        name, path, args, kwargs = super(
            LocalizedField, self).deconstruct()

        if self.uniqueness:
            kwargs['uniqueness'] = self.uniqueness

        return name, path, args, kwargs
