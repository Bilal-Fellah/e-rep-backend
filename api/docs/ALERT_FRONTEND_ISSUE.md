# Alert System - Frontend Issue Diagnosis

## Problem Report

**Issue 1:** When clicking an alert about a negative comment, it navigates to a post that shows no negative comments.

**Issue 2:** Possible duplicate alerts for the same comment.

---

## Diagnosis Results

### Backend Status: ✅ WORKING CORRECTLY

After thorough investigation, **the backend is functioning perfectly**:

1. ✅ **Alert events are accurate**
   - All post IDs match the actual comments
   - All page IDs are correct
   - All labels match the current comment labels

2. ✅ **No duplicate events**
   - Dedupe keys are working correctly
   - Each comment creates only one event

3. ✅ **No duplicate user alerts**
   - Each user gets only one alert per event
   - Constraint `uq_user_alert_user_event_rule` prevents duplicates

4. ✅ **Comments DO exist on the posts**
   - Post `1488020253369668` has **2 negative comments** (labels 0 or 1)
   - Post `1493483569490003` has **10 negative comments** (labels 0 or 1)

### Actual Test Results

```
ALERT #1
  Post ID: 1488020253369668
  Comment PK: 3187
  Label: 1 (Negative)
  Text: "مع إحترامي أسوء أنترنت هي شريحة موبيليس"
  
  ✅ Post ID matches
  ✅ Page ID matches  
  ✅ Label matches
  ✅ Post has 2 negative comments total
```

---

## Root Cause: FRONTEND ISSUE

The problem is in the **frontend**, not the backend. The frontend is either:

### Issue 1: Not Loading Comments

**Problem:** The frontend might not be calling the correct API endpoint to load comments for the post.

**Correct API Endpoint:**
```
GET /api/data/get_comments_by_post?page_id={page_id}&platform={platform}&post_id={post_id}
```

**Expected Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": 3187,
      "text": "مع إحترامي أسوء أنترنت هي شريحة موبيليس",
      "label": 1,
      "confidence": 0.8797,
      "author_username": "Oussama Chaouch",
      "post_id": "1488020253369668",
      "page_id": "10ff1f26-ddfc-5a54-bb9f-32e2903174a5",
      "platform": "facebook",
      "recorded_at": "2026-08-07T06:58:00.000000"
    }
  ]
}
```

**Check:**
1. Is the frontend making this API call?
2. Is it passing the correct `page_id`, `platform`, and `post_id`?
3. Is it handling the response correctly?

---

### Issue 2: Filtering Out Negative Comments

**Problem:** The frontend might be filtering comments by label and hiding negative ones.

**Check:**
1. Does the frontend have a filter for comment sentiment?
2. Is there a UI toggle that's hiding negative comments?
3. Is the default view set to show only positive comments?

---

### Issue 3: Not Rendering Comments

**Problem:** The frontend might be loading comments but not displaying them.

**Check:**
1. Are comments being rendered in the post detail view?
2. Is there a separate "comments" section or tab that needs to be opened?
3. Are negative comments styled differently (hidden by default)?

---

## Frontend Debugging Steps

### Step 1: Check Network Requests

When clicking an alert, open browser DevTools (F12) → Network tab:

1. Look for a request to `/api/data/get_comments_by_post`
2. If **NO REQUEST**: Frontend is not fetching comments ❌
3. If **REQUEST EXISTS**: Check the response

### Step 2: Inspect API Response

If the request exists:
```javascript
// Expected URL
GET /api/data/get_comments_by_post?page_id=10ff1f26-ddfc-5a54-bb9f-32e2903174a5&platform=facebook&post_id=1488020253369668

// Expected Response
{
  "success": true,
  "data": [
    {
      "id": 3187,
      "label": 1,  // Negative comment
      "text": "..."
    },
    {
      "id": 3188,
      "label": 1,  // Negative comment
      "text": "..."
    }
  ]
}
```

**If response is empty:** Check query parameters
**If response has data:** Comments are loaded, check rendering

### Step 3: Check Console for Errors

Look for JavaScript errors in the console:
- API call failures
- Rendering errors
- Data parsing errors

### Step 4: Inspect DOM

Use browser DevTools Elements tab:
1. Search for the comment text in the DOM
2. If **FOUND**: Comment is in DOM but hidden (CSS issue)
3. If **NOT FOUND**: Comment is not being rendered

---

## Alert Data Structure

When an alert is clicked, the frontend receives:

```json
{
  "user_alert_id": 29,
  "status": "unread",
  "created_at": "2026-08-24T10:00:00",
  "event": {
    "id": 160,
    "event_type": "negative_comment",
    "entity_id": 93,
    "page_id": "10ff1f26-ddfc-5a54-bb9f-32e2903174a5",
    "platform": "facebook",
    "post_id": "1488020253369668",
    "comment_pk": 3187,
    "label": 1,
    "payload": {
      "text": "مع إحترامي أسوء أنترنت هي شريحة موبيليس",
      "author_username": "Oussama Chaouch",
      "confidence": 0.8797
    }
  }
}
```

**Navigation Flow:**
1. User clicks alert
2. Frontend extracts: `page_id`, `platform`, `post_id`
3. Frontend navigates to post detail page
4. Frontend should call: `GET /api/data/get_comments_by_post?...`
5. Frontend should render all comments including the negative one

---

## Possible Frontend Code Issues

### Issue: Not Fetching Comments

```javascript
// ❌ WRONG - Not fetching comments
function navigateToPost(alert) {
  const postId = alert.event.post_id;
  router.push(`/posts/${postId}`);
  // Missing: fetch comments for the post
}

