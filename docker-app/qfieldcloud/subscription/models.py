import logging
import math
import uuid
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext as _
from qfieldcloud.core.models import User, UserAccount


class Plan(models.Model):
    @classmethod
    def get_or_create_default(cls) -> "Plan":
        """Returns the default plan, creating one if none exists.
        To be used as a default value for UserAccount.type"""
        if cls.objects.count() == 0:
            with transaction.atomic():
                cls.objects.create(
                    code="default_user",
                    display_name="default user (autocreated)",
                    is_default=True,
                    is_public=False,
                    user_type=User.Type.PERSON,
                )
                cls.objects.create(
                    code="default_org",
                    display_name="default organization (autocreated)",
                    is_default=True,
                    is_public=False,
                    user_type=User.Type.ORGANIZATION,
                )
        return cls.objects.order_by("-is_default").first()

    # unique identifier of the subscription plan
    code = models.CharField(max_length=100, unique=True)

    # the plan would be applicable only to user of that `user_type`
    user_type = models.PositiveSmallIntegerField(
        choices=User.Type.choices, default=User.Type.PERSON
    )

    # relative ordering of the record
    ordering = models.PositiveIntegerField(
        default=0,
        help_text=_(
            'Relative ordering of the record. Lower values have higher priority (will be first in the list). Records with same ordering will be sorted by "Display name" and "Code". Please set with gaps for different records for easy reordering (e.g. 5, 10, 15, but not 5, 6, 7).'
        ),
    )

    # TODO: match requirements in QF-234 (fields like automatic old versions)
    # TODO: decide how to localize display_name. Possible approaches:
    # - django-vinaigrette (never tried, but like the name, and seems to to exactly what we want)
    # - django-modeltranslation (tried, works well, but maybe overkill as it creates new database columns for each locale)
    # - something else ? there's probably some json based stuff
    display_name = models.CharField(max_length=100)
    storage_mb = models.PositiveIntegerField(default=10)
    storage_keep_versions = models.PositiveIntegerField(default=10)
    job_minutes = models.PositiveIntegerField(default=10)
    can_add_storage = models.BooleanField(default=False)
    can_add_job_minutes = models.BooleanField(default=False)
    is_external_db_supported = models.BooleanField(default=False)
    can_configure_repackaging_cache_expire = models.BooleanField(default=False)
    min_repackaging_cache_expire = models.DurationField(
        default=timedelta(minutes=60),
        validators=[MinValueValidator(timedelta(minutes=1))],
    )
    synchronizations_per_months = models.PositiveIntegerField(default=30)

    # the plan is visible option for non-admin users
    is_public = models.BooleanField(default=False)

    # the plan is set by default for new users
    is_default = models.BooleanField(default=False)

    # the plan is marked as premium which assumes it has premium access
    is_premium = models.BooleanField(default=False)

    # the plan is set as trial
    is_trial = models.BooleanField(default=False)

    # The maximum number of organizations members that are allowed to be added per organization
    # This constraint is useful for public administrations with limited resources who want to cap
    # the maximum amount of money that they are going to pay.
    # Only makes sense when the user_type == User.Type.ORGANIZATION
    # If the organization subscription is changed from unlimited to limited organization members,
    # the existing members that are over the max_organization_members configuration remain active.
    max_organization_members = models.IntegerField(
        default=-1,
        help_text=_(
            "Maximum organization members allowed. Set -1 to allow unlimited organization members."
        ),
    )

    # The maximum number of premium collaborators that are allowed to be added per project.
    # If the project owner's plan is changed from unlimited to limited organization members,
    # the existing members that are over the `max_premium_collaborators_per_private_project` configuration remain active.
    max_premium_collaborators_per_private_project = models.IntegerField(
        default=-1,
        help_text=_(
            "Maximum premium collaborators per private project. Set -1 to allow unlimited project collaborators."
        ),
    )

    # The maximum number of trial organizations that the user can create.
    # Set -1 to allow unlimited trial organizations.
    max_trial_organizations = models.IntegerField(
        default=1,
        help_text=_(
            "Maximum number of trial organizations that the user can create. Set -1 to allow unlimited trial organizations."
        ),
    )

    def save(self, *args, **kwargs):
        if self.user_type not in (User.Type.PERSON, User.Type.ORGANIZATION):
            raise ValidationError(
                'Only "PERSON" and "ORGANIZATION" user types are allowed.'
            )

        with transaction.atomic():
            # If default is set to true, we unset default on all other plans
            if self.is_default:
                Plan.objects.filter(user_type=self.user_type).update(is_default=False)
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.display_name} ({self.code})"

    class Meta:
        ordering = (
            "ordering",
            "display_name",
            "code",
        )


