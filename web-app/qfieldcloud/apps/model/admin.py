from django.contrib import admin
from .models import (
    User, Organization, OrganizationMember, Project, File, ProjectCollaborator)


admin.site.register(User)
admin.site.register(Organization)
admin.site.register(OrganizationMember)
admin.site.register(Project)
admin.site.register(File)
admin.site.register(ProjectCollaborator)