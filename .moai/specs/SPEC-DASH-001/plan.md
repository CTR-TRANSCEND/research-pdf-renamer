# SPEC-DASH-001: Implementation Plan

## Metadata

| Field | Value |
|-------|-------|
| SPEC ID | SPEC-DASH-001 |
| Plan Version | 1.0 |
| Last Updated | 2025-12-31 |
| Status | Ready for Implementation |

## Implementation Overview

This plan outlines the development of a personalized user dashboard experience for logged-in users. The implementation prioritizes minimal disruption to existing functionality while delivering a clear value proposition for authenticated users.

### Technical Approach

**Strategy**: Conditional Rendering with Shared Components

- Use Jinja2 conditional blocks to switch between dashboard and marketing content
- Reuse existing API endpoints (`/api/usage-stats`) with potential enhancements
- Adapt admin dashboard card layouts for visual consistency
- Maintain single-page architecture (no new routes required)

**Rationale**:
- Minimal code changes reduce risk of regression
- Leverages existing, tested infrastructure
- Preserves current URL structure (`/` for main page)
- No database schema changes required

## Milestones (Priority-Based)

### Primary Goal (Must Have)

**Goal 1: Dashboard Skeleton with Statistics Display**
- Create conditional rendering in `index.html`
- Implement basic 3-column statistics grid
- Connect to existing `/api/usage-stats` endpoint
- Display personalized greeting

**Success Criteria**:
- Authenticated users see dashboard instead of marketing content
- Anonymous users see existing marketing content (no regression)
- Statistics load accurately from API
- Page load time <2 seconds

**Dependencies**: None

---

**Goal 2: Preferences Guidance Section**
- Add "Preferences Guide" card to dashboard
- Include link to Profile > Preferences
- Show example of custom filename format

**Success Criteria**:
- Clear explanation of custom filename format feature
- Clickable link navigates to Profile settings
- Visual example helps users understand the feature

**Dependencies**: Goal 1 completion

---

**Goal 3: Quick Action Buttons**
- Add Profile, Upload, and Settings buttons to dashboard
- Implement proper navigation routing
- Style consistently with existing UI patterns

**Success Criteria**:
- All buttons navigate to correct pages
- Visual feedback on hover/click
- Mobile-responsive layout

**Dependencies**: Goal 1 completion

### Secondary Goal (Should Have)

**Goal 4: Pending User Status Message**
- Create conditional message for pending approval users
- Explain approval workflow
- Hide statistics until approval

**Success Criteria**:
- Pending users see clear status explanation
- No dashboard features exposed to unapproved users
- Graceful UI experience

**Dependencies**: Goal 1 completion

---

**Goal 5: Recent Activity Feed**
- Display last 5 submissions
- Show timestamps and file counts
- Add success/failure indicators

**Success Criteria**:
- Recent activity loads from API
- Timestamps display in user's local timezone
- Visual distinction between successful/failed submissions

**Dependencies**: Goal 1 completion, potential API enhancement

### Optional Goal (Nice to Have)

**Goal 6: Dashboard Stats API Enhancement**
- Create `/api/user/dashboard-stats` endpoint
- Calculate success rate
- Add "files remaining today" metric
- Optimize for dashboard-specific queries

**Success Criteria**:
- Endpoint returns all dashboard data in single call
- Reduces page load time
- Simplified frontend data fetching

**Dependencies**: Goal 4 completion

---

**Goal 7: Empty State Design**
- Create welcoming message for new users (zero activity)
- Provide onboarding guidance
- Encourage first file upload

**Success Criteria**:
- New users feel guided and welcomed
- Clear call-to-action for first upload
- No confusing empty data states

**Dependencies**: Goal 3 completion

## Technical Approach

### Backend Implementation

#### Phase 1: API Assessment (Goal 1)
**File**: `backend/routes/main.py`

**Tasks**:
1. Review existing `/api/usage-stats` endpoint
2. Verify response schema includes all dashboard data needs
3. Add `@login_required` decorator if not present
4. Test endpoint with authenticated user token

**Acceptance**:
- API returns user-specific data
- Response includes: `total_files_processed`, `total_submissions`, `max_files_per_submission`
- Authentication properly enforced

#### Phase 2: Dashboard Stats Endpoint (Optional - Goal 6)
**File**: `backend/routes/main.py` (new endpoint)

