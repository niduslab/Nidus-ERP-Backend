# backend/authentication/factories.py
#
# factory-boy factories for the authentication app.
#
# Usage in tests:
#     user = UserFactory()                          # Fresh verified user
#     user = UserFactory(is_email_verified=False)   # Unverified
#     users = UserFactory.create_batch(10)          # Bulk
#     user = UserFactory(email='custom@example.com')# Override any field
#
# Key concepts:
#   Sequence    → generates unique values per call (good for unique fields)
#   LazyAttribute → computed from other fields at creation time
#
# Why NOT hardcode emails like 'test@test.com': factory-boy's Sequence
# auto-generates user1@..., user2@..., so 100 UserFactory() calls produce
# 100 unique emails without collision errors on the email unique constraint.

import factory
from django.contrib.auth import get_user_model


User = get_user_model()


# The canonical password every UserFactory-produced user has.
# Hoisted to a module constant so test code can reference it without
# magic-string drift:  from authentication.factories import TEST_PASSWORD
TEST_PASSWORD = 'TestPassword123!'


class UserFactory(factory.django.DjangoModelFactory):
    """
    Produces a fully-verified User with a known hashed password.

    WHY WE OVERRIDE `_create` INSTEAD OF USING `PostGenerationMethodCall`:
        DjangoModelFactory's default `_create` calls Model.objects.create()
        which bypasses password hashing — the plaintext password goes
        straight into the `password` column and `check_password()` fails.

        PostGenerationMethodCall('set_password', ...) can hash the password
        but runs AFTER the instance is saved. Combined with
        `skip_postgeneration_save=True` the hashed password is never
        persisted; dropping that flag triggers a double-save and a
        deprecation warning.

        Delegating to the project's own `User.objects.create_user()` manager
        method is the clean fix: it hashes + saves in one step, and uses
        the exact same path that the real registration flow uses. Tests are
        now faithful to production behaviour.

    The password used is TEST_PASSWORD (module constant). Tests that log in
    should pass this same string.
    """

    class Meta:
        model = User

    # Sequence → each call produces user1@example.com, user2@example.com, ...
    # LazyAttribute reads the email to derive a matching full_name, so tests
    # with the user's name in the assertion don't need a magic-string match.
    email = factory.Sequence(lambda n: f'user{n}@example.com')
    full_name = factory.LazyAttribute(
        lambda obj: f'Test User {obj.email.split("@")[0]}'
    )
    phone = factory.Sequence(lambda n: f'+8801{n:09d}'[:14])

    is_email_verified = True
    is_active = True
    is_staff = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """
        Override the factory's default create to route through
        User.objects.create_user() — the project's own manager method
        that handles password hashing.

        STEP BY STEP:
          1. Pull the password out of kwargs. Fall back to TEST_PASSWORD so
             tests that don't override `password=` still get a known one.
          2. Split the required `email` and `full_name` fields out of kwargs
             — create_user() takes them as positional args.
          3. Everything else (is_active, is_email_verified, phone, etc.)
             is forwarded as **extra_fields.
          4. create_user() runs set_password() then save(), producing a
             persisted User with a properly hashed password.
        """
        password = kwargs.pop('password', TEST_PASSWORD)
        email = kwargs.pop('email')
        full_name = kwargs.pop('full_name')

        return model_class.objects.create_user(
            email=email,
            full_name=full_name,
            password=password,
            **kwargs,     # is_email_verified, is_active, phone, etc.
        )


class SuperuserFactory(UserFactory):
    """A superuser for admin-access tests. Uses User.objects.create_superuser."""
    is_staff = True
    is_superuser = True
    is_email_verified = True

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Route through create_superuser to set the right defaults."""
        password = kwargs.pop('password', TEST_PASSWORD)
        email = kwargs.pop('email')
        full_name = kwargs.pop('full_name')

        # create_superuser forces is_staff=True and is_superuser=True,
        # so we don't pass them explicitly — it would raise ValueError
        # if they were passed as False.
        kwargs.pop('is_staff', None)
        kwargs.pop('is_superuser', None)

        return model_class.objects.create_superuser(
            email=email,
            full_name=full_name,
            password=password,
            **kwargs,
        )