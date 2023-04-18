# Unauthenticated access configuration

This doc show how to configure routes, GraphQL queries and mutations to be accessible without authentication.

## Public routes

Public routes are defined using the `PUBLIC_BASE_PATHS` list in the `settings.py` file. The paths defined in this list will be accessible without authentication.

## GraphQL

### Read access

To restrict read access to unauthenticated users, you have to define a query set that handles the access control. See `get_queryset` in `apps/graphql/schema/story_maps.py` for an example.

```python
@classmethod
def get_queryset(cls, queryset, info):
    user_pk = getattr(info.context.user, "pk", False)
    return queryset.filter(Q(is_published=True) | Q(created_by=user_pk))
```

### Write access

To allow write access to a specific route it has to be added to `PUBLIC_BASE_PATH` in `settings.py` and the needed validations should be added.

To allow write access for GraphQL mutations the mutation should inherit from `apps.graphql.schema.commons.BaseUnauthenticatedMutation`. See `UserUnsubscribeUpdate` in `apps.graphql.schema.users.py` for an example.
