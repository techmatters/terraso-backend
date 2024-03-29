# Copyright © 2023 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

# Generated by Django 4.2.7 on 2023-11-16 17:00

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.core.models.commons


def copy_memberships(apps, schema_editor):
    Group = apps.get_model("core", "Group")
    MembershipList = apps.get_model("collaboration", "MembershipList")
    Membership = apps.get_model("collaboration", "Membership")
    groups = Group.objects.all()
    for group in groups:
        if not group.membership_list:
            group.membership_list = MembershipList.objects.create(
                enroll_method=group.enroll_method,
                membership_type=group.membership_type,
            )
            group.save()
        current_memberships = group.memberships.filter(deleted_at__isnull=True).distinct("user")
        for membership in current_memberships:
            Membership.objects.create(
                membership_list=group.membership_list,
                user=membership.user,
                user_role=membership.user_role,
                membership_status=membership.membership_status,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("collaboration", "0005_change_collaborator_to_editor"),
        ("core", "0047_landscape_membership_list"),
    ]

    operations = [
        migrations.AddField(
            model_name="group",
            name="membership_list",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="group",
                to="collaboration.membershiplist",
            ),
        ),
        migrations.AlterField(
            model_name="group",
            name="enroll_method",
            field=models.CharField(
                blank=True,
                choices=[("join", "Join"), ("invite", "Invite"), ("both", "Both")],
                default="join",
                max_length=10,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="group",
            name="membership_type",
            field=models.CharField(
                blank=True,
                choices=[("open", "Open"), ("closed", "Closed")],
                max_length=32,
                null=True,
            ),
        ),
        migrations.RunPython(copy_memberships),
    ]
