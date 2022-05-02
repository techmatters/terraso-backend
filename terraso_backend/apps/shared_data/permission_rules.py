import rules


@rules.predicate
def allowed_to_change_data_entry(user, data_entry):
    return data_entry.created_by == user


@rules.predicate
def allowed_to_delete_data_entry(user, data_entry):
    return data_entry.created_by == user


@rules.predicate
def allowed_to_view_data_entry(user, data_entry):
    return user.memberships.filter(group__in=data_entry.groups.all()).exists()
