import rules


@rules.predicate
def allowed_to_change_data_entry(user, data_entry):
    return data_entry.created_by == user


@rules.predicate
def allowed_to_delete_data_entry(user, data_entry):
    return data_entry.created_by == user
