
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import SchoolMembership

User = get_user_model()


class AddSchoolMemberSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    role = serializers.ChoiceField(
        choices=SchoolMembership.Role.choices
    )

    def validate_user_id(self, value):
        if not User.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                "No user exists with this ID."
            )
        return value

    def validate(self, attrs):
        request = self.context["request"]
        school = self.context["school"]

        # Only a Django superuser can assign the ADMIN role.
        if (
            attrs["role"] == SchoolMembership.Role.ADMIN
            and not request.user.is_superuser
        ):
            raise serializers.ValidationError({
                "role": "Only a platform superuser can assign "
                        "the school administrator role."
            })

        if SchoolMembership.objects.filter(
            school=school,
            user_id=attrs["user_id"],
        ).exists():
            raise serializers.ValidationError({
                "user_id": "This user is already a member of this school."
            })

        return attrs