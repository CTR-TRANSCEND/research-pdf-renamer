# SPEC-DASH-001: Acceptance Criteria

## Metadata

| Field | Value |
|-------|-------|
| SPEC ID | SPEC-DASH-001 |
| Document Version | 1.0 |
| Last Updated | 2025-12-31 |
| Status | Ready for Testing |

## Overview

This document defines the acceptance criteria for the User Dashboard Experience feature. All scenarios use the Given-When-Then (Gherkin) format for clarity and testability.

## Success Definition

**Overall Success Criteria**:
- All Primary Goal scenarios must pass for feature acceptance
- Secondary Goal scenarios are optional but recommended for full functionality
- Zero regression in anonymous user experience
- Page load time under 2 seconds for authenticated users
- Zero security vulnerabilities (authentication bypasses, data exposure)

---

## Acceptance Criteria (Gherkin Format)

### AC-001: Conditional Content Display

**Scenario 1: Anonymous user sees marketing content**
```
GIVEN I am an anonymous user (not authenticated)
WHEN I visit the main page (/)
THEN I shall see the "How It Works" section
AND I shall see the "Features" section
AND I shall NOT see any user dashboard content
AND I shall NOT see any personal usage statistics
```

**Acceptance Tests**:
- Visual inspection of marketing content presence
- Inspect DOM to confirm dashboard elements absent
- Verify browser localStorage has no `auth_token`

**Scenario 2: Approved authenticated user sees dashboard**
```
GIVEN I am an authenticated and approved user
WHEN I visit the main page (/)
THEN I shall see a personalized welcome message with my name
AND I shall see statistics cards with my usage data
AND I shall NOT see the "How It Works" marketing section
AND I shall NOT see the "Features" marketing section
```

**Acceptance Tests**:
- Dashboard container present in DOM
- Welcome message contains user's name
- Marketing sections absent from DOM
- Statistics cards display actual user data

**Scenario 3: Pending user sees status message**
```
GIVEN I am an authenticated but pending approval user
WHEN I visit the main page (/)
THEN I shall see a "Pending Approval" status message
AND I shall see an explanation of the approval workflow
AND I shall NOT see my personal usage statistics
AND I shall NOT see the dashboard functionality
```

**Acceptance Tests**:
- Status message visible with clear "Pending" indication
- Statistics cards absent
- Dashboard functionality hidden/disabled

---

### AC-002: Statistics Display and Accuracy

**Scenario 4: Dashboard shows accurate usage statistics**
```
GIVEN I am an authenticated user with previous activity
WHEN the dashboard loads
THEN I shall see "Files Processed" count matching my total processed files
AND I shall see "Total Submissions" count matching my upload sessions
AND I shall see "Max Files Per Session" matching my account limit
AND I shall see "Success Rate" percentage calculated correctly
```

**Acceptance Tests**:
- Compare displayed values with `/api/usage-stats` response
- Verify calculations: `success_rate = (successful_files / total_files) * 100`
- Confirm data matches user's actual historical activity

**Scenario 5: New user sees empty state gracefully**
```
GIVEN I am an authenticated user with zero previous activity
WHEN the dashboard loads
THEN I shall see statistics with zero values
AND I shall see a welcoming message encouraging first upload
AND I shall NOT see any error messages or loading indicators
```

**Acceptance Tests**:
- Zero values display correctly (not "undefined" or "null")
- Welcome message present and actionable
- No console errors in browser dev tools

**Scenario 6: Statistics load in acceptable time**
```
GIVEN I am an authenticated user
WHEN I visit the main page (/)
THEN the dashboard shall load and display statistics within 2 seconds
AND I shall see a loading indicator while data is being fetched
AND I shall see error handling if API call fails
```

**Acceptance Tests**:
- Measure page load time from navigation to complete render
- Verify loading spinner present during API fetch
- Simulate API failure and confirm error state works

---

### AC-003: Preferences Guidance

**Scenario 7: Dashboard includes preferences guidance section**
```
GIVEN I am an authenticated user viewing the dashboard
WHEN I look at the preferences guidance card
THEN I shall see a title "Custom Filename Format"
AND I shall see a brief explanation of the feature
AND I shall see an example of a custom format
AND I shall see a clickable link/button to Profile > Preferences
```

**Acceptance Tests**:
- Preferences card visible in dashboard layout
- Example format displays clearly (e.g., `{firstauthor_lastname}_{year}_{journal}.pdf`)
- Link/button navigates to `/profile` and scrolls to Preferences section

**Scenario 8: Preferences link navigation works correctly**
```
GIVEN I am on the dashboard viewing preferences guidance
WHEN I click the "Configure Preferences" button
THEN I shall be navigated to the Profile page
AND the page shall scroll to the Preferences section
AND I shall see the custom filename format builder interface
```

