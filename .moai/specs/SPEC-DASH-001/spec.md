# SPEC-DASH-001: User Dashboard Experience

## Metadata

| Field | Value |
|-------|-------|
| SPEC ID | SPEC-DASH-001 |
| Title | User Dashboard Experience for Logged-In Users |
| Created | 2025-12-31 |
| Completed | 2025-12-31 |
| Status | Completed |
| Priority | High |
| Assigned | moai-workflow-tdd |
| Related SPECs | None |
| Lifecycle Level | spec-first |
| Last Updated | 2026-01-01 |

## TAG BLOCK

**Completed Features:**
- User dashboard with personalized greeting
- Statistics cards (Total Submissions, Files Processed, Max Files Per Upload, Account Status)
- Preferences guidance section
- Recent activity display
- Responsive design (mobile, tablet, desktop)
- Conditional rendering based on authentication status

**Related Files:**
- `frontend/templates/index.html` - Dashboard template
- `frontend/static/js/main.js` - Dashboard JavaScript functions
- `backend/routes/main.py` - Usage stats API endpoint

**API Endpoints:**
- GET `/api/usage-stats` - Get user statistics and recent activity

**Implementation Status:** COMPLETED

**Testing Status:** SEE docs/SPEC-DASH-001-TEST-RESULTS.md

## Environment

### Context
ResearchPDFFileRenamerGLM is a web-based application that helps researchers rename PDF files using AI-powered metadata extraction. Currently, all users (anonymous and authenticated) see the same landing page with "How It Works" and "Features" sections. This SPEC aims to create a personalized dashboard experience for logged-in users.

### Current State
- Main template (`frontend/templates/index.html`) shows marketing content to all users
- Authentication exists with JWT tokens and user sessions
- Profile page (`frontend/templates/profile.html`) has user settings and usage stats
- Admin dashboard (`frontend/templates/admin.html`) demonstrates statistics display patterns
- Usage tracking via `/api/usage-stats` endpoint already implemented

### Problem Statement
Authenticated users currently see the same "How It Works" and "Features" marketing content as anonymous users. Logged-in users who have already registered and been approved should see:
- Their personal usage statistics at a glance
- Quick access to their preferences (especially custom filename format)
- Guidance on using advanced features
- Relevant account information

This creates a disjointed user experience where registered users must navigate through marketing content they no longer need.

## Assumptions

### Technical Assumptions
- [HIGH] Flask 2.3.3 and Jinja2 templating engine support conditional rendering
- [HIGH] Existing authentication system (`current_user.is_authenticated`) works correctly
- [MEDIUM] `/api/usage-stats` endpoint returns comprehensive user statistics
- [MEDIUM] Admin dashboard card layouts can be adapted for user dashboard
- [LOW] No significant performance impact from conditional content rendering

### Business Assumptions
- [HIGH] Users who register want quick access to their statistics and settings
- [MEDIUM] Marketing content is primarily for anonymous users to understand the service
- [MEDIUM] Logged-in users benefit from seeing usage statistics on the main page
- [LOW] Reducing friction for logged-in users increases retention and engagement

### User Assumptions
- [HIGH] Approved registered users understand the basic "How It Works" flow
- [MEDIUM] Users want to track their usage (files processed, submissions made)
- [MEDIUM] Users need guidance on custom filename format feature
- [LOW] Users prefer a personalized dashboard over generic marketing content

## Requirements (EARS Format)

### Ubiquitous Requirements (Always Active)

**REQ-U-001**: The system shall always authenticate users via JWT token before displaying dashboard content.
WHY: Security and data protection require verified user identity.
IMPACT: Prevents unauthorized access to personal usage statistics.

**REQ-U-002**: The system shall always preserve existing anonymous user experience when user is not authenticated.
WHY: Marketing content is essential for new user acquisition.
IMPACT: Anonymous users continue to see "How It Works" and "Features" sections.

### Event-Driven Requirements (Trigger-Response)

**REQ-E-001**: WHEN a logged-in user visits the main page (`/`), the system shall display user dashboard instead of marketing content.
WHY: Personalized experience improves engagement for registered users.
IMPACT: Logged-in users see relevant content without navigation.

**REQ-E-002**: WHEN a logged-in user's authentication token expires, the system shall redirect to login or show anonymous content.
WHY: Expired sessions should not display sensitive user data.
IMPACT: Graceful handling of session expiration.

**REQ-E-003**: WHEN the user dashboard loads, the system shall fetch usage statistics from `/api/usage-stats` endpoint.
WHY: Real-time statistics provide accurate user activity information.
IMPACT: Users see current usage data on dashboard.