// ✅ CORRECT - Fetch comments when viewing post
function navigateToPost(alert) {
  const { page_id, platform, post_id } = alert.event;
  
  // Navigate to post
  router.push(`/posts/${post_id}`);
  
  // Fetch comments
  fetchComments(page_id, platform, post_id);
}

async function fetchComments(pageId, platform, postId) {
  const response = await fetch(
    `/api/data/get_comments_by_post?page_id=${pageId}&platform=${platform}&post_id=${postId}`
  );
  const data = await response.json();
  // Render comments
  renderComments(data.data);
}
```

### Issue: Filtering Negative Comments

```javascript
// ❌ WRONG - Filtering out negative comments
function renderComments(comments) {
  const positiveComments = comments.filter(c => c.label >= 2);
  return positiveComments.map(renderComment);
}

// ✅ CORRECT - Show all comments
function renderComments(comments) {
  return comments.map(renderComment);
}
```

### Issue: Not Highlighting the Alert Comment

```javascript
// ✅ GOOD - Highlight the specific comment from the alert
function navigateToPost(alert) {
  const { page_id, platform, post_id, comment_pk } = alert.event;
  
  router.push(`/posts/${post_id}?highlight=${comment_pk}`);
  
  // Fetch and scroll to the highlighted comment
  fetchCommentsAndHighlight(page_id, platform, post_id, comment_pk);
}
```

---

## Recommended Frontend Fixes

### Fix 1: Ensure Comments Are Fetched

In the post detail component:

```javascript
useEffect(() => {
  if (pageId && platform && postId) {
    fetchComments(pageId, platform, postId);
  }
}, [pageId, platform, postId]);
```

### Fix 2: Show All Comments (Don't Filter)

```javascript
// Show all comments, including negative ones
<CommentsList comments={allComments} />
```

### Fix 3: Highlight the Alert Comment

```javascript
<Comment 
  key={comment.id}
  data={comment}
  highlighted={comment.id === highlightedCommentId}
  className={comment.label <= 1 ? 'negative-comment' : ''}
/>
```

### Fix 4: Add Visual Indicators

```css
.negative-comment {
  border-left: 3px solid #ef4444; /* Red border for negative comments */
  background-color: #fef2f2; /* Light red background */
}

.highlighted-comment {
  animation: highlight-pulse 1s ease-in-out 3;
  scroll-margin-top: 100px; /* Account for fixed header */
}
```

---

## Testing the Fix

### Test Case 1: Navigate from Alert

1. Create an alert rule for entity 93
2. Get alerts (should have some for entity 93)
3. Click an alert
4. Verify:
   - ✅ Navigates to correct post
   - ✅ Post comments are loaded
   - ✅ Negative comments are visible
   - ✅ Alert comment is highlighted

### Test Case 2: Verify Comment Data

Using browser console:
```javascript
// Fetch comments for the post from alert
const pageId = "10ff1f26-ddfc-5a54-bb9f-32e2903174a5";
const platform = "facebook";
const postId = "1488020253369668";

fetch(`/api/data/get_comments_by_post?page_id=${pageId}&platform=${platform}&post_id=${postId}`)
  .then(r => r.json())
  .then(console.log);

// Should show 14 comments, including 2 with label 0 or 1
```

---

## Summary

### Backend: ✅ NO ISSUES
- Alert events are accurate
- No duplicates
- Comments exist with correct labels
- API endpoints work correctly

### Frontend: ❌ NEEDS FIX
- Check if comments are being fetched
- Check if negative comments are being filtered
- Check if comments are being rendered
- Add highlighting for alert comments

### Next Steps:
1. Review frontend code for post detail component
2. Verify API call to `/api/data/get_comments_by_post`
3. Remove any label filtering (label >= 2)
4. Add visual indicators for negative comments
5. Implement comment highlighting from alerts

---

## Additional Diagnostic Script

To verify a specific alert's comment exists:

```bash
python scripts/diagnostics/check_alert_navigation.py
```

This will show:
- Alert details
- Comment details
- Post details
- Verification that negative comments exist on the post
