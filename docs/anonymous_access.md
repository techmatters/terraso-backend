# Anonymous access configuration

Anonymous authentication is a way to allow unauthenticated read or write access.

## Public routes

Public routes are defined using the `PUBLIC_BASE_PATHS` list in the `settings.py` file. The paths defined in this list will be accessible without authentication.

## GraphQL

### Read access

To restrict read access to anonymous users, you have to define a query set that handles the access control. See `get_queryset` in `apps/graphql/schema/story_maps.py` for an example.

```python
@classmethod
def get_queryset(cls, queryset, info):
    user_pk = getattr(info.context.user, "pk", False)
    return queryset.filter(Q(is_published=True) | Q(created_by=user_pk))
```

### Write access

By default write access is restricted to authenticated users.
