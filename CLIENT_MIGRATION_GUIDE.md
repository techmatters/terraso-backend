# Export Token Client Migration Guide

## Overview

The export token system has been redesigned from a **resource-centric** model to a **user-centric** model. This enables multiple users to have their own tokens for the same resource.

## Summary of Changes

### What Changed (Backend)
- Export tokens are now **user-scoped** (each user gets their own token for a resource)
- Added `user_id` field to export tokens
- Users can only see and manage their own tokens
- Tokens are automatically cleaned up when users are removed from projects

### What Stayed the Same (Good News!)
- ✅ GraphQL mutation/query **signatures are unchanged**
- ✅ Token **URLs still work** exactly the same way
- ✅ **Permissions** work the same (same access rules)
- ✅ All existing GraphQL **field names** are the same

## Client Changes Required

### ⚠️ IMPORTANT: Behavioral Changes

Even though the GraphQL API signatures haven't changed, the **behavior** has changed in important ways:

#### 1. **One Token Per User, Not One Token Per Resource**

**Old Behavior:**
- When User A creates a token for Project X, everyone with access to Project X sees the same token
- If User B queries for the token, they get User A's token

**New Behavior:**
- When User A creates a token for Project X, only User A sees that token
- If User B queries for the token, they get `null` (no token exists for User B yet)
- User B must create their own token for Project X

**Client Impact:**
```graphql
# User A creates a token
mutation {
  createExportToken(resourceType: PROJECT, resourceId: "project-123") {
    token {
      token
      resourceType
      resourceId
      userId  # NEW FIELD - will be User A's ID
    }
  }
}

# User B queries for the same project's token
query {
  exportToken(resourceType: PROJECT, resourceId: "project-123") {
    token  # Returns NULL (not User A's token)
  }
}

# User B must create their own token
mutation {
  createExportToken(resourceType: PROJECT, resourceId: "project-123") {
    token {
      token  # Different token than User A's
    }
  }
}
```

#### 2. **Export Token Field Now Available in Response**

The `ExportToken` type now includes the `user_id` field:

**Old Schema:**
```graphql
type ExportToken {
  token: String!
  resourceType: ResourceTypeEnum!
  resourceId: ID!
}
```

**New Schema:**
```graphql
type ExportToken {
  token: String!
  resourceType: ResourceTypeEnum!
  resourceId: ID!
  userId: String!  # NEW FIELD
}
```

**Client Impact:**
- If you query for `userId`, it will be included
- If you don't query for it, nothing breaks (backwards compatible)
- The `userId` will always match the authenticated user making the request

#### 3. **Token Sharing Between Users No Longer Works**

**Old Behavior:**
```javascript
// User A creates token
const tokenA = await createExportToken("PROJECT", "project-123");

// User B could use User A's token URL
const url = `/export/token/project/${tokenA.token}/data.csv`;
// This would work because there was only one token per resource
```

**New Behavior:**
```javascript
// User A creates token
const tokenA = await createExportToken("PROJECT", "project-123");

// User B creates their own token (different token!)
const tokenB = await createExportToken("PROJECT", "project-123");

// tokenA.token !== tokenB.token
// Each user must use their own token URL
```

**Client Impact:**
- If your UI was showing "the project's export link" to all users, you need to change it to "your export link for this project"
- Don't try to share token strings between users
- Each user needs to create/fetch their own token

## Required Client Code Updates

### 1. **Update Token Query Logic**

**Before:**
```javascript
// Assumed if any user created a token, all users could see it
async function getProjectExportToken(projectId) {
  const result = await graphql(`
    query {
      exportToken(resourceType: PROJECT, resourceId: "${projectId}") {
        token
      }
    }
  `);
  return result.exportToken?.token;
}
```

**After:**
```javascript
// Now understand that null means "I don't have a token yet"
async function getProjectExportToken(projectId) {
  const result = await graphql(`
    query {
      exportToken(resourceType: PROJECT, resourceId: "${projectId}") {
        token
        userId  # Optional: can verify it's your token
      }
    }
  `);

  // null means the current user hasn't created a token yet
  return result.exportToken?.token;
}
```

