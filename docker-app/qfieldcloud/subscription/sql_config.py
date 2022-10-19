from migrate_sql.config import SQLItem

sql_items = [
    # SQLItem(
    #     "subscription_subscription_insert_update_trigger_func",
    #     r"""
    #         CREATE OR REPLACE FUNCTION subscription_subscription_insert_update_trigger_func()
    #         RETURNS trigger
    #         AS
    #         $$
    #             BEGIN
    #                 NEW.is_active := (NEW.status ~ '^active_');
    #                 RETURN NEW;
    #             END;
    #         $$
    #         LANGUAGE PLPGSQL
    #     """,
    #     r"""
    #         DROP FUNCTION IF EXISTS subscription_subscription_insert_update_trigger_func()
    #     """,
    # ),
    # SQLItem(
    #     "subscription_subscription_insert_update_trigger",
    #     r"""
    #         CREATE TRIGGER subscription_subscription_insert_update_trigger BEFORE INSERT OR UPDATE ON subscription_subscription
    #         FOR EACH ROW
    #         EXECUTE FUNCTION subscription_subscription_insert_update_trigger_func()
    #     """,
    #     r"""
    #         DROP TRIGGER IF EXISTS subscription_subscription_insert_update_trigger ON subscription_subscription
    #     """,
    # ),
    # SQLItem(
    #     "subscription_subscription_is_active_uniq",
    #     r"""
    #         CREATE UNIQUE INDEX IF NOT EXISTS subscription_subscription_is_active_uniq ON subscription_subscription (account_id)
    #         WHERE is_active = TRUE
    #     """,
    #     r"""
    #         DROP INDEX IF EXISTS subscription_subscription_is_active_uniq
    #     """,
    # ),
    SQLItem(
        "subscription_subscription_prevent_overlaps_idx",
        r"""
            ALTER TABLE subscription_subscription
            ADD CONSTRAINT subscription_subscription_prevent_overlaps
            EXCLUDE USING gist (
                account_id WITH =,
                tstzrange(active_since, active_until) WITH &&
            )
            WHERE (active_since IS NOT NULL)
        """,
        r"""
            ALTER TABLE subscription_subscription DROP CONSTRAINT subscription_subscription_prevent_overlaps
        """,
    ),
]
