## Public
only public pages

## Registered (Starter / Free)
- See the top 10 global brands ranked by followers, interactions, and more
- Follower/interactions/top-post data remains on the free restrictions used by the API

## Paid Subscriptions

### Growth
- Ranking limit: up to 30 brands
- Top posts limit: up to 30 posts
- Custom ranges: not allowed
- Premium periods: allowed
- Category scope: one category at a time

### Advanced
- Everything in Growth, plus:
- Ranking limit: up to 50 brands
- Top posts limit: up to 50 posts
- Custom ranges: allowed
- Premium periods: allowed
- Category scope: all categories
- AI/advanced capabilities flagged in `access_rights`:
  - `ai_insights`
  - `ai_recommendations`
  - `comment_sentiment`
  - `influencer_discovery`
  - `ereputation_score`

## Pack policy wiring
Pack policy defaults are derived from `pack_code` (`starter`, `growth`, `advanced`)
and stored in subscription `access_rights`. Admin can still pass explicit
`access_rights` overrides when granting a subscription/preapproval.