**Tasks**:
1. Create `/api/user/dashboard-stats` endpoint
2. Query usage data with aggregation
3. Calculate success rate: `(successful_files / total_files) * 100`
4. Calculate remaining daily limit
5. Return formatted JSON response

**Implementation Sketch**:
```python
@main_bp.route('/api/user/dashboard-stats', methods=['GET'])
@login_required
def get_dashboard_stats():
    user_id = current_user.id

    # Get usage statistics
    stats = get_user_usage_stats(user_id)

    # Calculate success rate
    success_rate = (stats['successful_files'] / stats['total_files'] * 100) if stats['total_files'] > 0 else 0

    # Get recent activity
    recent = get_recent_submissions(user_id, limit=5)

    return jsonify({
        'stats': {
            'total_files_processed': stats['total_files'],
            'total_submissions': stats['submissions'],
            'max_files_per_submission': stats['max_files'],
            'success_rate': round(success_rate, 1),
            'files_remaining_today': calculate_daily_limit_remaining(user_id)
        },
        'recent_activity': recent
    })
```

### Frontend Implementation

#### Phase 1: Template Structure (Goal 1)
**File**: `frontend/templates/index.html`

**Tasks**:
1. Locate marketing content section (lines 68-144)
2. Wrap existing marketing content in `{% else %}` block
3. Add `{% if current_user.is_authenticated and current_user.is_approved %}` condition
4. Create dashboard container div with grid layout

**Template Changes**:
```jinja2
{# Replace lines 68-144 with conditional rendering: #}
{% if current_user.is_authenticated and current_user.is_approved %}
    {# User Dashboard #}
    <div id="user-dashboard" class="max-w-7xl mx-auto py-8 px-4">
        {# Dashboard content will be injected here #}
    </div>
{% elif current_user.is_authenticated and not current_user.is_approved %}
    {# Pending User Message (Goal 4) #}
    <div id="pending-user-message">
        {# Status explanation #}
    </div>
{% else %}
    {# Existing Marketing Content #}
    {# Preserve lines 68-144 exactly as-is #}
{% endif %}
```

#### Phase 2: Dashboard Components (Goal 1, 2, 3)
**File**: `frontend/templates/index.html` (dashboard section)

**Component Structure**:
```jinja2
{# Welcome Section #}
<div class="mb-8">
    <h1 class="text-3xl font-bold text-gray-900">Welcome back, {{ current_user.name }}!</h1>
    <p class="text-gray-600 mt-2">Here's your activity overview</p>
</div>

{# Statistics Grid #}
<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
    {# Statistics cards... #}
</div>

{# Preferences Guide (Goal 2) #}
<div class="bg-white rounded-lg shadow-lg p-6 mb-6">
    {# Preferences guidance content #}
</div>

{# Quick Actions (Goal 3) #}
<div class="flex gap-4 mb-8">
    <button onclick="navigateToProfile()">Profile</button>
    <button onclick="navigateToUpload()">Upload Files</button>
    <button onclick="navigateToSettings()">Settings</button>
</div>

{# Recent Activity (Goal 5 - Optional) #}
<div class="bg-white rounded-lg shadow-lg p-6">
    <h3 class="text-lg font-semibold mb-4">Recent Activity</h3>
    <div id="recent-activity-list">
        {# Activity items injected via JS #}
    </div>
</div>
```

#### Phase 3: JavaScript Implementation (Goal 1, 5)
**File**: `frontend/static/js/main.js`

