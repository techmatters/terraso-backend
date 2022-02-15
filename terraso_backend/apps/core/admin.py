from django.contrib import admin

from .models import Group, Landscape, LandscapeGroup, Membership, User


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "website", "created_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        landscape_group_ids = [
            values[0]
            for values in LandscapeGroup.objects.filter(
                is_default_landscape_group=True
            ).values_list("group__id")
        ]
        return qs.exclude(id__in=landscape_group_ids)


@admin.register(Landscape)
class LandscapeAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "location", "website", "created_at")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "user_role", "created_at")


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "created_at", "is_staff")