class ExtraPackageType(models.Model):
    class Type(models.TextChoices):
        STORAGE = "storage", _("Storage")

    code = models.CharField(max_length=100, unique=True)
    # TODO: decide how to localize display_name. Possible approaches:
    # - django-vinaigrette (never tried, but like the name, and seems to to exactly what we want)
    # - django-modeltranslation (tried, works well, but maybe overkill as it creates new database columns for each locale)
    # - something else ? there's probably some json based stuff
    display_name = models.CharField(max_length=100)

    # the type of extra package
    type = models.CharField(choices=Type.choices, max_length=100, unique=True)

    # whether the package is available for the general public
    is_public = models.BooleanField(default=False)

    # the minimum quantity per subscription
    min_quantity = models.PositiveIntegerField()

    # the maximum quantity per subscription
    max_quantity = models.PositiveIntegerField()

    # the size of the package in `unit_label` units
    unit_amount = models.PositiveIntegerField()

    # Unit of measurement (e.g. gigabyte, minute, etc)
    unit_label = models.CharField(max_length=100, null=True, blank=True)


class ExtraPackageQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        qs = self.filter(
            Q(active_since__lte=now)
            & (Q(active_until__isnull=True) | Q(active_until__gte=now))
        )

        return qs


class ExtraPackage(models.Model):

    objects = ExtraPackageQuerySet.as_manager()

    subscription = models.ForeignKey(
        "subscription.Subscription",
        on_delete=models.CASCADE,
        related_name="packages",
    )
    type = models.ForeignKey(
        ExtraPackageType, on_delete=models.CASCADE, related_name="packages"
    )
    quantity = models.PositiveIntegerField(
        validators=[
            MinValueValidator(1),
        ],
    )
    active_since = models.DateTimeField()
    active_until = models.DateTimeField(null=True, blank=True)


# TODO add check constraint makes sure there are no two active extra packages at the same time,
# because we assume that once you change your quantity, the old ExtraPackage instance has an end_date
# and a new one with the new quantity is created right away.


class SubscriptionQuerySet(models.QuerySet):
    def active(self):
        now = timezone.now()
        qs = self.filter(
            Q(active_since__lte=now)
            & (Q(active_until__isnull=True) | Q(active_until__gte=now))
        )

        return qs


