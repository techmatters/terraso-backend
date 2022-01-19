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