### 2. **Update Token Creation Logic**

**Before:**
```javascript
// Might have checked "does any token exist before creating"
async function ensureExportToken(projectId) {
  const existing = await getProjectExportToken(projectId);
  if (existing) {
    return existing; // Reuse existing token
  }
  return await createExportToken("PROJECT", projectId);
}
```

**After:**
```javascript
// createExportToken is now idempotent - calling it multiple times returns the same token
async function ensureExportToken(projectId) {
  // Just call createExportToken - it will return existing or create new
  const result = await graphql(`
    mutation {
      createExportToken(resourceType: PROJECT, resourceId: "${projectId}") {
        token {
          token
          userId
        }
      }
    }
  `);
  return result.token.token;
}

// Even simpler - createExportToken is now safe to call repeatedly
async function getOrCreateToken(resourceType, resourceId) {
  const result = await createExportToken(resourceType, resourceId);
  return result.token.token;
}
```

### 3. **Update UI Text**

**Before:**
```jsx
<div>
  <h3>Export Link for {projectName}</h3>
  <p>Share this link with team members:</p>
  <input value={exportUrl} readOnly />
</div>
```

**After:**
```jsx
<div>
  <h3>Your Export Link for {projectName}</h3>
  <p>Your personal export link (each user has their own):</p>
  <input value={exportUrl} readOnly />
  <small>
    Note: This link is specific to your account.
    Other team members should generate their own export links.
  </small>
</div>
```

### 4. **Update Token Deletion Expectations**

**Before:**
```javascript
// Deleting a token affected all users
async function deleteProjectToken(token) {
  await deleteExportToken(token);
  // Now NO users can export this project
}
```

**After:**
```javascript
// Deleting a token only affects the current user
async function deleteProjectToken(token) {
  await deleteExportToken(token);
  // Only the current user's token is deleted
  // Other users can still export using their own tokens
}
```

## Testing Checklist

### Frontend Testing

- [ ] **Multi-user token creation**: Two different users create tokens for the same project
  - Verify they get different token strings
  - Verify each user can only see their own token in queries

- [ ] **Token query returns null**: User queries for a token they haven't created yet
  - Verify `exportToken` query returns `null`
  - Verify UI handles `null` gracefully (shows "create token" button)

- [ ] **Idempotent creation**: Call `createExportToken` twice for the same resource
  - Verify it returns the same token both times
  - Verify no duplicate tokens in database

- [ ] **Token deletion isolation**: User A deletes their token
  - Verify User A's token is deleted
  - Verify User B's token for same resource still exists

- [ ] **Export URLs work**: Each user's token generates working export URLs
  - User A's token URL works
  - User B's token URL works
  - Both return the same data (but different tokens)

- [ ] **Membership removal cleanup**: Remove user from project
  - Verify user's tokens for that project are deleted
  - Verify user's tokens for project sites are deleted
  - Verify other users' tokens are unaffected

### UI/UX Testing

- [ ] **UI text updated**: Check all export-related UI text
  - Changed "the export link" to "your export link"
  - Added explanations about user-specific tokens
  - Removed any "share this link with team" language

- [ ] **Token display**: When showing export token/URL
  - Shows current user's token (not another user's)
  - Handles null case (no token created yet)
  - Provides clear "create token" action

- [ ] **Permission errors**: User without permission tries to create token
  - Error message is clear
  - UI handles error gracefully

## Breaking Changes Summary

