from api import db


class AiInsightCache(db.Model):
    __tablename__ = "ai_insights_cache"

    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    view_type = db.Column(db.String(50), nullable=False)
    summary_text = db.Column(db.Text, nullable=False)
    model_used = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    expires_at = db.Column(db.DateTime, nullable=False)