### State-Driven Requirements (Conditional Behavior)

**REQ-S-001**: IF the user is authenticated and approved, the system shall display user dashboard with statistics cards.
WHY: Approved users have active accounts with usage data.
IMPACT: Dashboard shows personalized content for approved users.

**REQ-S-002**: IF the user is authenticated but pending approval, the system shall display pending status message with limited functionality.
WHY: Pending users need to know their account status but cannot use all features.
IMPACT: Clear communication of approval workflow status.

**REQ-S-003**: IF the user is anonymous (not authenticated), the system shall display standard marketing content (How It Works, Features).
WHY: Anonymous users need information about the service before registering.
IMPACT: New users receive proper introduction to the service.

### Optional Requirements (Enhancement Features)

**REQ-O-001**: WHERE possible, the system shall provide quick-access buttons to Profile and Settings from the dashboard.
WHY: Reduces navigation friction for common user tasks.
IMPACT: Improved user experience for account management.

**REQ-O-002**: WHERE possible, the system shall display a "Preferences Guide" section explaining custom filename format.
WHY: Users may not be aware of the custom filename format feature in Profile settings.
IMPACT: Increased feature discovery and utilization.

**REQ-O-003**: WHERE possible, the system shall show recent activity feed on the dashboard.
WHY: Users benefit from seeing their recent file processing history.
IMPACT: Enhanced user engagement and transparency.

### Unwanted Behavior Requirements (Prohibited Actions)

**REQ-UW-001**: The system shall NOT display user statistics or dashboard content to anonymous users.
WHY: User data is private and authentication-gated.
IMPACT: Maintains data privacy and access control.

**REQ-UW-002**: The system shall NOT break existing anonymous user upload functionality.
WHY: Anonymous users are a key user segment for conversion.
IMPACT: No regression in core feature accessibility.

**REQ-UW-003**: The system shall NOT expose user email or personal information in dashboard without authentication.
WHY: Privacy protection and GDPR compliance.
IMPACT: Secure handling of personal user data.

## Specifications

### Dashboard Content Layout

The authenticated user dashboard shall replace the marketing content (lines 68-144 in `index.html`) with the following sections:

#### 1. Welcome Section
- Personalized greeting with user's name
- Account status badge (Approved/Pending)
- Quick action buttons (Profile, Upload, Settings)

#### 2. Statistics Cards (3-Column Grid)
Adapted from admin dashboard pattern (`admin.html` lines 82-137):

| Card Title | Data Source | Description |
|------------|-------------|-------------|
| Files Processed | `total_files_processed` | Total files successfully renamed |
| Total Submissions | `total_submissions` | Number of upload sessions |
| Max Files Per Session | `max_files_per_submission` | Current upload limit |
| Success Rate | Calculated from API | Percentage of successful files |

#### 3. Preferences Guidance Section
- Brief explanation of custom filename format feature
- Link/button to navigate to Profile > Preferences
- Example of custom format with preview

#### 4. Recent Activity (Optional)
- Last 5 submissions with timestamps
- Files processed per submission
- Success/failure indicators

### Conditional Rendering Logic

```jinja2
{# In index.html, replace lines 68-144 with: #}
{% if current_user.is_authenticated and current_user.is_approved %}
    {# User Dashboard Content #}
    {% include 'components/user_dashboard.html' %}
{% elif current_user.is_authenticated and not current_user.is_approved %}
    {# Pending User Message #}
    {% include 'components/pending_user_message.html' %}
{% else %}
    {# Anonymous Marketing Content (existing) #}
    {# Keep existing How It Works and Features sections #}
{% endif %}
```

### API Endpoints

#### GET /api/user/dashboard-stats
**Purpose**: Aggregated statistics for user dashboard

**Response Schema**:
```json
{
    "stats": {
        "total_files_processed": 150,
        "total_submissions": 12,
        "max_files_per_submission": 30,
        "success_rate": 98.5,
        "files_today": 5,
        "submissions_today": 1
    },
    "recent_activity": [
        {
            "timestamp": "2025-12-31T10:30:00Z",
            "files_processed": 5,
            "success_count": 5,
            "failed_count": 0
        }
    ],
    "limits": {
        "files_per_session": 30,
        "sessions_per_day": 10,
        "files_remaining_today": 25
    }
}
```

**Implementation Notes**:
- Can reuse existing `/api/usage-stats` endpoint
- May need to add calculated fields (success_rate, files_remaining_today)
- Authentication required via JWT token

