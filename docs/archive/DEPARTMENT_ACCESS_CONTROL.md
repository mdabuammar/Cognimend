# Department Access Control in Cognimend

## Overview
Cognimend's Department Access Control provides strict, multi-tenant boundaries within a workspace. Instead of flattening a workspace into a single access level, users can be grouped into departments (e.g., HR, IT, Legal, Accounts). 

This allows organizations to isolate sensitive documents to specific departments without creating multiple standalone workspaces.

## Structure
- **Departments**: A workspace can contain multiple departments. Each has a unique slug.
- **Department Admin**: Can manage users and access policies strictly inside their assigned department. They cannot view or manage other departments.
- **Department Member**: Standard members of a department. They can query documents made available to their department.
- **Hierarchical Access**: A user can belong to multiple departments.

## Security Guarantees
1. **Zero Cross-Department Leakage**: Members of the HR department cannot query documents that are restricted to the Accounts department.
2. **Qdrant Vector Isolation**: The vector database query actively filters results by matching `document_id` allowed lists, so restricted chunks are never retrieved or sent to the LLM.
3. **No Name Leaks**: Users cannot see the titles, file names, or metadata of documents they do not have access to. 

## Management Flow
1. Workspace Owner navigates to `Workspace Admin -> Departments`.
2. Creates a department (e.g., "Legal").
3. Assigns users to "Legal" as `department_admin` or `department_member`.
4. When uploading a sensitive legal document, sets access to "Departments" -> "Legal".

## API Endpoints
- `GET /workspaces/{id}/admin/departments` - List departments
- `POST /workspaces/{id}/admin/departments` - Create department
- `PATCH /workspaces/{id}/admin/departments/{dept_id}` - Update department
- `POST /workspaces/{id}/admin/departments/{dept_id}/members` - Add member
- `DELETE /workspaces/{id}/admin/departments/{dept_id}/members/{user_id}` - Remove member
