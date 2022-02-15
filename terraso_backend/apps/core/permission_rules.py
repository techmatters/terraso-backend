import rules


@rules.predicate
def allowed_to_change_group(user, group_id):
    return user.is_group_manager(group_id)


@rules.predicate
def allowed_to_delete_group(user, group_id):
    return user.is_group_manager(group_id)


@rules.predicate
def allowed_to_add_group_association(user, parent_group_id):
    return user.is_group_manager(parent_group_id)


@rules.predicate
def allowed_to_delete_group_association(user, group_association):
    return user.is_group_manager(group_association.parent_group.pk) or user.is_group_manager(
        group_association.child_group.pk
    )


@rules.predicate
def allowed_to_change_landscape(user, landscape_id):
    return user.is_landscape_manager(landscape_id)


@rules.predicate
def allowed_to_delete_landscape(user, landscape_id):
    return user.is_landscape_manager(landscape_id)


@rules.predicate
def allowed_to_add_landscape_group(user, landscape_id):
    return user.is_landscape_manager(landscape_id)


@rules.predicate
def allowed_to_delete_landscape_group(user, landscape_group):
    return user.is_landscape_manager(landscape_group.landscape.id) or user.is_group_manager(
        landscape_group.group.id
    )


@rules.predicate
def allowed_to_change_membership(user, membership_group_id):
    return user.is_group_manager(membership_group_id)


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


@rules.predicate
def allowed_to_update_preferences(user, user_preferences):
    return user_preferences.user.id == user.id


rules.add_rule("allowed_group_managers_count", allowed_group_managers_count)
rules.add_rule("allowed_to_update_preferences", allowed_to_update_preferences)