**New Functions**:
```javascript
// Load user dashboard statistics
async function loadUserDashboard() {
    try {
        const token = localStorage.getItem('auth_token');
        const response = await axios.get('/api/usage-stats', {
            headers: { 'Authorization': `Bearer ${token}` }
        });

        renderDashboardCards(response.data);
        renderRecentActivity(response.data.recent_submissions || []);

    } catch (error) {
        console.error('Error loading dashboard:', error);
        // Show error state or fallback
    }
}

// Render statistics cards
function renderDashboardCards(stats) {
    document.getElementById('stat-files-processed').textContent = stats.total_files_processed;
    document.getElementById('stat-submissions').textContent = stats.total_submissions;
    document.getElementById('stat-max-files').textContent = stats.max_files_per_submission;

    // Calculate success rate if not provided by API
    const successRate = calculateSuccessRate(stats);
    document.getElementById('stat-success-rate').textContent = `${successRate}%`;
}

// Render recent activity feed
function renderRecentActivity(submissions) {
    const container = document.getElementById('recent-activity-list');

    if (submissions.length === 0) {
        container.innerHTML = '<p class="text-gray-500">No recent activity</p>';
        return;
    }

    container.innerHTML = submissions.map(sub => `
        <div class="flex justify-between items-center p-3 bg-gray-50 rounded">
            <div>
                <p class="text-sm font-medium">${sub.files_processed} files processed</p>
                <p class="text-xs text-gray-500">${new Date(sub.timestamp).toLocaleString()}</p>
            </div>
            <span class="text-xs ${sub.success ? 'text-green-600' : 'text-red-600'}">
                ${sub.success ? 'Success' : 'Failed'}
            </span>
        </div>
    `).join('');
}
```

**Modified Function**:
```javascript
// Update existing checkAuthStatus function
function checkAuthStatus() {
    const token = localStorage.getItem('auth_token');
    if (token) {
        axios.get('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${token}` }
        }).then(response => {
            currentUser = response.data.user;
            updateAuthUI(currentUser);

            // NEW: Load dashboard if on main page
            if (window.location.pathname === '/' && currentUser.is_approved) {
                loadUserDashboard();
            }
        }).catch(error => {
            console.error('Auth check failed:', error);
            logout();
        });
    } else {
        updateAuthUI(null);
    }
}
```

#### Phase 4: CSS Styling
**File**: `frontend/templates/index.html` (existing `<style>` block or inline)

**Approach**: Reuse existing Tailwind CSS classes from admin dashboard

**Key Classes**:
- Card: `bg-white rounded-lg shadow p-6`
- Grid: `grid grid-cols-1 md:grid-cols-3 gap-6`
- Stat number: `text-3xl font-bold text-blue-600`
- Stat label: `text-sm text-gray-600`
- Button: `bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700`

## Task Breakdown

### Backend Tasks

| Task ID | Description | Complexity | Dependencies | Status |
|---------|-------------|------------|--------------|--------|
| BE-001 | Review `/api/usage-stats` endpoint | Low | None | Pending |
| BE-002 | Add `@login_required` decorator (if missing) | Low | BE-001 | Pending |
| BE-003 | (Optional) Create `/api/user/dashboard-stats` endpoint | Medium | BE-001 | Pending |
| BE-004 | Add success rate calculation logic | Low | BE-003 | Pending |
| BE-005 | Calculate daily limit remaining logic | Low | BE-003 | Pending |

### Frontend Tasks

| Task ID | Description | Complexity | Dependencies | Status |
|---------|-------------|------------|--------------|--------|
| FE-001 | Create conditional rendering structure in `index.html` | Medium | None | Pending |
| FE-002 | Build statistics grid HTML | Low | FE-001 | Pending |
| FE-003 | Create welcome section HTML | Low | FE-001 | Pending |
| FE-004 | Add preferences guidance section | Medium | FE-001 | Pending |
| FE-005 | Add quick action buttons | Low | FE-001 | Pending |
| FE-006 | Implement `loadUserDashboard()` JavaScript function | Medium | None | Pending |
| FE-007 | Implement `renderDashboardCards()` function | Low | FE-006 | Pending |
| FE-008 | Implement `renderRecentActivity()` function | Medium | FE-006 | Pending |
| FE-009 | Update `checkAuthStatus()` to call dashboard loader | Low | FE-006 | Pending |
| FE-010 | Create pending user status message | Medium | FE-001 | Pending |
| FE-011 | (Optional) Create empty state for new users | Medium | FE-001 | Pending |

### Testing Tasks

| Task ID | Description | Complexity | Dependencies | Status |
|---------|-------------|------------|--------------|--------|
| TEST-001 | Test anonymous user sees marketing content | Low | FE-001 | Pending |
| TEST-002 | Test authenticated user sees dashboard | Low | FE-001, FE-006 | Pending |
| TEST-003 | Test pending user sees status message | Low | FE-010 | Pending |
| TEST-004 | Test dashboard statistics accuracy | Medium | BE-001, FE-007 | Pending |
| TEST-005 | Test quick action buttons navigation | Low | FE-005 | Pending |
| TEST-006 | Test mobile responsiveness | Medium | FE-001, FE-002 | Pending |
| TEST-007 | Test session expiration handling | Medium | FE-001, FE-006 | Pending |
| TEST-008 | Performance test (page load <2 seconds) | Medium | All | Pending |

## Development Sequence

### Sequence 1: Foundation (Primary Goals 1-3)
```
BE-001 -> BE-002 -> FE-001 -> FE-002 -> FE-003 -> FE-006 -> FE-007 -> FE-009 -> FE-005 -> FE-004
                                                              |
                                                            TEST-001
                                                              |
                                                            TEST-002
