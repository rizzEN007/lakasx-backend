
from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import SchoolMembership

User = get_user_model()


class AddSchoolMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=SchoolMembership.Role.choices)

    def validate(self, attrs):
        request = self.context["request"]
        school = self.context["school"]

        if (
            attrs["role"] == SchoolMembership.Role.ADMIN
            and not request.user.is_superuser
        ):
            raise serializers.ValidationError({
                "role": "Only a platform superuser can assign "
                        "the school administrator role."
            })

        user = User.objects.filter(email__iexact=attrs["email"]).first()
        if user is None or SchoolMembership.objects.filter(
            school=school, user=user
        ).exists():
            raise serializers.ValidationError(
                {"email": "This user cannot be added to the school."}
            )

        attrs["user"] = user
        return attrs