**Acceptance Tests**:
- Click event triggers navigation to `/profile`
- URL fragment or scroll position targets Preferences section
- Custom format builder interface is visible and functional

---

### AC-004: Quick Action Buttons

**Scenario 9: Dashboard provides quick action buttons**
```
GIVEN I am an authenticated user viewing the dashboard
WHEN I look at the quick action section
THEN I shall see a "Profile" button
AND I shall see an "Upload Files" button
AND I shall see a "Settings" button
AND all buttons shall have appropriate icons and labels
```

**Acceptance Tests**:
- Three buttons present in dashboard
- Icons display correctly (user, upload, settings)
- Buttons are visually distinct and clickable

**Scenario 10: Profile button navigates correctly**
```
GIVEN I am on the dashboard
WHEN I click the "Profile" button
THEN I shall be navigated to the Profile page (/profile)
AND the page shall load with my user information
```

**Acceptance Tests**:
- Navigation to `/profile` successful
- Profile page displays user's name, email, and settings

**Scenario 11: Upload Files button scrolls to upload zone**
```
GIVEN I am on the dashboard
WHEN I click the "Upload Files" button
THEN the page shall scroll to the upload drop zone
AND the upload zone shall be highlighted briefly
```

**Acceptance Tests**:
- Smooth scroll to upload section
- Visual highlight animation on drop zone
- Upload zone is ready for file drag-and-drop

**Scenario 12: Settings button navigates correctly**
```
GIVEN I am on the dashboard
WHEN I click the "Settings" button
THEN I shall be navigated to the Profile page (/profile)
AND the page shall scroll to the Preferences section
```

**Acceptance Tests**:
- Navigation to `/profile` successful
- Scroll position targets Preferences form

---

### AC-005: Recent Activity Feed (Secondary Goal)

**Scenario 13: Dashboard displays recent activity**
```
GIVEN I am an authenticated user with previous submissions
WHEN the dashboard loads
THEN I shall see a "Recent Activity" section
AND I shall see up to 5 most recent submissions
AND each activity shall show timestamp and file count
```

**Acceptance Tests**:
- Recent activity section present
- Displays 1-5 entries depending on user history
- Each entry shows timestamp in user's local timezone
- Each entry shows number of files processed

**Scenario 14: Recent activity shows success indicators**
```
GIVEN I am viewing my recent activity
WHEN I look at each activity entry
THEN I shall see a green success indicator for successful submissions
AND I shall see a red failure indicator for failed submissions
```

**Acceptance Tests**:
- Visual distinction between success/failure states
- Color-coded badges or icons
- Clear text labels ("Success" or "Failed")

**Scenario 15: Recent activity handles empty state**
```
GIVEN I am a new user with zero activity
WHEN the dashboard loads
THEN I shall see "No recent activity" message
AND I shall NOT see any error indicators
```

**Acceptance Tests**:
- Empty state message displays gracefully
- No broken UI or missing elements
- Message encourages first upload

---

### AC-006: Authentication State Management

**Scenario 16: Session expiration redirects appropriately**
```
GIVEN I am viewing my dashboard
WHEN my authentication token expires
THEN the dashboard shall show an error state
AND I shall be prompted to log in again
OR I shall be redirected to the anonymous view
```

**Acceptance Tests**:
- Simulate token expiration (clear localStorage or modify token)
- Dashboard gracefully handles error
- User can recover by logging in again

**Scenario 17: Login shows dashboard after authentication**
```
GIVEN I am an anonymous user
WHEN I log in successfully
THEN I shall be redirected to the main page (/)
AND I shall see my user dashboard (not marketing content)
```

**Acceptance Tests**:
- Successful login triggers navigation
- Dashboard loads automatically after login
- User remains authenticated across page refresh

---

### AC-007: Mobile Responsiveness

**Scenario 18: Dashboard displays correctly on mobile devices**
```
GIVEN I am viewing the dashboard on a mobile device (width < 768px)
WHEN the page renders
THEN the statistics grid shall stack vertically (single column)
AND buttons shall be appropriately sized for touch interaction
AND text shall remain readable without horizontal scrolling
```

**Acceptance Tests**:
- Test on iPhone (375px width)
- Test on Android (360px width)
- Test on tablet (768px width)
- Confirm no horizontal scrolling required
- Touch targets minimum 44x44 pixels

---

### AC-008: Performance and Loading States

**Scenario 19: Dashboard shows loading state during data fetch**
```
GIVEN I am an authenticated user
WHEN I visit the main page (/)
THEN I shall see a loading spinner or skeleton screen
AND the loading state shall disappear when data arrives
```