```

### Sequence 2: Enhancement (Secondary Goals 4-5)
```
FE-010 -> TEST-003
FE-008 -> TEST-004
```

### Sequence 3: Optimization (Optional Goals 6-7)
```
BE-003 -> BE-004 -> BE-005 -> FE-011 -> TEST-008
```

## Risk Management

### Technical Risks

**Risk 1: Breaking Anonymous User Flow**
- Mitigation: Comprehensive manual testing before deployment
- Rollback Plan: Revert `index.html` changes, preserve backup of original file
- Testing Strategy: TEST-001 must pass before merge

**Risk 2: API Performance Degradation**
- Mitigation: Reuse existing endpoint; no new database queries initially
- Monitoring: Track API response time; add caching if >500ms
- Rollback Plan: Use static/mock data if API fails

**Risk 3: Authentication State Edge Cases**
- Mitigation: Implement robust error handling in `loadUserDashboard()`
- Testing Strategy: TEST-007 covers session expiration
- Rollback Plan: Fallback to anonymous view on auth error

### User Experience Risks

**Risk 4: User Confusion About Content Changes**
- Mitigation: Clear messaging; progressive rollout; feedback collection
- Monitoring: Track support requests related to dashboard
- Rollback Plan: Feature flag to disable dashboard temporarily

## Quality Gates

### Code Quality
- All JavaScript must pass ESLint (if configured)
- HTML must follow existing indentation patterns (4 spaces)
- Tailwind CSS classes must match existing patterns
- No console errors in browser dev tools

### Testing Quality
- All test cases (TEST-001 through TEST-008) must pass
- Manual testing on Chrome, Firefox, Safari
- Mobile testing on iOS and Android devices
- Performance benchmark: Page load <2 seconds on 3G connection

### Documentation
- Update `README.md` with dashboard screenshot (after implementation)
- Document new API endpoint (if created) in API documentation
- Add inline comments for complex JavaScript logic

## Deployment Strategy

### Staging Deployment
1. Deploy to staging environment first
2. Conduct full regression testing
3. Monitor error logs and performance metrics
4. Collect feedback from internal testers

### Production Deployment
1. Create git branch: `feature/user-dashboard`
2. Implement all Primary Goal tasks
3. Submit pull request with checklist
4. Code review by senior developer
5. Merge to main after approval
6. Deploy during low-traffic period

### Rollback Plan
- Quick revert: Git revert of merge commit
- Database rollback: Not applicable (no schema changes)
- Frontend rollback: Clear browser cache if needed

## Post-Implementation

### Monitoring (First 7 Days)
- Track dashboard page load times
- Monitor API error rates
- Collect user feedback via support channels
- Compare anonymous vs. authenticated user conversion rates

### Iteration Opportunities
- Add data visualizations (usage charts)
- Implement user-configurable dashboard widgets
- Add achievement badges or milestones
- Create onboarding flow for new registered users

## Notes

### Reusable Patterns
- Admin dashboard card layout: `frontend/templates/admin.html` lines 82-137
- Statistics display pattern: `frontend/templates/profile.html` lines 296-310
- Authentication check: `frontend/static/js/main.js` `checkAuthStatus()` function

### Performance Considerations
- Dashboard data should load asynchronously (non-blocking)
- Implement loading states for better perceived performance
- Consider browser localStorage caching for statistics (5-minute TTL)

### Accessibility
- Use semantic HTML (`<main>`, `<section>`, `<h1>`-`<h3>`)
- Ensure all interactive elements are keyboard accessible
- Add ARIA labels for dynamic content regions
- Maintain color contrast ratios (WCAG AA compliant)
