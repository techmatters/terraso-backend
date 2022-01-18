import rules


@rules.predicate
def allowed_to_change_group(user, group_id):
    return user.is_group_manager(group_id)