class Subscription(models.Model):

    objects = SubscriptionQuerySet.as_manager()

    class Status(models.TextChoices):
        """Status of the subscription.

        Initially the status is INACTIVE_DRAFT.

        INACTIVE_DRAFT -> (INACTIVE_DRAFT_EXPIRED, INACTIVE_REQUESTED_CREATE)
        INACTIVE_REQUESTED_CREATE -> (INACTIVE_AWAITS_PAYMENT, INACTIVE_CANCELLED)

        """

        # the user drafted a subscription, initial status
        INACTIVE_DRAFT = "inactive_draft", _("Inactive Draft")
        # the user draft expired (e.g. a new subscription is attempted)
        INACTIVE_DRAFT_EXPIRED = "inactive_draft_expired", _("Inactive Draft Expired")
        # requested creating the subscription on Stripe
        INACTIVE_REQUESTED_CREATE = "inactive Requested_create", _(
            "Inactive_Requested Create"
        )
        # requested creating the subscription on Stripe
        INACTIVE_AWAITS_PAYMENT = "inactive_awaits_payment", _(
            "Inactive Awaits Payment"
        )
        # payment succeeded
        ACTIVE_PAID = "active_paid", _("Active Paid")
        # payment failed, but the subscription is still active
        ACTIVE_PAST_DUE = "active_past_due", _("Active Past Due")
        # successfully cancelled
        INACTIVE_CANCELLED = "inactive_cancelled", _("Inactive Cancelled")

    uuid = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    plan = models.ForeignKey(
        Plan,
        on_delete=models.DO_NOTHING,
        related_name="+",
    )

    account = models.ForeignKey(
        UserAccount,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )

    storage_quantity = models.PositiveIntegerField(default=0)

    status = models.CharField(
        max_length=100, choices=Status.choices, default=Status.INACTIVE_DRAFT
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="+",
    )

    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)

    updated_at = models.DateTimeField(_("Updated at"), auto_now=True)

    requested_cancel_at = models.DateTimeField(
        _("Requested cancel at"), null=True, blank=True
    )

    # the time since the subscription is active. Note the value is null until the subscription is valid.
    active_since = models.DateTimeField(_("Active since"), null=True, blank=True)

    active_until = models.DateTimeField(_("Active until"), null=True, blank=True)

    @property
    def active_storage_package(self) -> ExtraPackage:
        from qfieldcloud.subscription.models import ExtraPackageType

        storage_package_qs = self.packages.active().filter(
            Q(type__type=ExtraPackageType.Type.STORAGE)
        )

        return storage_package_qs.first()

    @property
    def active_storage_package_quantity(self) -> int:
        return (
            self.active_storage_package.quantity if self.active_storage_package else 0
        )

    @property
    def active_storage_package_mb(self) -> int:
        return (
            self.active_storage_package.quantity * 1000
            if self.active_storage_package
            else 0
        )

    @property
    def min_storage_package_quantity(self) -> int:
        used = self.account.storage_quota_used_mb
        included = self.plan.storage_mb

        return math.ceil(max(used - included, 0) / 1000)

    def update_package_quantity(
        self,
        package_type: ExtraPackageType,
        quantity: int,
    ):
        assert (
            self.plan.is_premium
        ), "Only premium accounts can have additional packages!"

        with transaction.atomic():
            now = timezone.now()
            new_package = None

            try:
                old_package = (
                    ExtraPackage.objects.active()
                    .select_for_update()
                    .get(
                        subscription=self.subscription,
                        type=package_type,
                    )
                )
                old_package.active_until = now
                old_package.save(update_fields=["active_until"])
            except ExtraPackage.DoesNotExist:
                old_package = None

            if quantity > 0:
                new_package = ExtraPackage.objects.create(
                    subscription=self,
                    quantity=quantity,
                    type=package_type,
                    active_since=now,
                )

        return new_package

    @classmethod
    def get_or_create_active_subscription(cls, account: UserAccount) -> "Subscription":
        """Returns the currently active subscription, if not exists returns a newly created subscription with the default plan.

        Args:
            account (UserAccount): the account the subscription belongs to.

        Returns:
            Subscription: the currently active subscription
        """
        try:
            subscription = cls.objects.active().get(account_id=account.pk)
        except cls.DoesNotExist:
            subscription = cls.create_default_plan_subscription(account)

        return subscription

    @classmethod
    def update_subscription(
        cls,
        subscription: "Subscription",
        status: Status,
        active_since: datetime,
        active_until: datetime = None,
        **kwargs,
    ) -> "Subscription":
        with transaction.atomic():
            subscription = cls.objects.select_for_update().get(id=subscription.id)

            # all other active subscriptions must be cancelled
            update_count = (
                cls.objects.active()
                .filter(
                    account_id=subscription.account_id,
                )
                .exclude(
                    pk=subscription.pk,
                )
                .update(
                    status=cls.Status.INACTIVE_CANCELLED,
                    active_until=active_since,
                )
            )

            logging.info(f"Updated {update_count} previously active subscription(s)")

            subscription.status = status
            subscription.active_since = active_since
            subscription.active_until = active_until

            update_fields = ["status", "active_since", "active_until"]

            for attr_name, attr_value in kwargs.items():
                update_fields.append(attr_name)
                setattr(subscription, attr_name, attr_value)

            subscription.save(update_fields=update_fields)

        return subscription

    @classmethod
    def create_default_plan_subscription(
        cls, account: UserAccount, active_since: datetime = None
    ) -> "Subscription":
        """Activates the default (free) subscription for a given account.

        Args:
            account (UserAccount): the account the subscription belongs to.
            active_since (datetime): active since for the subscription

        Raises:
            Exception: If the account already has an account, raises an exception.

        Returns:
            Subscription: the currently active subscription.
        """
        active_subscription = cls.objects.active().filter(account=account)

        if active_subscription:
            raise Exception(
                f"There is already an active subscription {active_subscription.id} for this account."
            )

        if active_since is None:
            active_since = timezone.now()

        plan = Plan.objects.get(
            user_type=account.user.type,
            is_default=True,
        )

        subscription = cls.objects.create(
            plan=plan,
            account=account,
            created_by=account.user,
            status=cls.Status.ACTIVE_PAID,
            active_since=active_since,
        )

        return subscription
