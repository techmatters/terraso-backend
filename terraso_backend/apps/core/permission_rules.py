import rules


@rules.predicate
def is_group_manager(user, group_id):
    return user.is_group_manager(group_id)