| Aspect | Old Behavior | New Behavior | Breaking? |
|--------|-------------|--------------|-----------|
| GraphQL Schema | `type ExportToken { token, resourceType, resourceId }` | `type ExportToken { token, resourceType, resourceId, userId }` | No - additive only |
| Mutation Signature | `createExportToken(resourceType, resourceId)` | `createExportToken(resourceType, resourceId)` | No - unchanged |
| Query Signature | `exportToken(resourceType, resourceId)` | `exportToken(resourceType, resourceId)` | No - unchanged |
| Token Scope | One token per resource (shared by all users) | One token per user-resource pair | **Yes - behavioral** |
| Query Returns | Returns token if ANY user created one | Returns token only if CURRENT user created one | **Yes - behavioral** |
| Token URLs | Same URL for all users | Different URL per user | **Yes - behavioral** |
| Idempotency | `createExportToken` might fail if token exists | `createExportToken` always succeeds (get or create) | No - improvement |
| Deletion Scope | Deleting token affects all users | Deleting token only affects current user | **Yes - behavioral** |

## Migration Strategy

### Recommended Approach

1. **Phase 1: Update backend** (✅ Already done)
   - Deploy new backend with redesigned token system
   - Old client code will continue to work (with new behavior)

2. **Phase 2: Update client queries** (Optional but recommended)
   - Add `userId` field to token queries
   - Add validation that `userId` matches current user

3. **Phase 3: Update client UI/UX**
   - Update text from "the project's token" to "your token for this project"
   - Add explanations about user-specific tokens
   - Remove token sharing features/UI

4. **Phase 4: Simplify client logic**
   - Remove "check if token exists" logic before creating
   - Use `createExportToken` directly (it's idempotent)

### Backwards Compatibility Notes

✅ **The API is backwards compatible** - old client code will work, but with different behavior:
- Queries that returned a shared token will now return `null` (if current user hasn't created one)
- Creating a token will work, but creates a user-specific token
- Token URLs will still work (same format)

⚠️ **The behavior is NOT backwards compatible**:
- Users must create their own tokens (can't rely on another user's token)
- Token sharing between users no longer works

## Example Client Code

### React Hook Example

```typescript
import { useMutation, useQuery } from '@apollo/client';

const GET_EXPORT_TOKEN = gql`
  query GetExportToken($resourceType: ResourceTypeEnum!, $resourceId: ID!) {
    exportToken(resourceType: $resourceType, resourceId: $resourceId) {
      token
      resourceType
      resourceId
      userId
    }
  }
`;

const CREATE_EXPORT_TOKEN = gql`
  mutation CreateExportToken($resourceType: ResourceTypeEnum!, $resourceId: ID!) {
    createExportToken(resourceType: $resourceType, resourceId: $resourceId) {
      token {
        token
        resourceType
        resourceId
        userId
      }
    }
  }
`;

function useProjectExportToken(projectId: string) {
  // Query for current user's token
  const { data, loading } = useQuery(GET_EXPORT_TOKEN, {
    variables: {
      resourceType: 'PROJECT',
      resourceId: projectId
    }
  });

  // Mutation to create token (idempotent)
  const [createToken, { loading: creating }] = useMutation(CREATE_EXPORT_TOKEN);

  const ensureToken = async () => {
    // Just call createExportToken - it will return existing or create new
    const result = await createToken({
      variables: {
        resourceType: 'PROJECT',
        resourceId: projectId
      }
    });
    return result.data.createExportToken.token.token;
  };

  return {
    token: data?.exportToken?.token,
    hasToken: !!data?.exportToken,
    loading: loading || creating,
    createToken: ensureToken
  };
}

// Usage in component
function ProjectExportButton({ projectId, projectName }) {
  const { token, hasToken, loading, createToken } = useProjectExportToken(projectId);

  const handleGetExportLink = async () => {
    const tokenStr = token || await createToken();
    const url = `/export/token/project/${tokenStr}/${projectName}.csv`;
    // Copy to clipboard or show in modal
    navigator.clipboard.writeText(url);
  };

  return (
    <button onClick={handleGetExportLink} disabled={loading}>
      {loading ? 'Loading...' : 'Get Your Export Link'}
    </button>
  );
}
```

## Questions?

If you have questions about migrating your client code, please:
1. Check this guide first
2. Review the EXPORT_TOKEN_REDESIGN_PLAN.md for technical details
3. Contact the backend team for clarification