**Acceptance Tests**:
- Loading indicator visible within 100ms of page load
- Loading indicator replaced with actual data when API responds
- No janky layout shifts during loading

**Scenario 20: Dashboard handles API errors gracefully**
```
GIVEN I am an authenticated user
WHEN the `/api/usage-stats` endpoint returns an error
THEN I shall see a user-friendly error message
AND I shall NOT see technical error details
AND I shall have an option to retry loading the dashboard
```

**Acceptance Tests**:
- Simulate API error (network failure, server error)
- Error message is clear and non-technical
- Retry button triggers reload of dashboard data

---

## Non-Functional Requirements

### NFR-001: Accessibility

**WCAG 2.1 AA Compliance**:
- All interactive elements must be keyboard accessible (Tab, Enter, Escape)
- Color contrast ratios must meet WCAG AA standards (4.5:1 for text)
- Dynamic content regions must have appropriate ARIA labels
- Focus indicators must be visible on all interactive elements

**Testing**:
- Keyboard-only navigation test
- Screen reader compatibility test (NVDA or VoiceOver)
- Color contrast validator check

### NFR-002: Security

**Data Protection**:
- User statistics must NOT be visible to anonymous users
- Authentication must be verified before displaying dashboard
- No sensitive data in browser console logs
- API responses must not include passwords or tokens

**Testing**:
- Attempt to access dashboard with expired/invalid token
- Inspect browser console for leaked data
- Verify HTTPS enforced in production

### NFR-003: Browser Compatibility

**Supported Browsers**:
- Chrome 90+ (Primary)
- Firefox 88+ (Secondary)
- Safari 14+ (Secondary)
- Edge 90+ (Secondary)

**Testing**:
- Manual testing on each supported browser
- Verify consistent styling and functionality
- Check for browser-specific console errors

---

## Testing Checklist

### Manual Testing Required

- [ ] Anonymous user sees marketing content
- [ ] Authenticated approved user sees dashboard
- [ ] Pending user sees status message
- [ ] Statistics values match API response
- [ ] New user sees empty state correctly
- [ ] Preferences guidance section visible
- [ ] All quick action buttons navigate correctly
- [ ] Recent activity displays with proper formatting
- [ ] Session expiration handled gracefully
- [ ] Login redirects to dashboard
- [ ] Mobile responsive layout works
- [ ] Loading states display correctly
- [ ] API error handling works
- [ ] Page load time under 2 seconds
- [ ] No console errors in any browser

### Automated Testing Recommended

- [ ] Unit tests for `renderDashboardCards()` function
- [ ] Unit tests for `renderRecentActivity()` function
- [ ] Integration tests for `/api/usage-stats` endpoint
- [ ] Visual regression tests for dashboard layout
- [ ] Performance tests for page load time

---

## Definition of Done

**For Primary Goals (AC-001 through AC-004)**:
- All Given-When-Then scenarios pass manual testing
- Code reviewed by senior developer
- No console errors or JavaScript exceptions
- Mobile responsive on at least 2 devices
- Page load time under 2 seconds
- Anonymous user experience not degraded

**For Secondary Goals (AC-005 through AC-008)**:
- All applicable scenarios pass manual testing
- Error handling implemented and tested
- Loading states implemented and tested
- Accessibility audit passed

**For Documentation**:
- README.md updated with dashboard screenshot
- API documentation updated (if new endpoint created)
- Inline code comments added for complex logic

---

## Test Data Preparation

### Test User Accounts

| Account Type | Email | Password | Status | Activity Level |
|--------------|-------|----------|--------|----------------|
| Anonymous | N/A | N/A | N/A | N/A |
| New User | new@test.com | Test123! | Approved | 0 files |
| Active User | active@test.com | Test123! | Approved | 50+ files |
| Pending User | pending@test.com | Test123! | Pending | 0 files |
| Admin User | admin@test.com | Test123! | Admin | 100+ files |

### Mock API Responses

**Successful Response**:
```json
{
    "total_files_processed": 150,
    "total_submissions": 12,
    "max_files_per_submission": 30,
    "recent_submissions": [
        {
            "timestamp": "2025-12-31T10:30:00Z",
            "files_processed": 5,
            "success": true
        }
    ]
}
```

**Error Response**:
```json
{
    "error": "Unauthorized",
    "message": "Invalid or expired authentication token"
}
```

---

## Sign-Off

**Staging Verification**:
- [ ] Product Owner: _________________ Date: _______
- [ ] Senior Developer: _________________ Date: _______
- [ ] QA Tester: _________________ Date: _______

**Production Deployment Approval**:
- [ ] Product Owner: _________________ Date: _______
- [ ] Tech Lead: _________________ Date: _______
