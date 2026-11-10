from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuthToken, CustomUser


class AuthTokenInline(admin.TabularInline):
    model = AuthToken
    extra = 0
    readonly_fields = ("key_hash", "created_at", "last_used_at")
    can_delete = True


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff", "is_superuser")
    search_fields = ("email", "first_name", "last_name", "phone")
    inlines = [AuthTokenInline]
    
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "phone")}),
        ("Access", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "role", "password")}),
    )


@admin.register(AuthToken)
class AuthTokenAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "created_at", "last_used_at")
    list_filter = ("created_at", "last_used_at")
    search_fields = ("name", "user__email", "key_hash")
    readonly_fields = ("key_hash", "created_at", "last_used_at")
