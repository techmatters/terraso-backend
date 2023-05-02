import typing as t

from DateTime import DateTime as D
from graphene import DateTime, List, ObjectType, String

from apps.audit_logs import services


class Log(ObjectType):
    """
    Log is a GraphQL type that represents an audit log
    """
    client_timestamp = DateTime()
    user = String()
    action = String()
    resource = String()


class Query(ObjectType):
    """
    Query is a GraphQL type that represents the query interface for audit logs
    """
    logs = List(
        Log,
        user_id=String(required=False),
        action=String(required=False),
        resource_id=String(required=False),
        start_date=DateTime(required=False),
        end_date=DateTime(required=False)
    )

    def resolve_get_logs(
        self,
        info,
        user_id: t.Optional[str] = None,
        action: t.Optional[str] = None,
        resource_id: t.Optional[str] = None,
        resource_content_type: t.Optional[str] = None,
        start_date: D.DateTime = D.DateTime.MinValue,
        end_date: D.DateTime = D.DateTime.MaxValue
    ) -> t.List[Log]:

        args = []
        if user_id is not None:
            args.append(('user', user_id))
        if action is not None:
            args.append(('action', action))
        if resource_id is not None:
            args.append(('resource', resource_id))
        if resource_content_type is not None:
            args.append(('resource_type', resource_content_type))

        return services.get_logs(args, start_date)