### JavaScript Changes

**File**: `frontend/static/js/main.js`

**New Functions**:
- `loadUserDashboard()`: Fetch dashboard stats and update UI
- `renderDashboardCards(stats)`: Populate statistics cards
- `renderRecentActivity(activity)`: Display recent submissions
- `updateDashboardGreeting()`: Set personalized welcome message

**Modified Functions**:
- `checkAuthStatus()`: Call `loadUserDashboard()` when authenticated

### CSS/Styling

Reuse existing Tailwind CSS classes from admin dashboard:
- Card layout: `bg-white rounded-lg shadow p-6`
- Statistics: `text-3xl font-bold text-{color}-600`
- Grid: `grid grid-cols-1 md:grid-cols-3 gap-6`

## Traceability Tags

**Requirements to Implementation Mapping**:
- REQ-E-001, REQ-S-001, REQ-S-003 -> `frontend/templates/index.html` conditional rendering
- REQ-E-003 -> `frontend/static/js/main.js` `loadUserDashboard()` function
- REQ-O-001 -> Dashboard quick action buttons
- REQ-O-002 -> Preferences guidance section
- REQ-O-003 -> Recent activity feed
- REQ-UW-001, REQ-UW-002, REQ-UW-003 -> Authentication checks in all dashboard components

**Additional Features (Post-SPEC Implementation)**:
- PUT `/api/admin/users/:id/edit` -> Admin user editing functionality
- Enhanced session management with `SESSION_COOKIE_PATH` and `REMEMBER_COOKIE_PATH`
- Reverse proxy compatibility with relative API paths
- Fixed logout to properly clear cookies
- Users list pagination changed from 20 to 10 users per page
- Users list now shows all users including admins

**Acceptance Criteria Links**:
- AC-001 -> REQ-E-001, REQ-S-001, REQ-S-003
- AC-002 -> REQ-E-003, REQ-O-001
- AC-003 -> REQ-O-002
- AC-004 -> REQ-UW-001, REQ-UW-002

**Implementation Files**:
- `frontend/templates/index.html` - Dashboard template with conditional rendering
- `frontend/templates/base.html` - User menu in navigation
- `frontend/templates/admin.html` - Admin panel with user editing modal
- `frontend/static/js/main.js` - Dashboard JavaScript functions
- `backend/routes/admin.py` - Admin endpoints including user editing (lines 632-693)
- `backend/routes/auth.py` - Authentication with improved logout (lines 101-116)
- `backend/config.py` - Session and cookie configuration (lines 15-20)

## Dependencies

### External Dependencies
- None (uses existing infrastructure)

### Internal Dependencies
- Existing authentication system (`backend/routes/auth.py`)
- Existing usage tracking (`backend/models/usage.py`)
- Existing `/api/usage-stats` endpoint
- Admin dashboard card layout patterns

### Blocked By
- None

### Blocks
- Potential future enhancements (user onboarding flow, dashboard customization)

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Breaking anonymous user flow | High | Low | Thorough testing of conditional rendering; preserve existing templates |
| Performance degradation from API calls | Medium | Low | Reuse existing endpoint; implement caching if needed |
| User confusion about content changes | Medium | Medium | Clear communication; progressive rollout; feedback collection |
| Authentication token edge cases | High | Medium | Comprehensive error handling; graceful fallback to anonymous view |

## Success Metrics

### User Engagement
- Dashboard page load time <2 seconds for authenticated users
- 90%+ of authenticated users see dashboard instead of marketing content
- 20%+ increase in Profile/Settings page visits (via dashboard quick links)

### Quality Metrics
- Zero regression in anonymous user conversion rate
- 100% of authenticated users receive accurate, real-time statistics
- Zero errors in authentication state management

### Business Metrics
- Increased retention rate for registered users (measure 30-day return rate)
- Reduced support requests related to account status confusion

## Notes

### Design Considerations
- Dashboard should be mobile-responsive (reuse existing responsive grid classes)
- Maintain visual consistency with admin dashboard styling
- Consider adding empty state for new users with zero activity

### Future Enhancements
- User-configurable dashboard widgets
- Data visualizations (charts/graphs for usage over time)
- Achievement badges or milestones
- Integration with reference management software hints

### References
- Admin dashboard implementation: `frontend/templates/admin.html`
- Profile page with settings: `frontend/templates/profile.html`
- Usage stats API: `backend/routes/main.py` (usage-stats endpoint)
