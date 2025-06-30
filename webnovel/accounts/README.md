# Accounts App - Role-Based User Management

This app provides a comprehensive role-based user management system for the WebNovel platform.

## Features

### User Roles
- **Reader**: Basic access to read published books
- **Writer**: Can create and manage their own books
- **Translator**: Can work on translation assignments
- **Editor**: Can manage books, approve translations, and assign tasks
- **Administrator**: Full system access and user management

### Key Components

#### 1. Custom User Model (`User`)
- Extends Django's `AbstractUser`
- Role-based permissions
- Avatar support with automatic resizing
- Pen name for authors
- Verification system

#### 2. Book Collaboration System (`BookCollaborator`)
- Multiple users can work on the same book
- Granular permissions per collaboration
- Roles: Owner, Co-Author, Translator, Editor, Reviewer

#### 3. Translation Assignment System (`TranslationAssignment`)
- Assign translation tasks to specific users
- Workflow: Pending → Assigned → In Progress → Review → Approved/Rejected
- Due date tracking and overdue notifications

#### 4. Permission System
- Global permissions based on user role
- Book-specific permissions through collaborations
- Granular control over user actions

## Usage

### Creating Users with Roles

```python
from accounts.models import User

# Create a writer
writer = User.objects.create_user(
    username='author1',
    email='author@example.com',
    password='password123',
    role='writer',
    pen_name='John Doe'
)

# Create a translator
translator = User.objects.create_user(
    username='translator1',
    email='translator@example.com',
    password='password123',
    role='translator'
)
```

### Checking Permissions

```python
from accounts.permissions import check_permission, get_user_permissions

# Check specific permission
can_write = check_permission(user, 'can_write', book)

# Get all permissions for a user
permissions = get_user_permissions(user, book)
```

### Adding Book Collaborators

```python
from accounts.models import BookCollaborator

# Add a co-author to a book
collaborator = BookCollaborator.objects.create(
    book=book,
    user=co_author,
    role='co_author',
    permissions={'can_write': True, 'can_translate': True}
)
```

### Creating Translation Assignments

```python
from accounts.permissions import assign_translation_task

# Assign a translation task
assignment = assign_translation_task(
    user=translator,
    chapter=chapter,
    target_language=spanish,
    assigned_by=editor,
    due_date=datetime.now() + timedelta(days=7)
)
```

## Views and URLs

### Profile Management
- `accounts:profile` - User profile page
- `accounts:profile_edit` - Edit profile form

### User Management (Admin/Editor)
- `accounts:user_list` - List all users
- `accounts:user_detail` - View user details
- `accounts:assign_role_ajax` - Assign roles via AJAX

### Translation Management
- `accounts:translation_assignments` - List user's assignments
- `accounts:translation_assignment_detail` - View assignment details
- `accounts:start_translation_assignment` - Start working on assignment
- `accounts:submit_translation_assignment` - Submit for review
- `accounts:approve_translation_assignment` - Approve translation
- `accounts:reject_translation_assignment` - Reject translation

## Permission Mixins

Use these mixins in your views for automatic permission checking:

```python
from accounts.mixins import (
    BookPermissionMixin,
    TranslationPermissionMixin,
    EditorPermissionMixin,
    AdminPermissionMixin,
    WriterPermissionMixin
)

class MyView(BookPermissionMixin, ListView):
    required_permission = 'can_write'
    # ... rest of view
```

## Admin Interface

The app provides comprehensive admin interfaces for:
- User management with role assignment
- Book collaboration management
- Translation assignment tracking

## Templates

### Profile Template
- Displays user information, statistics, and permissions
- Shows recent books and translation assignments
- Quick action buttons based on user role

### Navigation Integration
- User dropdown shows role and quick access links
- Role-specific menu items (translations for translators, user management for editors)

## Testing

Run the tests to verify the role system:

```bash
python manage.py test accounts
```

## Migration Notes

When implementing this system in an existing project:

1. **Backup your database** before running migrations
2. **Create a superuser** with admin role after migration
3. **Update existing users** to appropriate roles
4. **Test thoroughly** before deploying to production

## Future Enhancements

- Email notifications for assignment updates
- Advanced permission inheritance
- Role-based dashboard customization
- Integration with external authentication systems
- Audit logging for permission changes 