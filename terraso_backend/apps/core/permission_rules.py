import rules


@rules.predicate
def allowed_to_change_group(user, group_id):
    return user.is_group_manager(group_id)


@rules.predicate
def allowed_to_delete_membership(user, membership_id):
    from apps.core.models import Membership

    # Users are deleting their own membership
    if user.memberships.filter(pk=membership_id).exists():
        return True

    membership = Membership.objects.get(pk=membership_id)

    # Group Managers can delete any Membership in their Groups
    if user.is_group_manager(membership.group.id):
        return True

    return False


@rules.predicate
def allowed_group_managers_count(user, membership_id):
    from apps.core.models import Membership

    membership = Membership.objects.get(pk=membership_id)
    is_user_manager = user.is_group_manager(membership.group.id)
    managers_count = membership.group.memberships.managers_only().count()
    is_own_membership = user.memberships.filter(pk=membership_id).exists()

    # User is the last manager and a Group cannot have no managers
    if managers_count == 1 and is_user_manager and is_own_membership:
        return False

    return True


rules.add_rule("allowed_group_managers_count", allowed_group_managers_count)
