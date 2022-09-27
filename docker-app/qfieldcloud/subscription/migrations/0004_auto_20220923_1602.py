# Generated by Django 3.2.15 on 2022-09-23 14:02

import uuid

import django.db.migrations.state
import django.db.models.deletion
import migrate_sql.operations
from django.conf import settings
from django.contrib.postgres.operations import BtreeGistExtension
from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone

now = timezone.now()


def populate_subscriptions_model(apps, schema_editor):
    UserAccount = apps.get_model("core", "UserAccount")
    Subscription = apps.get_model("subscription", "Subscription")

    for account in UserAccount.objects.all():
        Subscription.objects.create(
            account=account,
            plan_id=account.plan_id,
            status="active_paid",
            created_by_id=account.user_id,
            active_since=now,
            active_until=None,
        )


def populate_account_plan_field(apps, schema_editor):
    UserAccount = apps.get_model("core", "UserAccount")
    Subscription = apps.get_model("subscription", "Subscription")

    for subscription in Subscription.objects.filter(
        Q(active_until__gte=now) | Q(active_until__isnull=True)
    ):
        UserAccount.objects.filter(user_id=subscription.account_id).update(
            plan_id=subscription.plan_id
        )


def add_packages_to_subscriptions(apps, schema_editor):
    Subscription = apps.get_model("subscription", "Subscription")
    Package = apps.get_model("subscription", "Package")

    for package in Package.objects.all():
        subscription = (
            Subscription.objects.filter(
                account=package.account,
                active_since__lte=package.active_since,
            )
            .order_by("active_since")
            .first()
        )

        if subscription is None:
            subscription = Subscription.objects.create(
                account=package.account,
                plan_id=package.account.plan_id,
                status="active_paid",
                created_by_id=package.account.user_id,
                active_since=package.active_since,
                active_until=now,
            )

        package.subscription = subscription
        package.save()


def add_packages_to_accounts(apps, schema_editor):
    Package = apps.get_model("subscription", "Package")

    for package in Package.objects.all():
        package.account = package.subscription.account
        package.save()


class Migration(migrations.Migration):

    dependencies = [
        ("subscription", "0003_auto_20221028_1901"),
    ]

    operations = [
        BtreeGistExtension(),
        migrations.CreateModel(
            name="Subscription",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        db_index=True,
                    ),
                ),
                (
                    "account",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subscriptions",
                        to="core.useraccount",
                    ),
                ),
                (
                    "plan",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="subscription.plan",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("inactive_draft", "Inactive Draft"),
                            ("inactive_draft_expired", "Inactive Draft Expired"),
                            ("inactive Requested_create", "Inactive_Requested Create"),
                            ("inactive_awaits_payment", "Inactive Awaits Payment"),
                            ("active_paid", "Active Paid"),
                            ("active_past_due", "Active Past Due"),
                            ("inactive_cancelled", "Inactive Cancelled"),
                        ],
                        default="inactive_draft",
                        max_length=100,
                    ),
                ),
                (
                    "active_since",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Active since"
                    ),
                ),
                (
                    "active_until",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Active until"
                    ),
                ),
                (
                    "billing_cycle_anchor_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "current_period_since",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "current_period_until",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "requested_cancel_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Requested cancel at"
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created at"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Updated at"),
                ),
            ],
        ),
        migrations.RunPython(populate_subscriptions_model, populate_account_plan_field),
        migrate_sql.operations.CreateSQL(
            name="subscription_subscription_prevent_overlaps_idx",
            sql="\n            ALTER TABLE subscription_subscription\n            ADD CONSTRAINT subscription_subscription_prevent_overlaps\n            EXCLUDE USING gist (\n                account_id WITH =,\n                tstzrange(active_since, active_until) WITH &&\n            )\n            WHERE (active_since IS NOT NULL)\n        ",
            reverse_sql="\n            ALTER TABLE subscription_subscription DROP CONSTRAINT subscription_subscription_prevent_overlaps\n        ",
        ),
        #################
        # Packages
        #################
        migrations.AlterField(
            model_name="package",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RenameField(
            model_name="package",
            old_name="start_date",
            new_name="active_since",
        ),
        migrations.RenameField(
            model_name="package",
            old_name="end_date",
            new_name="active_until",
        ),
        migrations.AlterField(
            model_name="package",
            name="active_since",
            field=models.DateTimeField(),
        ),
        migrations.AlterField(
            model_name="package",
            name="active_until",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="package",
            name="subscription",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="packages",
                to="subscription.subscription",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="package",
            name="account",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="extra_packages",
                to="core.useraccount",
                null=True,
            ),
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # put your sql, python, whatever data migrations here
            ],
            state_operations=[
                # field/model changes goes here
            ],
        ),
        # NOTE avoids `django.db.utils.OperationalError: cannot CREATE INDEX "subscription_package" because it has pending trigger events`
        # I failed to solve the issue by using `SeparateDatabaseAndState`.
        migrations.RunSQL(
            "SET CONSTRAINTS ALL IMMEDIATE", reverse_sql=migrations.RunSQL.noop
        ),
        migrations.RunPython(add_packages_to_subscriptions, add_packages_to_accounts),
        migrations.RunSQL(
            migrations.RunSQL.noop, reverse_sql="SET CONSTRAINTS ALL DEFERRED"
        ),
        migrations.RemoveField(
            model_name="package",
            name="account",
        ),
        migrations.AlterField(
            model_name="package",
            name="subscription",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="packages",
                to="subscription.subscription",
                null=False,
            ),
        ),
        migrate_sql.operations.CreateSQL(
            name="subscription_package_prevent_overlaps_idx",
            sql="\n            ALTER TABLE subscription_package\n            ADD CONSTRAINT subscription_package_prevent_overlaps\n            EXCLUDE USING gist (\n                subscription_id WITH =,\n                tstzrange(active_since, active_until) WITH &&\n            )\n            WHERE (active_since IS NOT NULL)\n        ",
            reverse_sql="\n            ALTER TABLE subscription_package DROP CONSTRAINT subscription_package_prevent_overlaps\n        ",
        ),
        ####################
        # Add auditing fields to plans and packages
        ####################
        migrations.AddField(
            model_name="package",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="package",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="packagetype",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="packagetype",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="plan",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="plan",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        ####################
        # Add trial organizations support
        ####################
        migrations.AddField(
            model_name="plan",
            name="is_trial",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="plan",
            name="max_trial_organizations",
            field=models.IntegerField(
                default=1,
                help_text="Maximum number of trial organizations that the user can create. Set -1 to allow unlimited trial organizations.",
            ),
        ),
    ]
